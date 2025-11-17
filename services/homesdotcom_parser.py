"""
homesdotcom_parser.py

Parser for Homes.com listing pages.

Attempts to extract:
- Full address (with city, state, ZIP)
- Price
- Beds, baths
- Building square footage
- Lot size
- Year built
- Property type
- Unit count (when inferable)

This is a defensive HTML parser using multiple fallbacks since
Homes.com may change their front-end structure periodically.
"""

import re
import json
from typing import Optional, Dict

import requests
from bs4 import BeautifulSoup


class HomesDotComParser:
    """
    Input:
        url: Homes.com listing URL

    Output:
        {
            "success": True/False,
            "source": "homes.com",
            "address_full": str | None,
            "city": str | None,
            "state": str | None,
            "zip": str | None,
            "price": float | None,
            "beds": float | None,
            "baths": float | None,
            "sqft": int | None,
            "lot_size": int | None,
            "year_built": int | None,
            "property_type": str | None,
            "num_units": int | None,
        }
    """

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, url: str):
        self.url = url
        self.html: Optional[str] = None
        self.soup: Optional[BeautifulSoup] = None

    # ---------------------------------------------------------
    # Fetch HTML
    # ---------------------------------------------------------

    def fetch(self) -> bool:
        try:
            resp = requests.get(
                self.url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=10,
            )
            resp.raise_for_status()
            self.html = resp.text
            self.soup = BeautifulSoup(self.html, "html.parser")
            return True
        except Exception:
            return False

    # ---------------------------------------------------------
    # JSON / Script Extraction Helpers
    # ---------------------------------------------------------

    def _extract_embedded_json(self) -> Dict:
        """
        Some Homes.com pages ship structured property data inside
        <script type="application/ld+json"> or other JSON blobs.
        """
        if not self.soup:
            return {}

        data = {}

        # Try JSON-LD first
        for tag in self.soup.find_all("script", type="application/ld+json"):
            try:
                j = json.loads(tag.string or "{}")
                # Take the first object that looks like a residence
                if isinstance(j, dict) and j.get("@type") in [
                    "SingleFamilyResidence",
                    "Apartment",
                    "House",
                    "Residence",
                ]:
                    data = j
                    break
                if isinstance(j, list):
                    for item in j:
                        if isinstance(item, dict) and item.get("@type") in [
                            "SingleFamilyResidence",
                            "Apartment",
                            "House",
                            "Residence",
                        ]:
                            data = item
                            break
            except Exception:
                continue

        return data

    # ---------------------------------------------------------
    # Field Extractors (JSON-LD first, then HTML fallback)
    # ---------------------------------------------------------

    def _extract_price(self, json_ld: Dict) -> Optional[float]:
        # JSON-LD offer
        offer = json_ld.get("offers", {})
        if isinstance(offer, dict):
            price = offer.get("price")
            if price:
                try:
                    return float(price)
                except Exception:
                    pass

        # Fallback: search for a currency pattern
        if self.html:
            m = re.search(r"\$([\d,]+)", self.html)
            if m:
                return float(m.group(1).replace(",", ""))

        return None

    def _extract_address_full(self, json_ld: Dict) -> Optional[str]:
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

        # Fallback from page title / meta
        if self.soup:
            meta = self.soup.find("meta", property="og:title")
            if meta and meta.get("content"):
                return meta["content"].strip()

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

        # Fallback: regex from raw HTML
        if self.html:
            m = re.search(r",\s*([\w\s]+),\s*([A-Z]{2})\s*(\d{5})", self.html)
            if m:
                return m.group(1), m.group(2), m.group(3)

        return None, None, None

    def _extract_beds(self, json_ld: Dict) -> Optional[float]:
        if "numberOfRooms" in json_ld:
            try:
                return float(json_ld["numberOfRooms"])
            except Exception:
                pass

        if self.html:
            m = re.search(r"([\d\.]+)\s*beds?", self.html.lower())
            if m:
                return float(m.group(1))

        return None

    def _extract_baths(self, json_ld: Dict) -> Optional[float]:
        if "numberOfBathroomsTotal" in json_ld:
            try:
                return float(json_ld["numberOfBathroomsTotal"])
            except Exception:
                pass

        if self.html:
            m = re.search(r"([\d\.]+)\s*baths?", self.html.lower())
            if m:
                return float(m.group(1))

        return None

    def _extract_sqft(self, json_ld: Dict) -> Optional[int]:
        floor_size = json_ld.get("floorSize", {})
        if isinstance(floor_size, dict) and "value" in floor_size:
            try:
                return int(floor_size["value"])
            except Exception:
                pass

        if self.html:
            m = re.search(r"([\d,]+)\s*sq\s*ft", self.html.lower())
            if m:
                return int(m.group(1).replace(",", ""))

        return None

    def _extract_lot_size(self, json_ld: Dict) -> Optional[int]:
        lot = json_ld.get("lotSize", {})
        if isinstance(lot, dict) and "value" in lot:
            try:
                return int(lot["value"])
            except Exception:
                pass

        if self.html:
            m = re.search(r"([\d,]+)\s*sq\s*ft\s*lot", self.html.lower())
            if m:
                return int(m.group(1).replace(",", ""))

        return None

    def _extract_year_built(self) -> Optional[int]:
        if not self.html:
            return None

        m = re.search(r"Built\s+in\s+(\d{4})", self.html)
        if m:
            return int(m.group(1))

        m = re.search(r"Year Built[:\s]+(\d{4})", self.html)
        if m:
            return int(m.group(1))

        return None

    def _extract_property_type(self, json_ld: Dict) -> Optional[str]:
        if "@type" in json_ld:
            return json_ld["@type"]

        if self.html:
            m = re.search(r"Property Type[:\s]+([\w\s]+)<", self.html)
            if m:
                return m.group(1).strip()

        return None

    def _extract_num_units(self) -> Optional[int]:
        """
        Try to infer unit count based on descriptive text.
        """
        if not self.html:
            return None

        text = self.html.lower()
        m = re.search(r"(\d+)[ -]?unit\b", text)
        if m:
            return int(m.group(1))

        if "duplex" in text:
            return 2
        if "triplex" in text:
            return 3
        if "fourplex" in text or "quadruplex" in text:
            return 4

        return None

    # ---------------------------------------------------------
    # Main parse method
    # ---------------------------------------------------------

    def parse(self) -> Dict:
        if not self.fetch():
            return {"success": False, "error": "Failed to fetch Homes.com page"}

        json_ld = self._extract_embedded_json()

        address_full = self._extract_address_full(json_ld)
        city, state, zipcode = self._extract_city_state_zip(json_ld)

        return {
            "success": True,
            "source": "homes.com",
            "address_full": address_full,
            "city": city,
            "state": state,
            "zip": zipcode,
            "price": self._extract_price(json_ld),
            "beds": self._extract_beds(json_ld),
            "baths": self._extract_baths(json_ld),
            "sqft": self._extract_sqft(json_ld),
            "lot_size": self._extract_lot_size(json_ld),
            "year_built": self._extract_year_built(),
            "property_type": self._extract_property_type(json_ld),
            "num_units": self._extract_num_units(),
        }
