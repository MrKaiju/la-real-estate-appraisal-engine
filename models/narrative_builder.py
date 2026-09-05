"""
models/narrative_builder.py

Turns the engine's numbers into plain-English paragraphs a first-time buyer
can read, and an underwriter can defend. Every formatter is None-safe: a
missing input produces a sentence saying what is missing, never a crash.
"""

from typing import Dict, Any, Optional


def money(v: Optional[float], default: str = "n/a") -> str:
    try:
        return f"${float(v):,.0f}" if v is not None else default
    except (TypeError, ValueError):
        return default


def pct(v: Optional[float], digits: int = 2, default: str = "n/a") -> str:
    try:
        return f"{float(v) * 100:.{digits}f}%" if v is not None else default
    except (TypeError, ValueError):
        return default


def num(v: Any, default: str = "n/a") -> str:
    return default if v is None else (f"{v:,.0f}" if isinstance(v, (int, float)) else str(v))


class NarrativeBuilder:
    def __init__(self, subject, income, cap_rate, financing, valuation, sales_comparison,
                 market_confidence, recommendation, jurisdiction,
                 regulatory: Optional[Dict[str, Any]] = None,
                 house_hack: Optional[Dict[str, Any]] = None):
        self.subject = subject or {}
        self.income = income or {}
        self.cap_rate = cap_rate or {}
        self.financing = financing or {}
        self.valuation = valuation or {}
        self.sales_comparison = sales_comparison or {}
        self.market_confidence = market_confidence or {}
        self.recommendation = recommendation or {}
        self.jurisdiction = jurisdiction or {}
        self.regulatory = regulatory or {}
        self.house_hack = house_hack

    # ------------------------------------------------------------------
    def _subject_summary(self) -> str:
        l = self.subject.get("listing_core", {}) or {}
        addr = self.subject.get("address_raw") or "the subject property"
        ptype = l.get("property_type") or l.get("property_type_raw") or "property"
        units = l.get("num_units")
        return (
            f"{addr} is a {units}-unit {ptype}" if units and units > 1 else f"{addr} is a {ptype}"
        ) + (
            f" with {num(l.get('beds'))} beds and {num(l.get('baths'))} baths, {num(l.get('sqft'))} sq ft "
            f"on a {num(l.get('lot_size'))} sq ft lot, built in {l.get('year_built') or 'n/a'}. "
            f"Asking price is {money(l.get('price'))}."
        )

    def _regulatory_summary(self) -> str:
        s = self.regulatory.get("summary") or {}
        if not s:
            return "Regulatory screen not run."
        risks, opps = s.get("risk_flags") or [], s.get("opportunity_flags") or []
        parts = []
        if risks:
            parts.append("Regulatory risks: " + "; ".join(risks) + ".")
        else:
            parts.append("No major LA regulatory risk flags fired.")
        if opps:
            parts.append("Upside flags: " + "; ".join(opps) + ".")
        parts.append(f"Rent growth is underwritten at {pct(s.get('underwriting_rent_growth'), 1)} per year "
                     f"under the {s.get('regime') or 'unknown'} regime.")
        return " ".join(parts)

    def _income_summary(self) -> str:
        if not self.income.get("success"):
            return "The income approach could not run because no market rent was available."
        opex = self.income.get("operating_expenses") or {}
        tax = opex.get("property_tax")
        return (
            f"At {money(self.income.get('market_rent_monthly_avg'))}/month average rent across "
            f"{self.income.get('units')} unit(s), gross potential income is {money(self.income.get('gross_potential_income'))} "
            f"and effective gross income after {pct(self.income.get('vacancy_rate'), 0)} vacancy is "
            f"{money(self.income.get('effective_gross_income'))}. Operating expenses total "
            f"{money(self.income.get('operating_expenses_annual'))} ({pct(self.income.get('expense_ratio'), 0)} of EGI)"
            + (f", of which Prop 13 property tax at the new purchase price is {money(tax)}" if tax else "")
            + f". Net operating income is {money(self.income.get('noi'))}, a going-in cap rate of "
            f"{pct(self.income.get('going_in_cap_rate'))} and a GRM of {num(self.income.get('grm'))}."
            + (f" Stabilized NOI, once rents reach market, is {money(self.income.get('noi_stabilized'))}."
               if self.income.get("stabilized_rent_uplift") else "")
        )

    def _cap_rate_summary(self) -> str:
        return (
            f"The market cap rate for this asset class and submarket is {pct(self.cap_rate.get('base_cap_rate'))} "
            f"base, adjusted {pct(self.cap_rate.get('risk_adjustment'))} for risk and "
            f"{pct(self.cap_rate.get('rent_control_adjustment'))} for rent control, giving a reconciled "
            f"{pct(self.cap_rate.get('final_cap_rate'))} (calibration {self.cap_rate.get('calibration_as_of', 'n/a')})."
        )

    def _valuation_summary(self) -> str:
        p, a, s = (self.valuation.get(k) for k in ("purchase_price", "as_is_value", "stabilized_value"))
        if a is None:
            return "An income-based value could not be derived."
        rel = "above" if (p and a < p) else "at or below"
        return (
            f"Capitalising NOI at the reconciled rate gives an as-is income value of {money(a)}"
            + (f" and a stabilized value of {money(s)}" if s and s != a else "")
            + f". The asking price of {money(p)} is {rel} the income value "
            f"({pct(self.valuation.get('income_value_gap_pct'), 1)} gap)."
        )

    def _sales_comparison_summary(self) -> str:
        sc = self.sales_comparison
        if not sc or not sc.get("success"):
            return "No sales comparison was run; supply comparable sales to add a second value indicator."
        comp = (self.recommendation.get("components") or {}).get("sales_comparison") or {}
        ve = sc.get("value_estimates") or {}
        base = ve.get("base_value")
        pdiff = comp.get("pct_diff")
        stats = sc.get("stats") or {}
        txt = (f"{len(sc.get('normalized_comps') or [])} comparable sales indicate a value of {money(base)} "
               f"(range {money(ve.get('low_value'))} to {money(ve.get('high_value'))}) at a median "
               f"{money(stats.get('median_ppsf'))}/sq ft.")
        if pdiff is not None:
            txt += (f" That is {abs(pdiff) * 100:.1f}% {'above' if pdiff > 0 else 'below'} asking, "
                    f"rated '{comp.get('rating')}'.")
        return txt

    def _market_confidence_summary(self) -> str:
        mc = self.market_confidence
        if not mc.get("active"):
            return "Market confidence is unknown because no sales comps were supplied."
        d = mc.get("details") or {}
        return (f"Market confidence is {mc.get('level')} ({mc.get('score')}/5) based on {d.get('comp_count')} comps "
                f"averaging {d.get('avg_distance_miles') or 'n/a'} miles away with a "
                f"{pct(d.get('ppsf_spread_pct'), 0)} price-per-foot spread.")

    def _financing_summary(self) -> str:
        f = self.financing
        if f.get("meets_min_dscr") is None:
            return f.get("note") or "Financing was not evaluated."
        i = f.get("inputs") or {}
        base = (f"At {pct(i.get('interest_rate'))} over {i.get('amort_years')} years with a {i.get('min_dscr')}x "
                f"minimum DSCR and {pct(i.get('max_ltv'), 0)} max LTV, the lender-supported loan is "
                f"{money(f.get('final_loan_amount'))} (binding constraint: {f.get('binding_constraint')}), "
                f"requiring {money(f.get('equity_required'))} of equity plus closing costs. ")
        if f.get("meets_min_dscr"):
            base += (f"The property clears DSCR at full leverage ({f.get('dscr_at_max_ltv_loan')}x at max LTV).")
        else:
            base += (f"At full {pct(i.get('max_ltv'), 0)} leverage DSCR would be only {f.get('dscr_at_max_ltv_loan')}x; "
                     f"the price a DSCR lender would fully support is about {money(f.get('max_supported_price'))}, "
                     f"{money(abs(f.get('price_gap_vs_dscr') or 0))} below asking.")
        coc = self.income.get("cash_on_cash")
        if coc is not None:
            base += f" Year-one cash-on-cash at that leverage is {pct(coc, 1)}."
        return base

    def _house_hack_summary(self) -> str:
        hh = self.house_hack
        if not hh:
            return ""
        m, lo, v = hh.get("monthly", {}), hh.get("loan", {}), hh.get("verdict", {})
        txt = (f"House-hack view ({lo.get('program')}, {pct(lo.get('down_payment_pct'), 1)} down, "
               f"{money(lo.get('cash_to_close_estimate'))} to close): total monthly payment is {money(m.get('pitia'))}; "
               f"the other units bring in {money(m.get('effective_rent_other_units'))} after vacancy, leaving a net "
               f"housing cost of {money(m.get('net_housing_cost'))} versus {money(m.get('owner_unit_market_rent'))} "
               f"to rent the same unit. ")
        if hh.get("lender_tests", {}).get("self_sufficiency_test_required"):
            ok = hh["lender_tests"].get("self_sufficiency_test_pass")
            txt += (f"FHA self-sufficiency test: {'PASS' if ok else 'FAIL'} "
                    f"({hh['lender_tests'].get('self_sufficiency_ratio')}x). ")
        txt += f"Verdict: {v.get('label')}. " + " ".join(v.get("reasons") or [])
        return txt

    def _final_recommendation_summary(self) -> str:
        r = self.recommendation
        c = r.get("components") or {}
        return (f"Overall recommendation: {r.get('final_recommendation')} (score {r.get('final_score')} / 5). "
                f"Components: cap-rate spread {c.get('cap_rate_score')}, DSCR {c.get('dscr_score')}, "
                f"cash-on-cash {c.get('cash_on_cash_score')}, sales comps "
                f"{(c.get('sales_comparison') or {}).get('score')}, regulatory adjustment "
                f"{c.get('regulatory_adjustment')}.")

    # ------------------------------------------------------------------
    def build_narrative(self) -> Dict[str, Any]:
        sections = {
            "subject": self._subject_summary(),
            "regulatory": self._regulatory_summary(),
            "income": self._income_summary(),
            "cap_rate": self._cap_rate_summary(),
            "valuation": self._valuation_summary(),
            "sales_comparison": self._sales_comparison_summary(),
            "market_confidence": self._market_confidence_summary(),
            "financing": self._financing_summary(),
            "house_hack": self._house_hack_summary(),
            "recommendation": self._final_recommendation_summary(),
        }
        full = "\n\n".join(v for v in sections.values() if v)
        return {"full_text": full, "sections": sections}
