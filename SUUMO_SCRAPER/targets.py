from __future__ import annotations

import re
from urllib.parse import urljoin

from .fetcher import FetchConfig, fetch_html


TOKYO_SALE_ENTRY_URLS = [
    "https://suumo.jp/ms/chuko/tokyo/city/",
    "https://suumo.jp/ikkodate/tokyo/city/",
    "https://suumo.jp/chukoikkodate/tokyo/city/",
]

CITY_URL_PATTERNS = [
    re.compile(r'href="(/ms/chuko/tokyo/sc_[^"/]+/)"'),
    re.compile(r'href="(/ikkodate/tokyo/sc_[^"/]+/)"'),
    re.compile(r'href="(/chukoikkodate/tokyo/sc_[^"/]+/)"'),
]
PAGINATION_PAGE_PATTERN = re.compile(r"[?&]page=(\d+)")


def discover_tokyo_sale_urls(config: FetchConfig, city_limit: int = 0) -> list[str]:
    discovered: list[str] = []
    seen: set[str] = set()

    for entry_url in TOKYO_SALE_ENTRY_URLS:
        html_text = fetch_html(entry_url, config)
        for pattern in CITY_URL_PATTERNS:
            for path in pattern.findall(html_text):
                full_url = urljoin(entry_url, path)
                if full_url in seen:
                    continue
                seen.add(full_url)
                discovered.append(full_url)
                if city_limit and len(discovered) >= city_limit:
                    return discovered

    return discovered


def discover_paginated_urls(base_url: str, html_text: str) -> list[str]:
    page_numbers = [int(match) for match in PAGINATION_PAGE_PATTERN.findall(html_text)]
    max_page = max(page_numbers, default=1)

    paginated_urls = [base_url]
    for page in range(2, max_page + 1):
        separator = "&" if "?" in base_url else "?"
        paginated_urls.append(f"{base_url}{separator}page={page}")

    return paginated_urls
