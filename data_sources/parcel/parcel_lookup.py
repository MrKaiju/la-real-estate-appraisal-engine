"""
parcel_lookup.py

Parcel lookup scaffold for LA County GIS or other GIS systems.
Currently returns placeholder values. Later you can link real APIs.
"""

from typing import Dict, Optional


class ParcelLookup:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key

    def lookup(self, lat: float, lng: float) -> Dict:
        """
        Lookup parcel info by geographic coordinates.
        Returns structured placeholder until API integration.
        """
        return {
            "apn": None,
            "jurisdiction": None,    
            "zoning_code": None,     
            "community_plan_area": None
        }
