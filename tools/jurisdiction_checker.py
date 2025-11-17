"""
jurisdiction_checker.py

Determines whether a property is located in:
- City of Los Angeles
- Unincorporated Los Angeles County
- A different incorporated city within LA County

This tool uses simple keyword matching and is designed
to integrate with parcel/APN lookup data or geocoder outputs.

This is NOT a legal determination of jurisdiction. For official
confirmation, verify with:
- ZIMAS (City of LA)
- LA County GIS Data Portal
- Local city planning departments
"""

from typing import Optional, Dict


class JurisdictionChecker:
    """
    Inputs:
        - raw_address: Full string address
        - geocoder_label: Display name from geocoder
        - parcel_jurisdiction: Data from parcel lookup (if any)

    Outputs:
        - jurisdiction: "LA City", "LA County", "Other City"
        - city_name: extracted city name
        - reason: explanation of classification
    """

    LA_CITY_KEYWORDS = [
        "los angeles", "los ángeles", "city of los angeles",
        "la city", "city of la"
    ]

    LA_COUNTY_KEYWORDS = [
        "unincorporated los angeles county",
        "unincorporated la county",
        "unincorporated"
    ]

    def __init__(
        self,
        raw_address: Optional[str] = None,
        geocoder_label: Optional[str] = None,
        parcel_jurisdiction: Optional[str] = None
    ):
        self.raw_address = (raw_address or "").lower()
        self.label = (geocoder_label or "").lower()
        self.parcel = (parcel_jurisdiction or "").lower()

    # ---------------------------------------------------------
    # Helper Methods
    # ---------------------------------------------------------

    def _contains(self, keywords):
        """Check if any keyword appears in the known text sources."""
        text_sources = [self.raw_address, self.label, self.parcel]
        combined = " ".join(text_sources).lower()
        return any(k in combined for k in keywords)

    def _extract_city_from_label(self) -> Optional[str]:
        """
        Attempts to extract the city from the geocoder label.
        Example format: "123 Main St, Los Angeles, CA 90012"
        """
        try:
            parts = self.label.split(",")
            if len(parts) >= 2:
                city = parts[-2].strip().title()
                return city
        except:
            pass
        return None

    # ---------------------------------------------------------
    # Main Evaluation Logic
    # ---------------------------------------------------------

    def evaluate(self) -> Dict:
        """
        Returns:
            {
                "jurisdiction": "LA City" | "LA County" | "Other City",
                "city_name": str or None,
                "reason": str message
            }
        """

        # 1. Check for City of LA
        if self._contains(self.LA_CITY_KEYWORDS):
            return {
                "jurisdiction": "LA City",
                "city_name": "Los Angeles",
                "reason": "Address/geocoder/parcel data indicates City of LA"
            }

        # 2. Check for unincorporated LA County
        if self._contains(self.LA_COUNTY_KEYWORDS):
            return {
                "jurisdiction": "LA County",
                "city_name": None,
                "reason": "Location appears to be unincorporated LA County"
            }

        # 3. Attempt city extraction
        city_guess = self._extract_city_from_label()
        if city_guess and city_guess.lower() not in ["los angeles"]:
            return {
                "jurisdiction": "Other City",
                "city_name": city_guess,
                "reason": f"Address appears to be in {city_guess}, not LA City or LA County"
            }

        # 4. Unknown fallback
        return {
            "jurisdiction": "Other City",
            "city_name": city_guess,
            "reason": "Unable to determine jurisdiction; defaulting to Other City"
        }
