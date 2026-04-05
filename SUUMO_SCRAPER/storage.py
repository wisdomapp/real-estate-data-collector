from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import ListingRecord


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_parent(path)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[ListingRecord]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[ListingRecord]) -> None:
    ensure_parent(path)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].to_dict().keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())

