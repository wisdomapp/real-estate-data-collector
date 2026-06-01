from __future__ import annotations

import argparse

from google.cloud import bigquery


DEFAULT_LOCATION = "asia-northeast1"


# エリア(市区町村) × 種類 × 四半期 の成約㎡単価の中央値と、前期比(QoQ)/前年比(YoY)を出すビュー。
# 学習テーブルに「そのエリア×時期の相場・騰落率」を特徴量として結合するための土台。
# 注: 実テーブルが無いと検証できないため、初回はテーブル作成・データ投入後に流すこと。
VIEW_SQL_TEMPLATE = """
CREATE OR REPLACE VIEW `{view_table_id}` AS
WITH agg AS (
  SELECT
    municipality_code,
    municipality,
    type,
    period_year,
    period_quarter,
    period_start_date,
    COUNT(*) AS n_transactions,
    -- 成約価格(02)では API の UnitPrice/PricePerUnit が常に空のため、
    -- ㎡単価は 総額(trade_price_yen) ÷ 面積(area_m2) から都度導出する（両方とも100%充足）。
    APPROX_QUANTILES(SAFE_DIVIDE(trade_price_yen, area_m2), 2)[OFFSET(1)] AS median_unit_price_per_m2_yen,
    APPROX_QUANTILES(trade_price_yen, 2)[OFFSET(1)] AS median_trade_price_yen,
    AVG(building_age_years) AS avg_building_age_years
  FROM `{source_table_id}`
  WHERE trade_price_yen IS NOT NULL
    AND area_m2 IS NOT NULL AND area_m2 > 0
    AND period_start_date IS NOT NULL
  GROUP BY municipality_code, municipality, type, period_year, period_quarter, period_start_date
)
SELECT
  municipality_code,
  municipality,
  type,
  period_year,
  period_quarter,
  period_start_date,
  n_transactions,
  median_unit_price_per_m2_yen,
  median_trade_price_yen,
  avg_building_age_years,
  LAG(median_unit_price_per_m2_yen) OVER w AS prev_quarter_median_unit_price,
  SAFE_DIVIDE(
    median_unit_price_per_m2_yen - LAG(median_unit_price_per_m2_yen) OVER w,
    LAG(median_unit_price_per_m2_yen) OVER w
  ) AS qoq_change_rate,
  LAG(median_unit_price_per_m2_yen, 4) OVER w AS prev_year_median_unit_price,
  SAFE_DIVIDE(
    median_unit_price_per_m2_yen - LAG(median_unit_price_per_m2_yen, 4) OVER w,
    LAG(median_unit_price_per_m2_yen, 4) OVER w
  ) AS yoy_change_rate
FROM agg
WINDOW w AS (PARTITION BY municipality_code, type ORDER BY period_start_date)
""".strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="国交省取引データの エリア×四半期 相場ビューを作成する。"
    )
    parser.add_argument("--project-id", required=True, help="GCP project id")
    parser.add_argument("--dataset", required=True, help="BigQuery dataset name")
    parser.add_argument(
        "--source-table",
        default="transactions_raw",
        help="取引データの元テーブル名",
    )
    parser.add_argument(
        "--view-name",
        default="transactions_area_quarterly_v1",
        help="作成するビュー名",
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

    source_table_id = f"{args.project_id}.{args.dataset}.{args.source_table}"
    view_table_id = f"{args.project_id}.{args.dataset}.{args.view_name}"
    query = VIEW_SQL_TEMPLATE.format(
        source_table_id=source_table_id,
        view_table_id=view_table_id,
    )

    job = client.query(query)
    job.result()

    table = client.get_table(view_table_id)
    print(f"view_id={table.full_table_id}")
    print(f"source_table={source_table_id}")
    print("view_type=VIEW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
