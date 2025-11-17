"""
income_scenarios.py

Generates multiple rental scenarios for underwriting:
- Base Scenario (Market Rent)
- Downside Scenario (10–20% decline)
- Voucher Scenario (Section 8) using HUD FMR

Integrates with:
- IncomeApproach model
- Rent estimation utilities
"""

from typing import Optional, Dict
from models.income_approach import IncomeApproach


class IncomeScenarios:
    """
    Parameters:
        market_rent_per_unit: expected rent per unit
        num_units: number of units
        hud_fmr: optional FMR value for voucher scenario
        downside_pct: percentage reduction for downside scenario
        vacancy_rate: default 5%
        op_ex_ratio: default 35%
    """

    def __init__(
        self,
        market_rent_per_unit: float,
        num_units: int,
        hud_fmr: Optional[float] = None,
        downside_pct: float = 0.10,
        vacancy_rate: float = 0.05,
        op_ex_ratio: float = 0.35
    ):
        self.market_rent = market_rent_per_unit
        self.num_units = num_units
        self.hud_fmr = hud_fmr
        self.downside_pct = downside_pct
        self.vacancy_rate = vacancy_rate
        self.op_ex_ratio = op_ex_ratio

    # ------------------------------------------------------
    # Market Scenario
    # ------------------------------------------------------

    def scenario_market(self) -> Dict:
        income = IncomeApproach(
            monthly_market_rent=self.market_rent,
            num_units=self.num_units,
            vacancy_rate=self.vacancy_rate,
            operating_expense_ratio=self.op_ex_ratio
        )
        return {
            "scenario": "market",
            "rent_per_unit": self.market_rent,
            "gsr": income.gsr(),
            "noi": income.noi()
        }

    # ------------------------------------------------------
    # Downside Scenario
    # ------------------------------------------------------

    def scenario_downside(self) -> Dict:
        adjusted_rent = self.market_rent * (1 - self.downside_pct)

        income = IncomeApproach(
            monthly_market_rent=adjusted_rent,
            num_units=self.num_units,
            vacancy_rate=self.vacancy_rate,
            operating_expense_ratio=self.op_ex_ratio
        )
        return {
            "scenario": "downside",
            "rent_per_unit": round(adjusted_rent, 2),
            "gsr": income.gsr(),
            "noi": income.noi()
        }

    # ------------------------------------------------------
    # Voucher Scenario (Section 8)
    # ------------------------------------------------------

    def scenario_voucher(self) -> Optional[Dict]:
        if self.hud_fmr is None:
            return None

        income = IncomeApproach(
            monthly_market_rent=self.hud_fmr,
            num_units=self.num_units,
            vacancy_rate=self.vacancy_rate,
            operating_expense_ratio=self.op_ex_ratio
        )
        return {
            "scenario": "voucher",
            "rent_per_unit": self.hud_fmr,
            "gsr": income.gsr(),
            "noi": income.noi()
        }

    # ------------------------------------------------------
    # Combined Output
    # ------------------------------------------------------

    def all_scenarios(self) -> Dict:
        data = {
            "market": self.scenario_market(),
            "downside": self.scenario_downside()
        }

        voucher = self.scenario_voucher()
        if voucher:
            data["voucher"] = voucher

        return data
