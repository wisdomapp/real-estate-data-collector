from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


# 駅名の正規化は SUUMO_SCRAPER.normalizer.normalize_station_name と同一ロジックにする。
# reinfolib の nearest_station / SUUMO の station_name と結合するための共通キーなので、
# 3者で同じ正規化でなければ結合できない（変更時は両方を揃えること）。
_REPLACEMENTS = {
    "　": " ",
    "ヶ": "ケ",
    "ヵ": "カ",
    "之": "ノ",
    "・": "",
    "−": "-",
    "―": "-",
    "ｰ": "-",
    "－": "-",
}


def normalize_station_name(text: str | None) -> str:
    value = (text or "").strip()
    for before, after in _REPLACEMENTS.items():
        value = value.replace(before, after)
    value = " ".join(value.split()).lower()
    value = value.replace("駅", "")
    value = re.sub(r"\s+", "", value)
    return value


def clean_label(text: str | None) -> str:
    """路線名・運営会社名の防御的な表記ゆれ除去（前後/全角空白の整理）。

    集約キーに使うため、余分な空白で同一ラベルが別物として line_count を
    水増しするのを防ぐ。括弧つきの別路線（例「山手線(貨物)」）は保持する。
    """
    if not text:
        return ""
    return " ".join(text.replace("　", " ").split())


@dataclass(slots=True)
class StationLineRecord:
    station_name: str
    station_name_normalized: str
    line_name: str
    operator: str
    railway_class: str
    station_code: str
    station_group_code: str
    lon: float | None
    lat: float | None

    @classmethod
    def from_props(
        cls,
        props: dict[str, Any],
        lon: float | None,
        lat: float | None,
    ) -> "StationLineRecord":
        def g(key: str) -> str:
            value = props.get(key, "")
            return "" if value is None else str(value)

        station_name = g("N02_005")
        return cls(
            station_name=station_name,
            station_name_normalized=normalize_station_name(station_name),
            line_name=clean_label(g("N02_003")),
            operator=clean_label(g("N02_004")),
            railway_class=g("N02_001"),
            station_code=g("N02_005c"),
            station_group_code=g("N02_005g"),
            lon=lon,
            lat=lat,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
