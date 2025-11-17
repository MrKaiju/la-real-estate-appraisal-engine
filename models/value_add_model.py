"""
value_add_model.py

Models a value-add or BRRRR-style investment by estimating:
- Rehab / CapEx budget
- Stabilized rents and NOI after improvements
- After-Repair Value (ARV) using cap rate or $/SF
- Incremental return on invested capital

Integrates with:
- IncomeApproach (for stabilized NOI)
- SalesComparison or cap rate for ARV
"""

from typing import Optional, Dict
from models.income_approach import IncomeApproach


class ValueAddModel:
    """
    Parameters:
        current_rent_per_unit: existing average rent per unit
        stabilized_rent_per_unit: target rent per unit after improvements
        num_units: number of units
        rehab_budget: total CapEx (construction + soft costs)
        purchase_price: acquisition price
        other_closing_costs: escrow, title, loan fees, etc.
        target_cap_rate: cap rate used to estimate ARV from stabilized NOI
        vacancy_rate: assumed long-term vacancy (default 5%)
        op_ex_ratio: stabilized operating expense ratio (default 35%)
    """

    def __init__(
        self,
        current_rent_per_unit: float,
        stabilized_rent_per_unit: float,
        num_units: int,
        rehab_budget: float,
        purchase_price: float,
        other_closing_costs: float = 0.0,
        target_cap_rate: float = 0.05,
        vacancy_rate: float = 0.05,
        op_ex_ratio: float = 0.35,
    ):
        self.current_rent = current_rent_per_unit
        self.stabilized_rent = stabilized_rent_per_unit
        self.num_units = num_units
        self.rehab_budget = rehab_budget
        self.purchase_price = purchase_price
        self.other_closing_costs = other_closing_costs
        self.target_cap_rate = target_cap_rate
        self.vacancy_rate = vacancy_rate
        self.op_ex_ratio = op_ex_ratio

    # ----------------------------------------------------------
    # Baseline (as-is) performance
    # ----------------------------------------------------------

    def as_is_income(self) -> Dict:
        """
        As-is income profile before value-add.
        """
        inc = IncomeApproach(
            monthly_market_rent=self.current_rent,
            num_units=self.num_units,
            vacancy_rate=self.vacancy_rate,
            operating_expense_ratio=self.op_ex_ratio
        )

        return {
            "rent_per_unit": self.current_rent,
            "gsr": inc.gsr(),
            "noi": inc.noi()
        }

    # ----------------------------------------------------------
    # Stabilized (post-renovation) performance
    # ----------------------------------------------------------

    def stabilized_income(self) -> Dict:
        """
        Income profile after renovations and rent increases.
        """
        inc = IncomeApproach(
            monthly_market_rent=self.stabilized_rent,
            num_units=self.num_units,
            vacancy_rate=self.vacancy_rate,
            operating_expense_ratio=self.op_ex_ratio
        )

        return {
            "rent_per_unit": self.stabilized_rent,
            "gsr": inc.gsr(),
            "noi": inc.noi()
        }

    # ----------------------------------------------------------
    # ARV and equity creation
    # ----------------------------------------------------------

    def arv_from_cap_rate(self) -> Optional[float]:
        """
        Uses stabilized NOI and target cap rate to estimate ARV.
        """
        stabilized = self.stabilized_income()
        noi = stabilized.get("noi", 0)
        if self.target_cap_rate <= 0:
            return None
        return noi / self.target_cap_rate

    def total_project_cost(self) -> float:
        """
        All-in cost to get to stabilized condition (excluding financing costs):
        purchase + rehab + closing
        """
        return self.purchase_price + self.rehab_budget + self.other_closing_costs

    def created_equity(self) -> Optional[float]:
        """
        ARV minus total project cost.
        """
        arv = self.arv_from_cap_rate()
        if arv is None:
            return None
        return arv - self.total_project_cost()

    # ----------------------------------------------------------
    # Value-add return metrics
    # ----------------------------------------------------------

    def value_add_return_on_cost(self) -> Optional[float]:
        """
        Measures profit relative to all-in project cost.
        """
        equity = self.created_equity()
        if equity is None:
            return None
        total_cost = self.total_project_cost()
        if total_cost == 0:
            return None
        return equity / total_cost

    def rent_uplift_per_unit(self) -> float:
        """
        Monthly rent increase per unit after stabilization.
        """
        return self.stabilized_rent - self.current_rent

    def summary(self) -> Dict:
        """
        High-level summary of the value-add play.
        """
        as_is = self.as_is_income()
        stab = self.stabilized_income()
        arv = self.arv_from_cap_rate()
        equity = self.created_equity()
        roc = self.value_add_return_on_cost()

        return {
            "as_is": as_is,
            "stabilized": stab,
            "project": {
                "purchase_price": self.purchase_price,
                "rehab_budget": self.rehab_budget,
                "other_closing_costs": self.other_closing_costs,
                "total_project_cost": self.total_project_cost()
            },
            "arv": arv,
            "created_equity": equity,
            "value_add_return_on_cost": roc,
            "rent_uplift_per_unit": self.rent_uplift_per_unit()
        }
