"""
property_type_classifier.py

Classifies a property based on:
- number of units
- property type labels (SFR, Condo, Duplex, etc.)
- zoning code signals (R1, RD2, R3, C2, etc.)

Used for:
- rent control analysis
- income approach assumptions
- DSCR and financing strategy
- risk scoring
"""

from typing import Optional, Dict


class PropertyTypeClassifier:
    """
    Inputs:
        - num_units: from listing or assessor data
        - zoning_code: optional zoning string (R1, RD2, R3, C2)
        - building_type_label: raw type label (e.g., "Single Family", "Multiplex")

    Outputs:
        - property_type: standardized classification
        - category: "residential", "commercial", "mixed_use"
        - reason: explanation
    """

    def __init__(
        self,
        num_units: Optional[int] = None,
        zoning_code: Optional[str] = None,
        building_type_label: Optional[str] = None
    ):
        self.num_units = num_units or 0
        self.zoning = (zoning_code or "").upper().strip()
        self.label = (building_type_label or "").lower().strip()

    # --------------------------------------------------------
    # Classification by explicit unit count
    # --------------------------------------------------------

    def _unit_count_based(self) -> Optional[str]:
        if self.num_units == 1:
            return "sfr"
        if self.num_units == 2:
            return "duplex"
        if self.num_units == 3:
            return "triplex"
        if self.num_units == 4:
            return "fourplex"
        if self.num_units >= 5:
            return "multifamily_5plus"
        return None

    # --------------------------------------------------------
    # Classification using building type labels
    # --------------------------------------------------------

    def _label_based(self) -> Optional[str]:
        if "single" in self.label:
            return "sfr"
        if "condo" in self.label:
            return "condo"
        if "townhome" in self.label or "townhouse" in self.label:
            return "townhome"
        if "apartment" in self.label:
            return "multifamily_5plus"
        if "duplex" in self.label:
            return "duplex"
        if "triplex" in self.label:
            return "triplex"
        if "fourplex" in self.label or "quadplex" in self.label:
            return "fourplex"
        if "multi" in self.label:
            return "multifamily_5plus"
        if "commercial" in self.label:
            return "commercial"
        return None

    # --------------------------------------------------------
    # Classification using zoning code
    # --------------------------------------------------------

    def _zoning_based(self) -> Optional[str]:
        if self.zoning.startswith("R1") or self.zoning.startswith("RS") or self.zoning.startswith("RE"):
            return "sfr"
        if self.zoning.startswith("RD"):
            # RD zones typically allow small multifamily
            return "small_multifamily"
        if self.zoning.startswith("R2"):
            return "duplex"
        if self.zoning.startswith("R3"):
            return "small_multifamily"
        if self.zoning.startswith("R4"):
            return "multifamily_5plus"
        if self.zoning.startswith("R5"):
            return "multifamily_5plus"
        if self.zoning.startswith("C"):
            return "commercial"
        return None

    # --------------------------------------------------------
    # Main evaluation
    # --------------------------------------------------------

    def evaluate(self) -> Dict:
        """
        Returns a standardized classification.
        """

        # Primary: unit count
        unit_based = self._unit_count_based()
        if unit_based:
            return {
                "property_type": unit_based,
                "category": "residential" if "multi" not in unit_based else "residential_income",
                "reason": "Classified based on unit count"
            }

        # Secondary: listing label
        label_based = self._label_based()
        if label_based:
            category = "commercial" if label_based == "commercial" else "residential"
            return {
                "property_type": label_based,
                "category": category,
                "reason": "Classified based on building type label"
            }

        # Fallback: zoning
        zoning_based = self._zoning_based()
        if zoning_based:
            if zoning_based == "commercial":
                category = "commercial"
            else:
                category = "residential"
            return {
                "property_type": zoning_based,
                "category": category,
                "reason": "Classified based on zoning code"
            }

        # Unknown fallback
        return {
            "property_type": "unknown",
            "category": "unknown",
            "reason": "Insufficient data to classify property type"
        }
