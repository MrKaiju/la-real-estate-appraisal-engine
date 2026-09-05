"""
core/house_hack.py

Owner-occupant "house hack" underwriting for 2-4 unit properties.

This is the consumer wedge. The largest addressable group of first-time LA
property buyers who can actually close in a $975k-median market are people
using FHA (3.5% down) or conventional 5% down on a duplex/triplex/fourplex and
living in one unit. No mainstream tool answers their real question:

    "What will it actually cost me per month to live here, after the other
     units pay rent, and will a lender let me count that rent?"

Rules encoded (FHA Handbook 4000.1, 2026 loan limits):
  * 75% of gross market rent on non-owner units counts toward qualifying income.
  * 3-4 unit properties must pass the Self-Sufficiency Test:
        75% * gross rent of ALL units  >=  full PITIA (incl. MIP).
  * Upfront MIP 1.75% financed; annual MIP 0.55% (LTV > 95%, term > 15 yrs, 2023+ cut).
  * 2026 FHA limits for LA County (high-cost ceiling): 1 unit $1,249,125;
    2-4 unit figures derived from HUD's statutory unit multipliers (verify
    against the HUD limit lookup before relying on the 2-4 unit values).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional

FHA_LIMITS_LA_2026 = {1: 1_249_125, 2: 1_599_400, 3: 1_933_175, 4: 2_402_600}
FHA_MIN_DOWN = 0.035
FHA_UPFRONT_MIP = 0.0175
FHA_ANNUAL_MIP = 0.0055
FHA_RENT_CREDIT = 0.75
CONVENTIONAL_MIN_DOWN_2_4 = 0.05   # Fannie Mae 5% down on 2-4 unit owner-occupied (Nov 2023+)


def monthly_payment(principal: float, annual_rate: float, years: int = 30) -> float:
    r = annual_rate / 12.0
    n = years * 12
    if r <= 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


@dataclass
class HouseHackInputs:
    purchase_price: float
    num_units: int
    unit_rents: List[float]          # market rent per unit, len == num_units
    owner_unit_index: int = 0        # which unit the buyer lives in
    interest_rate: float = 0.0675
    loan_program: str = "fha"        # fha | conventional
    down_payment_pct: Optional[float] = None
    property_tax_rate: float = 0.0125
    insurance_annual: Optional[float] = None
    hoa_monthly: float = 0.0
    maintenance_pct_of_rent: float = 0.08
    vacancy_pct: float = 0.05
    utilities_owner_paid_monthly: float = 0.0
    current_rent_paid: Optional[float] = None   # what the buyer pays today, for comparison


def analyze(i: HouseHackInputs) -> Dict[str, Any]:
    if i.num_units < 1 or i.num_units > 4:
        raise ValueError("House-hack analysis covers 1-4 unit properties.")
    if len(i.unit_rents) != i.num_units:
        raise ValueError("unit_rents must have one entry per unit.")

    fha = i.loan_program.lower() == "fha"
    down_pct = i.down_payment_pct or (FHA_MIN_DOWN if fha else CONVENTIONAL_MIN_DOWN_2_4)
    down = i.purchase_price * down_pct
    base_loan = i.purchase_price - down
    ufmip = base_loan * FHA_UPFRONT_MIP if fha else 0.0
    loan = base_loan + ufmip

    pi = monthly_payment(loan, i.interest_rate)
    tax = i.purchase_price * i.property_tax_rate / 12
    ins = (i.insurance_annual or i.purchase_price * 0.004) / 12
    mip = loan * FHA_ANNUAL_MIP / 12 if fha else 0.0
    pmi = base_loan * 0.006 / 12 if (not fha and down_pct < 0.20) else 0.0
    pitia = pi + tax + ins + mip + pmi + i.hoa_monthly

    rents_other = [r for k, r in enumerate(i.unit_rents) if k != i.owner_unit_index]
    gross_other = sum(rents_other)
    gross_all = sum(i.unit_rents)
    owner_unit_market_rent = i.unit_rents[i.owner_unit_index]

    qualifying_rent = gross_other * FHA_RENT_CREDIT
    self_sufficiency_required = i.num_units >= 3
    self_sufficiency_pass = (gross_all * FHA_RENT_CREDIT) >= pitia if self_sufficiency_required else None

    effective_rent_collected = gross_other * (1 - i.vacancy_pct)
    opex = gross_other * i.maintenance_pct_of_rent + i.utilities_owner_paid_monthly
    net_housing_cost = pitia + opex - effective_rent_collected

    # What happens the day the owner moves out and rents their unit too.
    move_out_cash_flow = (gross_all * (1 - i.vacancy_pct)) - (gross_all * i.maintenance_pct_of_rent) \
        - i.utilities_owner_paid_monthly - pitia

    cash_to_close = down + i.purchase_price * 0.02  # ~2% closing costs (LA)
    limit = FHA_LIMITS_LA_2026.get(i.num_units)
    within_limit = loan <= limit if fha else True

    verdict = _verdict(net_housing_cost, owner_unit_market_rent, i.current_rent_paid,
                       self_sufficiency_required, self_sufficiency_pass, within_limit)

    return {
        "loan": {
            "program": "FHA" if fha else "Conventional",
            "down_payment_pct": down_pct,
            "down_payment": round(down),
            "base_loan": round(base_loan),
            "upfront_mip_financed": round(ufmip),
            "total_loan": round(loan),
            "fha_limit_la_2026": limit if fha else None,
            "within_fha_limit": within_limit,
            "cash_to_close_estimate": round(cash_to_close),
        },
        "monthly": {
            "principal_interest": round(pi),
            "property_tax": round(tax),
            "insurance": round(ins),
            "mortgage_insurance": round(mip + pmi),
            "hoa": round(i.hoa_monthly),
            "pitia": round(pitia),
            "gross_rent_other_units": round(gross_other),
            "effective_rent_other_units": round(effective_rent_collected),
            "operating_expenses": round(opex),
            "net_housing_cost": round(net_housing_cost),
            "owner_unit_market_rent": round(owner_unit_market_rent),
            "savings_vs_renting_same_unit": round(owner_unit_market_rent - net_housing_cost),
            "savings_vs_current_rent": (round(i.current_rent_paid - net_housing_cost)
                                        if i.current_rent_paid else None),
            "cash_flow_if_owner_moves_out": round(move_out_cash_flow),
        },
        "lender_tests": {
            "qualifying_rental_income_monthly": round(qualifying_rent),
            "self_sufficiency_test_required": self_sufficiency_required,
            "self_sufficiency_test_pass": self_sufficiency_pass,
            "self_sufficiency_ratio": (round(gross_all * FHA_RENT_CREDIT / pitia, 3)
                                       if self_sufficiency_required else None),
        },
        "verdict": verdict,
    }


def _verdict(net_cost: float, owner_unit_rent: float, current_rent: Optional[float],
             sst_required: bool, sst_pass: Optional[bool], within_limit: bool) -> Dict[str, Any]:
    reasons = []
    if not within_limit:
        reasons.append("Loan exceeds the 2026 FHA limit for this unit count; needs conventional or jumbo.")
    if sst_required and sst_pass is False:
        reasons.append("Fails FHA self-sufficiency test; lender will not approve at this price/rate.")
    if net_cost <= 0:
        label = "LIVE FREE"
        reasons.append("Other units cover the full PITIA and expenses.")
    elif net_cost < owner_unit_rent * 0.6:
        label = "STRONG HACK"
        reasons.append("Net housing cost is under 60% of what the unit would rent for.")
    elif net_cost < owner_unit_rent:
        label = "MODEST HACK"
        reasons.append("Cheaper than renting the same unit, but with landlord duties.")
    else:
        label = "EXPENSIVE"
        reasons.append("Costs more per month than renting the same unit; only makes sense for appreciation.")
    if current_rent and net_cost < current_rent:
        reasons.append(f"Saves about ${current_rent - net_cost:,.0f}/mo versus current rent.")
    blocked = (sst_required and sst_pass is False) or not within_limit
    return {"label": "BLOCKED" if blocked else label, "reasons": reasons}
