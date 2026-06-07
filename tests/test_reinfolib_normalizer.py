from __future__ import annotations

import json
import unittest
from pathlib import Path

from reinfolib.models import (
    TransactionRecord,
    parse_building_year,
    parse_float,
    parse_int,
    parse_minutes,
    parse_period,
)

FIXTURE = Path(__file__).parent / "fixtures" / "reinfolib_sample.json"


class ParseHelpersTest(unittest.TestCase):
    def test_parse_int_handles_commas_and_empty(self) -> None:
        self.assertEqual(parse_int("53,000,000"), 53000000)
        self.assertEqual(parse_int("53000000"), 53000000)
        self.assertIsNone(parse_int(""))
        self.assertIsNone(parse_int(None))

    def test_parse_float_strips_units(self) -> None:
        self.assertEqual(parse_float("55"), 55.0)
        self.assertEqual(parse_float("2,000㎡以上"), 2000.0)
        self.assertIsNone(parse_float(""))

    def test_parse_building_year_seireki_and_wareki(self) -> None:
        self.assertEqual(parse_building_year("1995年"), 1995)
        self.assertEqual(parse_building_year("平成22年"), 2010)
        self.assertEqual(parse_building_year("昭和60年"), 1985)
        self.assertIsNone(parse_building_year("戦前"))
        self.assertIsNone(parse_building_year(""))

    def test_parse_period(self) -> None:
        self.assertEqual(parse_period("2024年第1四半期"), (2024, 1))
        self.assertEqual(parse_period("2023年第4四半期"), (2023, 4))
        self.assertEqual(parse_period(""), (None, None))

    def test_parse_minutes(self) -> None:
        self.assertEqual(parse_minutes("3"), 3)
        self.assertEqual(parse_minutes("1H30"), 90)
        self.assertEqual(parse_minutes("30?60"), 30)
        self.assertIsNone(parse_minutes(""))


class TransactionRecordTest(unittest.TestCase):
    def setUp(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.records = [
            TransactionRecord.from_api(raw, price_classification="", fetched_at="2026-05-30T00:00:00+00:00")
            for raw in payload["data"]
        ]

    def test_mansion_record(self) -> None:
        rec = self.records[0]
        self.assertEqual(rec.type, "中古マンション等")
        self.assertEqual(rec.trade_price_yen, 53000000)
        self.assertEqual(rec.unit_price_per_m2_yen, 963000)
        self.assertEqual(rec.area_m2, 55.0)
        self.assertEqual(rec.building_year_int, 1995)
        self.assertEqual(rec.period_year, 2024)
        self.assertEqual(rec.period_quarter, 1)
        self.assertEqual(rec.building_age_years, 29)
        self.assertEqual(rec.nearest_station_minutes, 3)
        self.assertEqual(rec.municipality, "千代田区")
        self.assertEqual(rec.period_start_date, "2024-01-01")

    def test_house_record_with_commas_and_wareki(self) -> None:
        rec = self.records[1]
        self.assertEqual(rec.type, "宅地(土地と建物)")
        self.assertEqual(rec.trade_price_yen, 78000000)
        self.assertEqual(rec.total_floor_area_m2, 95.0)
        self.assertEqual(rec.building_year_int, 2010)
        self.assertEqual(rec.building_age_years, 13)
        self.assertEqual(rec.nearest_station_minutes, 90)

    def test_to_dict_is_serializable(self) -> None:
        as_dict = self.records[0].to_dict()
        json.dumps(as_dict, ensure_ascii=False)
        self.assertIn("trade_price_yen", as_dict)


class SchemaCoverageTest(unittest.TestCase):
    """BQスキーマJSONと TransactionRecord の列が完全一致することを保証する。"""

    def test_schema_matches_record_fields(self) -> None:
        schema_path = Path(__file__).parents[1] / "bq" / "reinfolib_transactions_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_names = {field["name"] for field in schema}

        empty_record = TransactionRecord.from_api(
            {}, price_classification="", fetched_at="2026-05-30T00:00:00+00:00"
        )
        record_names = set(empty_record.to_dict().keys())

        self.assertEqual(schema_names, record_names)


if __name__ == "__main__":
    unittest.main()
