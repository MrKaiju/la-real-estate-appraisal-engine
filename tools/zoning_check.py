"""
zoning_check.py

Simple zoning classifier for Los Angeles style zoning codes.
Determines whether a subject parcel appears to be:
- Single-family residential (SFR)
- Multifamily residential
- Commercial

This is a simplified helper and should be used together with
official zoning sources (ZIMAS, LA County GIS, etc.).
"""

class ZoningCheck:
    """
    ZoningCheck takes a zoning code string (e.g., 'R1', 'RD2', 'R3', 'C2')
    and returns a basic classification.
    """

    def __init__(self, zoning_code: str):
        # Normalize the code for easier comparisons
        self.code = (zoning_code or "").upper().strip()

    def is_multi_family(self) -> bool:
        """
        Returns True if the zoning appears to allow multifamily use.
        Common LA patterns: RD, R2, R3, R4, R5.
        """
        return any(prefix in self.code for prefix in ["RD", "R2", "R3", "R4", "R5"])

    def is_single_family(self) -> bool:
        """
        Returns True if the zoning appears to be low-density SFR.
        Common LA patterns: R1, RE (Residential Estate), RS (Suburban).
        """
        return any(prefix in self.code for prefix in ["R1", "RE", "RS"])

    def is_commercial(self) -> bool:
        """
        Returns True if the zoning appears commercial.
        Common LA patterns: C1, C2, C4, CR, etc.
        """
        return any(prefix in self.code for prefix in ["C1", "C2", "C3", "C4", "CR"])

    def summary(self) -> dict:
        """
        Returns a simple dictionary with zoning classification flags.
        """
        return {
            "zoning_code": self.code or None,
            "is_sfr": self.is_single_family(),
            "is_multifamily": self.is_multi_family(),
            "is_commercial": self.is_commercial()
        }
