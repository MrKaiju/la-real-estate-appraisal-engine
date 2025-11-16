import numpy as np

class SalesComparison:
    """
    AVM-like valuation using simple statistical methods.
    """

    def __init__(self, subject_sqft: float, comps: list):
        """
        comps = [
            {"price": 950000, "sqft": 1200},
            {"price": 975000, "sqft": 1250},
            ...
        ]
        """
        self.subject_sqft = subject_sqft
        self.comps = comps

    def price_per_sf(self):
        return [c["price"] / c["sqft"] for c in self.comps if c["sqft"] > 0]

    def valuation_range(self):
        ppsf = self.price_per_sf()
        if len(ppsf) == 0:
            return None

        low = np.percentile(ppsf, 20) * self.subject_sqft
        base = np.percentile(ppsf, 50) * self.subject_sqft
        high = np.percentile(ppsf, 80) * self.subject_sqft
        
        return {
            "low_value": round(low, 0),
            "base_value": round(base, 0),
            "high_value": round(high, 0)
        }
