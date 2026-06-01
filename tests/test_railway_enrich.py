from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from railway.cli import aggregate_station_to_lines
from railway.enrich import (
    enrich_records,
    load_station_line_index,
    lookup_lines,
    match_rate,
)
from railway.parse_n02 import parse_stations

FIXTURE = Path(__file__).parent / "fixtures" / "n02_sample.geojson"


def _build_index() -> dict:
    geojson = json.loads(FIXTURE.read_text(encoding="utf-8"))
    aggregated = aggregate_station_to_lines(parse_stations(geojson))
    return {row["station_name_normalized"]: row for row in aggregated}


class LookupLinesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.index = _build_index()

    def test_match_with_eki_suffix(self) -> None:
        # 入力が「神保町駅」でも正規化して一致する
        result = lookup_lines("神保町駅", self.index)
        self.assertTrue(result["railway_matched"])
        self.assertEqual(result["line_count"], 2)
        self.assertEqual(result["line_names"], ["都営三田線", "都営新宿線"])

    def test_match_plain(self) -> None:
        result = lookup_lines("蒲田", self.index)
        self.assertTrue(result["railway_matched"])
        self.assertEqual(result["operators"], ["東日本旅客鉄道"])

    def test_miss(self) -> None:
        result = lookup_lines("存在しない駅", self.index)
        self.assertFalse(result["railway_matched"])
        self.assertEqual(result["line_names"], [])
        self.assertEqual(result["line_count"], 0)

    def test_none_input(self) -> None:
        result = lookup_lines(None, self.index)
        self.assertFalse(result["railway_matched"])


class EnrichRecordsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.index = _build_index()

    def test_enrich_reinfolib_like_records(self) -> None:
        records = [
            {"municipality": "千代田区", "nearest_station": "神保町"},
            {"municipality": "大田区", "nearest_station": "蒲田"},
            {"municipality": "どこか", "nearest_station": "未知"},
        ]
        enriched = enrich_records(records, self.index, station_field="nearest_station")
        self.assertEqual(len(enriched), 3)
        self.assertEqual(enriched[0]["line_count"], 2)
        self.assertTrue(enriched[1]["railway_matched"])
        self.assertFalse(enriched[2]["railway_matched"])
        # 元の列は保持される
        self.assertEqual(enriched[0]["municipality"], "千代田区")

    def test_match_rate(self) -> None:
        records = [
            {"station_name": "神保町"},
            {"station_name": "未知"},
        ]
        enriched = enrich_records(records, self.index, station_field="station_name")
        self.assertAlmostEqual(match_rate(enriched), 0.5)


class LoadIndexTest(unittest.TestCase):
    def test_round_trip_via_jsonl(self) -> None:
        geojson = json.loads(FIXTURE.read_text(encoding="utf-8"))
        aggregated = aggregate_station_to_lines(parse_stations(geojson))
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "station_to_lines.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for row in aggregated:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            index = load_station_line_index(path)
        self.assertIn("神保町", index)
        self.assertEqual(index["神保町"]["line_count"], 2)


if __name__ == "__main__":
    unittest.main()
