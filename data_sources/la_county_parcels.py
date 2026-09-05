"""
data_sources/la_county_parcels.py

LA County Assessor parcel facts from the public ArcGIS REST layer
(no key; owner name and mailing address are withheld by Gov. Code 7928.205).

Layer (verified June 2026, override with LA_COUNTY_PARCEL_LAYER):
  https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0

Field names on the county layer drift between roll years, so every value is
read through a candidate list and anything missing is simply None.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from .arcgis import query_layer, query_at_point, first, to_int, to_float
from .http import HttpClient

PARCEL_LAYER = os.getenv(
    "LA_COUNTY_PARCEL_LAYER",
    "https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0",
)

# Assessor use-code prefixes (first digit = general use, next digits = subtype).
_USE_CODE_TYPES = {
    "01": "sfr", "02": "2-4", "03": "2-4", "04": "2-4", "05": "5+",
    "06": "commercial", "07": "commercial", "08": "commercial", "09": "commercial",
    "10": "office", "11": "retail", "12": "retail", "13": "retail", "14": "retail",
    "15": "office", "17": "office", "18": "office", "19": "office",
    "20": "industrial", "21": "industrial", "22": "industrial", "23": "industrial",
    "30": "industrial", "31": "industrial", "32": "industrial", "33": "industrial",
}


@dataclass
class ParcelRecord:
    apn: Optional[str] = None
    ain: Optional[str] = None
    situs_address: Optional[str] = None
    situs_city: Optional[str] = None
    situs_zip: Optional[str] = None
    use_code: Optional[str] = None
    use_description: Optional[str] = None
    property_type: Optional[str] = None
    year_built: Optional[int] = None
    num_units: Optional[int] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    building_sqft: Optional[float] = None
    lot_sqft: Optional[float] = None
    assessed_land: Optional[float] = None
    assessed_improvements: Optional[float] = None
    assessed_total: Optional[float] = None
    tax_rate_area: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    source_layer: str = PARCEL_LAYER

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_apn(apn: str) -> Optional[str]:
    digits = re.sub(r"\D", "", apn or "")
    return digits if len(digits) == 10 else None


def _parse(attrs: Dict[str, Any]) -> ParcelRecord:
    use_code = first(attrs, "UseCode", "USECODE", "Use_Code", "UseCode1")
    use_code = str(use_code).zfill(4) if use_code is not None else None
    ptype = _USE_CODE_TYPES.get(use_code[:2]) if use_code else None
    units = to_int(first(attrs, "Units1", "UNITS1", "Units", "NumUnits", "UnitsTotal"))
    if ptype == "2-4" and units and units >= 5:
        ptype = "5+"
    if ptype == "sfr" and units and 2 <= units <= 4:
        ptype = "2-4"
    return ParcelRecord(
        apn=first(attrs, "APN", "Apn", "AssessorID", "AIN_APN"),
        ain=str(first(attrs, "AIN", "Ain")) if first(attrs, "AIN", "Ain") is not None else None,
        situs_address=first(attrs, "SitusFullAddress", "SitusAddress", "SITUS_ADDR", "SitusStreet"),
        situs_city=first(attrs, "SitusCity", "SITUS_CITY", "City"),
        situs_zip=str(first(attrs, "SitusZIP", "SitusZip", "SITUS_ZIP", "ZIP") or "")[:5] or None,
        use_code=use_code,
        use_description=first(attrs, "UseDescription", "UseType", "USETYPE", "Use_Desc"),
        property_type=ptype,
        year_built=to_int(first(attrs, "YearBuilt1", "YEARBUILT1", "YearBuilt", "EffectiveYear1")),
        num_units=units,
        beds=to_int(first(attrs, "Bedrooms1", "BEDROOMS1", "Bedrooms")),
        baths=to_float(first(attrs, "Bathrooms1", "BATHROOMS1", "Bathrooms")),
        building_sqft=to_float(first(attrs, "SQFTmain1", "SQFTMAIN1", "SqftMain", "BuildingSqft")),
        lot_sqft=to_float(first(attrs, "Shape_Area", "LotSqft", "LandSqft", "SQFTLot", "Shape__Area")),
        assessed_land=to_float(first(attrs, "Roll_LandValue", "LandValue", "ROLL_LANDVALUE")),
        assessed_improvements=to_float(first(attrs, "Roll_ImpValue", "ImpValue", "ROLL_IMPVALUE")),
        assessed_total=to_float(first(attrs, "Roll_totLandImp", "TotalValue", "ROLL_TOTLANDIMP")),
        tax_rate_area=first(attrs, "TaxRateArea", "TRA", "TaxRateArea_CITY"),
        lat=to_float(first(attrs, "CENTER_LAT", "LAT", "Latitude", "CenterLat")),
        lon=to_float(first(attrs, "CENTER_LON", "LON", "Longitude", "CenterLon")),
    )


class LACountyParcels:
    def __init__(self, client: Optional[HttpClient] = None, layer_url: str = PARCEL_LAYER):
        self.client = client or HttpClient()
        self.layer = layer_url

    def by_apn(self, apn: str) -> Optional[ParcelRecord]:
        n = normalize_apn(apn)
        if not n:
            return None
        pretty = f"{n[:4]}-{n[4:7]}-{n[7:]}"
        rows = query_layer(self.client, self.layer,
                           where=f"APN='{pretty}' OR APN='{n}' OR AIN='{n}'", max_records=1)
        return _parse(rows[0]) if rows else None

    def by_address(self, street_address: str) -> Optional[ParcelRecord]:
        """Match on the situs street line (number + street), case-insensitive prefix."""
        street = (street_address or "").split(",")[0].strip().upper().replace("'", "")
        if not street:
            return None
        rows = query_layer(self.client, self.layer,
                           where=f"UPPER(SitusFullAddress) LIKE '{street}%'", max_records=1)
        return _parse(rows[0]) if rows else None

    def by_point(self, lon: float, lat: float) -> Optional[ParcelRecord]:
        attrs = query_at_point(self.client, self.layer, lon, lat)
        return _parse(attrs) if attrs else None
