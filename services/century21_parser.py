"""
century21_parser.py

Parser for Century21.com listing pages.

Century21 often embeds clean JSON data but may also provide HTML-only data.
This parser pulls from:
- JSON-LD
- Embedded script JSON blocks
- HTML property detail fields

Goal:
Produce a standardized property data output consistent with Zillow/Redfin/Realtor.com/Homes.com parsers.
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict


class Century21Parser:
    """
    Input:
        - url: Century21 listing URL

    Output standardized dict:
        {
            "success": True/False,
            "source": "century21",
            "address_full": str,
            "city": str,
            "state": str,
            "zip": str,
            "price": float | None,
            "beds": float | None,
            "baths": float | None,
            "sqft": int | None,
            "lot_size": int | None,
            "year_built": int | None,
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
    # Fetch Page
    # -------------------------------------------------------------

    def fetch(self) -> bool:
        try:
            resp = requests.get(
                self.url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=15,
            )
            if resp.status_code != 200:
                return False

            self.html = resp.text
            self.soup = BeautifulSoup(self.html, "html.parser")
            return True
        except Exception:
            return False

    # -------------------------------------------------------------
    # Embedded JSON & JSON-LD
    # -------------------------------------------------------------

    def _extract_json_ld(self) -> Dict:
        """
        Extracts JSON-LD embedded in <script type='application/ld+json'>.
        """
        data = {}
        for tag in self.soup.find_all("script", type="application/ld+json"):
            try:
                parsed = json.loads(tag.string)
                if isinstance(parsed, dict) and parsed.get("@type") in [
                    "SingleFamilyResidence",
                    "Apartment",
                    "House",
                    "Residence",
                ]:
                    data = parsed
                    break
            except Exception:
                continue

        return data

    def _extract_embedded_json(self) -> Dict:
        """
        Century21 sometimes embeds property data in window.__INITIAL_STATE__ JSON.
        """
        if not self.html:
            return {}

        match = re.search(r"window\.__INITIAL_STATE__\s*=\s*({.*?});", self.html)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                return {}

        return {}

    # -------------------------------------------------------------
    # Field Extraction Helpers
    # -------------------------------------------------------------

    def _extract_price(self, json_data: Dict) -> Optional[float]:
        # JSON-LD first
        offers = json_data.get("offers", {})
        if isinstance(offers, dict) and "price" in offers:
            try:
                return float(offers["price"])
            except Exception:
                pass

        # initial_state for price
        try:
            price = (
                json_data.get("propertyDetails", {})
                .get("pricing", {})
                .get("listPrice")
            )
            if price:
                return float(price)
        except Exception:
            pass

        # HTML fallback
        if self.html:
            m = re.search(r"\$([\d,]+)", self.html)
            if m:
                return float(m.group(1).replace(",", ""))

        return None

    def _extract_address(self, json_ld: Dict) -> Optional[str]:
        addr = json_ld.get("address", {})
        if isinstance(addr, dict):
            street = addr.get("streetAddress")
            city = addr.get("addressLocality")
            state = addr.get("addressRegion")
            zipcode = addr.get("postalCode")
            parts = [street, city, state, zipcode]
            parts = [p for p in parts if p]
            if parts:
                return ", ".join(parts)

        # HTML fallback
        h1 = self.soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        title = self.soup.find("title")
        if title:
            return title.get_text(strip=True)

        return None

    def _extract_city_state_zip(self, json_ld: Dict) -> (Optional[str], Optional[str], Optional[str]):
        addr = json_ld.get("address", {})
        if isinstance(addr, dict):
            return (
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("postalCode"),
            )

        # HTML fallback
        if self.html:
            m = re.search(r",\s*([\w\s]+),\s*([A-Z]{2})\s*(\d{5})", self.html)
            if m:
                return m.group(1), m.group(2), m.group(3)

        return None, None, None

    def _extract_beds(self, json_data: Dict) -> Optional[float]:
        # JSON data
        try:
            bed = (
                json_data.get("propertyDetails", {})
                .get("characteristics", {})
                .get("bedrooms", {})
                .get("value")
            )
            if bed:
                return float(bed)
        except Exception:
            pass

        # HTML fallback
        if self.html:
            m = re.search(r"([\d\.]+)\s*beds?", self.html.lower())
            if m:
                return float(m.group(1))

        return None

    def _extract_baths(self, json_data: Dict) -> Optional[float]:
        try:
            bath = (
                json_data.get("propertyDetails", {})
                .get("characteristics", {})
                .get("bathrooms", {})
                .get("value")
            )
            if bath:
                return float(bath)
        except Exception:
            pass

        if self.html:
            m = re.search(r"([\d\.]+)\s*bath", self.html.lower())
            if m:
                return float(m.group(1))

        return None

    def _extract_sqft(self, json_data: Dict) -> Optional[int]:
        try:
            sqft = (
                json_data.get("propertyDetails", {})
                .get("characteristics", {})
                .get("livingArea", {})
                .get("value")
            )
            if sqft:
                return int(sqft)
        except Exception:
            pass

        if self.html:
            m = re.search(r"([\d,]+)\s*sq\s*ft", self.html.lower())
            if m:
                return int(m.group(1).replace(",", ""))

        return None

    def _extract_lot_size(self, json_data: Dict) -> Optional[int]:
        try:
            lot = (
                json_data.get("propertyDetails", {})
                .get("characteristics", {})
                .get("lotSize", {})
                .get("value")
            )
            if lot:
                return int(lot)
        except Exception:
            pass

        if self.html:
            m = re.search(r"([\d,]+)\s*sq\s*ft\s*lot", self.html.lower())
            if m:
                return int(m.group(1).replace(",", ""))

        return None

    def _extract_year_built(self, json_data: Dict) -> Optional[int]:
        try:
            year = (
                json_data.get("propertyDetails", {})
                .get("characteristics", {})
                .get("yearBuilt", {})
                .get("value")
            )
            if year:
                return int(year)
        except Exception:
            pass

        # HTML fallback
        if self.html:
            m = re.search(r"Year Built[:\s]+(\d{4})", self.html)
            if m:
                return int(m.group(1))

        return None

    def _extract_property_type(self, json_ld: Dict, json_data: Dict) -> Optional[str]:
        if "@type" in json_ld:
            return json_ld["@type"]

        try:
            pt = (
                json_data.get("propertyDetails", {})
                .get("characteristics", {})
                .get("propertyType", {})
                .get("value")
            )
            if pt:
                return pt
        except Exception:
            pass

        return None

    def _extract_num_units(self) -> Optional[int]:
        """
        Try to infer number of units from description text.
        """
        text = self.html.lower() if self.html else ""

        # Explicit detection
        m = re.search(r"(\d+)[ -]?unit\b", text)
        if m:
            return int(m.group(1))

        # Keyword inference
        if "duplex" in text:
            return 2
        if "triplex" in text:
            return 3
        if "fourplex" in text or "quadruplex" in text:
            return 4

        return None

    # -------------------------------------------------------------
    # MAIN PARSE METHOD
    # -------------------------------------------------------------

    def parse(self) -> Dict:
        if not self.fetch():
            return {"success": False, "error": "Failed to fetch Century21 page"}

        json_ld = self._extract_json_ld()
        embedded_json = self._extract_embedded_json()

        # If JSON-LD is empty but embedded JSON exists, merge the two
        primary_json = {**json_ld, **embedded_json} if embedded_json else json_ld

        address_full = self._extract_address(primary_json)
        city, state, zipcode = self._extract_city_state_zip(primary_json)

        return {
            "success": True,
            "source": "century21",
            "address_full": address_full,
            "city": city,
            "state": state,
            "zip": zipcode,
            "price": self._extract_price(primary_json),
            "beds": self._extract_beds(primary_json),
            "baths": self._extract_baths(primary_json),
            "sqft": self._extract_sqft(primary_json),
            "lot_size": self._extract_lot_size(primary_json),
            "year_built": self._extract_year_built(primary_json),
            "property_type": self._extract_property_type(json_ld, primary_json),
            "num_units": self._extract_num_units(),
        }
