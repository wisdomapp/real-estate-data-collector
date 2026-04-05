from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class ListingRecord:
    source: str
    scraped_at: str
    search_url: str
    detail_url: str
    listing_id: str
    listing_kind: str
    building_name: str
    address: str
    access: str
    layout: str
    area_m2: str
    age: str
    floor: str
    rent_text: str
    admin_fee_text: str
    deposit_text: str
    gratuity_text: str
    price_text: str = ""
    land_area_m2: str = ""
    building_area_m2: str = ""
    detail_address: str = ""
    detail_age: str = ""
    detail_floor_info: str = ""
    detail_direction: str = ""
    detail_building_type: str = ""
    detail_structure: str = ""
    detail_built_at: str = ""
    detail_transaction_type: str = ""
    rent_yen: str = ""
    admin_fee_yen: str = ""
    deposit_yen: str = ""
    gratuity_yen: str = ""
    area_m2_value: str = ""
    age_years: str = ""
    detail_age_years: str = ""
    detail_built_month: str = ""
    station_name: str = ""
    station_walk_minutes: str = ""
    price_yen: str = ""
    land_area_m2_value: str = ""
    building_area_m2_value: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)
