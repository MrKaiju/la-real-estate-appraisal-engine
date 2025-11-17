"""
cap_rate_model.py

Cap Rate Selection & Adjustment Model

Purpose:
- Provide a programmatic way to estimate a reasonable cap rate
  for a property based on:
    - property type (SFR, 2–4 units, 5+ MF, retail, etc.)
    - submarket quality (prime, core, stable, transitional, distressed)
    - risk score (0–100 from risk_scoring model)
    - rent control / RSO flag

Outputs:
- base_cap_rate: cap rate before detailed risk adjustments
- adjusted_cap_rate: final cap rate after risk/rent-control adjustments
"""

from typing import Optional, Dict


class CapRateModel:
    """
    Parameters:
        property_type: one of:
            - "sfr"
            - "2-4"
            - "5+"
            - "mixed_use"
            - "retail"
            - "office"
            - "industrial"
            - "land"
        submarket_class: one of:
            - "prime"        (e.g., West LA, Beverly Hills adj., top corridors)
            - "core"         (e.g., good infill LA areas)
            - "stable"       (average LA neighborhoods)
            - "transitional" (up-and-coming, more volatility)
            - "distressed"   (high vacancy/crime/instability)
        risk_score: 0–100 risk score from risk_scoring model
                    (higher = more risk)
        is_rent_controlled: True/False for LA-style rent control (RSO/County)
    """

    def __init__(
        self,
        property_type: str,
        submarket_class: str,
        risk_score: Optional[float] = None,
        is_rent_controlled: bool = False,
    ):
        self.property_type = (property_type or "").lower()
        self.submarket_class = (submarket_class or "").lower()
        self.risk_score = risk_score
        self.is_rent_controlled = is_rent_controlled

    # ----------------------------------------------------------
    # Base cap rate grid
    # ----------------------------------------------------------

    def _base_cap_rate_grid(self) -> Dict[str, Dict[str, float]]:
        """
        Baseline LA-style cap rate assumptions (approximate ranges).
        These are midpoints that you can tweak over time.
        """
        return {
            "sfr": {
                "prime": 0.035,
                "core": 0.040,
                "stable": 0.0425,
                "transitional": 0.045,
                "distressed": 0.050,
            },
            "2-4": {
                "prime": 0.0375,
                "core": 0.0425,
                "stable": 0.045,
                "transitional": 0.0475,
                "distressed": 0.0525,
            },
            "5+": {
                "prime": 0.040,
                "core": 0.045,
                "stable": 0.0475,
                "transitional": 0.050,
                "distressed": 0.055,
            },
            "mixed_use": {
                "prime": 0.0425,
                "core": 0.0475,
                "stable": 0.050,
                "transitional": 0.0525,
                "distressed": 0.0575,
            },
            "retail": {
                "prime": 0.045,
                "core": 0.050,
                "stable": 0.0525,
                "transitional": 0.055,
                "distressed": 0.060,
            },
            "office": {
                "prime": 0.050,
                "core": 0.055,
                "stable": 0.060,
                "transitional": 0.065,
                "distressed": 0.070,
            },
            "industrial": {
                "prime": 0.040,
                "core": 0.045,
                "stable": 0.0475,
                "transitional": 0.050,
                "distressed": 0.055,
            },
            "land": {
                "prime": 0.020,  # often valued on residual basis, not simple cap
                "core": 0.025,
                "stable": 0.030,
                "transitional": 0.035,
                "distressed": 0.040,
            },
        }

    def base_cap_rate(self) -> Optional[float]:
        """
        Get the base cap rate for the specified property type & submarket.
        """
        grid = self._base_cap_rate_grid()

        p_type = self.property_type
        if p_type not in grid:
            # Default to 5+ MF stable if unrecognized
            p_type = "5+"

        s_class = self.submarket_class
        if s_class not in grid[p_type]:
            s_class = "stable"

        return grid[p_type][s_class]

    # ----------------------------------------------------------
    # Risk-based adjustment
    # ----------------------------------------------------------

    def _risk_adjustment_bps(self) -> float:
        """
        Convert risk score (0–100) into a cap rate adjustment (bps).

        Concept:
            - Risk score ~ 20–40: modest downward adjustment (-10 to 0 bps)
            - Risk score ~ 40–60: neutral to slightly upward (+0 to +20 bps)
            - Risk score ~ 60–80: moderate upward (+20 to +40 bps)
            - Risk score ~ 80–100: significant upward (+40 to +75 bps)

        Return value is in absolute decimals, e.g. 0.0025 = 25 bps.
        """
        if self.risk_score is None:
            return 0.0

        rs = max(0.0, min(100.0, float(self.risk_score)))

        if rs < 20:
            # exceptionally low risk
            return -0.0010  # -10 bps
        elif rs < 40:
            return -0.0005  # -5 bps
        elif rs < 60:
            return 0.0000   # flat
        elif rs < 80:
            return 0.0020   # +20 bps
        else:
            return 0.0075   # +75 bps

    def _rent_control_adjustment_bps(self, base_cap: float) -> float:
        """
        Simple premium for rent-controlled assets.

        RSO / strong rent control usually:
        - reduces upside
        - increases regulatory risk
        so investors often demand a higher yield.

        We'll add a modest premium in bps.
        """
        if not self.is_rent_controlled:
            return 0.0

        # ~25–50 bps depending on base cap
        if base_cap <= 0.04:
            return 0.0030  # +30 bps
        elif base_cap <= 0.05:
            return 0.0040  # +40 bps
        else:
            return 0.0050  # +50 bps

    # ----------------------------------------------------------
    # Final adjusted cap rate
    # ----------------------------------------------------------

    def adjusted_cap_rate(self) -> Optional[float]:
        """
        Returns final cap rate after risk and rent-control adjustments.
        """
        base = self.base_cap_rate()
        if base is None:
            return None

        adj = base + self._risk_adjustment_bps() + self._rent_control_adjustment_bps(base)
        return round(adj, 4)

    # ----------------------------------------------------------
    # Summary output
    # ----------------------------------------------------------

    def summary(self) -> Dict:
        base = self.base_cap_rate()
        risk_adj = self._risk_adjustment_bps()
        rc_adj = self._rent_control_adjustment_bps(base or 0.0) if base is not None else 0.0
        final = self.adjusted_cap_rate()

        return {
            "inputs": {
                "property_type": self.property_type,
                "submarket_class": self.submarket_class,
                "risk_score": self.risk_score,
                "is_rent_controlled": self.is_rent_controlled,
            },
            "base_cap_rate": base,
            "risk_adjustment": risk_adj,
            "rent_control_adjustment": rc_adj,
            "final_cap_rate": final,
            "notes": "Cap rates are heuristic and must be benchmarked against real LA market comps."
        }
