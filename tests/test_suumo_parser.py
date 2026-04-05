from pathlib import Path
import unittest

from SUUMO_SCRAPER.parser import parse_listings


FIXTURE_PATH = Path("tests/fixtures/suumo_list_sample.html")


class ParseListingsTest(unittest.TestCase):
    def test_parse_listings_from_fixture(self) -> None:
        html_text = FIXTURE_PATH.read_text(encoding="utf-8")

        rows = parse_listings(html_text, "https://suumo.jp/jj/chintai/ichiran/FR301FC001/")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].building_name, "サンプルレジデンス")
        self.assertEqual(rows[0].rent_text, "12.3万円")
        self.assertEqual(rows[0].layout, "1LDK")
        self.assertEqual(rows[0].listing_id, "100000000001")


if __name__ == "__main__":
    unittest.main()
