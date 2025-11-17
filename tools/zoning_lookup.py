"""
zoning_lookup.py

Zoning lookup and interpretation tool for Los Angeles properties.

This module:
1) Normalizes and interprets zoning codes such as:
   - "R1-1"
   - "RD1.5-1-O"
   - "C2-1VL-CPIO"
   - "R3-1-TOC"

2) Optionally parses HTML copied from ZIMAS or other zoning portals to extract:
   - Base zone (R1, R2, RD1.5, R3, R4, C2, etc.)
   - Height district (e.g. 1, 1VL, 2D)
   - Overlays (TOC, CDO, SNAP, Specific Plan, etc.)
   - Community Plan Area
   - RSO flag (where available)

NOTE:
This is not an official zoning determination. All conclusions must be
verified with the City of Los Angeles Department of City Planning and
ZIMAS or equivalent official sources.
"""

import re
from typing import Optional, Dict

from bs4 import BeautifulSoup


class ZoningInterpreter:
    """
    Interprets zoning code strings such as 'R3-1-TOC' or 'C2-1VL-O-CPIO'.

    Example:

        zi = ZoningInterpreter("RD1.5-1-TOC")
        info = zi.interpret()

        -> {
            "raw_zoning": "RD1.5-1-TOC",
            "base_zone": "RD1.5",
            "height_district": "1",
            "overlays": ["TOC"],
            "is_residential": True,
            "is_commercial": False,
            "density_category": "small_multifamily",
        }
    """

    def __init__(self, zoning_code: Optional[str]):
        self.raw = (zoning_code or "").upper().strip()

    def interpret(self) -> Dict:
        if not self.raw:
            return {
                "raw_zoning": None,
                "base_zone": None,
                "height_district": None,
                "overlays": [],
                "is_residential": None,
                "is_commercial": None,
                "density_category": None,
                "notes": "No zoning code provided"
            }

        parts = self.raw.split("-")
        base_zone = parts[0] if parts else None
        height_district = parts[1] if len(parts) > 1 else None
        overlays = parts[2:] if len(parts) > 2 else []

        is_residential = self._is_residential_zone(base_zone)
        is_commercial = self._is_commercial_zone(base_zone)
        density_category = self._density_category(base_zone)

        return {
            "raw_zoning": self.raw,
            "base_zone": base_zone,
            "height_district": height_district,
            "overlays": overlays,
            "is_residential": is_residential,
            "is_commercial": is_commercial,
            "density_category": density_category,
            "notes": None
        }

    def _is_residential_zone(self, base_zone: Optional[str]) -> Optional[bool]:
        if not base_zone:
            return None

        if base_zone.startswith(("R", "RD", "RE", "RS")):
            return True
        return False

    def _is_commercial_zone(self, base_zone: Optional[str]) -> Optional[bool]:
        if not base_zone:
            return None

        if base_zone.startswith(("C", "CR", "CM", "M")):
            return True
        return False

    def _density_category(self, base_zone: Optional[str]) -> Optional[str]:
        """
        Very rough density classification.
        """

        if not base_zone:
            return None

        z = base_zone.upper()

        # Single-family neighborhood style zones
        if z.startswith(("R1", "RE", "RS")):
            return "single_family"

        # Duplex / small lot
        if z.startswith("R2"):
            return "duplex"

        # RD zones often allow small multifamily
        if z.startswith("RD"):
            return "small_multifamily"

        # R3 / R4 / R5 = higher density multi
        if z.startswith("R3"):
            return "medium_multifamily"
        if z.startswith("R4"):
            return "high_multifamily"
        if z.startswith("R5"):
            return "very_high_multifamily"

        # Commercial / mixed
        if z.startswith(("C", "CM", "CR", "M")):
            return "commercial_mixed"

        return "unknown"


class ZoningLookup:
    """
    Zoning lookup combining:
    - zoning code string interpretation
    - optional HTML parsing from ZIMAS or other city portals

    Usage:

        zl = ZoningLookup()
        info = zl.from_zoning_code("R3-1-TOC")

        or

        info = zl.from_zimas_html(html_snippet_with_zoning)
    """

    def __init__(self):
        pass

    # ---------------------------------------------------------
    # Direct zoning code interface
    # ---------------------------------------------------------

    def from_zoning_code(self, zoning_code: str) -> Dict:
        interpreter = ZoningInterpreter(zoning_code)
        interpreted = interpreter.interpret()

        return {
            "source": "code",
            "zoning": interpreted,
            "community_plan_area": None,
            "rso_flag": None,
            "notes": "Parsed from zoning code only; no ZIMAS HTML provided."
        }

    # ---------------------------------------------------------
    # ZIMAS / HTML parsing interface (optional)
    # ---------------------------------------------------------

    def from_zimas_html(self, html_text: str) -> Dict:
        """
        User copies HTML from ZIMAS zoning profile page and pastes it in.
        This function attempts to extract:
            - zoning code (e.g. R3-1-TOC)
            - community plan area
            - RSO flag (if shown)
        """
        soup = BeautifulSoup(html_text, "html.parser")

        # Generic helper to find nearest value after a label
        def extract_after_label(label_pattern: str) -> Optional[str]:
            el = soup.find(text=re.compile(label_pattern, re.IGNORECASE))
            if not el:
                return None
            parent = el.parent
            # Look for next sibling span/div/etc.
            nxt = parent.find_next("span") or parent.find_next("div")
            if nxt:
                return nxt.get_text(strip=True)
            return None

        zoning_code = extract_after_label(r"Zoning")
        community_plan = extract_after_label(r"Community Plan")
        rso_flag = extract_after_label(r"RSO") or extract_after_label(r"Rent Stabilization")

        # Interpret zoning code if found
        zoning_info = None
        if zoning_code:
            interpreter = ZoningInterpreter(zoning_code)
            zoning_info = interpreter.interpret()

        return {
            "source": "zimas_html",
            "zoning": zoning_info,
            "community_plan_area": community_plan,
            "rso_flag": rso_flag,
            "notes": "Parsed from ZIMAS-like HTML; verify with official records."
        }

    # ---------------------------------------------------------
    # Unified lookup
    # ---------------------------------------------------------

    def lookup(
        self,
        zoning_code: Optional[str] = None,
        zimas_html: Optional[str] = None
    ) -> Dict:
        """
        Unified method:

        - If HTML is provided, use from_zimas_html()
        - Else, if zoning_code is provided, use from_zoning_code()
        - Else, return empty structure
        """
        if zimas_html:
            return self.from_zimas_html(zimas_html)

        if zoning_code:
            return self.from_zoning_code(zoning_code)

        return {
            "source": None,
            "zoning": None,
            "community_plan_area": None,
            "rso_flag": None,
            "notes": "No zoning information provided."
        }
