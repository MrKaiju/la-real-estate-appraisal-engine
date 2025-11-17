"""
Enhanced RecommendationEngine

Includes:
- DSCR analysis
- Cap rate analysis
- Valuation (as-is & stabilized)
- Cash-on-cash return impact
- Jurisdiction risk flags
- Sales comparison valuation logic
- Market Confidence Score (based on comp depth & consistency)

Outputs a BUY / WATCH / PASS recommendation.
"""

from typing import Dict, Any, Optional, List
from statistics import mean


class RecommendationEngine:
    def __init__(
        self,
        risk_score: Optional[float],
        risk_grade: Optional[str],
        dscr_summary: Dict[str, Any],
        cap_rate_summary: Dict[str, Any],
        valuation_summary: Dict[str, Any],
        cash_on_cash: Optional[float],
        jurisdiction_flags: Dict[str, Any],
        sales_comparison: Optional[Dict[str, Any]] = None,
    ):
        self.risk_score = risk_score
        self.risk_grade = risk_grade
        self.dscr_summary = dscr_summary
        self.cap_rate_summary = cap_rate_summary
        self.valuation_summary = valuation_summary
        self.cash_on_cash = cash_on_cash
        self.jurisdiction = jurisdiction_flags
        self.sales_comparison = sales_comparison or {}

    # ---------------------------------------------------------
    # 1) SALES COMPARISON SCORE
    # ---------------------------------------------------------
    def _sales_comparison_score(self) -> Dict[str, Any]:
        """
        Scores the deal based on where the purchase price sits
        relative to sales comp value estimates.
        """

        if not self.sales_comparison or not self.sales_comparison.get("success"):
            return {
                "active": False,
                "score": None,
                "rating": "unknown",
                "details": "No valid sales comps provided."
            }

        value_estimates = self.sales_comparison.get("value_estimates", {}) or {}
        median_value = (
            value_estimates.get("base_value")
            or value_estimates.get("value_by_ppsf_median")
            or value_estimates.get("value_by_ppu_median")
        )

        purchase_price = self.valuation_summary.get("purchase_price")

        if not median_value or not purchase_price:
            return {
                "active": False,
                "score": None,
                "rating": "unknown",
                "details": "Missing purchase price or comp-based value estimate."
            }

        pct_diff = (median_value - purchase_price) / purchase_price

        # Scoring model:
        # +20% above list → STRONG BUY
        # +10% above list → BUY
        # ±5% → NEUTRAL/WATCH
        # −15% → WEAK
        # below −15% → PASS
        if pct_diff >= 0.20:
            rating = "strong_buy"
            score = 5
        elif pct_diff >= 0.10:
            rating = "buy"
            score = 4
        elif pct_diff >= -0.05:
            rating = "neutral"
            score = 3
        elif pct_diff >= -0.15:
            rating = "weak"
            score = 2
        else:
            rating = "pass"
            score = 1

        return {
            "active": True,
            "score": score,
            "rating": rating,
            "pct_diff": round(pct_diff, 4),
            "median_value": median_value,
            "purchase_price": purchase_price,
        }

    # ---------------------------------------------------------
    # 2) MARKET CONFIDENCE SCORE (NEW)
    # ---------------------------------------------------------
    def _market_confidence_score(self) -> Dict[str, Any]:
        """
        Evaluates the *quality* of the sales comp set:
        - number of comps
        - average distance
        - PPSF spread (low vs high vs median)

        Returns:
            {
                "active": bool,
                "score": 1–5,
                "level": "high" | "medium" | "low" | "unknown",
                "details": {...}
            }
        """

        if not self.sales_comparison or not self.sales_comparison.get("success"):
            return {
                "active": False,
                "score": None,
                "level": "unknown",
                "details": {
                    "reason": "No sales comparison results available."
                }
            }

        normalized_comps: List[Dict[str, Any]] = self.sales_comparison.get("normalized_comps") or []
        stats = self.sales_comparison.get("stats") or {}

        comp_count = len(normalized_comps)

        if comp_count == 0:
            return {
                "active": False,
                "score": None,
                "level": "unknown",
                "details": {
                    "reason": "No normalized comps available."
                }
            }

        # --- Base score from comp count ---
        # 0-1: very weak; 2: weak; 3-4: medium; 5-7: strong; 8+: very strong
        if comp_count >= 8:
            base_score = 5.0
        elif comp_count >= 5:
            base_score = 4.0
        elif comp_count >= 3:
            base_score = 3.0
        elif comp_count >= 2:
            base_score = 2.0
        else:
            base_score = 1.0

        # --- Distance component ---
        distances = [
            c.get("distance_miles")
            for c in normalized_comps
            if isinstance(c.get("distance_miles"), (int, float))
        ]
        avg_distance = mean(distances) if distances else None

        distance_adjust = 0.0
        if avg_distance is not None:
            if avg_distance <= 0.25:
                distance_adjust = 0.5
            elif avg_distance <= 0.50:
                distance_adjust = 0.25
            elif avg_distance <= 1.0:
                distance_adjust = 0.0
            elif avg_distance <= 2.0:
                distance_adjust = -0.25
            else:
                distance_adjust = -0.5

        # --- PPSF spread component ---
        median_ppsf = stats.get("median_ppsf")
        low_ppsf = stats.get("low_ppsf")
        high_ppsf = stats.get("high_ppsf")

        spread_adjust = 0.0
        ppsf_spread_pct = None
        if median_ppsf and low_ppsf and high_ppsf and median_ppsf > 0:
            ppsf_spread_pct = (high_ppsf - low_ppsf) / median_ppsf
            # Tighter spread = more confidence
            if ppsf_spread_pct <= 0.15:
                spread_adjust = 0.5
            elif ppsf_spread_pct <= 0.30:
                spread_adjust = 0.0
            else:
                spread_adjust = -0.5

        # Final confidence score
        score = base_score + distance_adjust + spread_adjust
        score = max(1.0, min(5.0, score))

        if score >= 4.25:
            level = "high"
        elif score >= 2.75:
            level = "medium"
        else:
            level = "low"

        return {
            "active": True,
            "score": round(score, 2),
            "level": level,
            "details": {
                "comp_count": comp_count,
                "avg_distance_miles": round(avg_distance, 3) if avg_distance is not None else None,
                "median_ppsf": median_ppsf,
                "low_ppsf": low_ppsf,
                "high_ppsf": high_ppsf,
                "ppsf_spread_pct": round(ppsf_spread_pct, 4) if ppsf_spread_pct is not None else None,
            },
        }

    # ---------------------------------------------------------
    # 3) FINAL RECOMMENDATION (COMBINE ALL SCORES)
    # ---------------------------------------------------------
    def recommend(self) -> Dict[str, Any]:
        """
        Combines:
        - Sales comparison score
        - Cap rate score
        - DSCR score
        - Cash-on-cash score
        - Market confidence (adjusts final score slightly)

        to produce BUY / WATCH / PASS.
        """

        # --- Sales Comparison ---
        sales_score_data = self._sales_comparison_score()
        sales_score = sales_score_data.get("score")

        # --- Cap Rate Score ---
        cap_rate = self.cap_rate_summary.get("final_cap_rate")
        if cap_rate is not None:
            if cap_rate >= 0.06:
                cap_score = 4
            elif cap_rate >= 0.05:
                cap_score = 3
            else:
                cap_score = 2
        else:
            cap_score = None

        # --- DSCR Score ---
        dscr_ok = self.dscr_summary.get("meets_min_dscr", False)
        dscr_score = 4 if dscr_ok else 1

        # --- Cash-on-Cash Score ---
        if self.cash_on_cash is None:
            coc_score = None
        else:
            if self.cash_on_cash >= 0.07:
                coc_score = 4
            elif self.cash_on_cash >= 0.05:
                coc_score = 3
            elif self.cash_on_cash >= 0.03:
                coc_score = 2
            else:
                coc_score = 1

        # --- Aggregate base score (without market confidence) ---
        component_scores = [s for s in [sales_score, cap_score, dscr_score, coc_score] if s is not None]
        base_score = sum(component_scores) / len(component_scores) if component_scores else 0.0

        # --- Market Confidence Adjustment ---
        market_conf = self._market_confidence_score()
        conf_level = market_conf.get("level")
        conf_score = market_conf.get("score")

        # Light adjustment only: this should not dominate the recommendation
        adjustment = 0.0
        if conf_level == "high":
            adjustment = 0.10
        elif conf_level == "low":
            adjustment = -0.20

        final_score = base_score + adjustment

        # --- Final Rating Thresholds (on adjusted score) ---
        if final_score >= 4.2:
            final_rating = "BUY"
        elif final_score >= 3.2:
            final_rating = "WATCH"
        else:
            final_rating = "PASS"

        return {
            "final_recommendation": final_rating,
            "final_score": round(final_score, 3),
            "base_score": round(base_score, 3),
            "components": {
                "sales_comparison": sales_score_data,
                "cap_rate_score": cap_score,
                "dscr_score": dscr_score,
                "cash_on_cash_score": coc_score,
            },
            "market_confidence": market_conf,
            "context": {
                "risk_score": self.risk_score,
                "risk_grade": self.risk_grade,
                "jurisdiction": self.jurisdiction,
            },
        }
