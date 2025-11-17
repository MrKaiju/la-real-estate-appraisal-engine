"""
pelias_geocoder.py

Geocoding utility using Pelias (if configured)
or Nominatim (OpenStreetMap) as fallback.
"""

import os
from typing import Optional, Dict
import requests


class Geocoder:
    def __init__(self):
        self.pelias_url = os.getenv("PELIAS_URL")  
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"

    def geocode(self, address: str) -> Optional[Dict]:
        """
        Returns dictionary with latitude, longitude, and formatted label.
        """
        if self.pelias_url:
            data = self._geocode_pelias(address)
            if data:
                return data

        return self._geocode_nominatim(address)

    def _geocode_pelias(self, address: str) -> Optional[Dict]:
        try:
            params = {"text": address, "size": 1}
            resp = requests.get(self.pelias_url, params=params, timeout=10)
            resp.raise_for_status()
            features = resp.json().get("features", [])
            if not features:
                return None

            props = features[0]["properties"]
            coords = features[0]["geometry"]["coordinates"]

            return {
                "lat": float(coords[1]),
                "lng": float(coords[0]),
                "label": props.get("label")
            }
        except:
            return None

    def _geocode_nominatim(self, address: str) -> Optional[Dict]:
        try:
            params = {"q": address, "format": "json", "limit": 1}
            headers = {"User-Agent": "LA-Appraisal-Engine/1.0"}
            resp = requests.get(self.nominatim_url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            results = resp.json()
            if not results:
                return None

            r = results[0]
            return {
                "lat": float(r["lat"]),
                "lng": float(r["lon"]),
                "label": r.get("display_name")
            }
        except:
            return None
