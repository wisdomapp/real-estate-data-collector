from __future__ import annotations

from typing import Any

from .models import StationLineRecord


def _iter_coords(geometry: dict[str, Any] | None) -> list[list[float]]:
    """GeoJSON ジオメトリから [lon, lat] の座標列を平坦化して取り出す。"""
    if not geometry:
        return []
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")
    if coords is None:
        return []
    if geom_type == "Point":
        return [coords]
    if geom_type == "LineString":
        return list(coords)
    if geom_type == "MultiLineString":
        return [point for line in coords for point in line]
    if geom_type == "MultiPoint":
        return list(coords)
    return []


def representative_point(
    geometry: dict[str, Any] | None,
) -> tuple[float | None, float | None]:
    """駅セグメントの代表点（座標の平均）を返す。"""
    points = _iter_coords(geometry)
    if not points:
        return None, None
    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)
    return lon, lat


def parse_stations(geojson: dict[str, Any]) -> list[StationLineRecord]:
    """N02 GeoJSON から駅フィーチャ（N02_005=駅名 が入っている）だけを抽出する。

    路線のみの区間フィーチャ（駅名が空）は除外する。
    """
    records: list[StationLineRecord] = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {}) or {}
        station_name = props.get("N02_005")
        if not station_name:
            continue
        lon, lat = representative_point(feature.get("geometry"))
        records.append(StationLineRecord.from_props(props, lon, lat))
    return records
