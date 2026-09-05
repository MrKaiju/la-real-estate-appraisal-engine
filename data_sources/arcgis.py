"""
data_sources/arcgis.py

Helpers for the ArcGIS REST "query" operation that LA County, LA City GeoHub
and CAL FIRE all expose. No API key is needed for the public layers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .http import HttpClient


def query_layer(client: HttpClient, layer_url: str, where: str = "1=1",
                out_fields: str = "*", max_records: int = 5,
                geometry: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "false",
        "resultRecordCount": max_records,
        "f": "json",
    }
    if geometry:
        params.update(geometry)
    data = client.get_json(f"{layer_url.rstrip('/')}/query", params=params)
    if not isinstance(data, dict) or "features" not in data:
        return []
    return [f.get("attributes") or {} for f in data["features"]]


def point_geometry(lon: float, lat: float) -> Dict[str, Any]:
    return {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
    }


def query_at_point(client: HttpClient, layer_url: str, lon: float, lat: float,
                   out_fields: str = "*") -> Optional[Dict[str, Any]]:
    rows = query_layer(client, layer_url, out_fields=out_fields, max_records=1,
                       geometry=point_geometry(lon, lat))
    return rows[0] if rows else None


def first(attrs: Dict[str, Any], *candidates: str) -> Any:
    """Return the first present, non-empty attribute among candidate field names (case-insensitive)."""
    lowered = {k.lower(): v for k, v in attrs.items()}
    for c in candidates:
        v = lowered.get(c.lower())
        if v not in (None, "", " "):
            return v
    return None


def to_int(v: Any) -> Optional[int]:
    try:
        return int(float(v)) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def to_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None
