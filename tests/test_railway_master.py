from __future__ import annotations

import json
import unittest
from pathlib import Path

from railway.cli import aggregate_station_to_lines
from railway.models import StationLineRecord, clean_label, normalize_station_name
from railway.parse_n02 import parse_stations, representative_point

FIXTURE = Path(__file__).parent / "fixtures" / "n02_sample.geojson"


class NormalizeStationNameTest(unittest.TestCase):
    def test_strips_suffix_and_spaces(self) -> None:
        self.assertEqual(normalize_station_name("神保町駅"), "神保町")
        self.assertEqual(normalize_station_name(" 蒲田 "), "蒲田")
        self.assertEqual(normalize_station_name(""), "")
        self.assertIsNone(normalize_station_name(None) or None)


class CleanLabelTest(unittest.TestCase):
    def test_strips_and_collapses_whitespace(self) -> None:
        self.assertEqual(clean_label(" 都営三田線 "), "都営三田線")
        self.assertEqual(clean_label("都営三田線　"), "都営三田線")
        self.assertEqual(clean_label(""), "")
        self.assertEqual(clean_label(None), "")

    def test_keeps_meaningful_distinctions(self) -> None:
        # 貨物線などの括弧つき別路線は別物として保持する
        self.assertNotEqual(clean_label("山手線(貨物)"), clean_label("山手線"))


class AggregateDedupTest(unittest.TestCase):
    def test_whitespace_variants_collapse_in_line_count(self) -> None:
        # 同一路線名に余分な空白が混ざっても line_count を水増ししない
        props_variants = [
            {"N02_003": "都営三田線", "N02_004": "東京都", "N02_005": "大手町"},
            {"N02_003": " 都営三田線", "N02_004": "東京都", "N02_005": "大手町"},
            {"N02_003": "都営三田線　", "N02_004": "東京都", "N02_005": "大手町"},
            {"N02_003": "東京地下鉄丸ノ内線", "N02_004": "東京地下鉄", "N02_005": "大手町"},
        ]
        records = [StationLineRecord.from_props(p, None, None) for p in props_variants]
        aggregated = aggregate_station_to_lines(records)
        row = {r["station_name_normalized"]: r for r in aggregated}["大手町"]
        self.assertEqual(row["line_count"], 2)
        self.assertEqual(row["line_names"], ["東京地下鉄丸ノ内線", "都営三田線"])


class RepresentativePointTest(unittest.TestCase):
    def test_average_of_linestring(self) -> None:
        geometry = {"type": "LineString", "coordinates": [[139.0, 35.0], [141.0, 37.0]]}
        lon, lat = representative_point(geometry)
        self.assertAlmostEqual(lon, 140.0)
        self.assertAlmostEqual(lat, 36.0)

    def test_empty_geometry(self) -> None:
        self.assertEqual(representative_point(None), (None, None))


class ParseStationsTest(unittest.TestCase):
    def setUp(self) -> None:
        geojson = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.records = parse_stations(geojson)

    def test_filters_out_non_station_features(self) -> None:
        # 駅名が空の路線区間フィーチャ(1件)は除外され、駅フィーチャ3件のみ残る
        self.assertEqual(len(self.records), 3)

    def test_station_record_fields(self) -> None:
        jimbocho = [r for r in self.records if r.station_name == "神保町"]
        self.assertEqual(len(jimbocho), 2)
        self.assertEqual({r.line_name for r in jimbocho}, {"都営三田線", "都営新宿線"})
        self.assertEqual(jimbocho[0].station_name_normalized, "神保町")


class AggregateTest(unittest.TestCase):
    def setUp(self) -> None:
        geojson = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.aggregated = aggregate_station_to_lines(parse_stations(geojson))
        self.by_name = {row["station_name_normalized"]: row for row in self.aggregated}

    def test_jimbocho_has_two_lines(self) -> None:
        row = self.by_name["神保町"]
        self.assertEqual(row["line_count"], 2)
        self.assertEqual(row["line_names"], ["都営三田線", "都営新宿線"])
        self.assertEqual(row["station_group_codes"], ["G001"])

    def test_kamata_single_line(self) -> None:
        row = self.by_name["蒲田"]
        self.assertEqual(row["line_count"], 1)
        self.assertEqual(row["operators"], ["東日本旅客鉄道"])


if __name__ == "__main__":
    unittest.main()
