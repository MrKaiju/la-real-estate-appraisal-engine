"""
data_sources/la_geohub.py

Point-in-polygon lookups against free public GIS layers:

  * LA City zoning (GeoHub)          -> zone string, e.g. "RD1.5-1", plus overlay hints
  * LA County city boundaries        -> jurisdiction: which city, or unincorporated
  * CAL FIRE Fire Hazard Severity    -> very-high / high / moderate, LRA or SRA

Every layer URL is overridable by environment variable because hosted-layer
item IDs change when agencies republish. Defaults are the layers as published
in 2025-2026; verify with a single query before a production deploy.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .arcgis import query_at_point, first
from .http import HttpClient

LA_CITY_ZONING_LAYER = os.getenv(
    "LA_CITY_ZONING_LAYER",
    "https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/Zoning/FeatureServer/0",
)
LA_COUNTY_CITY_BOUNDARIES_LAYER = os.getenv(
    "LA_COUNTY_CITY_BOUNDARIES_LAYER",
    "https://public.gis.lacounty.gov/public/rest/services/LACounty_Dynamic/Political_Boundaries/MapServer/19",
)
CAL_FIRE_FHSZ_LAYER = os.getenv(
    "CAL_FIRE_FHSZ_LAYER",
    "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/FHSZ_SRA_LRA_Combined/FeatureServer/0",
)

LA_CITY_NAMES = {"los angeles", "city of los angeles", "la"}


class LAGeoHub:
    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()

    def zoning(self, lon: float, lat: float) -> Optional[Dict[str, Any]]:
        attrs = query_at_point(self.client, LA_CITY_ZONING_LAYER, lon, lat)
        if not attrs:
            return None
        zone = first(attrs, "ZONE_CMPLT", "ZONE_CLASS", "ZONING", "Zone", "ZONE")
        return {
            "zone": str(zone).strip() if zone else None,
            "zone_class": first(attrs, "ZONE_CLASS", "ZoneClass"),
            "height_district": first(attrs, "HEIGHT_DIST", "HeightDistrict"),
            "specific_plan": first(attrs, "SPECIFIC_PLAN", "SpecificPlan"),
            "source": "LA City GeoHub zoning",
        }

    def jurisdiction(self, lon: float, lat: float) -> Optional[Dict[str, Any]]:
        attrs = query_at_point(self.client, LA_COUNTY_CITY_BOUNDARIES_LAYER, lon, lat)
        if attrs is None:
            return None
        name = first(attrs, "CITY_NAME", "CITY", "NAME", "CityName", "City_Name", "LABEL")
        city_type = first(attrs, "CITY_TYPE", "TYPE", "CityType")
        if not name:
            return {"city": "unincorporated", "is_la_city": False, "is_unincorporated": True,
                    "source": "LA County city boundaries"}
        n = str(name).strip()
        unincorporated = "unincorporated" in n.lower() or (city_type and "unincorporated" in str(city_type).lower())
        return {
            "city": "unincorporated" if unincorporated else n.title(),
            "is_la_city": n.lower() in LA_CITY_NAMES,
            "is_unincorporated": bool(unincorporated),
            "source": "LA County city boundaries",
        }

    def fire_hazard(self, lon: float, lat: float) -> Optional[Dict[str, Any]]:
        attrs = query_at_point(self.client, CAL_FIRE_FHSZ_LAYER, lon, lat)
        if attrs is None:
            # No polygon = not in a mapped hazard zone. Distinguish from a failed call.
            return {"severity": None, "very_high": False, "responsibility_area": None,
                    "source": "CAL FIRE FHSZ"} if self.client.last_error is None else None
        sev = first(attrs, "HAZ_CLASS", "FHSZ", "HAZ_CODE", "SEVERITY", "Haz_Class")
        sev_s = str(sev).lower() if sev is not None else ""
        very_high = "very" in sev_s or sev_s in ("3", "vh", "very high")
        return {
            "severity": str(sev) if sev is not None else None,
            "very_high": very_high,
            "responsibility_area": first(attrs, "SRA", "LRA", "RESP_AREA", "SRA_LRA"),
            "source": "CAL FIRE FHSZ",
        }
