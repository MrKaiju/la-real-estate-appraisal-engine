"""
value_add_model.py

Value-add underwriting model.

Takes:
- purchase price
- rehab / capex budget
- going-in NOI
- stabilized NOI (after renovations, lease-up, etc.)
- exit cap rate
- hold period

Outputs:
- yield on cost
- going-in cap rate
- stabilized cap rate
- equity creation (value uplift vs total cost)
- simple 5-year hold IRR approximation (optional, rough)
"""

from typing import Optional, Dict


class ValueAddModel:
    """
    Parameters:
        purchase_price: acquisition price
        rehab_budget: total renovation / capex spend
        noi_initial: current or year-1 NOI
        noi_stabilized: NOI after stabilization
        exit_cap_rate: assumed exit cap rate for selling
        hold_years: hold period for simple IRR approximation

    Notes:
        This is a simplified value-add model intended to give
        directional metrics, not a full DCF.
    """

    def __init__(
        self,
        purchase_price: float,
        rehab_budget: float,
        noi_initial: float,
        noi_stabilized: float,
        exit_cap_rate: float,
        hold_years: int = 5,
    ):
        self.purchase_price = float(purchase_price)
        self.rehab_budget = float(rehab_budget)
        self.noi_initial = float(noi_initial)
        self.noi_stabilized = float(noi_stabilized)
        self.exit_cap_rate = float(exit_cap_rate)
        self.hold_years = max(1, int(hold_years))

    # ---------------------------------------------------------
    # Core metrics
    # ---------------------------------------------------------

    @property
    def total_cost(self) -> float:
        return self.purchase_price + self.rehab_budget

    def going_in_cap_rate(self) -> Optional[float]:
        if self.purchase_price <= 0:
            return None
        return self.noi_initial / self.purchase_price

    def stabilized_cap_rate_on_cost(self) -> Optional[float]:
        if self.total_cost <= 0:
            return None
        return self.noi_stabilized / self.total_cost

    def yield_on_cost(self) -> Optional[float]:
        """
        Same as stabilized cap on total cost.
        """
        return self.stabilized_cap_rate_on_cost()

    def exit_value(self) -> Optional[float]:
        """
        Value at sale based on stabilized NOI and exit cap.
        """
        if self.exit_cap_rate <= 0:
            return None
        return self.noi_stabilized / self.exit_cap_rate

    def equity_creation(self) -> Optional[float]:
        """
        Equity created = exit value - total cost.
        """
        ev = self.exit_value()
        if ev is None:
            return None
        return ev - self.total_cost

    def simple_5yr_irr(self) -> Optional[float]:
        """
        Very rough IRR approximation over hold_years, assuming:

        - Initial investment = total_cost
        - Annual cash flow = noi_initial first year, then noi_stabilized
          for remaining years (ignores financing).
        - Final year adds exit_value.

        This is intentionally simplified; replace with a full DCF if needed.
        """
        ev = self.exit_value()
        if ev is None or self.total_cost <= 0:
            return None

        # Simple cash flows
        cf0 = -self.total_cost
        cfs = []

        for year in range(1, self.hold_years + 1):
            if year == 1:
                cf = self.noi_initial
            else:
                cf = self.noi_stabilized
            if year == self.hold_years:
                cf += ev
            cfs.append(cf)

        # Internal IRR approximation via binary search
        low, high = -0.5, 0.5  # -50% to +50% IRR
        for _ in range(60):
            mid = (low + high) / 2.0
            npv = cf0
            for t, cf in enumerate(cfs, start=1):
                npv += cf / ((1 + mid) ** t)
            if npv > 0:
                low = mid
            else:
                high = mid
        irr = (low + high) / 2.0
        return irr

    # ---------------------------------------------------------
    # Public summary
    # ---------------------------------------------------------

    def summary(self) -> Dict:
        gin_cap = self.going_in_cap_rate()
        yoc = self.yield_on_cost()
        exit_val = self.exit_value()
        eq = self.equity_creation()
        irr = self.simple_5yr_irr()

        return {
            "inputs": {
                "purchase_price": self.purchase_price,
                "rehab_budget": self.rehab_budget,
                "noi_initial": self.noi_initial,
                "noi_stabilized": self.noi_stabilized,
                "exit_cap_rate": self.exit_cap_rate,
                "hold_years": self.hold_years,
            },
            "total_cost": round(self.total_cost, 2),
            "going_in_cap_rate": round(gin_cap, 4) if gin_cap is not None else None,
            "yield_on_cost": round(yoc, 4) if yoc is not None else None,
            "exit_value": round(exit_val, 2) if exit_val is not None else None,
            "equity_creation": round(eq, 2) if eq is not None else None,
            "simple_irr": round(irr, 4) if irr is not None else None,
        }
