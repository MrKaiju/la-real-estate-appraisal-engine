"""
data_sources/rentcast.py

RentCast API adapter (https://developers.rentcast.io).

Used for: property record, long-term rent estimate with comps, AVM with sale
comps. Requires RENTCAST_API_KEY; without it every call returns None and the
enrichment layer records "rentcast: no key". Responses are cached on disk for
7 days (records) / 1 day (estimates) because the free tier is 50 calls/month.

Licensing note: RentCast terms permit caching for your own application and
prohibit redistribution of raw records. Never expose raw comps through a
public API without a commercial agreement.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .http import HttpClient

BASE = "https://api.rentcast.io/v1"


class RentCast:
    def __init__(self, api_key: Optional[str] = None, client: Optional[HttpClient] = None):
        self.api_key = api_key if api_key is not None else os.getenv("RENTCAST_API_KEY", "")
        self.client = client or HttpClient(cache_ttl_s=86400)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: Dict[str, Any]) -> Optional[Any]:
        if not self.enabled:
            return None
        return self.client.get_json(f"{BASE}{path}", params=params,
                                    headers={"X-Api-Key": self.api_key})

    # ------------------------------------------------------------------
    def property_record(self, address: str) -> Optional[Dict[str, Any]]:
        data = self._get("/properties", {"address": address})
        rec = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else None)
        if not rec:
            return None
        taxes = rec.get("propertyTaxes") or {}
        latest_tax = None
        if isinstance(taxes, dict) and taxes:
            latest_tax = taxes[max(taxes)].get("total")
        return {
            "address": rec.get("formattedAddress"),
            "lat": rec.get("latitude"), "lon": rec.get("longitude"),
            "property_type": _map_type(rec.get("propertyType")),
            "beds": rec.get("bedrooms"), "baths": rec.get("bathrooms"),
            "sqft": rec.get("squareFootage"), "lot_size": rec.get("lotSize"),
            "year_built": rec.get("yearBuilt"), "num_units": rec.get("unitCount"),
            "zoning": rec.get("zoning"), "county": rec.get("county"),
            "last_sale_price": rec.get("lastSalePrice"), "last_sale_date": rec.get("lastSaleDate"),
            "current_annual_tax": latest_tax,
            "source": "RentCast property record",
        }

    def rent_estimate(self, address: str, property_type: Optional[str] = None,
                      beds: Optional[int] = None, baths: Optional[float] = None,
                      sqft: Optional[float] = None) -> Optional[Dict[str, Any]]:
        params: Dict[str, Any] = {"address": address, "compCount": 10}
        if property_type:
            params["propertyType"] = _unmap_type(property_type)
        if beds is not None:
            params["bedrooms"] = beds
        if baths is not None:
            params["bathrooms"] = baths
        if sqft:
            params["squareFootage"] = int(sqft)
        data = self._get("/avm/rent/long-term", params)
        if not isinstance(data, dict) or not data.get("rent"):
            return None
        return {
            "rent": data.get("rent"),
            "rent_low": data.get("rentRangeLow"), "rent_high": data.get("rentRangeHigh"),
            "comps": _comps(data.get("comparables") or [], "price"),
            "source": "RentCast rent AVM",
        }

    def value_estimate(self, address: str, property_type: Optional[str] = None,
                       beds: Optional[int] = None, baths: Optional[float] = None,
                       sqft: Optional[float] = None) -> Optional[Dict[str, Any]]:
        params: Dict[str, Any] = {"address": address, "compCount": 10}
        if property_type:
            params["propertyType"] = _unmap_type(property_type)
        if beds is not None:
            params["bedrooms"] = beds
        if baths is not None:
            params["bathrooms"] = baths
        if sqft:
            params["squareFootage"] = int(sqft)
        data = self._get("/avm/value", params)
        if not isinstance(data, dict) or not data.get("price"):
            return None
        return {
            "value": data.get("price"),
            "value_low": data.get("priceRangeLow"), "value_high": data.get("priceRangeHigh"),
            "comps": _comps(data.get("comparables") or [], "price"),
            "source": "RentCast value AVM",
        }


def _comps(raw: List[Dict[str, Any]], price_key: str) -> List[Dict[str, Any]]:
    out = []
    for c in raw:
        out.append({
            "address": c.get("formattedAddress"),
            "price": c.get(price_key),
            "beds": c.get("bedrooms"), "baths": c.get("bathrooms"),
            "sqft": c.get("squareFootage"),
            "distance_miles": c.get("distance"),
            "days_on_market": c.get("daysOnMarket"),
            "sale_date": c.get("removedDate") or c.get("listedDate"),
            "source": "rentcast",
        })
    return out


def _map_type(t: Optional[str]) -> Optional[str]:
    if not t:
        return None
    t = t.lower()
    if "single" in t:
        return "sfr"
    if "condo" in t or "townh" in t:
        return "condo"
    if "multi" in t:
        return "2-4"
    if "apartment" in t:
        return "5+"
    if "land" in t:
        return "land"
    return t


def _unmap_type(t: str) -> str:
    return {"sfr": "Single Family", "condo": "Condo", "2-4": "Multi-Family",
            "5+": "Apartment", "land": "Land"}.get(t, "Single Family")
