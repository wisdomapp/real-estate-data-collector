from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from .models import ListingRecord


PRICE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>万円|円)")
AREA_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*m")
AGE_PATTERN = re.compile(r"築\s*(\d+)\s*年")
WALK_PATTERN = re.compile(r"[「/](?P<station>[^」/]+)[」]?\s*徒歩?\s*(?P<minutes>\d+)\s*分")
BUILT_MONTH_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月")


def _format_int(value: int | None) -> str:
    return "" if value is None else str(value)


def _format_float(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}".rstrip("0").rstrip(".")


def _normalize_space(text: str) -> str:
    return " ".join(text.split())


def normalize_text(text: str) -> str:
    normalized = text.strip()
    replacements = {
        "　": " ",
        "ヶ": "ケ",
        "ヵ": "カ",
        "之": "ノ",
        "・": "",
        "−": "-",
        "―": "-",
        "ｰ": "-",
        "－": "-",
    }
    for before, after in replacements.items():
        normalized = normalized.replace(before, after)
    normalized = _normalize_space(normalized)
    return normalized.lower()


def normalize_address(text: str) -> str:
    normalized = normalize_text(text)
    replacements = {
        "東京都": "",
        "都": "",
        "地先": "",
        "付近": "",
    }
    for before, after in replacements.items():
        normalized = normalized.replace(before, after)
    normalized = re.sub(r"(\d+)丁目", r"\1-", normalized)
    normalized = re.sub(r"(\d+)番地", r"\1-", normalized)
    normalized = re.sub(r"(\d+)番", r"\1-", normalized)
    normalized = re.sub(r"(\d+)号", r"\1", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized


def normalize_building_name(text: str) -> str:
    normalized = normalize_text(text)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def normalize_station_name(text: str) -> str:
    normalized = normalize_text(text)
    normalized = normalized.replace("駅", "")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


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


def infer_age_years_from_built_month(built_month: str, snapshot_date: str) -> int | None:
    if not built_month or not snapshot_date:
        return None
    try:
        built_year, built_month_num = [int(part) for part in built_month.split("-")]
        snap_year, snap_month, _ = [int(part) for part in snapshot_date.split("-")]
    except ValueError:
        return None

    age = snap_year - built_year
    if snap_month < built_month_num:
        age -= 1
    return max(age, 0)


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


def build_hash(parts: list[str]) -> str:
    joined = "|".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:20]


def infer_snapshot_fields(scraped_at: str) -> tuple[str, str]:
    dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.date().isoformat(), dt.strftime("%Y-%m")


def enrich_listing(record: ListingRecord) -> ListingRecord:
    station_name, station_walk_minutes = parse_station_walk(record.access)

    record.price_yen = _format_int(parse_price_yen(record.price_text))
    record.rent_yen = _format_int(parse_price_yen(record.rent_text))
    record.admin_fee_yen = _format_int(parse_price_yen(record.admin_fee_text))
    record.deposit_yen = _format_int(parse_price_yen(record.deposit_text))
    record.gratuity_yen = _format_int(parse_price_yen(record.gratuity_text))
    record.area_m2_value = _format_float(parse_area_m2(record.area_m2))
    record.land_area_m2_value = _format_float(parse_area_m2(record.land_area_m2))
    record.building_area_m2_value = _format_float(parse_area_m2(record.building_area_m2))
    record.snapshot_date, record.snapshot_month = infer_snapshot_fields(record.scraped_at)
    record.partition_id = record.snapshot_date
    record.detail_built_month = parse_built_month(record.detail_built_at or record.age)
    age_years = parse_age_years(record.age)
    if age_years is None:
        age_years = infer_age_years_from_built_month(parse_built_month(record.age), record.snapshot_date)
    detail_age_years = parse_age_years(record.detail_age)
    if detail_age_years is None:
        detail_age_years = infer_age_years_from_built_month(record.detail_built_month, record.snapshot_date)
    record.age_years = _format_int(age_years)
    record.detail_age_years = _format_int(detail_age_years)
    record.station_name = station_name or record.station_name or ""
    record.station_walk_minutes = _format_int(station_walk_minutes)
    record.address_normalized = normalize_address(record.detail_address or record.address)
    record.building_name_normalized = normalize_building_name(record.building_name)
    record.station_name_normalized = normalize_station_name(record.station_name)

    building_key_parts = [
        record.source,
        record.listing_kind,
        record.address_normalized,
        record.building_name_normalized,
        record.detail_structure,
        record.detail_built_month or record.age,
    ]
    record.canonical_building_id = build_hash(building_key_parts)

    property_key_parts = [
        record.canonical_building_id,
        record.layout,
        record.area_m2_value or record.area_m2,
        record.land_area_m2_value or record.land_area_m2,
        record.building_area_m2_value or record.building_area_m2,
        normalize_text(record.floor),
        normalize_text(record.detail_direction),
    ]
    record.canonical_property_id = build_hash(property_key_parts)
    return record


def enrich_listings(records: list[ListingRecord]) -> list[ListingRecord]:
    return [enrich_listing(record) for record in records]
