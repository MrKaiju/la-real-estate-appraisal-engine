"""
assessor_scraper.py

API-ready client for assessor/parcel data.
Does NOT scrape websites to avoid violating TOS.

You are expected to later connect this to a lawful API,
internal dataset, or downloaded assessor CSV.
"""

from typing import Optional, Dict


class AssessorClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key

    def get_by_apn(self, apn: str) -> Dict:
        return self._fetch_from_source(apn=apn, address=None)

    def get_by_address(self, address: str) -> Dict:
        return self._fetch_from_source(apn=None, address=address)

    def _fetch_from_source(self, apn: Optional[str], address: Optional[str]) -> Dict:
        """
        Replace this placeholder with an approved API call.
        """
        return {
            "apn": apn or "UNKNOWN",
            "address": address or "UNKNOWN",
            "owner_name": None,
            "land_use_code": None,
            "assessed_land_value": None,
            "assessed_structure_value": None,
            "total_assessed_value": None,
            "year_built": None,
            "living_area_sqft": None,
            "lot_sqft": None
        }
