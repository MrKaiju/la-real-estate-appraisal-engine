"""
rent_control_classifier.py

Determines whether a property is subject to:
- LA City Rent Stabilization Ordinance (RSO)
- LA County Rent Stabilization Ordinance
- Exempt status (SFR, condos, new construction, ADUs, etc.)

This is NOT legal advice. It serves as a classification tool
based on known public rules and should be verified using
City of LA ZIMAS, County RSO registry, and local ordinances.
"""

from typing import Optional, Dict


class RentControlClassifier:
    """
    Rent Control Evaluation Process:

    Inputs:
        - year_built
        - property_type (SFR, duplex, multifamily, condo, commercial)
        - jurisdiction (la_city, la_county, other_city)
        - num_units

    Outputs:
        - rso_applies: True/False
        - jurisdiction: string ("LA City", "LA County", "Unknown")
        - exemption_reason: string explanation
    """

    def __init__(
        self,
        year_built: Optional[int],
        property_type: Optional[str],
        jurisdiction: Optional[str],
        num_units: Optional[int]
    ):
        self.year_built = year_built
        self.property_type = (property_type or "").lower().strip()
        self.jurisdiction = (jurisdiction or "").lower().strip()
        self.num_units = num_units or 0

    # ------------------------------------------------------------
    # Core Classification Rules
    # ------------------------------------------------------------

    def is_new_construction(self) -> bool:
        """
        Properties built after 1978 are generally exempt from LA City RSO.
        For LA County, exemption rules vary by region.
        """
        if not self.year_built:
            return False
        return self.year_built >= 1979

    def is_sfr_or_condo(self) -> bool:
        """
        SFRs and condos are exempt from LA City RSO.
        LA County rules depend on tenancy circumstances.
        """
        return self.property_type in ["sfr", "single_family", "condo"]

    def is_small_multiunit(self) -> bool:
        """
        Duplexes, triplexes, fourplexes — covered by RSO in City of LA
        if built before 1978.
        """
        return self.num_units in [2, 3, 4]

    def is_large_multifamily(self) -> bool:
        """
        5+ units — covered by RSO in City of LA if built before 1978.
        """
        return self.num_units >= 5

    # ------------------------------------------------------------
    # Jurisdiction Logic
    # ------------------------------------------------------------

    def is_la_city(self) -> bool:
        return self.jurisdiction in ["la city", "city of la", "los angeles"]

    def is_la_county(self) -> bool:
        return self.jurisdiction in ["la county", "los angeles county", "unincorporated la"]

    # ------------------------------------------------------------
    # Main Evaluation
    # ------------------------------------------------------------

    def evaluate(self) -> Dict:
        """
        Returns a structured assessment of rent control applicability.
        """

        # Unknown jurisdiction
        if self.jurisdiction == "" or self.jurisdiction == "unknown":
            return {
                "rso_applies": None,
                "jurisdiction": "Unknown",
                "reason": "Insufficient jurisdiction data"
            }

        # -----------------------------
        # LA CITY RSO LOGIC
        # -----------------------------
        if self.is_la_city():
            if self.is_new_construction():
                return {
                    "rso_applies": False,
                    "jurisdiction": "LA City",
                    "reason": "New construction (post-1978) exempt"
                }

            if self.is_sfr_or_condo():
                return {
                    "rso_applies": False,
                    "jurisdiction": "LA City",
                    "reason": "SFR or condo is exempt from LA City RSO"
                }

            if self.is_small_multiunit() or self.is_large_multifamily():
                return {
                    "rso_applies": True,
                    "jurisdiction": "LA City",
                    "reason": "Pre-1978 multifamily subject to LA City RSO"
                }

            return {
                "rso_applies": None,
                "jurisdiction": "LA City",
                "reason": "Unable to classify property type"
            }

        # -----------------------------
        # LA COUNTY RSO LOGIC
        # -----------------------------
        if self.is_la_county():
            if self.is_new_construction():
                return {
                    "rso_applies": False,
                    "jurisdiction": "LA County",
                    "reason": "Post-1995 construction generally exempt"
                }

            if self.is_sfr_or_condo():
                return {
                    "rso_applies": False,
                    "jurisdiction": "LA County",
                    "reason": "SFR/condo generally exempt under County RSO"
                }

            if self.num_units >= 2:
                return {
                    "rso_applies": True,
                    "jurisdiction": "LA County",
                    "reason": "Multifamily units may fall under LA County RSO"
                }

            return {
                "rso_applies": None,
                "jurisdiction": "LA County",
                "reason": "Insufficient data for County classification"
            }

        # -----------------------------
        # OTHER CITIES IN LA COUNTY
        # -----------------------------
        return {
            "rso_applies": False,
            "jurisdiction": "Other City",
            "reason": "Most other cities in LA County do not have RSO"
        }
