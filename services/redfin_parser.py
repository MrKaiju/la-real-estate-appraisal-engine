"""
redfin_parser.py

Attempts to parse Redfin listing pages and extract property data.

This parser uses defensive scraping strategies because Redfin HTML
structure changes frequently. All selectors include fallbacks.

Outputs a standardized dictionary so downstream analysis
(income approach, zoning, risk scoring) can work consistently.

NOTE: This is a lightweight HTML scraper, not an API. For large-scale use,
a proper proxy + browser-based automation tool is recommended.
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict


class RedfinParser:
    """
    Input:
        - url: Redfin listing URL

    Output:
        - dict containing standardized property fields:
            {
                "address": str,
                "city": str,
                "state": str,
                "zip": str,
                "price": float,
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
    # Fetch & Parse HTML
    # -------------------------------------------------------------

    def fetch(self) -> bool:
        try:
            response = requests.get(self.url, headers={"User-Agent": self.USER_AGENT}, timeout=10)
            if response.status_code != 200:
                return False
            self.html = response.text
            self.soup = BeautifulSoup(self.html, "html.parser")
            return True
        except:
            return False

    # -------------------------------------------------------------
    # Extraction Helpers
    # -------------------------------------------------------------

    def _extract_price(self) -> Optional[float]:
        patterns = [
            r"\$([\d,]+)",  # $1,234,000
        ]
        for p in patterns:
            match = re.search(p, self.html or "")
            if match:
                return float(match.group(1).replace(",", ""))
        return None

    def _extract_address(self) -> Optional[str]:
        el = self.soup.select_one("div.address > h1")
        if el:
            return el.get_text(strip=True)

        # fallback
        title = self.soup.find("title")
        if title:
            parts = title.get_text().split("|")
            if len(parts) > 0:
                return parts[0].strip()

        return None

    def _extract_beds(self) -> Optional[float]:
        text = self._find_text(["Beds", "bed"])
        if text:
            match = re.search(r"([\d\.]+)", text)
            if match:
                return float(match.group(1))
        return None

    def _extract_baths(self) -> Optional[float]:
        text = self._find_text(["Bath", "bath"])
        if text:
            match = re.search(r"([\d\.]+)", text)
            if match:
                return float(match.group(1))
        return None

    def _extract_sqft(self) -> Optional[int]:
        text = self._find_text(["Sq. Ft", "sqft", "Sq Ft"])
        if text:
            m = re.search(r"([\d,]+)", text)
            if m:
                return int(m.group(1).replace(",", ""))
        return None

    def _extract_lot_size(self) -> Optional[int]:
        text = self._find_text(["Lot Size", "lot size"])
        if text:
            m = re.search(r"([\d,]+)", text)
            if m:
                return int(m.group(1).replace(",", ""))
        return None

    def _extract_year_built(self) -> Optional[int]:
        text = self._find_text(["Year Built", "Built"])
        if text:
            m = re.search(r"(\d{4})", text)
            if m:
                return int(m.group(1))
        return None

    def _extract_property_type(self) -> Optional[str]:
        text = self._find_text(["Property Type", "Home Type", "Type"])
        if text:
            return text.strip()
        return None

    def _extract_num_units(self) -> Optional[int]:
        """
        Redfin rarely shows unit count directly — this tries to infer from description.
        """
        text = self.html or ""
        m = re.search(r"(\d+)[ -]?unit", text.lower())
        if m:
            return int(m.group(1))

        # fallback: property type hints
        if "duplex" in text.lower():
            return 2
        if "triplex" in text.lower():
            return 3
        if "fourplex" in text.lower() or "quadruplex" in text.lower():
            return 4

        return None

    # -------------------------------------------------------------
    # Utility for scanning common Redfin fields
    # -------------------------------------------------------------

    def _find_text(self, keywords):
        for key in keywords:
            el = self.soup.find(text=re.compile(key, re.IGNORECASE))
            if el:
                return el.parent.get_text(" ", strip=True)
        return None

    # -------------------------------------------------------------
    # Main Parse Method
    # -------------------------------------------------------------

    def parse(self) -> Dict:
        if not self.fetch():
            return {
                "success": False,
                "error": "Could not fetch Redfin page"
            }

        # address parsing
        full_address = self._extract_address() or ""

        # attempt city / state / zip split
        city, state, zipcode = None, None, None
        parts = full_address.split(",")
        if len(parts) >= 3:
            city = parts[-3].strip()
            state_zip = parts[-2].strip().split(" ")
            if len(state_zip) >= 2:
                state = state_zip[0]
                zipcode = state_zip[1]

        return {
            "success": True,
            "source": "redfin",
            "address_full": full_address,
            "city": city,
            "state": state,
            "zip": zipcode,
            "price": self._extract_price(),
            "beds": self._extract_beds(),
            "baths": self._extract_baths(),
            "sqft": self._extract_sqft(),
            "lot_size": self._extract_lot_size(),
            "year_built": self._extract_year_built(),
            "property_type": self._extract_property_type(),
            "num_units": self._extract_num_units()
        }
