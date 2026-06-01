from __future__ import annotations

import argparse

from google.cloud import bigquery


DEFAULT_LOCATION = "asia-northeast1"


# フェーズD-1: 学習用 features ビュー。
# 粒度 = 1行: (市区町村 × 種類 × 四半期)。
# 目的変数 target_change_rate = N四半期先の㎡単価(中央値)の変化率 (P[t+N]-P[t]) / P[t]。
#   N は --horizon-quarters（既定4＝1年先）。
# リーク防止: 特徴量は時点 t 以前の情報のみ（現水準・QoQ・YoY・取引数・平均築年・季節）。
#   目的変数の算出にだけ未来(t+N)を参照する。
# 欠損四半期に頑健: 先読み(LEAD)を行位置ではなく暦の四半期(DATE_ADD)でジョインして算出する。
VIEW_SQL_TEMPLATE = """
CREATE OR REPLACE VIEW `{view_table_id}` AS
WITH src AS (
  SELECT * FROM `{source_view_id}`
)
SELECT
  -- キー / 次元
  s.municipality_code,
  s.municipality,{district_select}
  s.type,
  s.period_year,
  s.period_quarter,
  s.period_start_date,
  -- 特徴量（すべて時点 t 以前で確定する情報）
  s.n_transactions,
  s.median_unit_price_per_m2_yen AS unit_price_m2_yen,
  LN(s.median_unit_price_per_m2_yen) AS log_unit_price_m2_yen,
  s.median_trade_price_yen,
  s.avg_building_age_years,
  s.qoq_change_rate,
  s.yoy_change_rate,
  s.prev_quarter_median_unit_price,
  s.prev_year_median_unit_price,
  -- 目的変数（ラベル）: N四半期先の㎡単価変化率。未来が無い直近N期は NULL。
  f.median_unit_price_per_m2_yen AS future_unit_price_m2_yen,
  SAFE_DIVIDE(
    f.median_unit_price_per_m2_yen - s.median_unit_price_per_m2_yen,
    s.median_unit_price_per_m2_yen
  ) AS target_change_rate,
  {horizon_q} AS horizon_quarters
FROM src s
LEFT JOIN src f
  ON s.municipality_code = f.municipality_code
 AND s.type = f.type{district_join}
 AND f.period_start_date = DATE_ADD(s.period_start_date, INTERVAL {horizon_months} MONTH)
""".strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="フェーズD: リーク無しの学習用 features ビューを作成する（目的変数=N期先㎡単価変化率）。"
    )
    parser.add_argument("--project-id", required=True, help="GCP project id")
    parser.add_argument("--dataset", required=True, help="BigQuery dataset name")
    parser.add_argument(
        "--source-view",
        default="transactions_area_quarterly_v1",
        help="元になるエリア×四半期 相場ビュー名",
    )
    parser.add_argument(
        "--view-name",
        default="features_v1",
        help="作成する features ビュー名",
    )
    parser.add_argument(
        "--horizon-quarters",
        type=int,
        default=4,
        help="目的変数の予測ホライズン（四半期数。既定4=1年先）",
    )
    parser.add_argument(
        "--by-district",
        action="store_true",
        help="町丁目(district_name)粒度の相場ビューを元に作る（結合キーに district_name を含める）",
    )
    parser.add_argument(
        "--location",
        default=DEFAULT_LOCATION,
        help="BigQuery dataset location",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    client = bigquery.Client(project=args.project_id, location=args.location)

    source_view_id = f"{args.project_id}.{args.dataset}.{args.source_view}"
    view_table_id = f"{args.project_id}.{args.dataset}.{args.view_name}"
    query = VIEW_SQL_TEMPLATE.format(
        view_table_id=view_table_id,
        source_view_id=source_view_id,
        horizon_q=args.horizon_quarters,
        horizon_months=args.horizon_quarters * 3,
        district_select="\n  s.district_name," if args.by_district else "",
        district_join="\n AND s.district_name = f.district_name" if args.by_district else "",
    )

    job = client.query(query)
    job.result()

    table = client.get_table(view_table_id)
    print(f"view_id={table.full_table_id}")
    print(f"source_view={source_view_id}")
    print(f"horizon_quarters={args.horizon_quarters}")
    print("view_type=VIEW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
