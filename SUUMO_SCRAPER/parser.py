from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlparse

from .models import ListingRecord


RENTAL_CARD_PATTERN = re.compile(
    r'(<div[^>]+class="[^"]*\bcassetteitem\b[^"]*"[^>]*>.*?</table>.*?</div>)',
    re.DOTALL,
)
RENTAL_ROW_PATTERN = re.compile(r'(<tr[^>]+class="[^"]*\bjs-cassette_link\b[^"]*"[^>]*>.*?</tr>)', re.DOTALL)
SALE_CARD_PATTERN = re.compile(r'(<div[^>]+class="[^"]*\bproperty_unit\b[^"]*"[^>]*>.*?</div>\s*</div>\s*</div>)', re.DOTALL)
DETAIL_LINK_PATTERN = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>', re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")
TD_PATTERN = re.compile(r"<td\b[^>]*>(.*?)</td>", re.DOTALL)
DL_PATTERN = re.compile(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", re.DOTALL)


def extract_first(block: str, class_name: str) -> str:
    pattern = re.compile(
        rf'<[^>]+class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(.*?)</[^>]+>',
        re.DOTALL,
    )
    match = pattern.search(block)
    return clean_html(match.group(1)) if match else ""


def extract_all(block: str, class_name: str) -> list[str]:
    pattern = re.compile(
        rf'<[^>]+class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(.*?)</[^>]+>',
        re.DOTALL,
    )
    return [clean_html(item) for item in pattern.findall(block)]


def extract_key_values(block: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_key, raw_value in DL_PATTERN.findall(block):
        key = clean_html(raw_key)
        value = clean_html(raw_value)
        if key and value and key not in values:
            values[key] = value
    return values


def clean_html(value: str) -> str:
    no_tags = TAG_PATTERN.sub(" ", value)
    unescaped = html.unescape(no_tags)
    return " ".join(unescaped.split())


def infer_listing_id(url: str) -> str:
    parsed = urlparse(url)
    query_value = parse_qs(parsed.query).get("bc", [""])[0]
    if query_value:
        return query_value

    path = parsed.path.rstrip("/").split("/")
    if not path:
        return url

    last_part = path[-1]
    if last_part.startswith("nc_"):
        return last_part.removeprefix("nc_")
    return last_part


def infer_listing_kind(search_url: str) -> str:
    if "/ms/chuko/" in search_url:
        return "used_mansion"
    if "/ikkodate/" in search_url:
        return "new_house"
    if "/chukoikkodate/" in search_url:
        return "used_house"
    if "/chintai/" in search_url:
        return "rental"
    return "unknown"


def parse_rental_listings(html_text: str, search_url: str) -> list[ListingRecord]:
    scraped_at = datetime.now(timezone.utc).isoformat()
    records: list[ListingRecord] = []

    for block in RENTAL_CARD_PATTERN.findall(html_text):
        building_name = extract_first(block, "cassetteitem_content-title")
        address = extract_first(block, "cassetteitem_detail-col1")
        access = extract_first(block, "cassetteitem_detail-col2")
        age = extract_first(block, "cassetteitem_detail-col3")

        row_blocks = RENTAL_ROW_PATTERN.findall(block) or [block]
        for row_block in row_blocks:
            detail_href = ""
            for candidate in DETAIL_LINK_PATTERN.findall(row_block):
                if "/chintai/" in candidate or "/ms/" in candidate or "/ikkodate/" in candidate:
                    detail_href = candidate
                    break

            detail_url = urljoin(search_url, detail_href) if detail_href else ""
            cells = TD_PATTERN.findall(row_block)
            row_prices = extract_all(row_block, "cassetteitem_price")
            floor = clean_html(cells[2]) if len(cells) > 2 else ""

            record = ListingRecord(
                source="suumo",
                scraped_at=scraped_at,
                partition_id="",
                snapshot_date="",
                snapshot_month="",
                search_url=search_url,
                detail_url=detail_url,
                listing_id=infer_listing_id(detail_url),
                listing_kind="rental",
                building_name=building_name,
                address=address,
                access=access,
                layout=extract_first(row_block, "cassetteitem_madori") or (row_prices[3] if len(row_prices) > 3 else ""),
                area_m2=extract_first(row_block, "cassetteitem_menseki") or (row_prices[4] if len(row_prices) > 4 else ""),
                age=age or (row_prices[5] if len(row_prices) > 5 else ""),
                floor=floor or (row_prices[6] if len(row_prices) > 6 else ""),
                rent_text=extract_first(row_block, "cassetteitem_price--rent") or (row_prices[0] if len(row_prices) > 0 else ""),
                admin_fee_text=extract_first(row_block, "cassetteitem_price--administration") or (row_prices[1] if len(row_prices) > 1 else ""),
                deposit_text=extract_first(row_block, "cassetteitem_price--deposit") or (row_prices[2] if len(row_prices) > 2 else ""),
                gratuity_text=extract_first(row_block, "cassetteitem_price--gratuity") or "",
            )
            if record.building_name or record.detail_url:
                records.append(record)

    return records


def parse_sale_listings(html_text: str, search_url: str) -> list[ListingRecord]:
    scraped_at = datetime.now(timezone.utc).isoformat()
    listing_kind = infer_listing_kind(search_url)
    records: list[ListingRecord] = []

    for block in SALE_CARD_PATTERN.findall(html_text):
        values = extract_key_values(block)
        detail_href = ""
        for candidate in DETAIL_LINK_PATTERN.findall(block):
            if "/ms/chuko/" in candidate or "/ikkodate/" in candidate or "/chukoikkodate/" in candidate:
                detail_href = candidate
                break
        detail_url = urljoin(search_url, detail_href) if detail_href else ""

        area_m2 = values.get("専有面積", "")
        land_area_m2 = values.get("土地面積", "")
        building_area_m2 = values.get("建物面積", "")
        age = values.get("築年月", "")

        records.append(
            ListingRecord(
                source="suumo",
                scraped_at=scraped_at,
                partition_id="",
                snapshot_date="",
                snapshot_month="",
                search_url=search_url,
                detail_url=detail_url,
                listing_id=infer_listing_id(detail_url),
                listing_kind=listing_kind,
                building_name=values.get("物件名", "") or extract_first(block, "property_unit-title"),
                address=values.get("所在地", ""),
                access=values.get("沿線・駅", ""),
                layout=values.get("間取り", ""),
                area_m2=area_m2,
                land_area_m2=land_area_m2,
                building_area_m2=building_area_m2,
                age=age,
                floor=values.get("所在階", "") or values.get("階建", ""),
                rent_text="",
                price_text=values.get("販売価格", ""),
                admin_fee_text=values.get("管理費", "") or values.get("管理費等", ""),
                deposit_text="",
                gratuity_text="",
            )
        )

    return records


def parse_listings(html_text: str, search_url: str) -> list[ListingRecord]:
    if any(token in search_url for token in ["/ms/chuko/", "/ikkodate/", "/chukoikkodate/"]):
        return parse_sale_listings(html_text, search_url)
    return parse_rental_listings(html_text, search_url)
