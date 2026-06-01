from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .client import (
    PRICE_CLASSIFICATION_CHOICES,
    ClientConfig,
    ReinfolibClient,
    ReinfolibError,
)
from .models import TransactionRecord


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "国交省 不動産情報ライブラリ API から成約価格・取引価格情報を取得し、"
            "raw JSON と正規化済み JSONL/CSV を保存する（学習テーブルの試験取得）。"
        )
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("REINFOLIB_API_KEY", ""),
        help="reinfolib API キー（既定: 環境変数 REINFOLIB_API_KEY）",
    )
    parser.add_argument("--year", type=int, help="取引時期の開始年（例 2024）")
    parser.add_argument(
        "--to-year",
        type=int,
        help="取引時期の終了年（指定すると --year〜--to-year を巡回）",
    )
    parser.add_argument(
        "--quarter",
        type=int,
        choices=[1, 2, 3, 4],
        help="四半期。未指定なら 1〜4 を巡回する",
    )
    parser.add_argument(
        "--area",
        default="13",
        help="都道府県コード（既定: 13=東京都）",
    )
    parser.add_argument(
        "--city",
        action="append",
        help="市区町村コード（複数指定可）。未指定なら都道府県全体",
    )
    parser.add_argument("--station", help="駅コード（任意）")
    parser.add_argument(
        "--price-classification",
        choices=list(PRICE_CLASSIFICATION_CHOICES),
        help=(
            "価格情報区分。01=取引価格（2005Q3〜）/ 02=成約価格（2021Q1〜）。"
            "成約価格が欲しい場合は 02。未指定なら両方取得（各行 PriceCategory で判別可）"
        ),
    )
    parser.add_argument("--language", default="ja", help="言語（既定: ja）")
    parser.add_argument(
        "--out-dir",
        default="data/reinfolib",
        help="正規化済み JSONL/CSV の出力先",
    )
    parser.add_argument(
        "--raw-dir",
        default="raw/reinfolib",
        help="API 生レスポンス(JSON)の保存先",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="リクエスト間の待機秒（負荷配慮）",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=0,
        help="正規化して保存する最大件数（0=無制限）。試験取得時の確認用",
    )
    parser.add_argument(
        "--input-json",
        help=(
            "オフライン解析モード: 保存済みのAPIレスポンスJSON"
            "（{status,data} もしくは data 配列）を読み込み、ネットワークアクセスせず正規化する"
        ),
    )
    return parser


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_jsonl(path: Path, records: Iterable[TransactionRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")


def _write_csv(path: Path, records: list[TransactionRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(records[0].to_dict().keys())
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())


def _normalize(
    raw_records: list[dict[str, Any]],
    *,
    price_classification: str,
    fetched_at: str,
) -> list[TransactionRecord]:
    return [
        TransactionRecord.from_api(
            raw, price_classification=price_classification, fetched_at=fetched_at
        )
        for raw in raw_records
    ]


def _print_summary(records: list[TransactionRecord], failed: list[str]) -> None:
    print(f"record_count={len(records)}")
    if not records:
        print("WARNING: 0 件です。パラメータ（年/エリア/区分）またはAPI応答を確認してください。")

    type_counts = Counter(r.type or "(空)" for r in records)
    print("type_breakdown=" + ", ".join(f"{k}:{v}" for k, v in type_counts.most_common()))

    period_counts = Counter(
        f"{r.period_year}Q{r.period_quarter}" for r in records if r.period_year
    )
    if period_counts:
        print("period_breakdown=" + ", ".join(f"{k}:{v}" for k, v in sorted(period_counts.items())))

    total = len(records) or 1
    for field in ("trade_price_yen", "area_m2", "building_year_int", "nearest_station_minutes"):
        filled = sum(1 for r in records if getattr(r, field) is not None)
        print(f"fill_rate[{field}]={filled}/{len(records)} ({filled * 100 // total}%)")

    if failed:
        print(f"failed_requests={len(failed)}: " + "; ".join(failed))


def _iter_request_params(args: argparse.Namespace) -> list[dict[str, Any]]:
    years = [args.year]
    if args.to_year:
        years = list(range(args.year, args.to_year + 1))
    quarters: list[int | None] = [args.quarter] if args.quarter else [1, 2, 3, 4]
    cities: list[str | None] = list(args.city) if args.city else [None]

    combos: list[dict[str, Any]] = []
    for year in years:
        for quarter in quarters:
            for city in cities:
                combos.append({"year": year, "quarter": quarter, "city": city})
    return combos


def _run_online(args: argparse.Namespace, stamp: str) -> int:
    if args.year is None:
        raise SystemExit("--year is required (または --input-json を使用)")

    config = ClientConfig(api_key=args.api_key, sleep_seconds=args.sleep_seconds)
    try:
        client = ReinfolibClient(config)
    except ReinfolibError as exc:
        raise SystemExit(str(exc))

    fetched_at = datetime.now(timezone.utc).isoformat()
    raw_dir = Path(args.raw_dir) / stamp
    raw_dir.mkdir(parents=True, exist_ok=True)

    all_records: list[TransactionRecord] = []
    failed: list[str] = []

    for combo in _iter_request_params(args):
        label = f"y{combo['year']}_q{combo['quarter']}_{combo['city'] or args.area}"
        try:
            raw_records = client.fetch_transactions(
                year=combo["year"],
                quarter=combo["quarter"],
                area=args.area,
                city=combo["city"],
                station=args.station,
                price_classification=args.price_classification,
                language=args.language,
            )
        except ReinfolibError as exc:
            print(f"WARN fetch failed [{label}]: {exc}")
            failed.append(f"{label}: {exc}")
            continue

        # 生レスポンスを都度保存（途中失敗でも取得済み分は残す）
        (raw_dir / f"transactions_{label}.json").write_text(
            json.dumps(raw_records, ensure_ascii=False), encoding="utf-8"
        )
        records = _normalize(
            raw_records,
            price_classification=args.price_classification or "",
            fetched_at=fetched_at,
        )
        all_records.extend(records)
        print(f"fetched [{label}]: {len(records)} records")

    return _finalize(args, stamp, all_records, failed)


def _run_offline(args: argparse.Namespace, stamp: str) -> int:
    fetched_at = datetime.now(timezone.utc).isoformat()
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    raw_records = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw_records, list):
        raise SystemExit("--input-json の形式が不正です（data 配列が見つかりません）")
    records = _normalize(
        raw_records,
        price_classification=args.price_classification or "",
        fetched_at=fetched_at,
    )
    return _finalize(args, stamp, records, [])


def _finalize(
    args: argparse.Namespace,
    stamp: str,
    records: list[TransactionRecord],
    failed: list[str],
) -> int:
    if args.max_records and len(records) > args.max_records:
        records = records[: args.max_records]

    out_dir = Path(args.out_dir)
    jsonl_path = out_dir / f"reinfolib_transactions_{stamp}.jsonl"
    csv_path = out_dir / f"reinfolib_transactions_{stamp}.csv"
    _write_jsonl(jsonl_path, records)
    _write_csv(csv_path, records)

    _print_summary(records, failed)
    print(f"jsonl_path={jsonl_path}")
    print(f"csv_path={csv_path}")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    stamp = _stamp()
    if args.input_json:
        return _run_offline(args, stamp)
    return _run_online(args, stamp)


if __name__ == "__main__":
    raise SystemExit(main())
