from __future__ import annotations

import unittest

from SUUMO_SCRAPER.models import ListingRecord
from SUUMO_SCRAPER.normalizer import enrich_listing


class NormalizerTest(unittest.TestCase):
    def test_enrich_listing_builds_canonical_ids_and_snapshot_fields(self) -> None:
        record = ListingRecord(
            source="suumo",
            scraped_at="2026-04-05T04:25:41.048754+00:00",
            partition_id="",
            snapshot_date="",
            snapshot_month="",
            search_url="https://suumo.jp/ms/chuko/tokyo/sc_setagaya/",
            detail_url="https://suumo.jp/ms/chuko/tokyo/sc_setagaya/nc_12345678/",
            listing_id="12345678",
            listing_kind="used_mansion",
            building_name="サンプルマンション",
            address="東京都世田谷区桜1-1-1",
            access="東急世田谷線「上町」徒歩10分",
            layout="3LDK",
            area_m2="70.12m 2",
            age="築12年",
            floor="3階",
            rent_text="",
            admin_fee_text="12000円",
            deposit_text="",
            gratuity_text="",
            price_text="7280万円",
            detail_address="東京都世田谷区桜1-1-1",
            detail_age="築12年",
            detail_floor_info="3階/5階建",
            detail_direction="南",
            detail_building_type="中古マンション",
            detail_structure="RC",
            detail_built_at="2014年10月",
            detail_transaction_type="仲介",
        )

        enriched = enrich_listing(record)

        self.assertEqual(enriched.snapshot_date, "2026-04-05")
        self.assertEqual(enriched.partition_id, "2026-04-05")
        self.assertEqual(enriched.snapshot_month, "2026-04")
        self.assertEqual(enriched.price_yen, "72800000")
        self.assertEqual(enriched.area_m2_value, "70.12")
        self.assertEqual(enriched.station_name, "上町")
        self.assertEqual(enriched.station_walk_minutes, "10")
        self.assertTrue(enriched.canonical_building_id)
        self.assertTrue(enriched.canonical_property_id)
        self.assertEqual(len(enriched.canonical_building_id), 20)
        self.assertEqual(len(enriched.canonical_property_id), 20)


if __name__ == "__main__":
    unittest.main()
