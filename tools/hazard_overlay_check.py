"""
hazard_overlay_check.py

High-level hazard overlay checker.

This module is structured to eventually connect to:
- FEMA flood maps
- USGS earthquake fault / liquefaction zones
- CAL FIRE Very High Fire Hazard Severity Zones

For now, it returns a clean placeholder structure that your
analysis and reports can depend on without breaking.
"""

from typing import Dict, Optional


class HazardOverlayChecker:
    """
    HazardOverlayChecker takes latitude and longitude and returns
    a summary of key environmental/hazard risk flags.

    In the future, you can plug in real API calls or GIS lookups
    where the placeholder logic currently lives.
    """

    def __init__(self, lat: Optional[float], lng: Optional[float]):
        self.lat = lat
        self.lng = lng

    def check_flood_zone(self) -> Dict:
        """
        Placeholder for FEMA flood zone lookup.
        """
        return {
            "source": "FEMA",
            "zone": "UNKNOWN",        # e.g., X, AE, AO, etc.
            "is_high_risk": None      # True / False when implemented
        }

    def check_earthquake_fault(self) -> Dict:
        """
        Placeholder for USGS earthquake fault/rupture zone.
        """
        return {
            "source": "USGS",
            "within_fault_zone": None  # True / False when implemented
        }

    def check_fire(self) -> Dict:
        """
        Placeholder for CAL FIRE Very High Fire Hazard Severity Zone.
        """
        return {
            "source": "CAL_FIRE",
            "within_high_fire_hazard_area": None  # True / False when implemented
        }

    def summary(self) -> Dict:
        """
        Returns a combined hazard summary.

        Even though the values are placeholders today, the shape
        of this data will not need to change when you later
        connect real hazard APIs.
        """
        flood = self.check_flood_zone()
        fault = self.check_earthquake_fault()
        fire = self.check_fire()

        return {
            "flood": flood,
            "earthquake_fault": fault,
            "fire": fire
        }
