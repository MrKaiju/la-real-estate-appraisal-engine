"""
property_tax_estimator.py

Property tax estimator for California (Prop 13 style).
Defaults:
- Base levy: 1.00% of assessed value
- Local add-ons: 0.10%–0.25% typical in LA County
"""

from typing import Optional


class PropertyTaxEstimator:
    def __init__(self, base_rate: float = 0.01, local_add_on_rate: float = 0.0025):
        self.base_rate = base_rate
        self.local_add_on_rate = local_add_on_rate

    def estimate_annual_tax(self, purchase_price: float, custom_rate: Optional[float] = None) -> float:
        """
        Estimate annual property tax.
        If custom_rate is provided, it overrides base + local add.
        """
        if custom_rate is not None:
            rate = custom_rate
        else:
            rate = self.base_rate + self.local_add_on_rate
        return purchase_price * rate

    def estimate_monthly_tax(self, purchase_price: float, custom_rate: Optional[float] = None) -> float:
        return self.estimate_annual_tax(purchase_price, custom_rate) / 12
