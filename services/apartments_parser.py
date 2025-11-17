"""
apartments_parser.py

Parser for Apartments.com rental listings.
This is essential for rental comp analysis and underwriting accuracy.

Apartments.com typically provides:
- Rent ranges
- Unit types (Studio, 1 Bed, 2 Bed, etc.)
- Sqft ranges
- Amenities
- Availability
- Property type (apartment, house, duplex, etc.)

This parser extracts:
- address
- city, state, zip
- rent_min / rent_max
- bedrooms
- bathrooms
- unit sqft
- building/type info
- number of units (when available)
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional, List


class ApartmentsParser:
    """
    Input:
        url (str): Apartments.com listing URL

    Output (standardized dict):
        {
            "success": True/False,
            "source": "apartments.com",
            "address_full": str,
            "city": str,
            "state": str,
            "zip": str,
            "rent_min": float | None,
            "rent_max": float | None,
            "unit_types": [
                {
                    "beds": float | None,
                    "baths": float | None,
                    "sqft_min": int | None,
                    "sqft_max": int | None,
                    "rent_min": float | None,
                    "rent_max": float | None
                }, ...
            ],
            "property_type": str | None,
            "num_units": int | None
        }
    """

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, url: str):
        self.url = url
        self.html = None
        self.soup = None

    # -------------------------------------------------------------
    # Fetch HTML
    # -------------------------------------------------------------

    def fetch(self) -> bool:
        try:
            r = requests.get(
                self.url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=12,
            )
            if r.status_code != 200:
                return False

            self.html = r.text
            self.soup = BeautifulSoup(self.html, "html.parser")
            return True
        except Exception:
            return False

    # -------------------------------------------------------------
    # Address Extraction
    # -------------------------------------------------------------

    def _extract_address(self) -> Optional[str]:
        """
        Apartments.com usually includes the full address in:
            <span class="address">...</span>
        or inside <script> JSON blocks.
        """
        if not self.soup:
            return None

        addr = self.soup.select_one("span.address")
        if addr:
            return addr.get_text(strip=True)

        # fallback: try meta
        meta = self.soup.find("meta", property="og:street-address")
        if meta and meta.get("content"):
            return meta["content"]

        # fallback: title may contain address fragment
        title = self.soup.find("title")
        if title:
            text = title.get_text(strip=True)
            if re.search(r"\d{5}", text):
                return text

        return None

    def _extract_city_state_zip(self, address_full: str):
        if not address_full:
            return None, None, None

        # Example: "1234 W Adams Blvd, Los Angeles, CA 90018"
        m = re.search(r",\s*([\w\s]+),\s*([A-Z]{2})\s*(\d{5})", address_full)
        if m:
            return m.group(1), m.group(2), m.group(3)

        return None, None, None

    # -------------------------------------------------------------
    # Rent Extraction
    # -------------------------------------------------------------

    def _extract_rent_range(self) -> (Optional[float], Optional[float]):
        """
        Extract global rent range for the listing (if available)
        Examples:
            $2,300 - $3,200
            $1,850+
        """
        if not self.html:
            return None, None

        m = re.search(r"\$([\d,]+)\s*[-–]\s*\$([\d,]+)", self.html)
        if m:
            return (
                float(m.group(1).replace(",", "")),
                float(m.group(2).replace(",", "")),
            )

        # Single rent: "$1,800+"
        m = re.search(r"\$([\d,]+)\s*\+", self.html)
        if m:
            val = float(m.group(1).replace(",", ""))
            return val, val

        return None, None

    # -------------------------------------------------------------
    # Unit Type Extraction
    # -------------------------------------------------------------

    def _extract_unit_types(self) -> List[Dict]:
        """
        Parses each individual unit type block, e.g.:

            Studio | 1 Bath | 450 Sq Ft | $1,500 - $1,650
            1 Bed | 1 Bath | 600-750 Sq Ft | $1,900 - $2,100

        Returns a list of standardized unit types.
        """
        results = []
        if not self.soup:
            return results

        unit_rows = self.soup.select("tr.rentalGridRow")

        for row in unit_rows:
            text = row.get_text(" ", strip=True).lower()

            # Beds
            beds = None
            m = re.search(r"(\d+)\s*bed", text)
            if m:
                beds = float(m.group(1))
            elif "studio" in text:
                beds = 0.0

            # Baths
            baths = None
            m = re.search(r"([\d\.]+)\s*bath", text)
            if m:
                baths = float(m.group(1))

            # Sqft range
            sqft_min, sqft_max = None, None
            m = re.search(r"([\d,]+)\s*-\s*([\d,]+)\s*sq", text)
            if m:
                sqft_min = int(m.group(1).replace(",", ""))
                sqft_max = int(m.group(2).replace(",", ""))

            # Single sqft
            m = re.search(r"([\d,]+)\s*sq\s*ft", text)
            if m and sqft_min is None:
                sqft_min = sqft_max = int(m.group(1).replace(",", ""))

            # Rent range
            rent_min, rent_max = None, None
            m = re.search(r"\$([\d,]+)\s*[-–]\s*\$([\d,]+)", text)
            if m:
                rent_min = float(m.group(1).replace(",", ""))
                rent_max = float(m.group(2).replace(",", ""))
            else:
                m = re.search(r"\$([\d,]+)", text)
                if m:
                    rent_min = rent_max = float(m.group(1).replace(",", ""))

            results.append(
                {
                    "beds": beds,
                    "baths": baths,
                    "sqft_min": sqft_min,
                    "sqft_max": sqft_max,
                    "rent_min": rent_min,
                    "rent_max": rent_max,
                }
            )

        return results

    # -------------------------------------------------------------
    # Property Type & Unit Count
    # -------------------------------------------------------------

    def _extract_property_type(self) -> Optional[str]:
        if not self.html:
            return None

        m = re.search(r"Property Type[:\s]+([\w\s]+)<", self.html)
        if m:
            return m.group(1).strip()

        # fallback: Apartments.com meta tags
        meta = self.soup.find("meta", property="og:type")
        if meta:
            return meta.get("content")

        return None

    def _extract_unit_count(self) -> Optional[int]:
        if not self.html:
            return None

        # Often appears in description
        m = re.search(r"(\d+)[ -]?unit\b", self.html.lower())
        if m:
            return int(m.group(1))

        return None

    # -------------------------------------------------------------
    # MAIN PARSE METHOD
    # -------------------------------------------------------------

    def parse(self) -> Dict:
        if not self.fetch():
            return {
                "success": False,
                "error": "Failed to fetch Apartments.com page"
            }

        address_full = self._extract_address()
        city, state, zipcode = self._extract_city_state_zip(address_full or "")

        rent_min, rent_max = self._extract_rent_range()

        return {
            "success": True,
            "source": "apartments.com",
            "address_full": address_full,
            "city": city,
            "state": state,
            "zip": zipcode,
            "rent_min": rent_min,
            "rent_max": rent_max,
            "unit_types": self._extract_unit_types(),
            "property_type": self._extract_property_type(),
            "num_units": self._extract_unit_count(),
        }
