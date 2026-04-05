from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .detail_parser import parse_detail
from .fetcher import FetchConfig, fetch_detail_pages, fetch_html
from .normalizer import enrich_listings
from .parser import parse_listings
from .storage import write_csv, write_jsonl, write_text
from .targets import discover_tokyo_sale_urls


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch a SUUMO list page and store raw HTML plus parsed listings."
    )
    parser.add_argument("--url", action="append", help="SUUMO list/search URL. Can be passed multiple times.")
    parser.add_argument(
        "--profile",
        default="tokyo_sale_all",
        choices=["tokyo_sale_all", "custom_urls"],
        help="Scraping target profile",
    )
    parser.add_argument(
        "--raw-dir",
        default="raw/suumo",
        help="Directory for raw HTML snapshots",
    )
    parser.add_argument(
        "--out-dir",
        default="data/suumo",
        help="Directory for parsed JSONL and CSV outputs",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=2.0,
        help="Wait time after a request to reduce load",
    )
    parser.add_argument(
        "--input-html",
        help="Parse a saved HTML file instead of making a network request",
    )
    parser.add_argument(
        "--fetch-details",
        action="store_true",
        help="Fetch raw detail pages for the parsed listings",
    )
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=5,
        help="Maximum number of detail pages to fetch when --fetch-details is used",
    )
    parser.add_argument(
        "--city-limit",
        type=int,
        default=10,
        help="Maximum number of Tokyo municipality listing pages to fetch for tokyo_sale_all. Use 0 for no limit.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.input_html:
        html_text = Path(args.input_html).read_text(encoding="utf-8")
        source_urls = args.url or ["https://suumo.jp/"]
        html_pairs = [(source_urls[0], html_text)]
    else:
        config = FetchConfig(sleep_seconds=args.sleep_seconds)
        if args.url:
            source_urls = args.url
        elif args.profile == "tokyo_sale_all":
            source_urls = discover_tokyo_sale_urls(config, city_limit=args.city_limit)
        else:
            raise SystemExit("Either --url or --profile tokyo_sale_all is required.")

        html_pairs = []
        for index, source_url in enumerate(source_urls, start=1):
            html_text = fetch_html(source_url, config)
            raw_path = Path(args.raw_dir) / f"suumo_list_{stamp}_{index:03d}.html"
            write_text(raw_path, html_text)
            html_pairs.append((source_url, html_text))

    rows = []
    for source_url, html_text in html_pairs:
        rows.extend(parse_listings(html_text, source_url))
    jsonl_path = Path(args.out_dir) / f"suumo_listings_{stamp}.jsonl"
    csv_path = Path(args.out_dir) / f"suumo_listings_{stamp}.csv"

    detail_saved_paths: list[Path] = []
    if args.fetch_details:
        detail_urls = []
        seen_urls: set[str] = set()
        for row in rows:
            if row.detail_url and row.detail_url not in seen_urls:
                seen_urls.add(row.detail_url)
                detail_urls.append(row.detail_url)
            if len(detail_urls) >= args.detail_limit:
                break

        fetched_details = fetch_detail_pages(
            detail_urls,
            Path(args.raw_dir) / f"details_{stamp}",
            FetchConfig(sleep_seconds=args.sleep_seconds),
        )
        detail_saved_paths = [item.path for item in fetched_details]
        detail_by_url = {item.url: parse_detail(item.html_text) for item in fetched_details}
        for row in rows:
            detail = detail_by_url.get(row.detail_url)
            if not detail:
                continue
            row.detail_address = detail.address
            row.detail_age = detail.age
            row.detail_floor_info = detail.floor_info
            row.detail_direction = detail.direction
            row.detail_building_type = detail.building_type
            row.detail_structure = detail.structure
            row.detail_built_at = detail.built_at
            row.detail_transaction_type = detail.transaction_type

    rows = enrich_listings(rows)
    write_jsonl(jsonl_path, rows)
    write_csv(csv_path, rows)

    print(f"saved_raw_html={not bool(args.input_html)}")
    print(f"source_page_count={len(html_pairs)}")
    print(f"listing_count={len(rows)}")
    print(f"jsonl_path={jsonl_path}")
    print(f"csv_path={csv_path}")
    print(f"detail_fetch_count={len(detail_saved_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
