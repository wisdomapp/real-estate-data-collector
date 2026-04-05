from __future__ import annotations

import argparse

from google.cloud import bigquery


DEFAULT_LOCATION = "asia-northeast1"


VIEW_SQL_TEMPLATE = """
CREATE OR REPLACE VIEW `{view_table_id}` AS
WITH base AS (
  SELECT
    partition_id,
    snapshot_date,
    snapshot_month,
    scraped_at,
    canonical_building_id,
    canonical_property_id,
    listing_id,
    listing_kind,
    building_name,
    address,
    station_name,
    station_walk_minutes,
    layout,
    area_m2_value,
    land_area_m2_value,
    building_area_m2_value,
    age_years,
    price_yen,
    detail_structure,
    detail_direction,
    LAG(price_yen) OVER (
      PARTITION BY canonical_property_id
      ORDER BY partition_id, scraped_at
    ) AS previous_price_yen,
    LAG(snapshot_date) OVER (
      PARTITION BY canonical_property_id
      ORDER BY partition_id, scraped_at
    ) AS previous_snapshot_date,
    MIN(snapshot_date) OVER (
      PARTITION BY canonical_property_id
    ) AS first_snapshot_date,
    MAX(snapshot_date) OVER (
      PARTITION BY canonical_property_id
    ) AS latest_snapshot_date,
    COUNT(*) OVER (
      PARTITION BY canonical_property_id
    ) AS snapshots_observed,
    ROW_NUMBER() OVER (
      PARTITION BY canonical_property_id, partition_id
      ORDER BY scraped_at DESC
    ) AS snapshot_rank_in_day
  FROM `{source_table_id}`
  WHERE canonical_property_id IS NOT NULL
    AND canonical_property_id != ''
)
SELECT
  partition_id,
  snapshot_date,
  snapshot_month,
  scraped_at,
  canonical_building_id,
  canonical_property_id,
  listing_id,
  listing_kind,
  building_name,
  address,
  station_name,
  station_walk_minutes,
  layout,
  area_m2_value,
  land_area_m2_value,
  building_area_m2_value,
  age_years,
  price_yen,
  detail_structure,
  detail_direction,
  previous_snapshot_date,
  previous_price_yen,
  DATE_DIFF(snapshot_date, previous_snapshot_date, DAY) AS days_since_previous_snapshot,
  price_yen - previous_price_yen AS price_diff_yen,
  SAFE_DIVIDE(price_yen - previous_price_yen, previous_price_yen) AS price_change_rate,
  first_snapshot_date,
  latest_snapshot_date,
  snapshots_observed,
  snapshot_date = latest_snapshot_date AS is_latest_snapshot
FROM base
WHERE snapshot_rank_in_day = 1
""".strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a BigQuery time-series view for SUUMO listings."
    )
    parser.add_argument("--project-id", required=True, help="GCP project id")
    parser.add_argument("--dataset", required=True, help="BigQuery dataset name")
    parser.add_argument(
        "--source-table",
        default="listings_raw_v2",
        help="BigQuery source table name",
    )
    parser.add_argument(
        "--view-name",
        default="listings_timeseries_v1",
        help="BigQuery view name",
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
