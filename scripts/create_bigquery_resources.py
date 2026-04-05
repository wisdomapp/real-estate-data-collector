from __future__ import annotations

import argparse
import json
from pathlib import Path

from google.cloud import bigquery


DEFAULT_LOCATION = "asia-northeast1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create BigQuery dataset and table for SUUMO listings."
    )
    parser.add_argument("--project-id", required=True, help="GCP project id")
    parser.add_argument("--dataset", required=True, help="BigQuery dataset name")
    parser.add_argument("--table", required=True, help="BigQuery table name")
    parser.add_argument(
        "--location",
        default=DEFAULT_LOCATION,
        help="BigQuery dataset location",
    )
    parser.add_argument(
        "--schema",
        default="bq/suumo_listings_schema.json",
        help="BigQuery schema JSON path",
    )
    parser.add_argument(
        "--clustering-fields",
        nargs="*",
        default=["listing_id", "station_name"],
        help="BigQuery clustering fields",
    )
    return parser


def load_schema(schema_path: Path) -> list[bigquery.SchemaField]:
    raw_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return [
        bigquery.SchemaField(
            item["name"],
            item["type"],
            mode=item.get("mode", "NULLABLE"),
        )
        for item in raw_schema
    ]


def ensure_dataset(client: bigquery.Client, dataset_id: str, location: str) -> bigquery.Dataset:
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = location
    return client.create_dataset(dataset, exists_ok=True)


def ensure_table(
    client: bigquery.Client,
    table_id: str,
    schema: list[bigquery.SchemaField],
    clustering_fields: list[str],
) -> bigquery.Table:
    table = bigquery.Table(table_id, schema=schema)
    table.time_partitioning = bigquery.TimePartitioning(field="scraped_at")
    table.clustering_fields = clustering_fields
    return client.create_table(table, exists_ok=True)


def main() -> int:
    args = build_parser().parse_args()
    client = bigquery.Client(project=args.project_id)

    dataset_id = f"{args.project_id}.{args.dataset}"
    table_id = f"{dataset_id}.{args.table}"
    schema = load_schema(Path(args.schema))

    dataset = ensure_dataset(client, dataset_id, args.location)
    table = ensure_table(client, table_id, schema, args.clustering_fields)

    print(f"dataset_id={dataset.full_dataset_id}")
    print(f"table_id={table.full_table_id}")
    print(f"partition_field=scraped_at")
    print(f"clustering_fields={','.join(table.clustering_fields or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

