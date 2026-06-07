from __future__ import annotations

import argparse

from google.cloud import bigquery


DEFAULT_LOCATION = "asia-northeast1"


# エリア × 種類 × 四半期 の成約㎡単価の中央値と、前期比(QoQ)/前年比(YoY)を出すビュー。
# 学習テーブルに「そのエリア×時期の相場・騰落率」を特徴量として結合するための土台。
# エリア粒度は --by-district で切替: 既定=市区町村(v1) / 指定時=市区町村+町丁目(v2)。
# 注: 実テーブルが無いと検証できないため、初回はテーブル作成・データ投入後に流すこと。
#   ㎡単価は 総額(trade_price_yen) ÷ 面積(area_m2) から都度導出する
#   （成約価格(02)では API の UnitPrice/PricePerUnit が常に空。trade_price/area は100%充足）。
#   QoQ/YoY は行位置ベースの LAG（連続四半期が前提）。歯抜けの多い町丁目では近似になる点に留意。
VIEW_SQL_TEMPLATE = """
CREATE OR REPLACE VIEW `{view_table_id}` AS
WITH agg AS (
  SELECT
    {dim_select},
    period_year,
    period_quarter,
    period_start_date,
    COUNT(*) AS n_transactions,
    APPROX_QUANTILES(SAFE_DIVIDE(trade_price_yen, area_m2), 2)[OFFSET(1)] AS median_unit_price_per_m2_yen,
    APPROX_QUANTILES(trade_price_yen, 2)[OFFSET(1)] AS median_trade_price_yen,
    AVG(building_age_years) AS avg_building_age_years
  FROM `{source_table_id}`
  WHERE trade_price_yen IS NOT NULL
    AND area_m2 IS NOT NULL AND area_m2 > 0
    AND period_start_date IS NOT NULL
  GROUP BY {dim_group}, period_year, period_quarter, period_start_date
)
SELECT
  {dim_select},
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
WINDOW w AS (PARTITION BY {partition_by} ORDER BY period_start_date)
""".strip()


def build_view_sql(view_table_id: str, source_table_id: str, by_district: bool) -> str:
    # 集約の次元列。町丁目粒度では district_name を type の前に挟む。
    dims = ["municipality_code", "municipality"]
    if by_district:
        dims.append("district_name")
    dims.append("type")
    # 時系列ウィンドウのパーティション（騰落率の系列単位）。
    partition = ["municipality_code"] + (["district_name"] if by_district else []) + ["type"]
    return VIEW_SQL_TEMPLATE.format(
        view_table_id=view_table_id,
        source_table_id=source_table_id,
        dim_select=",\n    ".join(dims),
        dim_group=", ".join(dims),
        partition_by=", ".join(partition),
    )


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
        "--by-district",
        action="store_true",
        help="町丁目(district_name)粒度で集約する（既定は市区町村粒度）",
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
    query = build_view_sql(view_table_id, source_table_id, args.by_district)

    job = client.query(query)
    job.result()

    table = client.get_table(view_table_id)
    print(f"view_id={table.full_table_id}")
    print(f"source_table={source_table_id}")
    print(f"granularity={'district' if args.by_district else 'municipality'}")
    print("view_type=VIEW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
