from __future__ import annotations

import argparse
import json
from pathlib import Path

from google.cloud import bigquery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load SUUMO JSONL data into BigQuery.")
    parser.add_argument("--project-id", required=True, help="GCP project id")
    parser.add_argument("--dataset", required=True, help="BigQuery dataset name")
    parser.add_argument("--table", required=True, help="BigQuery table name")
    parser.add_argument("--input", required=True, help="Input JSONL file path")
    parser.add_argument(
        "--schema",
        default="bq/suumo_listings_schema.json",
        help="BigQuery schema JSON path",
    )
    parser.add_argument(
        "--write-disposition",
        default="WRITE_APPEND",
        choices=["WRITE_APPEND", "WRITE_TRUNCATE", "WRITE_EMPTY"],
        help="BigQuery write disposition",
    )
    return parser


def load_schema(schema_path: Path) -> list[bigquery.SchemaField]:
    raw_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return [
        bigquery.SchemaField(
            item["name"],
            item["type"],
            mode=item.get("mode", "NULLABLE"),
            description=item.get("description", ""),
        )
        for item in raw_schema
    ]


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    schema_path = Path(args.schema)

    client = bigquery.Client(project=args.project_id)
    table_id = f"{args.project_id}.{args.dataset}.{args.table}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=load_schema(schema_path),
        write_disposition=args.write_disposition,
    )

    with input_path.open("rb") as handle:
        load_job = client.load_table_from_file(handle, table_id, job_config=job_config)

    load_job.result()
    table = client.get_table(table_id)
    print(f"loaded_rows={table.num_rows}")
    print(f"table_id={table.full_table_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

