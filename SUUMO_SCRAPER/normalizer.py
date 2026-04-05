from __future__ import annotations

import re

from .models import ListingRecord


PRICE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>万円|円)")
AREA_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*m")
AGE_PATTERN = re.compile(r"築\s*(\d+)\s*年")
WALK_PATTERN = re.compile(r"/\s*(?P<station>[^/]+?)\s*歩\s*(?P<minutes>\d+)\s*分")
BUILT_MONTH_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月")


def _format_int(value: int | None) -> str:
    return "" if value is None else str(value)


def _format_float(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}".rstrip("0").rstrip(".")


def parse_price_yen(text: str) -> int | None:
    cleaned = text.strip()
    if not cleaned or cleaned == "-":
        return None

    match = PRICE_PATTERN.search(cleaned)
    if not match:
        return None

    amount = float(match.group("value"))
    unit = match.group("unit")
    if unit == "万円":
        return int(amount * 10000)
    return int(amount)


def parse_area_m2(text: str) -> float | None:
    match = AREA_PATTERN.search(text)
    return float(match.group(1)) if match else None


def parse_age_years(text: str) -> int | None:
    if "新築" in text:
        return 0
    match = AGE_PATTERN.search(text)
    return int(match.group(1)) if match else None


def parse_station_walk(text: str) -> tuple[str | None, int | None]:
    match = WALK_PATTERN.search(text)
    if not match:
        return None, None
    return match.group("station").strip(), int(match.group("minutes"))


def parse_built_month(text: str) -> str:
    match = BUILT_MONTH_PATTERN.search(text)
    if not match:
        return ""
    return f"{match.group(1)}-{int(match.group(2)):02d}"


def enrich_listing(record: ListingRecord) -> ListingRecord:
    station_name, station_walk_minutes = parse_station_walk(record.access)
    record.rent_yen = _format_int(parse_price_yen(record.rent_text))
    record.admin_fee_yen = _format_int(parse_price_yen(record.admin_fee_text))
    record.deposit_yen = _format_int(parse_price_yen(record.deposit_text))
    record.gratuity_yen = _format_int(parse_price_yen(record.gratuity_text))
    record.area_m2_value = _format_float(parse_area_m2(record.area_m2))
    record.age_years = _format_int(parse_age_years(record.age))
    record.detail_age_years = _format_int(parse_age_years(record.detail_age))
    record.detail_built_month = parse_built_month(record.detail_built_at)
    record.station_name = station_name or ""
    record.station_walk_minutes = _format_int(station_walk_minutes)
    return record


def enrich_listings(records: list[ListingRecord]) -> list[ListingRecord]:
    return [enrich_listing(record) for record in records]
