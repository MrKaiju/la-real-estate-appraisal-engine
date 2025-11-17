"""
address_normalizer.py

Utility for cleaning and normalizing US street addresses.

Goals:
- Standardize street suffixes (Street -> St, Avenue -> Ave, etc.)
- Normalize directional prefixes/suffixes (North -> N, West -> W, etc.)
- Extract street, city, state, and ZIP where possible
- Produce a consistent normalized_full string that can be used for:
    - APN lookup
    - zoning/hazard overlay queries
    - matching across multiple data sources
"""

import re
from typing import Optional, Dict


class AddressNormalizer:
    """
    Example usage:

        norm = AddressNormalizer()
        result = norm.normalize("1234 West Adams Boulevard, Los Angeles, CA 90018")

        result =>
        {
            "raw": "1234 West Adams Boulevard, Los Angeles, CA 90018",
            "street": "1234 W Adams Blvd",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90018",
            "normalized_full": "1234 W Adams Blvd, Los Angeles, CA 90018"
        }
    """

    # Common USPS-style abbreviations
    STREET_SUFFIXES = {
        "STREET": "St",
        "ST": "St",
        "AVENUE": "Ave",
        "AVE": "Ave",
        "BOULEVARD": "Blvd",
        "BLVD": "Blvd",
        "ROAD": "Rd",
        "RD": "Rd",
        "DRIVE": "Dr",
        "DR": "Dr",
        "LANE": "Ln",
        "LN": "Ln",
        "COURT": "Ct",
        "CT": "Ct",
        "PLACE": "Pl",
        "PL": "Pl",
        "TERRACE": "Ter",
        "TER": "Ter",
        "WAY": "Way",
        "HIGHWAY": "Hwy",
        "HWY": "Hwy",
    }

    DIRECTIONALS = {
        "NORTH": "N",
        "SOUTH": "S",
        "EAST": "E",
        "WEST": "W",
        "NORTHEAST": "NE",
        "NORTHWEST": "NW",
        "SOUTHEAST": "SE",
        "SOUTHWEST": "SW",
        "N": "N",
        "S": "S",
        "E": "E",
        "W": "W",
        "NE": "NE",
        "NW": "NW",
        "SE": "SE",
        "SW": "SW",
    }

    ADDRESS_PATTERN = re.compile(
        r"""
        ^\s*
        (?P<street>.+?)          # street part (up to first comma)
        \s*,\s*
        (?P<city>[\w\s\.]+?)     # city name
        \s*,\s*
        (?P<state>[A-Za-z]{2})   # 2-letter state code
        \s+
        (?P<zip>\d{5})           # 5-digit ZIP
        \s*$
        """,
        re.VERBOSE,
    )

    def normalize(self, raw_address: str) -> Dict:
        """
        Main normalization entry point.

        Returns:
            {
                "raw": original string,
                "street": str | None,
                "city": str | None,
                "state": str | None,
                "zip": str | None,
                "normalized_full": str | None
            }
        """
        if not raw_address or not raw_address.strip():
            return {
                "raw": raw_address,
                "street": None,
                "city": None,
                "state": None,
                "zip": None,
                "normalized_full": None,
            }

        raw = raw_address.strip()
        match = self.ADDRESS_PATTERN.match(raw)

        if not match:
            # If we cannot parse, return raw as normalized_full
            return {
                "raw": raw,
                "street": raw,
                "city": None,
                "state": None,
                "zip": None,
                "normalized_full": raw,
            }

        street_raw = match.group("street")
        city_raw = match.group("city")
        state_raw = match.group("state")
        zip_raw = match.group("zip")

        street_norm = self._normalize_street(street_raw)
        city_norm = self._normalize_city(city_raw)
        state_norm = state_raw.upper()
        zip_norm = zip_raw

        normalized_full = f"{street_norm}, {city_norm}, {state_norm} {zip_norm}"

        return {
            "raw": raw,
            "street": street_norm,
            "city": city_norm,
            "state": state_norm,
            "zip": zip_norm,
            "normalized_full": normalized_full,
        }

    # ---------------------------------------------------------
    # Component normalizers
    # ---------------------------------------------------------

    def _normalize_city(self, city: str) -> str:
        """
        Title-case the city (e.g., 'los angeles' -> 'Los Angeles').
        """
        return city.strip().title()

    def _normalize_street(self, street: str) -> str:
        """
        Normalize directional prefixes/suffixes and street suffixes.
        Example:
            "1234 West Adams Boulevard" -> "1234 W Adams Blvd"
        """
        tokens = street.strip().split()
        if not tokens:
            return street.strip()

        # First token might be house number, keep as-is
        normalized_tokens = []

        for i, token in enumerate(tokens):
            upper = token.upper().strip(",")
            # Directionals (handle both prefix and suffix)
            if upper in self.DIRECTIONALS:
                normalized_tokens.append(self.DIRECTIONALS[upper])
                continue

            # Street suffixes
            if upper in self.STREET_SUFFIXES:
                normalized_tokens.append(self.STREET_SUFFIXES[upper])
                continue

            # Otherwise keep original casing, but strip commas
            normalized_tokens.append(token.strip(","))

        return " ".join(normalized_tokens)
