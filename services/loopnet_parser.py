"""
loopnet_parser.py

LoopNet parser for commercial and multifamily 5+ properties.

LoopNet is the primary listing platform for:
- 5+ unit multifamily
- retail, office, industrial
- mixed-use
- land / redevelopment sites

IMPORTANT:
LoopNet often blocks automated scraping at scale. This parser uses:
- basic HTML extraction
- meta-tag parsing
- embedded JSON extraction (when available)

This is the light version. A future upgrade will support:
- PDF Offering Memorandum extraction
- rent roll table extraction
- OM financial summary scraping
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict


class LoopNetParser:
    """
    Input:
        url: LoopNet listing URL

    Output (standardized):
        {
            "success": True/False,
            "source": "loopnet",
            "address_full": str,
            "city": str,
            "state": str,
            "zip": str,
            "price": float | None,
            "cap_rate": float | None,
            "building_sqft": int | None,
            "lot_sqft": int | None,
            "year_built": int | None,
            "property_type": str | None,
            "num_units": int | None,
            "noi": float | None,
            "rent_roll_raw": str | None,
        }
    """

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, url: str):
        self.url = url
        self.html = None
        self.soup: Optional[BeautifulSoup] = None

    # -------------------------------------------------------------
    # Fetch Page
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
        LoopNet address typically in: <h1 class="property-title">
        But fallback includes:
        - meta[property="og:title"]
        - title tag
        """
        if not self.soup:
            return None

        title_el = self.soup.select_one("h1.property-title")
        if title_el:
            return title_el.get_text(strip=True)

        meta = self.soup.find("meta", property="og:title")
        if meta and meta.get("content"):
            return meta["content"].strip()

        title2 = self.soup.find("title")
        if title2:
            return title2.get_text(strip=True)

        return None

    def _extract_city_state_zip(self, address: str):
        if not address:
            return None, None, None

        m = re.search(r",\s*([\w\s]+),\s*([A-Z]{2})\s*(\d{5})", address)
        if m:
            return m.group(1), m.group(2), m.group(3)

        return None, None, None

    # -------------------------------------------------------------
    # Price, Cap Rate, NOI
    # -------------------------------------------------------------

    def _extract_price(self) -> Optional[float]:
        if not self.html:
            return None

        # $3,200,000 style
        m = re.search(r"\$([\d,]+)", self.html)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except:
                return None

        return None

    def _extract_cap_rate(self) -> Optional[float]:
        if not self.html:
            return None

        m = re.search(r"Cap Rate[:\s]+([\d\.]+)%", self.html)
        if m:
            return float(m.group(1)) / 100

        return None

    def _extract_noi(self) -> Optional[float]:
        if not self.html:
            return None

        # NOI: $123,456
        m = re.search(r"NOI[:\s]+\$([\d,]+)", self.html)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except:
                pass

        return None

    # -------------------------------------------------------------
    # Building Specs
    # -------------------------------------------------------------

    def _extract_building_sqft(self) -> Optional[int]:
        if not self.html:
            return None

        m = re.search(r"([\d,]+)\s*SF", self.html)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except:
                return None

        return None

    def _extract_lot_sqft(self) -> Optional[int]:
        if not self.html:
            return None

        # Lot Size: 7,500 SF
        m = re.search(r"Lot Size[:\s]+([\d,]+)\s*SF", self.html)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except:
                return None

        return None

    def _extract_year_built(self) -> Optional[int]:
        if not self.html:
            return None

        m = re.search(r"Year Built[:\s]+(\d{4})", self.html)
        if m:
            return int(m.group(1))

        return None

    # -------------------------------------------------------------
    # Property Type / Units
    # -------------------------------------------------------------

    def _extract_property_type(self) -> Optional[str]:
        if not self.html:
            return None

        m = re.search(r"Property Type[:\s]+([\w\s]+)<", self.html)
        if m:
            return m.group(1).strip()

        # fallback meta
        meta = self.soup.find("meta", property="og:type")
        if meta:
            return meta.get("content")

        return None

    def _extract_num_units(self) -> Optional[int]:
        if not self.html:
            return None

        # 16 Units, 24-Unit Building, etc.
        m = re.search(r"(\d+)[ -]?[Uu]nit", self.html)
        if m:
            try:
                return int(m.group(1))
            except:
                pass

        return None

    # -------------------------------------------------------------
    # Rent Roll Capture (Raw Text)
    # -------------------------------------------------------------

    def _extract_rent_roll_raw(self) -> Optional[str]:
        """
        Some LoopNet listings include a rent roll block in plain text,
        which may appear as a <pre> block or <div> with financial text.

        This does NOT replace full OM/PDF extraction, but is a useful
        starting input for the underwriting model.
        """
        if not self.soup:
            return None

        # look for a preformatted block
        pre = self.soup.find("pre")
        if pre:
            return pre.get_text("\n", strip=True)

        # fallback: search for "Rent Roll" section title
        rr_block = None
        for tag in self.soup.find_all(["div", "section"]):
            if tag.get_text().strip().lower().startswith("rent roll"):
                rr_block = tag.get_text("\n", strip=True)
                break

        if rr_block:
            return rr_block

        return None

    # -------------------------------------------------------------
    # Main parse()
    # -------------------------------------------------------------

    def parse(self) -> Dict:
        if not self.fetch():
            return {"success": False, "error": "Failed to fetch LoopNet page"}

        address_full = self._extract_address()
        city, state, zipcode = self._extract_city_state_zip(address_full or "")

        return {
            "success": True,
            "source": "loopnet",
            "address_full": address_full,
            "city": city,
            "state": state,
            "zip": zipcode,
            "price": self._extract_price(),
            "cap_rate": self._extract_cap_rate(),
            "building_sqft": self._extract_building_sqft(),
            "lot_sqft": self._extract_lot_sqft(),
            "year_built": self._extract_year_built(),
            "property_type": self._extract_property_type(),
            "num_units": self._extract_num_units(),
            "noi": self._extract_noi(),
            "rent_roll_raw": self._extract_rent_roll_raw(),
        }
