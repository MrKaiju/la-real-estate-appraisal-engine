"""
risk_scoring.py

Produces a 0–100 risk score using:
- Hazard risk
- Rent control risk
- Jurisdiction risk
- Zoning/land-use risk
- Property age
- Underwriting (DSCR, cash flow)
- Income scenario volatility
- Property type risk

This model synthesizes multiple signals into a single,
comparable investment risk score.
"""

from typing import Dict, Optional


class RiskScoring:
    """
    Inputs:
        hazards: dict from HazardOverlayChecker.summary()
        rent_control: dict from RentControlClassifier.evaluate()
        jurisdiction: dict from JurisdictionChecker.evaluate()
        underwriting: dict {dscr, annual_cash_flow, coc_return}
        property_type: dict from PropertyTypeClassifier.evaluate()
        subject: property metadata {year_built, ...}
        income_scenarios: dict from IncomeScenarios.all_scenarios()

    Output:
        - score: 0 to 100 (100 = lowest risk)
        - grade: A, B, C, or D
        - interpretation
    """

    def __init__(
        self,
        hazards: Dict,
        rent_control: Dict,
        jurisdiction: Dict,
        underwriting: Dict,
        property_type: Dict,
        subject: Dict,
        income_scenarios: Optional[Dict] = None
    ):
        self.hazards = hazards or {}
        self.rent_control = rent_control or {}
        self.jurisdiction = jurisdiction or {}
        self.underwriting = underwriting or {}
        self.property_type = property_type or {}
        self.subject = subject or {}
        self.income_scenarios = income_scenarios or {}

    # -------------------------------------------------------------
    # Helper methods to generate component scores
    # -------------------------------------------------------------

    def _score_hazards(self) -> float:
        """
        Hazards: flood, fire, earthquake. Placeholder logic until GIS is added.
        """
        h = self.hazards

        # Default assumption: unknown hazards = neutral
        penalty = 0

        # If known high-risk zones later get integrated, adjust scoring
        flood = h.get("flood", {}).get("is_high_risk")
        fire = h.get("fire", {}).get("within_high_fire_hazard_area")
        fault = h.get("earthquake_fault", {}).get("within_fault_zone")

        for risk in [flood, fire, fault]:
            if risk is True:
                penalty += 20  # high hazard = major penalty

        # Score = 100 - penalty (min 40)
        return max(40, 100 - penalty)

    def _score_rent_control(self) -> float:
        """
        LA RSO reduces upside potential and increases regulatory complexity.
        """
        applies = self.rent_control.get("rso_applies")

        if applies is True:
            return 55  # moderate risk
        if applies is False:
            return 85  # low risk
        return 70  # unknown = medium risk

    def _score_jurisdiction(self) -> float:
        j = self.jurisdiction.get("jurisdiction", "").lower()
        if "la city" in j:
            return 70  # stricter regulations
        if "la county" in j:
            return 80
        return 85  # generally easier regulatory environment

    def _score_underwriting(self) -> float:
        dscr = self.underwriting.get("dscr", 1.0)
        cashflow = self.underwriting.get("annual_cash_flow", 0)

        score = 80

        # DSCR risk
        if dscr < 1.1:
            score -= 25
        elif dscr < 1.20:
            score -= 15
        elif dscr < 1.30:
            score -= 5

        # Cash flow risk
        if cashflow < 0:
            score -= 20

        return max(40, min(95, score))

    def _score_property_age(self) -> float:
        year = self.subject.get("year_built")
        if not year:
            return 75  # neutral

        if year < 1940:
            return 55  # older = more risk
        if 1940 <= year < 1978:
            return 65
        if 1978 <= year < 2000:
            return 75
        return 85  # newer = lower risk

    def _score_property_type(self) -> float:
        t = self.property_type.get("property_type")

        if t in ["commercial", "mixed_use"]:
            return 65
        if t in ["multifamily_5plus"]:
            return 75
        if t in ["duplex", "triplex", "fourplex"]:
            return 80
        if t == "sfr":
            return 85
        return 70  # unknown

    def _score_income_volatility(self) -> float:
        """
        Compares NOI across scenarios to measure volatility.
        """
        scenarios = self.income_scenarios or {}
        market = scenarios.get("market", {})
        downside = scenarios.get("downside", {})

        noi_market = market.get("noi", 0)
        noi_down = downside.get("noi", 0)

        if noi_market == 0:
            return 70

        drop_pct = (noi_market - noi_down) / noi_market

        if drop_pct > 0.20:
            return 60  # very volatile
        if drop_pct > 0.10:
            return 70
        return 80  # stable income

    # -------------------------------------------------------------
    # Final risk score calculation
    # -------------------------------------------------------------

    def calculate(self) -> Dict:
        """
        Combine weighted components into a single score.
        """

        weights = {
            "hazards": 0.15,
            "rent_control": 0.15,
            "jurisdiction": 0.10,
            "underwriting": 0.25,
            "property_age": 0.10,
            "property_type": 0.10,
            "income_volatility": 0.15
        }

        components = {
            "hazards": self._score_hazards(),
            "rent_control": self._score_rent_control(),
            "jurisdiction": self._score_jurisdiction(),
            "underwriting": self._score_underwriting(),
            "property_age": self._score_property_age(),
            "property_type": self._score_property_type(),
            "income_volatility": self._score_income_volatility()
        }

        # Weighted score calculation
        final_score = 0
        for k, v in components.items():
            final_score += v * weights[k]

        # Normalize to 0–100
        final_score = round(final_score, 2)

        # Grade
        if final_score >= 85:
            grade = "A"
        elif final_score >= 75:
            grade = "B"
        elif final_score >= 65:
            grade = "C"
        else:
            grade = "D"

        return {
            "score": final_score,
            "grade": grade,
            "components": components,
            "interpretation": self._interpret_grade(grade)
        }

    def _interpret_grade(self, grade: str) -> str:
        if grade == "A":
            return "Low-risk investment with strong fundamentals."
        if grade == "B":
            return "Moderate risk; acceptable for most investors."
        if grade == "C":
            return "Higher risk; proceed with caution."
        return "Very high risk; deal likely unsuitable unless value-add upside is strong."
