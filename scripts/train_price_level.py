"""目的変数① 基礎集計：中古マンションの「適正㎡単価」を物件属性から説明する
ヘドニック回帰のベースライン。

②（将来の変化率予測）と違い、これは「いま・その属性なら㎡単価はいくらか」の
断面推定。松岡さんの「まず基礎集計として①」に対応。評価はランダム分割（予測=断面の当てはめ）。
目的変数は log(㎡単価)=log(成約総額 / 面積)。どの属性が㎡単価に効くかも出す。
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NUMERIC_FEATURES = ["area_m2", "building_age_years"]
CATEGORICAL_FEATURES = [
    "municipality_code",
    "structure",
    "floor_plan",
    "city_planning",
    "renovation",
    "period_year",
    "period_quarter",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def load_frame(project_id: str, dataset: str, table: str) -> pd.DataFrame:
    client = bigquery.Client(project=project_id)
    sql = f"""
        SELECT
          municipality_code, structure, floor_plan, city_planning, renovation,
          period_year, period_quarter,
          area_m2, building_age_years,
          SAFE_DIVIDE(trade_price_yen, area_m2) AS unit_price_m2_yen
        FROM `{project_id}.{dataset}.{table}`
        WHERE type = '中古マンション等'
          AND trade_price_yen IS NOT NULL
          AND area_m2 IS NOT NULL AND area_m2 > 0
    """
    return client.query(sql).result().to_dataframe()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-id", default="real-estate-data-492405")
    p.add_argument("--dataset", default="suumo")
    p.add_argument("--table", default="transactions_raw")
    args = p.parse_args()

    df = load_frame(args.project_id, args.dataset, args.table)
    n0 = len(df)
    # 極端な外れ値（入力ミス等）を 0.5〜99.5 パーセンタイルで除外
    lo, hi = df["unit_price_m2_yen"].quantile([0.005, 0.995])
    df = df[(df["unit_price_m2_yen"] >= lo) & (df["unit_price_m2_yen"] <= hi)].copy()
    df["log_unit_price"] = np.log(df["unit_price_m2_yen"])
    print(f"rows={n0} -> after_outlier_trim={len(df)} (㎡単価 {lo:,.0f}〜{hi:,.0f} 円)")

    for c in CATEGORICAL_FEATURES:
        df[c] = df[c].astype("category")

    X = df[FEATURES]
    y = df["log_unit_price"].to_numpy()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"train={len(X_tr)} test={len(X_te)}")

    model = HistGradientBoostingRegressor(
        categorical_features="from_dtype",
        learning_rate=0.05, max_iter=600, max_depth=6,
        l2_regularization=1.0, early_stopping=True, random_state=42,
    )
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)

    r2 = r2_score(y_te, pred)
    mae_log = mean_absolute_error(y_te, pred)
    # log 残差の MAE を「中央的な誤差率」に変換（exp(MAE)-1）
    mape_like = np.exp(mae_log) - 1
    # 実額（㎡単価）での誤差中央値
    abs_pct = np.abs(np.exp(pred) - np.exp(y_te)) / np.exp(y_te)
    print("\n== ① 適正㎡単価モデル（検証=ランダム20%）==")
    print(f"R2(log㎡単価)        = {r2:.3f}")
    print(f"誤差率の目安(exp(MAE)-1) = {mape_like*100:.1f}%")
    print(f"絶対%誤差 中央値        = {np.median(abs_pct)*100:.1f}%")
    print(f"絶対%誤差 平均          = {np.mean(abs_pct)*100:.1f}%")

    print("\n== どの属性が㎡単価に効くか (permutation, R2低下量) ==")
    r = permutation_importance(model, X_te, y_te, scoring="r2", n_repeats=10, random_state=42)
    order = np.argsort(r.importances_mean)[::-1]
    print(f"{'feature':<22}{'importance(R2)':>16}")
    for i in order:
        print(f"{FEATURES[i]:<22}{r.importances_mean[i]:>16.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
