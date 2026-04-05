from __future__ import annotations

import time
from dataclasses import dataclass
import re
from pathlib import Path
from typing import NamedTuple

import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


@dataclass(slots=True)
class FetchConfig:
    timeout_seconds: int = 20
    sleep_seconds: float = 2.0


def decode_response(response: requests.Response) -> str:
    head = response.content[:4096].decode("ascii", errors="ignore")
    meta_match = re.search(r'charset=["\']?([a-zA-Z0-9_-]+)', head, flags=re.IGNORECASE)
    encoding = meta_match.group(1) if meta_match else response.encoding
    if not encoding or encoding.lower() == "iso-8859-1":
        encoding = response.apparent_encoding or "utf-8"

    return response.content.decode(encoding, errors="replace")


def fetch_html(url: str, config: FetchConfig) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=config.timeout_seconds)
    response.raise_for_status()
    time.sleep(config.sleep_seconds)
    return decode_response(response)


class FetchedDetail(NamedTuple):
    url: str
    path: Path
    html_text: str


def fetch_detail_pages(
    detail_urls: list[str],
    raw_dir: Path,
    config: FetchConfig,
) -> list[FetchedDetail]:
    saved_details: list[FetchedDetail] = []
    raw_dir.mkdir(parents=True, exist_ok=True)

    for index, url in enumerate(detail_urls, start=1):
        html_text = fetch_html(url, config)
        path = raw_dir / f"detail_{index:03d}.html"
        path.write_text(html_text, encoding="utf-8")
        saved_details.append(FetchedDetail(url=url, path=path, html_text=html_text))

    return saved_details
