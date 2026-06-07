from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any


# 和暦 → 西暦換算用のオフセット（元号 N 年 = base + N 年）
ERA_OFFSETS = {
    "令和": 2018,
    "平成": 1988,
    "昭和": 1925,
    "大正": 1911,
    "明治": 1867,
}


def parse_int(text: str | None) -> int | None:
    """カンマ・単位付きの数値文字列を int に。例 '53,000,000' -> 53000000"""
    if not text:
        return None
    cleaned = re.sub(r"[^\d-]", "", str(text))
    return int(cleaned) if cleaned not in ("", "-") else None


def parse_float(text: str | None) -> float | None:
    """面積などを float に。例 '2,000㎡以上' -> 2000.0"""
    if not text:
        return None
    cleaned = str(text).replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    return float(match.group()) if match else None


def parse_building_year(text: str | None) -> int | None:
    """建築年を西暦 int に。'1995年' -> 1995 / '平成7年' -> 1995 / '戦前' -> None"""
    if not text:
        return None
    value = str(text).strip()
    if not value or "戦前" in value:
        return None
    for era, base in ERA_OFFSETS.items():
        if era in value:
            match = re.search(r"\d+", value)
            return base + int(match.group()) if match else None
    match = re.search(r"(\d{4})", value)
    return int(match.group(1)) if match else None


def parse_period(text: str | None) -> tuple[int | None, int | None]:
    """取引時期を (年, 四半期) に。'2024年第1四半期' -> (2024, 1)"""
    if not text:
        return None, None
    value = unicodedata.normalize("NFKC", str(text))
    year_match = re.search(r"(\d{4})\s*年", value)
    quarter_match = re.search(r"第\s*([1-4])\s*四半期", value)
    year = int(year_match.group(1)) if year_match else None
    quarter = int(quarter_match.group(1)) if quarter_match else None
    return year, quarter


def parse_minutes(text: str | None) -> int | None:
    """最寄駅までの所要分。'3' -> 3 / '1H30' -> 90 / '30?60' -> 30"""
    if not text:
        return None
    value = unicodedata.normalize("NFKC", str(text)).strip().upper()
    if not value:
        return None
    if "H" in value:
        parts = value.split("H", 1)
        hours_digits = re.sub(r"\D", "", parts[0])
        minutes_digits = re.sub(r"\D", "", parts[1]) if len(parts) > 1 else ""
        hours = int(hours_digits) if hours_digits else 0
        minutes = int(minutes_digits) if minutes_digits else 0
        return hours * 60 + minutes
    match = re.search(r"\d+", value)
    return int(match.group()) if match else None


def quarter_start_date(year: int | None, quarter: int | None) -> str | None:
    """(2024, 1) -> '2024-01-01' / (2024, 4) -> '2024-10-01'。不明なら None。

    BigQuery の DATE パーティション列として使うため、欠損は空文字ではなく None
    （= JSON null）にする。空文字は DATE 列ロード時にエラーになるため。
    """
    if year is None or quarter is None:
        return None
    month = (quarter - 1) * 3 + 1
    return f"{year:04d}-{month:02d}-01"


@dataclass(slots=True)
class TransactionRecord:
    # メタ
    source: str
    fetched_at: str
    price_classification: str
    price_category: str
    # 生フィールド（API原文に対応）
    type: str
    region: str
    municipality_code: str
    prefecture: str
    municipality: str
    district_name: str
    floor_plan: str
    land_shape: str
    frontage: str
    structure: str
    use: str
    purpose: str
    direction: str
    classification: str
    breadth: str
    city_planning: str
    coverage_ratio: str
    floor_area_ratio: str
    period: str
    renovation: str
    remarks: str
    nearest_station: str
    # 正規化（数値化）フィールド
    trade_price_yen: int | None
    price_per_tsubo_yen: int | None
    unit_price_per_m2_yen: int | None
    area_m2: float | None
    total_floor_area_m2: float | None
    building_year_int: int | None
    building_age_years: int | None
    period_year: int | None
    period_quarter: int | None
    period_start_date: str | None
    nearest_station_minutes: int | None

    @classmethod
    def from_api(
        cls,
        raw: dict[str, Any],
        *,
        price_classification: str,
        fetched_at: str,
    ) -> "TransactionRecord":
        def g(key: str) -> str:
            value = raw.get(key, "")
            return "" if value is None else str(value)

        period_year, period_quarter = parse_period(g("Period"))
        building_year_int = parse_building_year(g("BuildingYear"))
        building_age_years: int | None = None
        if period_year is not None and building_year_int is not None:
            building_age_years = max(0, period_year - building_year_int)

        return cls(
            source="reinfolib",
            fetched_at=fetched_at,
            price_classification=price_classification,
            price_category=g("PriceCategory"),
            type=g("Type"),
            region=g("Region"),
            municipality_code=g("MunicipalityCode"),
            prefecture=g("Prefecture"),
            municipality=g("Municipality"),
            district_name=g("DistrictName"),
            floor_plan=g("FloorPlan"),
            land_shape=g("LandShape"),
            frontage=g("Frontage"),
            structure=g("Structure"),
            use=g("Use"),
            purpose=g("Purpose"),
            direction=g("Direction"),
            classification=g("Classification"),
            breadth=g("Breadth"),
            city_planning=g("CityPlanning"),
            coverage_ratio=g("CoverageRatio"),
            floor_area_ratio=g("FloorAreaRatio"),
            period=g("Period"),
            renovation=g("Renovation"),
            remarks=g("Remarks"),
            nearest_station=g("NearestStation"),
            trade_price_yen=parse_int(g("TradePrice")),
            price_per_tsubo_yen=parse_int(g("PricePerUnit")),
            unit_price_per_m2_yen=parse_int(g("UnitPrice")),
            area_m2=parse_float(g("Area")),
            total_floor_area_m2=parse_float(g("TotalFloorArea")),
            building_year_int=building_year_int,
            building_age_years=building_age_years,
            period_year=period_year,
            period_quarter=period_quarter,
            period_start_date=quarter_start_date(period_year, period_quarter),
            nearest_station_minutes=parse_minutes(g("TimeToNearestStation")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
