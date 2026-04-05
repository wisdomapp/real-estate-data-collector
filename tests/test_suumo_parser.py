from pathlib import Path
import unittest

from SUUMO_SCRAPER.parser import parse_listings


FIXTURE_PATH = Path("tests/fixtures/suumo_list_sample.html")
SALE_FIXTURE_PATH = Path("tests/fixtures/suumo_sale_list_sample.html")


class ParseListingsTest(unittest.TestCase):
    def test_parse_listings_from_fixture(self) -> None:
        html_text = FIXTURE_PATH.read_text(encoding="utf-8")

        rows = parse_listings(html_text, "https://suumo.jp/jj/chintai/ichiran/FR301FC001/")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].building_name, "サンプルレジデンス")
        self.assertEqual(rows[0].rent_text, "12.3万円")
        self.assertEqual(rows[0].layout, "1LDK")
        self.assertEqual(rows[0].listing_id, "100000000001")

    def test_parse_sale_listings_from_fixture(self) -> None:
        html_text = SALE_FIXTURE_PATH.read_text(encoding="utf-8")

        rows = parse_listings(html_text, "https://suumo.jp/ikkodate/tokyo/sc_setagaya/")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].listing_kind, "new_house")
        self.assertEqual(rows[0].price_text, "7280万円")
        self.assertEqual(rows[0].land_area_m2, "90.21m 2")
        self.assertEqual(rows[0].building_area_m2, "86.94m 2")
        self.assertEqual(rows[0].layout, "3LDK")
        self.assertEqual(rows[0].listing_id, "12345678")


if __name__ == "__main__":
    unittest.main()
