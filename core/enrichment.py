"""
core/enrichment.py

Fill the gaps in a structured subject from public and licensed data, and say
where every value came from.

Precedence, per field:   user input  >  enrichment  >  engine defaults

Order of operations (each step is skippable and never raises):
  1. Parcel record by APN, else by street address   (LA County, free)
  2. Coordinates from the parcel, else geocoder
  3. Jurisdiction, zoning, fire hazard by point     (County / GeoHub / CAL FIRE, free)
  4. Property record, rent estimate, value AVM      (RentCast, licensed, key required)
  5. HUD Small Area FMR by ZIP                      (HUD USER, token required)

Output: the enriched subject dict, a `provenance` map {field: source}, and a
list of `notes` describing what was tried and what was unavailable.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from data_sources.http import HttpClient
from data_sources.la_county_parcels import LACountyParcels
from data_sources.la_geohub import LAGeoHub
from data_sources.rentcast import RentCast
from data_sources.hud_fmr import HUDFairMarketRent
from data_sources.geocoder import Geocoder

ENRICHABLE = ("city", "zip", "beds", "baths", "sqft", "lot_size", "year_built", "property_type",
              "num_units", "zone", "in_very_high_fire_hazard_zone", "lat", "lon", "apn")


class Enricher:
    def __init__(self, client: Optional[HttpClient] = None, rentcast: Optional[RentCast] = None,
                 hud: Optional[HUDFairMarketRent] = None, parcels: Optional[LACountyParcels] = None,
                 geohub: Optional[LAGeoHub] = None, geocoder: Optional[Geocoder] = None,
                 enabled: Optional[bool] = None):
        self.enabled = enabled if enabled is not None else os.getenv("LA_ENGINE_ENRICH", "1") != "0"
        self.client = client or HttpClient()
        self.parcels = parcels or LACountyParcels(self.client)
        self.geohub = geohub or LAGeoHub(self.client)
        self.rentcast = rentcast or RentCast(client=self.client)
        self.hud = hud or HUDFairMarketRent(client=self.client)
        self.geocoder = geocoder or Geocoder(self.client)

    # ------------------------------------------------------------------
    def enrich(self, subject: Dict[str, Any], apn: Optional[str] = None) -> Dict[str, Any]:
        subject = dict(subject)
        provenance: Dict[str, str] = {k: "user" for k, v in subject.items() if v is not None}
        notes: List[str] = []
        extras: Dict[str, Any] = {}

        if not self.enabled:
            return {"subject": subject, "provenance": provenance, "notes": ["enrichment disabled"],
                    "extras": extras}

        def fill(field: str, value: Any, source: str) -> None:
            if value is None or value == "":
                return
            if subject.get(field) is None:
                subject[field] = value
                provenance[field] = source
            elif field in ("year_built", "num_units", "sqft") and subject.get(field) != value:
                extras.setdefault("conflicts", []).append(
                    {"field": field, "user": subject.get(field), "enrichment": value, "source": source})

        address = subject.get("address_full")

        # 1. Parcel -----------------------------------------------------------
        parcel = None
        try:
            if apn or subject.get("apn"):
                parcel = self.parcels.by_apn(apn or subject["apn"])
            if parcel is None and address:
                parcel = self.parcels.by_address(address)
        except Exception as e:  # pragma: no cover - adapters already swallow errors
            notes.append(f"parcel lookup error: {e}")
        if parcel:
            src = "LA County Assessor parcel"
            fill("apn", parcel.apn, src)
            fill("year_built", parcel.year_built, src)
            fill("num_units", parcel.num_units, src)
            fill("beds", parcel.beds, src)
            fill("baths", parcel.baths, src)
            fill("sqft", parcel.building_sqft, src)
            fill("lot_size", parcel.lot_sqft, src)
            fill("property_type", parcel.property_type, src)
            fill("zip", parcel.situs_zip, src)
            fill("lat", parcel.lat, src)
            fill("lon", parcel.lon, src)
            extras["parcel"] = parcel.as_dict()
        else:
            notes.append("parcel: no match" + (f" ({self.client.last_error})" if self.client.last_error else ""))

        # 2. Coordinates --------------------------------------------------------
        if (subject.get("lat") is None or subject.get("lon") is None) and address:
            g = self.geocoder.geocode(address)
            if g:
                fill("lat", g["lat"], g["source"])
                fill("lon", g["lon"], g["source"])
            else:
                notes.append("geocoder: no result")

        lat, lon = subject.get("lat"), subject.get("lon")

        # 3. GIS by point ---------------------------------------------------------
        if lat is not None and lon is not None:
            j = self.geohub.jurisdiction(lon, lat)
            if j:
                fill("city", j["city"], j["source"])
                extras["jurisdiction"] = j
            else:
                notes.append("jurisdiction: unavailable")
            z = self.geohub.zoning(lon, lat)
            if z and z.get("zone"):
                fill("zone", z["zone"], z["source"])
                extras["zoning"] = z
            elif (extras.get("jurisdiction") or {}).get("is_la_city"):
                notes.append("zoning: unavailable")
            f = self.geohub.fire_hazard(lon, lat)
            if f:
                fill("in_very_high_fire_hazard_zone", f["very_high"], f["source"])
                extras["fire_hazard"] = f
            else:
                notes.append("fire hazard: unavailable")
        else:
            notes.append("no coordinates: skipped jurisdiction, zoning and fire-hazard lookups")

        # 4. RentCast ----------------------------------------------------------------
        if self.rentcast.enabled and address:
            rec = self.rentcast.property_record(address)
            if rec:
                src = rec["source"]
                for k in ("beds", "baths", "sqft", "lot_size", "year_built", "num_units", "property_type"):
                    fill(k, rec.get(k), src)
                fill("lat", rec.get("lat"), src)
                fill("lon", rec.get("lon"), src)
                extras["rentcast_record"] = rec
            if subject.get("unit_rents") is None:
                r = self.rentcast.rent_estimate(address, subject.get("property_type"), subject.get("beds"),
                                                subject.get("baths"), subject.get("sqft"))
                if r:
                    units = int(subject.get("num_units") or 1)
                    # RentCast prices the whole property for SFR/condo and per-unit for multi.
                    per_unit = r["rent"] if units == 1 else r["rent"]
                    subject["unit_rents"] = [float(per_unit)] * units
                    provenance["unit_rents"] = r["source"]
                    extras["rent_estimate"] = r
                else:
                    notes.append("rent estimate: unavailable")
            v = self.rentcast.value_estimate(address, subject.get("property_type"), subject.get("beds"),
                                             subject.get("baths"), subject.get("sqft"))
            if v:
                extras["value_estimate"] = v
        elif not self.rentcast.enabled:
            notes.append("rentcast: no API key; rent and value estimates skipped")

        # 5. HUD SAFMR -----------------------------------------------------------------
        if self.hud.enabled and subject.get("zip"):
            fmr = self.hud.by_zip(str(subject["zip"]))
            if fmr:
                extras["hud_safmr"] = fmr
        elif not self.hud.enabled:
            notes.append("hud: no token; SAFMR skipped")

        return {"subject": subject, "provenance": provenance, "notes": notes, "extras": extras}


def sales_comps_from_extras(extras: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Turn RentCast value comps into the engine's sales-comp shape."""
    v = extras.get("value_estimate") or {}
    return [c for c in v.get("comps", []) if c.get("price") and c.get("sqft")]
