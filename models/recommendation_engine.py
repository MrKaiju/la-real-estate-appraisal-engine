"""
recommendation_engine.py

High-level investment recommendation model.

Inputs (expected from upstream models):
- risk_score: numeric 0–100 (higher = more risk)
- risk_grade: e.g. "A", "B", "C", "D", "F" (optional)
- dscr_summary: from DSCRLoanModel.summary()
- cap_rate_summary: from CapRateModel.summary()
- valuation_summary: dict with:
    - "as_is_value" (float)
    - "stabilized_value" (float)
    - "purchase_price" (float)
- cash_on_cash: estimated cash-on-cash return (optional)
- jurisdiction_flags: dict of key regulatory constraints
    - "is_rent_controlled": bool
    - "jurisdiction": "LA City" / "LA County" / etc.

Outputs:
- decision: "BUY", "WATCH", or "PASS"
- reasoning: list of bullet-point style strings
- diagnostics: structured numeric indicators
"""

from typing import Optional, Dict, List


class RecommendationEngine:
    """
    Example usage:

        engine = RecommendationEngine(
            risk_score=42,
            risk_grade="B",
            dscr_summary=dscr,
            cap_rate_summary=cap,
            valuation_summary={
                "as_is_value": 950_000,
                "stabilized_value": 1_100_000,
                "purchase_price": 900_000,
            },
            cash_on_cash=0.075,
            jurisdiction_flags={
                "is_rent_controlled": True,
                "jurisdiction": "LA City",
            }
        )
        result = engine.recommend()

        -> {
            "decision": "BUY",
            "reasoning": [...],
            "diagnostics": {...}
        }
    """

    def __init__(
        self,
        risk_score: Optional[float],
        risk_grade: Optional[str],
        dscr_summary: Optional[Dict],
        cap_rate_summary: Optional[Dict],
        valuation_summary: Optional[Dict],
        cash_on_cash: Optional[float] = None,
        jurisdiction_flags: Optional[Dict] = None,
    ):
        self.risk_score = risk_score
        self.risk_grade = (risk_grade or "").upper() if risk_grade else None
        self.dscr_summary = dscr_summary or {}
        self.cap_rate_summary = cap_rate_summary or {}
        self.valuation_summary = valuation_summary or {}
        self.cash_on_cash = cash_on_cash
        self.jurisdiction_flags = jurisdiction_flags or {}

    # ----------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------

    def _price_vs_value(self) -> Dict:
        """
        Compares purchase price vs. as-is and stabilized values.
        """
        purchase_price = self.valuation_summary.get("purchase_price")
        as_is_value = self.valuation_summary.get("as_is_value")
        stabilized_value = self.valuation_summary.get("stabilized_value")

        if not purchase_price:
            return {
                "has_data": False,
                "discount_to_as_is_pct": None,
                "discount_to_stabilized_pct": None,
            }

        def pct_diff(val):
            if val is None or val <= 0:
                return None
            return round((val - purchase_price) / val, 4)

        return {
            "has_data": True,
            "discount_to_as_is_pct": pct_diff(as_is_value),
            "discount_to_stabilized_pct": pct_diff(stabilized_value),
        }

    def _dscr_metrics(self) -> Dict:
        """
        Pull core DSCR metrics from DSCRLoanModel.summary()
        """
        return {
            "final_loan_amount": self.dscr_summary.get("final_loan_amount"),
            "dscr_at_final_loan": self.dscr_summary.get("dscr_at_final_loan"),
            "ltv_at_final_loan": self.dscr_summary.get("ltv_at_final_loan"),
        }

    def _cap_metrics(self) -> Dict:
        """
        Pull core cap rate metrics from CapRateModel.summary()
        """
        return {
            "final_cap_rate": self.cap_rate_summary.get("final_cap_rate"),
            "base_cap_rate": self.cap_rate_summary.get("base_cap_rate"),
        }

    def _risk_bucket(self) -> Optional[str]:
        """
        Bucket risk_score into qualitative bands.
        """
        if self.risk_score is None:
            return None

        rs = self.risk_score
        if rs < 25:
            return "very_low"
        if rs < 50:
            return "low"
        if rs < 70:
            return "moderate"
        if rs < 85:
            return "high"
        return "very_high"

    def _is_rent_controlled(self) -> bool:
        return bool(self.jurisdiction_flags.get("is_rent_controlled"))

    def _jurisdiction_label(self) -> Optional[str]:
        return self.jurisdiction_flags.get("jurisdiction")

    # ----------------------------------------------------------
    # Decision logic
    # ----------------------------------------------------------

    def _score_buy_watch_pass(self) -> Dict:
        """
        Internal numeric scoring to arrive at BUY / WATCH / PASS.

        We aggregate four dimensions:

        1) Risk score / grade
        2) DSCR strength
        3) Price vs. value
        4) Yield metrics (cap rate vs. base, cash-on-cash)

        Returns:
            {
                "score_buy": float,
                "score_watch": float,
                "score_pass": float
            }
        """
        score_buy = 0.0
        score_watch = 0.0
        score_pass = 0.0

        # 1) Risk factor
        rb = self._risk_bucket()
        if rb == "very_low":
            score_buy += 2.0
        elif rb == "low":
            score_buy += 1.5
        elif rb == "moderate":
            score_watch += 1.0
        elif rb == "high":
            score_pass += 1.5
        elif rb == "very_high":
            score_pass += 2.5

        # Risk grade overlay if provided
        if self.risk_grade:
            if self.risk_grade in ("A", "B"):
                score_buy += 1.5
            elif self.risk_grade == "C":
                score_watch += 1.0
            elif self.risk_grade in ("D", "F"):
                score_pass += 1.5

        # 2) DSCR
        dscr = self.dscr_summary.get("dscr_at_final_loan")
        ltv = self.dscr_summary.get("ltv_at_final_loan")
        if dscr is not None:
            if dscr >= 1.40:
                score_buy += 1.5
            elif dscr >= 1.20:
                score_buy += 1.0
            elif dscr >= 1.10:
                score_watch += 1.0
            else:
                score_pass += 1.5

        if ltv is not None:
            if ltv <= 0.65:
                score_buy += 0.5
            elif ltv <= 0.75:
                score_watch += 0.5
            else:
                score_pass += 0.5

        # 3) Price vs value
        pv = self._price_vs_value()
        if pv["has_data"]:
            disc_as_is = pv["discount_to_as_is_pct"]
            disc_stab = pv["discount_to_stabilized_pct"]

            # Purchase price below as-is value
            if disc_as_is is not None:
                if disc_as_is >= 0.10:  # >= 10% discount
                    score_buy += 1.5
                elif disc_as_is >= 0.05:
                    score_buy += 1.0
                elif disc_as_is >= 0.0:
                    score_watch += 0.5
                else:
                    # paying above as-is
                    score_pass += 0.5

            # Additional credit for discount to stabilized value
            if disc_stab is not None and disc_stab >= 0.15:
                score_buy += 1.0

        # 4) Yield metrics
        cap = self._cap_metrics()
        final_cap = cap["final_cap_rate"]
        base_cap = cap["base_cap_rate"]
        if final_cap and base_cap:
            # If actual cap > base cap, good; if lower, weaker
            spread = final_cap - base_cap
            if spread >= 0.005:  # +50 bps or more
                score_buy += 1.0
            elif spread >= 0.0:
                score_watch += 0.5
            else:
                score_pass += 0.5

        if self.cash_on_cash is not None:
            coc = self.cash_on_cash
            if coc >= 0.08:
                score_buy += 1.0
            elif coc >= 0.05:
                score_watch += 0.75
            else:
                score_pass += 0.5

        # Rent control pressure: slightly negative bias
        if self._is_rent_controlled():
            score_pass += 0.25
            score_watch += 0.25  # encourages more caution

        return {
            "score_buy": round(score_buy, 3),
            "score_watch": round(score_watch, 3),
            "score_pass": round(score_pass, 3),
        }

    def _decision_from_scores(self, scores: Dict) -> str:
        """
        Returns "BUY", "WATCH", or "PASS" based on scores.
        """
        buy = scores["score_buy"]
        watch = scores["score_watch"]
        pss = scores["score_pass"]

        # Determine which is largest
        if buy >= watch and buy >= pss:
            return "BUY"
        if pss >= buy and pss >= watch:
            return "PASS"
        return "WATCH"

    # ----------------------------------------------------------
    # Reasoning builder
    # ----------------------------------------------------------

    def _build_reasoning(self, decision: str, scores: Dict) -> List[str]:
        reasons: List[str] = []

        # Risk context
        rb = self._risk_bucket()
        if rb:
            reasons.append(f"Overall risk profile is {rb.replace('_', ' ')} (risk_score={self.risk_score}).")
        if self.risk_grade:
            reasons.append(f"Risk grade assessed as {self.risk_grade}.")

        # DSCR / leverage
        dscr = self.dscr_summary.get("dscr_at_final_loan")
        ltv = self.dscr_summary.get("ltv_at_final_loan")
        if dscr is not None and ltv is not None:
            reasons.append(f"Underwritten DSCR is approximately {dscr:.2f} at an LTV of about {ltv*100:.1f}%.")

        # Pricing vs value
        pv = self._price_vs_value()
        if pv["has_data"]:
            disc_as_is = pv["discount_to_as_is_pct"]
            disc_stab = pv["discount_to_stabilized_pct"]
            if disc_as_is is not None:
                if disc_as_is >= 0:
                    reasons.append(
                        f"Purchase price is estimated at a {disc_as_is*100:.1f}% discount to as-is value."
                    )
                else:
                    reasons.append(
                        f"Purchase price is estimated at a {abs(disc_as_is)*100:.1f}% premium to as-is value."
                    )
            if disc_stab is not None:
                reasons.append(
                    f"Relative to stabilized value, purchase price reflects a {disc_stab*100:.1f}% discount."
                )

        # Cap rate context
        cap = self._cap_metrics()
        final_cap = cap["final_cap_rate"]
        base_cap = cap["base_cap_rate"]
        if final_cap and base_cap:
            spread = (final_cap - base_cap) * 100
            reasons.append(
                f"Underwritten cap rate is {final_cap*100:.2f}%, compared to a target/base cap of {base_cap*100:.2f}% (spread {spread:.1f} bps)."
            )

        # Cash-on-cash
        if self.cash_on_cash is not None:
            reasons.append(
                f"Projected cash-on-cash return is approximately {self.cash_on_cash*100:.1f}%."
            )

        # Rent control / jurisdiction
        if self._is_rent_controlled():
            j = self._jurisdiction_label() or "rent-controlled jurisdiction"
            reasons.append(
                f"Property is in {j} with rent control in effect, which may limit upside and increase compliance risk."
            )

        # Decision framing
        if decision == "BUY":
            reasons.append(
                "Aggregate signals (risk, DSCR, pricing, and yield) are favorable relative to typical underwriting thresholds."
            )
        elif decision == "WATCH":
            reasons.append(
                "Signals are mixed; the asset may warrant monitoring or more detailed underwriting before committing."
            )
        else:
            reasons.append(
                "Risk, leverage, pricing, or yield metrics do not meet typical investment thresholds; proceed cautiously or pass."
            )

        return reasons

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def recommend(self) -> Dict:
        """
        Main method returning structured recommendation.
        """
        scores = self._score_buy_watch_pass()
        decision = self._decision_from_scores(scores)
        reasoning = self._build_reasoning(decision, scores)

        return {
            "decision": decision,
            "reasoning": reasoning,
            "diagnostics": scores,
        }
