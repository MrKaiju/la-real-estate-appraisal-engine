"""
hud_fmr_scraper.py

HUD Fair Market Rent API integration.
Uses HUD User API when API key is provided.
"""

import os
import requests
from typing import Optional


class HUDFMRClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("HUD_API_KEY")
        self.base_url = "https://www.huduser.gov/hudapi/public/fmr/data"

    def get_fmr(self, state_code: str, county_name: str, year: Optional[int] = None):
        if not self.api_key:
            raise RuntimeError("HUD_API_KEY is not set.")

        params = {
            "api_key": self.api_key,
            "state": state_code,
            "county": county_name,
        }

        if year:
            params["year"] = year

        try:
            resp = requests.get(self.base_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {})
        except Exception:
            return None
