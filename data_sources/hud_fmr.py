"""
data_sources/hud_fmr.py

HUD USER Fair Market Rent API (https://www.huduser.gov/portal/dataset/fmr-api.html).

  GET https://www.huduser.gov/hudapi/public/fmr/data/{entityid}?year=YYYY
  Authorization: Bearer <token>

entityid: a 5-digit ZIP returns the Small Area FMR for that ZIP inside its
metro; a county FIPS + "99999" (LA County = 0603799999) returns the metro FMR
with the ZIP-level SAFMR table in `basicdata`. Los Angeles is a mandatory
SAFMR area, so Section 8 payment standards are ZIP-specific.

Token: HUD_USER_API_TOKEN. Free; register at huduser.gov.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .http import HttpClient

BASE = "https://www.huduser.gov/hudapi/public/fmr/data"
LA_COUNTY_ENTITY = "0603799999"


class HUDFairMarketRent:
    def __init__(self, token: Optional[str] = None, client: Optional[HttpClient] = None):
        self.token = token if token is not None else os.getenv("HUD_USER_API_TOKEN", "")
        self.client = client or HttpClient(cache_ttl_s=30 * 86400)

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def by_zip(self, zip_code: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        if not self.enabled or not zip_code:
            return None
        params = {"year": year} if year else {}
        data = self.client.get_json(f"{BASE}/{zip_code[:5]}", params=params,
                                    headers={"Authorization": f"Bearer {self.token}"})
        if not isinstance(data, dict):
            return None
        d = data.get("data") or data
        basic = d.get("basicdata") or d
        if isinstance(basic, list):
            basic = next((b for b in basic if str(b.get("zip_code", "")) == zip_code[:5]), basic[0] if basic else {})
        return {
            "zip": zip_code[:5],
            "year": d.get("year") or year,
            "area_name": d.get("area_name"),
            "smallarea": d.get("smallarea_status"),
            "fmr": {
                0: _num(basic.get("Efficiency")), 1: _num(basic.get("One-Bedroom")),
                2: _num(basic.get("Two-Bedroom")), 3: _num(basic.get("Three-Bedroom")),
                4: _num(basic.get("Four-Bedroom")),
            },
            "source": "HUD USER FMR API",
        }


def _num(v: Any) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None
