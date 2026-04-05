from __future__ import annotations

import html
import re
from dataclasses import dataclass


TAG_PATTERN = re.compile(r"<[^>]+>")
PAIR_PATTERN = re.compile(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", re.DOTALL)


def clean_html(value: str) -> str:
    no_tags = TAG_PATTERN.sub(" ", value)
    unescaped = html.unescape(no_tags)
    return " ".join(unescaped.split())


@dataclass(slots=True)
class DetailRecord:
    address: str = ""
    age: str = ""
    floor_info: str = ""
    direction: str = ""
    building_type: str = ""
    structure: str = ""
    built_at: str = ""
    transaction_type: str = ""


def parse_detail(html_text: str) -> DetailRecord:
    values: dict[str, str] = {}
    for raw_key, raw_value in PAIR_PATTERN.findall(html_text):
        key = clean_html(raw_key)
        value = clean_html(raw_value)
        if key and value and key not in values:
            values[key] = value

    return DetailRecord(
        address=values.get("所在地", ""),
        age=values.get("築年数", ""),
        floor_info=values.get("階", "") or values.get("階建", ""),
        direction=values.get("向き", ""),
        building_type=values.get("建物種別", ""),
        structure=values.get("構造", ""),
        built_at=values.get("築年月", ""),
        transaction_type=values.get("取引態様", ""),
    )
