"""
Enhanced RecommendationEngine

Includes:
- DSCR analysis
- Cap rate analysis
- Valuation (as-is & stabilized)
- Cash-on-cash return impact
- Jurisdiction risk flags
- Sales comparison valuation logic

Outputs a BUY / WATCH / PASS recommendation.
"""

from typing import Dict, Any, Optional


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
    # SALES COMPARISON SCORE
    # ---------------------------------------------------------
    def _sales_comparison_score(self) -> Dict[str, Any]:

        if not self.sales_comparison or not self.sales_comparison.get("success"):
            return {
                "active": False,
                "score": None,
                "rating": "unknown",
                "details": "No valid sales comps provided."
            }

        median_value = self.sales_comparison.get("comp_value_estimate")
        purchase_price = self.valuation_summary.get("purchase_price")

        if not median_value or not purchase_price:
            return {
                "active": False,
                "score": None,
                "rating": "unknown",
                "details": "Missing purchase price or comp estimate."
            }

        pct_diff = (median_value - purchase_price) / purchase_price

        # Scoring model
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
    # COMBINE ALL SCORES AND GENERATE FINAL RECOMMENDATION
    # ---------------------------------------------------------
    def recommend(self) -> Dict[str, Any]:

        # Sales Comparison
        sales_score_data = self._sales_comparison_score()
        sales_score = sales_score_data.get("score")

        # Cap Rate Score
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

        # DSCR Score
        dscr_ok = self.dscr_summary.get("meets_min_dscr", False)
        dscr_score = 4 if dscr_ok else 1

        # Cash-on-Cash Score
        coc_score = None
        if self.cash_on_cash is not None:
            if self.cash_on_cash >= 0.07:
                coc_score = 4
            elif self.cash_on_cash >= 0.05:
                coc_score = 3
            elif self.cash_on_cash >= 0.03:
                coc_score = 2
            else:
                coc_score = 1

        # Combine all available scores
        all_scores = [s for s in [sales_score, cap_score, dscr_score, coc_score] if s is not None]

        final_score = sum(all_scores) / len(all_scores) if all_scores else 0

        # Final Rating Thresholds
        if final_score >= 4.2:
            final_rating = "BUY"
        elif final_score >= 3.2:
            final_rating = "WATCH"
        else:
            final_rating = "PASS"

        return {
            "final_recommendation": final_rating,
            "final_score": round(final_score, 3),
            "components": {
                "sales_comparison": sales_score_data,
                "cap_rate_score": cap_score,
                "dscr_score": dscr_score,
                "cash_on_cash_score": coc_score,
            },
        }
