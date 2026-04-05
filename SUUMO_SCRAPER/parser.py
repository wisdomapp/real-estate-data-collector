from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlparse

from .models import ListingRecord


CARD_PATTERN = re.compile(
    r'(<div[^>]+class="[^"]*\bcassetteitem\b[^"]*"[^>]*>.*?</table>.*?</div>)',
    re.DOTALL,
)
ROW_PATTERN = re.compile(r'(<tr[^>]+class="[^"]*\bjs-cassette_link\b[^"]*"[^>]*>.*?</tr>)', re.DOTALL)
DETAIL_LINK_PATTERN = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>', re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")
TD_PATTERN = re.compile(r"<td\b[^>]*>(.*?)</td>", re.DOTALL)


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
    return path[-1] if path else url


def parse_listings(html_text: str, search_url: str) -> list[ListingRecord]:
    scraped_at = datetime.now(timezone.utc).isoformat()
    records: list[ListingRecord] = []

    for block in CARD_PATTERN.findall(html_text):
        building_name = extract_first(block, "cassetteitem_content-title")
        address = extract_first(block, "cassetteitem_detail-col1")
        access = extract_first(block, "cassetteitem_detail-col2")
        age = extract_first(block, "cassetteitem_detail-col3")

        row_blocks = ROW_PATTERN.findall(block) or [block]
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
                search_url=search_url,
                detail_url=detail_url,
                listing_id=infer_listing_id(detail_url),
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
