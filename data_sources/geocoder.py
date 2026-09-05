"""
data_sources/geocoder.py

Address -> (lat, lon). Order of preference:
  1. A lat/lon the caller already has (parcel layer, RentCast record).
  2. Pelias, if PELIAS_URL is configured.
  3. Nominatim (OpenStreetMap). Free, requires a UA and ~1 req/s; cached 30 days.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .http import HttpClient


class Geocoder:
    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient(cache_ttl_s=30 * 86400)
        self.pelias_url = os.getenv("PELIAS_URL")

    def geocode(self, address: str) -> Optional[Dict[str, Any]]:
        if not address:
            return None
        if self.pelias_url:
            r = self._pelias(address)
            if r:
                return r
        return self._nominatim(address)

    def _pelias(self, address: str) -> Optional[Dict[str, Any]]:
        data = self.client.get_json(self.pelias_url, params={"text": address, "size": 1})
        feats = (data or {}).get("features") or []
        if not feats:
            return None
        c = feats[0]["geometry"]["coordinates"]
        return {"lat": float(c[1]), "lon": float(c[0]),
                "label": feats[0].get("properties", {}).get("label"), "source": "pelias"}

    def _nominatim(self, address: str) -> Optional[Dict[str, Any]]:
        data = self.client.get_json("https://nominatim.openstreetmap.org/search",
                                    params={"q": address, "format": "json", "limit": 1,
                                            "countrycodes": "us"})
        if not data:
            return None
        r = data[0]
        return {"lat": float(r["lat"]), "lon": float(r["lon"]),
                "label": r.get("display_name"), "source": "nominatim"}
