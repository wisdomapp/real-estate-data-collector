from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import normalize_station_name


# 駅→路線マスタ（station_to_lines_*.jsonl）を使って、reinfolib の nearest_station や
# SUUMO の station_name に「何線か（路線の集合）」を付与するための結合モジュール。
#
# 結合キーは normalize_station_name で揃えた駅名。
# 注意: 同名異駅（全国に同名駅）の曖昧性は名前だけでは解消できない。v1 は名前一致で付与し、
# matched フラグと候補数を返す。精度を上げたい場合は後段で市区町村/座標で絞り込む。


def load_station_line_index(path: str | Path) -> dict[str, dict[str, Any]]:
    """station_to_lines JSONL を読み、station_name_normalized をキーにした辞書を返す。"""
    index: dict[str, dict[str, Any]] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = row.get("station_name_normalized")
            if key:
                index[key] = row
    return index


def lookup_lines(station_name: str | None, index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """駅名から路線情報を引く。入力は生の駅名でよい（内部で正規化する）。

    返り値:
      - railway_matched: マスタに一致したか
      - line_names / operators: 路線・運営会社の集合（未一致なら空）
      - line_count: 路線数
      - station_group_codes: 同名駅の曖昧性確認用
    """
    key = normalize_station_name(station_name)
    row = index.get(key)
    if not row:
        return {
            "station_name_normalized": key,
            "railway_matched": False,
            "line_names": [],
            "operators": [],
            "line_count": 0,
            "station_group_codes": [],
        }
    return {
        "station_name_normalized": key,
        "railway_matched": True,
        "line_names": list(row.get("line_names", [])),
        "operators": list(row.get("operators", [])),
        "line_count": int(row.get("line_count", len(row.get("line_names", [])))),
        "station_group_codes": list(row.get("station_group_codes", [])),
    }


def enrich_records(
    records: Iterable[dict[str, Any]],
    index: dict[str, dict[str, Any]],
    *,
    station_field: str,
) -> list[dict[str, Any]]:
    """レコード(dict)の列挙に路線情報を付与した新しいリストを返す。

    station_field: 駅名が入っている列名（reinfolib なら "nearest_station",
    SUUMO なら "station_name"）。
    """
    enriched: list[dict[str, Any]] = []
    for record in records:
        lines = lookup_lines(record.get(station_field), index)
        merged = dict(record)
        merged["line_names"] = lines["line_names"]
        merged["line_count"] = lines["line_count"]
        merged["railway_matched"] = lines["railway_matched"]
        enriched.append(merged)
    return enriched


def match_rate(enriched: list[dict[str, Any]]) -> float:
    """付与済みレコードのうち路線一致した割合（品質確認用）。"""
    if not enriched:
        return 0.0
    matched = sum(1 for r in enriched if r.get("railway_matched"))
    return matched / len(enriched)
