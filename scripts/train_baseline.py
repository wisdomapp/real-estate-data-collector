"""フェーズD-2/D-3: features_v1 でベースライン回帰を学習し、特徴量重要度を出す。

目的変数 = N四半期先(既定4=1年先)のエリア×種類の㎡単価変化率。
時系列split（学習=過去 / 検証=直近年）でリークの無い汎化性能を測り、
素朴ベースライン（変化ゼロ / YoY持続 / 学習平均）と比較する。
特徴量重要度は permutation importance（検証集合・MAE基準）で算出。
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# 日本語(種類名・市区町村名)を Windows コンソールでも落とさず出力する
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NUMERIC_FEATURES = [
    "n_transactions",
    "unit_price_m2_yen",
    "median_trade_price_yen",
    "avg_building_age_years",
    "qoq_change_rate",
    "yoy_change_rate",
    "prev_quarter_median_unit_price",
    "prev_year_median_unit_price",
]
# period_year は学習範囲外の年(検証年)で木が外挿できず、暦トレンドのリーク懸念もあるため特徴量に含めない。
# 季節性は period_quarter(1-4) のカテゴリで表現する。
CATEGORICAL_FEATURES = ["type", "period_quarter", "municipality_code"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "target_change_rate"


def load_frame(project_id: str, dataset: str, view: str) -> pd.DataFrame:
    client = bigquery.Client(project=project_id)
    view_id = f"{project_id}.{dataset}.{view}"
    sql = f"""
        SELECT
          municipality_code, municipality, type,
          period_year, period_quarter, period_start_date,
          n_transactions, unit_price_m2_yen, median_trade_price_yen,
          avg_building_age_years, qoq_change_rate, yoy_change_rate,
          prev_quarter_median_unit_price, prev_year_median_unit_price,
          target_change_rate
        FROM `{view_id}`
        WHERE target_change_rate IS NOT NULL
    """
    return client.query(sql).result().to_dataframe()


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": float(r2_score(y_true, y_pred)),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-id", default="real-estate-data-492405")
    p.add_argument("--dataset", default="suumo")
    p.add_argument("--view", default="features_v1")
    p.add_argument("--min-transactions", type=int, default=5,
                   help="そのエリア×四半期の取引数の下限（ノイズ地区の足切り）")
    p.add_argument("--test-from", default="2024-01-01",
                   help="この period_start_date 以降を検証集合にする（時系列split）")
    args = p.parse_args()

    df = load_frame(args.project_id, args.dataset, args.view)
    df["period_start_date"] = pd.to_datetime(df["period_start_date"])
    n_all = len(df)
    df = df[df["n_transactions"] >= args.min_transactions].copy()
    print(f"labeled_rows={n_all}  after_min_transactions(>={args.min_transactions})={len(df)}")

    # カテゴリ列を category 化（HistGBR の categorical_features='from_dtype' 用）
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype("category")

    cutoff = pd.Timestamp(args.test_from)
    train = df[df["period_start_date"] < cutoff]
    test = df[df["period_start_date"] >= cutoff]
    print(f"train_rows={len(train)} (~{train['period_start_date'].min().date()}..{train['period_start_date'].max().date()})")
    print(f"test_rows ={len(test)} (~{test['period_start_date'].min().date()}..{test['period_start_date'].max().date()})")

    X_train, y_train = train[FEATURES], train[TARGET].to_numpy()
    X_test, y_test = test[FEATURES], test[TARGET].to_numpy()

    model = HistGradientBoostingRegressor(
        loss="absolute_error",  # MAE最適化（外れ値に頑健）
        categorical_features="from_dtype",
        learning_rate=0.05,
        max_iter=400,
        max_depth=4,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.15,
        random_state=42,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    print("\n== 検証(out-of-time)メトリクス ==")
    m_model = metrics(y_test, y_pred)
    # 対抗ベースライン
    b_zero = metrics(y_test, np.zeros_like(y_test))
    b_yoy = metrics(y_test, np.nan_to_num(test["yoy_change_rate"].to_numpy(), nan=0.0))
    b_mean = metrics(y_test, np.full_like(y_test, y_train.mean()))

    header = f"{'model':<22}{'MAE':>10}{'RMSE':>10}{'R2':>10}"
    print(header)
    for name, mm in [
        ("HistGBR", m_model),
        ("baseline:変化ゼロ", b_zero),
        ("baseline:YoY持続", b_yoy),
        ("baseline:学習平均", b_mean),
    ]:
        print(f"{name:<22}{mm['MAE']:>10.4f}{mm['RMSE']:>10.4f}{mm['R2']:>10.4f}")

    print("\n== 特徴量重要度 (permutation, 検証集合, MAE悪化量) ==")
    r = permutation_importance(
        model, X_test, y_test, scoring="neg_mean_absolute_error",
        n_repeats=20, random_state=42,
    )
    order = np.argsort(r.importances_mean)[::-1]
    print(f"{'feature':<32}{'importance':>12}{'std':>10}")
    for i in order:
        print(f"{FEATURES[i]:<32}{r.importances_mean[i]:>12.5f}{r.importances_std[i]:>10.5f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
