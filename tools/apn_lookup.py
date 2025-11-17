"""
apn_lookup.py

APN (Assessor Parcel Number) normalization and lookup utility.

LA County Assessor does not provide a public API for APN queries.
This module provides:

1. APN Normalization:
   - Cleans formatting
   - Strips hyphens
   - Ensures correct digit structure

2. Manual APN Input Support:
   - User can paste APN from LA County Assessor Portal

3. Optional HTML Extraction:
   - If user pastes assessor page HTML, extract:
       - land use code
       - lot size
       - building sqft
       - year built
       - number of units
       - assessed value

4. Standardized output format for integration with:
   - zoning tool
   - hazard tool
   - appraiser
"""

import re
from typing import Optional, Dict
from bs4 import BeautifulSoup


class APNLookup:
    """
    Example usage:

        apn_tool = APNLookup()
        result = apn_tool.normalize("5055-008-012")

        -> {
            "raw": "5055-008-012",
            "normalized": "5055008012",
            "pretty": "5055-008-012",
            "valid_format": True,
            ...
        }

    """

    # LA County APN is 10 digits (3 segments: xxxx-xxx-xxx)
    APN_PATTERN = re.compile(r"^(\d{4})[- ]?(\d{3})[- ]?(\d{3})$")

    # -----------------------------------------------------------
    # APN Normalization
    # -----------------------------------------------------------

    def normalize(self, raw_apn: str) -> Dict:
        raw = raw_apn.strip()

        m = self.APN_PATTERN.match(raw)
        if not m:
            return {
                "raw": raw,
                "normalized": None,
                "pretty": None,
                "valid_format": False
            }

        seg1, seg2, seg3 = m.groups()
        normalized = f"{seg1}{seg2}{seg3}"
        pretty = f"{seg1}-{seg2}-{seg3}"

        return {
            "raw": raw,
            "normalized": normalized,
            "pretty": pretty,
            "valid_format": True
        }

    # -----------------------------------------------------------
    # Assessor HTML Extraction (optional)
    # -----------------------------------------------------------

    def parse_assessor_html(self, html_text: str) -> Dict:
        """
        User pastes HTML from:
            https://portal.assessor.lacounty.gov/

        This extractor attempts to read common fields.
        """
        soup = BeautifulSoup(html_text, "html.parser")

        def extract_text(label):
            el = soup.find(text=re.compile(label, re.IGNORECASE))
            if not el:
                return None
            parent = el.parent
            if parent and parent.find_next("span"):
                return parent.find_next("span").get_text(strip=True)
            return None

        land_use = extract_text("Use Code")
        lot_size = extract_text("Lot Size")
        year_built = extract_text("Year Built")
        building_sqft = extract_text("Square Feet")
        assessed_total = extract_text("Assessed Value")
        units = extract_text("Units")

        # Numeric conversions
        def clean_num(val):
            if not val:
                return None
            return int(re.sub(r"[^\d]", "", val))

        return {
            "land_use_code": land_use,
            "lot_size_sqft": clean_num(lot_size),
            "building_sqft": clean_num(building_sqft),
            "year_built": clean_num(year_built),
            "num_units": clean_num(units),
            "assessed_value": clean_num(assessed_total),
        }

    # -----------------------------------------------------------
    # Combined APN + Assessor Merge
    # -----------------------------------------------------------

    def lookup(self, apn: str, assessor_html: Optional[str] = None) -> Dict:
        """
        Unified method:
        - Normalizes APN
        - If assessor_html included, parse details
        """

        norm = self.normalize(apn)

        result = {
            "apn_raw": norm["raw"],
            "apn_normalized": norm["normalized"],
            "apn_pretty": norm["pretty"],
            "valid_format": norm["valid_format"],
            "assessor_data": None,
        }

        if assessor_html:
            result["assessor_data"] = self.parse_assessor_html(assessor_html)

        return result
