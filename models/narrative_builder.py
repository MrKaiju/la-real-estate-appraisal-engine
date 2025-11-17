"""
NarrativeBuilder

This module converts the appraisal engine’s analytical output into a
professional-grade, human-readable narrative summary.

It synthesizes:
- Income approach results
- Cap rate interpretation
- Sales comparison results
- Market confidence
- DSCR & financeability
- Jurisdiction & regulatory risks

Outputs a structured narrative dictionary and a formatted text block.
"""

from typing import Dict, Any, List, Optional


class NarrativeBuilder:

    def __init__(
        self,
        subject: Dict[str, Any],
        income: Dict[str, Any],
        cap_rate: Dict[str, Any],
        financing: Dict[str, Any],
        valuation: Dict[str, Any],
        sales_comparison: Dict[str, Any],
        market_confidence: Dict[str, Any],
        recommendation: Dict[str, Any],
        jurisdiction: Dict[str, Any]
    ):
        self.subject = subject
        self.income = income
        self.cap_rate = cap_rate
        self.financing = financing
        self.valuation = valuation
        self.sales_comparison = sales_comparison
        self.market_confidence = market_confidence
        self.recommendation = recommendation
        self.jurisdiction = jurisdiction

    # ---------------------------------------------------------
    # 1. Generate Narrative Sections
    # ---------------------------------------------------------

    def _subject_summary(self) -> str:
        listing = self.subject.get("listing_core", {})
        addr = self.subject.get("address_normalized") or self.subject.get("address_raw")

        return (
            f"The subject property located at {addr} is characterized as a "
            f"{listing.get('property_type_raw', 'Unknown type')} consisting of "
            f"{listing.get('beds')} beds and {listing.get('baths')} baths, totaling "
            f"{listing.get('sqft')} square feet. The property is situated on a lot "
            f"measuring {listing.get('lot_size')} square feet and was built in "
            f"{listing.get('year_built')}. The listing indicates an asking price of "
            f"${listing.get('price'):,}."
        )

    def _income_summary(self) -> str:
        noi = self.income.get("noi")
        gpi = self.income.get("gross_potential_income")
        er = self.income.get("expense_ratio")

        return (
            f"The income approach indicates a Gross Potential Income (GPI) of "
            f"${gpi:,} with an operating expense ratio of {round(er * 100, 1)}%, "
            f"resulting in a Net Operating Income (NOI) of approximately ${noi:,}. "
            f"This NOI serves as the foundation for both valuation and loan-sizing "
            f"considerations."
        )

    def _cap_rate_summary(self) -> str:
        cap = self.cap_rate.get("final_cap_rate")
        base = self.cap_rate.get("base_cap_rate")
        adj = self.cap_rate.get("risk_adjustment")

        return (
            f"Market-derived cap rate analysis generated a base cap rate assumption "
            f"of {round(base * 100, 2)}%, with adjustments applied for risk factors "
            f"totaling {round(adj * 100, 2)}%. The final reconciled cap rate used "
            f"for valuation is {round(cap * 100, 2)}%."
        )

    def _valuation_summary(self) -> str:
        purchase = self.valuation.get("purchase_price")
        as_is = self.valuation.get("as_is_value")
        stabilized = self.valuation.get("stabilized_value")

        return (
            f"Based on the final cap rate and the calculated NOI, the income approach "
            f"yields an as-is valuation of ${as_is:,}. The stabilized valuation, "
            f"assuming full market rent realization and operational efficiency, is "
            f"estimated at ${stabilized:,}. Relative to the listing price of "
            f"${purchase:,}, the income-based valuation suggests the property is "
            f"{'above' if as_is < purchase else 'below'} market pricing."
        )

    def _sales_comparison_summary(self) -> str:
        if not self.sales_comparison or not self.sales_comparison.get("success"):
            return (
                "Sales comparison analysis could not be completed due to insufficient "
                "comparable data."
            )

        pct = self.sales_comparison.get("pct_diff")
        median_value = self.sales_comparison.get("median_value")
        rating = self.sales_comparison.get("rating")

        direction = "above" if pct < 0 else "below"
        magnitude = round(abs(pct) * 100, 1)

        return (
            f"The sales comparison approach produced a median value estimate of "
            f"${median_value:,}, which is {magnitude}% {direction} the subject’s "
            f"asking price. Based on comp alignment and market context, the "
            f"sales comparison rating is categorized as '{rating}'."
        )

    def _market_confidence_summary(self) -> str:
        level = self.market_confidence.get("level")
        score = self.market_confidence.get("score")

        return (
            f"Market Confidence Score is rated as '{level}' with a confidence score "
            f"of {score}. This reflects the number of comps, proximity of comps, and "
            f"price-per-square-foot consistency across the comparable set."
        )

    def _financing_summary(self) -> str:
        meets_dscr = self.financing.get("meets_min_dscr")
        ltv_limit = self.financing.get("max_supported_price")
        loan_amt = self.financing.get("max_loan_amount")

        if not meets_dscr:
            return (
                f"DSCR analysis indicates the property does not meet lender thresholds, "
                f"resulting in constrained financing options. Maximum supported loan "
                f"amount is approximately ${loan_amt:,}, implying tighter leverage "
                f"relative to the listing price."
            )

        return (
            f"DSCR evaluation confirms the property meets lender underwriting "
            f"requirements, supporting a maximum loan amount of ${loan_amt:,}. "
            f"Based on NOI and interest assumptions, the property qualifies under "
            f"customary DSCR criteria."
        )

    def _final_recommendation_summary(self) -> str:
        reco = self.recommendation.get("final_recommendation")
        score = self.recommendation.get("final_score")

        return (
            f"The final investment recommendation for the subject property is "
            f"'{reco}', supported by a blended quantitative score of {score}. "
            f"This reflects the combined influence of the income approach, "
            f"sales comparison analysis, market confidence rating, and DSCR results."
        )

    # ---------------------------------------------------------
    # 2. Build Final Narrative
    # ---------------------------------------------------------

    def build_narrative(self) -> Dict[str, str]:
        """
        Returns:
            {
                "full_text": "...",
                "sections": {
                    "subject": "...",
                    "income": "...",
                    "cap_rate": "...",
                    "valuation": "...",
                    "sales_comparison": "...",
                    "market_confidence": "...",
                    "financing": "...",
                    "recommendation": "..."
                }
            }
        """

        subject = self._subject_summary()
        income = self._income_summary()
        cap_rate = self._cap_rate_summary()
        valuation = self._valuation_summary()
        sales = self._sales_comparison_summary()
        confidence = self._market_confidence_summary()
        financing = self._financing_summary()
        rec = self._final_recommendation_summary()

        full = (
            subject + "\n\n" +
            income + "\n\n" +
            cap_rate + "\n\n" +
            valuation + "\n\n" +
            sales + "\n\n" +
            confidence + "\n\n" +
            financing + "\n\n" +
            rec
        )

        return {
            "full_text": full,
            "sections": {
                "subject": subject,
                "income": income,
                "cap_rate": cap_rate,
                "valuation": valuation,
                "sales_comparison": sales,
                "market_confidence": confidence,
                "financing": financing,
                "recommendation": rec,
            },
        }
