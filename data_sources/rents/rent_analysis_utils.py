"""
rent_analysis_utils.py

Hybrid rent estimation using HUD FMR + rental comps.
"""

from typing import Optional, List, Dict


def estimate_market_rent_from_fmr(
    fmr: Optional[float], 
    uplift_factor: float = 1.05
) -> Optional[float]:
    """
    Apply a simple upward adjustment to FMR to simulate real LA market rents.
    """
    if fmr is None:
        return None
    return round(fmr * uplift_factor, 2)


def blend_with_rental_comps(
    fmr_estimate: Optional[float],
    rental_comps: Optional[List[Dict]] = None
) -> Optional[float]:
    """
    Blend FMR-based estimate with user-provided rental comps.
    Expects rental_comps = [{"rent": 2200}, {"rent": 2400}]
    """
    if rental_comps:
        rents = [c["rent"] for c in rental_comps if c.get("rent")]
        if rents:
            avg = sum(rents) / len(rents)
            if fmr_estimate:
                return round((fmr_estimate * 0.4) + (avg * 0.6), 2)
            return round(avg, 2)

    return fmr_estimate
