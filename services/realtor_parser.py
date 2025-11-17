"""
realtor_parser.py

Attempts to parse Realtor.com listing pages and extract property data.

Realtor.com uses a mix of JSON-LD, embedded script tags,
and HTML metadata. This parser pulls from all three sources
to maximize accuracy.

Outputs standardized property fields so downstream valuation
models can use a consistent structure.

NOTE:
This is a lightweight HTML scraper. For high-volume usage,
Realtor pages should be parsed with rotating proxies or
headless browser automation.
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional


class RealtorParser:
    """
    Input:
        - url: Realtor.com listing URL

    Output:
        {
            "success": True/False,
            "source": "realtor",
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
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
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
            r = requests.get(self.url, headers={"User-Agent": self.USER_AGENT}, timeout=10)
            if r.status_code != 200:
                return False

            self.html = r.text
            self.soup = BeautifulSoup(self.html, "html.parser")
            return True
        except:
            return False

    # -------------------------------------------------------------
    # JSON-LD Extraction (Primary Source)
    # -------------------------------------------------------------

    def _extract_json_ld(self) -> Dict:
        """
        Realtor.com pages often contain JSON-LD card metadata.
        """
        scripts = self.soup.find_all("script", type="application/ld+json")

        for tag in scripts:
            try:
                data = json.loads(tag.string)
                if isinstance(data, dict) and data.get("@type") in ["SingleFamilyResidence", "Residence", "House"]:
                    return data
            except:
                continue

        return {}

    # -------------------------------------------------------------
    # Field Extractors (with Fallbacks)
    # -------------------------------------------------------------

    def _extract_price(self, json_ld: Dict) -> Optional[float]:
        # JSON-LD first
        offer = json_ld.get("offers", {})
        if isinstance(offer, dict):
            price = offer.get("price")
            if price:
                return float(price)

        # fallback HTML search
        m = re.search(r"\$([\d,]+)", self.html or "")
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

            components = [street, city, state, zipcode]
            if any(components):
                return ", ".join([c for c in components if c])

        # fallback meta tags
        meta = self.soup.find("meta", property="og:street-address")
        if meta:
            return meta.get("content")

        return None

    def _extract_city_state_zip(self, json_ld: Dict) -> (Optional[str], Optional[str], Optional[str]):
        addr = json_ld.get("address", {})

        if isinstance(addr, dict):
            return (
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("postalCode"),
            )

        # fallback attempt
        m = re.search(r",\s*([\w\s]+),\s*([A-Z]{2})\s*(\d{5})", self.html or "")
        if m:
            return m.group(1), m.group(2), m.group(3)

        return None, None, None

    def _extract_beds(self, json_ld: Dict) -> Optional[float]:
        if "numberOfRooms" in json_ld:
            return float(json_ld.get("numberOfRooms", 0))

        m = re.search(r"(\d+)\s*beds?", self.html.lower())
        if m:
            return float(m.group(1))

        return None

    def _extract_baths(self, json_ld: Dict) -> Optional[float]:
        if "numberOfBathroomsTotal" in json_ld:
            return float(json_ld.get("numberOfBathroomsTotal"))

        m = re.search(r"([\d\.]+)\s*bath", self.html.lower())
        if m:
            return float(m.group(1))

        return None

    def _extract_sqft(self, json_ld: Dict) -> Optional[int]:
        if "floorSize" in json_ld:
            val = json_ld["floorSize"].get("value")
            if val:
                return int(val)

        m = re.search(r"([\d,]+)\s*sq\s*ft", self.html.lower())
        if m:
            return int(m.group(1).replace(",", ""))

        return None

    def _extract_lot_size(self, json_ld: Dict) -> Optional[int]:
        if "lotSize" in json_ld:
            val = json_ld["lotSize"].get("value")
            if val:
                return int(val)

        m = re.search(r"([\d,]+)\s*sq\s*ft\s*lot", self.html.lower())
        if m:
            return int(m.group(1).replace(",", ""))

        return None

    def _extract_year_built(self) -> Optional[int]:
        m = re.search(r"Built\s*in\s*(\d{4})", self.html)
        if m:
            return int(m.group(1))

        m = re.search(r"Year Built[:\s]+(\d{4})", self.html)
        if m:
            return int(m.group(1))

        return None

    def _extract_property_type(self, json_ld: Dict) -> Optional[str]:
        if "@type" in json_ld:
            return json_ld["@type"]

        m = re.search(r"Property Type[:\s]+([\w\s]+)<", self.html)
        if m:
            return m.group(1).strip()

        return None

    def _extract_num_units(self) -> Optional[int]:
        text = self.html.lower()

        # explicit identification
        m = re.search(r"(\d+)[ -]?unit\b", text)
        if m:
            return int(m.group(1))

        # inference models
        if "duplex" in text:
            return 2
        if "triplex" in text:
            return 3
        if "fourplex" in text or "quadruplex" in text:
            return 4

        return None

    # -------------------------------------------------------------
    # Main Parse Method
    # -------------------------------------------------------------

    def parse(self) -> Dict:
        if not self.fetch():
            return {"success": False, "error": "Page fetch failed"}

        json_ld = self._extract_json_ld()

        # Extract address components
        address_full = self._extract_address(json_ld)
        city, state, zipcode = self._extract_city_state_zip(json_ld)

        return {
            "success": True,
            "source": "realtor",
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
