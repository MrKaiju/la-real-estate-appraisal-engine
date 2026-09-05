"""
models/income_approach.py

Income approach with an explicit LA operating-expense stack.

Why explicit line items instead of a flat 35% expense ratio:
  * Prop 13 resets property tax to purchase price at close. On a $2M fourplex
    that is ~$25k/yr, often 15-20% of EGI by itself and invisible to a ratio
    copied from the seller's pro forma.
  * Insurance in LA has re-priced 20-40% since 2023 and 2-3x in fire zones.
  * RSO buildings carry registration/SCEP fees and lower rent growth.
  * Replacement reserves are required by every DSCR lender.

The class accepts the keyword interface used by AppraiserEngine and also the
legacy positional interface (monthly_market_rent, num_units, ...) so that
IncomeScenarios keeps working.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List


class IncomeApproach:
    def __init__(
        self,
        monthly_market_rent: Optional[float] = None,
        num_units: int = 1,
        vacancy_rate: float = 0.05,
        operating_expense_ratio: Optional[float] = None,
        *,
        market_rent: Optional[float] = None,
        unit_rents: Optional[List[float]] = None,
        purchase_price: Optional[float] = None,
        property_tax_rate: float = 0.0125,
        insurance_rate_of_value: float = 0.004,
        management_pct: float = 0.06,
        maintenance_per_unit_annual: float = 1_200.0,
        reserves_per_unit_annual: float = 350.0,
        utilities_owner_paid_annual: float = 0.0,
        other_fixed_annual: float = 0.0,
        rso_fees_per_unit_annual: float = 0.0,
        stabilized_rent_uplift: float = 0.0,
        beds: Optional[int] = None,
        baths: Optional[float] = None,
        sqft: Optional[float] = None,
        rent_detail: Optional[Dict[str, Any]] = None,
    ):
        self.units = max(1, int(num_units or 1))
        rent = market_rent if market_rent is not None else monthly_market_rent
        if unit_rents:
            self.unit_rents = [float(r) for r in unit_rents]
            self.units = len(self.unit_rents)
        elif rent is not None:
            self.unit_rents = [float(rent)] * self.units
        else:
            self.unit_rents = []
        self.rent = (sum(self.unit_rents) / len(self.unit_rents)) if self.unit_rents else None
        self.vacancy_rate = vacancy_rate
        self.op_ex_ratio = operating_expense_ratio
        self.purchase_price = purchase_price
        self.property_tax_rate = property_tax_rate
        self.insurance_rate_of_value = insurance_rate_of_value
        self.management_pct = management_pct
        self.maintenance_per_unit = maintenance_per_unit_annual
        self.reserves_per_unit = reserves_per_unit_annual
        self.utilities_owner_paid = utilities_owner_paid_annual
        self.other_fixed = other_fixed_annual
        self.rso_fees_per_unit = rso_fees_per_unit_annual
        self.stabilized_rent_uplift = stabilized_rent_uplift
        self.beds, self.baths, self.sqft = beds, baths, sqft
        self.rent_detail = rent_detail or {}

    # ---- legacy method names (kept for IncomeScenarios) ----
    def gsr(self) -> float:
        return sum(self.unit_rents) * 12.0

    def vacancy_loss(self) -> float:
        return self.gsr() * self.vacancy_rate

    def effective_gross_income(self) -> float:
        return self.gsr() - self.vacancy_loss()

    def operating_expenses(self) -> float:
        return sum(self.expense_breakdown().values())

    def noi(self) -> float:
        return self.effective_gross_income() - self.operating_expenses()

    def cap_rate_value(self, cap_rate: float) -> Optional[float]:
        return None if not cap_rate else self.noi() / cap_rate

    # ---- explicit expense stack ----
    def expense_breakdown(self) -> Dict[str, float]:
        egi = self.effective_gross_income()
        if self.op_ex_ratio is not None and self.purchase_price is None:
            return {"ratio_based_opex": egi * self.op_ex_ratio}
        price = self.purchase_price or 0.0
        return {
            "property_tax": price * self.property_tax_rate,
            "insurance": price * self.insurance_rate_of_value,
            "management": egi * self.management_pct,
            "maintenance": self.maintenance_per_unit * self.units,
            "reserves": self.reserves_per_unit * self.units,
            "utilities_owner_paid": self.utilities_owner_paid,
            "rso_and_city_fees": self.rso_fees_per_unit * self.units,
            "other_fixed": self.other_fixed,
        }

    def summary(self) -> Dict[str, Any]:
        if not self.unit_rents:
            return {
                "success": False,
                "error": "No market rent available; supply rent comps or a rent estimate.",
                "noi": None, "noi_stabilized": None, "cash_on_cash": None,
            }
        gpi = self.gsr()
        egi = self.effective_gross_income()
        opex = self.expense_breakdown()
        opex_total = sum(opex.values())
        noi = egi - opex_total
        # Stabilized: rents to market (uplift) with the same expense stack except management scaling.
        stab_gpi = gpi * (1 + self.stabilized_rent_uplift)
        stab_egi = stab_gpi * (1 - self.vacancy_rate)
        stab_opex = opex_total + (stab_egi - egi) * self.management_pct
        noi_stab = stab_egi - stab_opex
        going_in_cap = (noi / self.purchase_price) if self.purchase_price else None
        return {
            "success": True,
            "units": self.units,
            "unit_rents_monthly": self.unit_rents,
            "market_rent_monthly_avg": round(self.rent, 2) if self.rent else None,
            "gross_potential_income": round(gpi, 2),
            "gross_scheduled_rent_annual": round(gpi, 2),
            "vacancy_rate": self.vacancy_rate,
            "vacancy_loss": round(self.vacancy_loss(), 2),
            "effective_gross_income": round(egi, 2),
            "effective_gross_income_annual": round(egi, 2),
            "operating_expenses": {k: round(v, 2) for k, v in opex.items()},
            "operating_expenses_annual": round(opex_total, 2),
            "expense_ratio": round(opex_total / egi, 4) if egi else None,
            "noi": round(noi, 2),
            "noi_stabilized": round(noi_stab, 2),
            "stabilized_rent_uplift": self.stabilized_rent_uplift,
            "going_in_cap_rate": round(going_in_cap, 4) if going_in_cap is not None else None,
            "grm": round(self.purchase_price / gpi, 2) if (self.purchase_price and gpi) else None,
            "cash_on_cash": None,   # filled by the engine once debt service is known
            "rent_detail": self.rent_detail,
        }
