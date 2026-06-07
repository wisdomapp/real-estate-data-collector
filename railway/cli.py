from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .models import StationLineRecord
from .parse_n02 import parse_stations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "国土数値情報 鉄道データ(N02)の GeoJSON から 駅→路線 マスタを作成する。"
            "ネットワーク不要（事前にN02 GeoJSONをダウンロードして --input に渡す）。"
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="N02 の GeoJSON ファイルパス",
    )
    parser.add_argument(
        "--out-dir",
        default="data/railway",
        help="出力先ディレクトリ",
    )
    return parser


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def aggregate_station_to_lines(
    records: list[StationLineRecord],
) -> list[dict[str, Any]]:
    """駅名(正規化)ごとに路線・運営会社を集約する。

    同名異駅（全国に同名駅が存在）の曖昧性が残るため、station_group_code と
    代表座標も保持して後段で必要なら絞り込めるようにする。
    """
    grouped: dict[str, dict[str, Any]] = {}
    line_sets: dict[str, set[str]] = defaultdict(set)
    operator_sets: dict[str, set[str]] = defaultdict(set)
    name_variants: dict[str, set[str]] = defaultdict(set)
    group_codes: dict[str, set[str]] = defaultdict(set)

    for record in records:
        key = record.station_name_normalized
        if record.line_name:
            line_sets[key].add(record.line_name)
        if record.operator:
            operator_sets[key].add(record.operator)
        if record.station_name:
            name_variants[key].add(record.station_name)
        if record.station_group_code:
            group_codes[key].add(record.station_group_code)
        grouped.setdefault(key, {"lon": record.lon, "lat": record.lat})

    result: list[dict[str, Any]] = []
    for key in sorted(grouped):
        result.append(
            {
                "station_name_normalized": key,
                "station_names": sorted(name_variants[key]),
                "line_names": sorted(line_sets[key]),
                "operators": sorted(operator_sets[key]),
                "line_count": len(line_sets[key]),
                "station_group_codes": sorted(group_codes[key]),
                "lon": grouped[key]["lon"],
                "lat": grouped[key]["lat"],
            }
        )
    return result


def main() -> int:
    args = build_parser().parse_args()
    stamp = _stamp()

    geojson = json.loads(Path(args.input).read_text(encoding="utf-8"))
    records = parse_stations(geojson)

    out_dir = Path(args.out_dir)
    station_lines_path = out_dir / f"station_lines_{stamp}.jsonl"
    station_lines_csv = out_dir / f"station_lines_{stamp}.csv"
    aggregated_path = out_dir / f"station_to_lines_{stamp}.jsonl"

    row_dicts = [record.to_dict() for record in records]
    _write_jsonl(station_lines_path, row_dicts)
    _write_csv(station_lines_csv, row_dicts)

    aggregated = aggregate_station_to_lines(records)
    _write_jsonl(aggregated_path, aggregated)

    unique_stations = len({r.station_name_normalized for r in records})
    unique_lines = len({r.line_name for r in records if r.line_name})
    print(f"station_line_rows={len(records)}")
    print(f"unique_stations={unique_stations}")
    print(f"unique_lines={unique_lines}")
    if not records:
        print("WARNING: 駅フィーチャが0件です。N02 GeoJSON の項目名(N02_005など)を確認してください。")
    print(f"station_lines_path={station_lines_path}")
    print(f"station_lines_csv={station_lines_csv}")
    print(f"station_to_lines_path={aggregated_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
