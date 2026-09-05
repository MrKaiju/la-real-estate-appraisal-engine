"""Adapters and the enrichment layer, exercised against canned responses."""
import json
from types import SimpleNamespace

from data_sources.http import HttpClient
from data_sources.la_county_parcels import LACountyParcels, normalize_apn
from data_sources.la_geohub import LAGeoHub
from data_sources.rentcast import RentCast
from data_sources.hud_fmr import HUDFairMarketRent
from data_sources.geocoder import Geocoder
from core.enrichment import Enricher
from engine.appraiser_engine import AppraiserEngine

PARCEL = {"features": [{"attributes": {
    "APN": "5055-008-012", "AIN": "5055008012", "SitusFullAddress": "1234 W 41ST PL LOS ANGELES CA 90037",
    "SitusZIP": "90037", "UseCode": "0400", "UseDescription": "Four Units (Any Combination)",
    "YearBuilt1": 1962, "Units1": 4, "Bedrooms1": 8, "Bathrooms1": 4, "SQFTmain1": 3600,
    "Shape_Area": 6500.0, "Roll_LandValue": 400000, "Roll_ImpValue": 250000, "Roll_totLandImp": 650000,
    "TaxRateArea": "00067", "CENTER_LAT": 34.0071, "CENTER_LON": -118.2963}}]}
CITY = {"features": [{"attributes": {"CITY_NAME": "Los Angeles", "CITY_TYPE": "City"}}]}
ZONING = {"features": [{"attributes": {"ZONE_CMPLT": "RD1.5-1", "ZONE_CLASS": "RD1.5", "HEIGHT_DIST": "1"}}]}
FIRE_NONE = {"features": []}
RC_PROPERTY = [{"formattedAddress": "1234 W 41st Pl, Los Angeles, CA 90037", "latitude": 34.0071,
                "longitude": -118.2963, "propertyType": "Multi-Family", "bedrooms": 8, "bathrooms": 4,
                "squareFootage": 3600, "lotSize": 6500, "yearBuilt": 1962, "unitCount": 4,
                "propertyTaxes": {"2025": {"total": 8100}}}]
RC_RENT = {"rent": 2450, "rentRangeLow": 2200, "rentRangeHigh": 2700,
           "comparables": [{"formattedAddress": "x", "price": 2400, "bedrooms": 2, "bathrooms": 1,
                            "squareFootage": 900, "distance": 0.3}]}
RC_VALUE = {"price": 1400000, "priceRangeLow": 1300000, "priceRangeHigh": 1500000,
            "comparables": [{"formattedAddress": "a", "price": 1380000, "squareFootage": 3400, "distance": 0.4},
                            {"formattedAddress": "b", "price": 1520000, "squareFootage": 3900, "distance": 0.7},
                            {"formattedAddress": "c", "price": 1295000, "squareFootage": 3300, "distance": 1.1}]}
HUD = {"data": {"year": 2026, "area_name": "Los Angeles-Long Beach-Glendale, CA HUD Metro FMR Area",
                "smallarea_status": "1", "basicdata": {"zip_code": "90037", "Efficiency": 1650,
                "One-Bedroom": 1900, "Two-Bedroom": 2400, "Three-Bedroom": 3100, "Four-Bedroom": 3400}}}


class FakeSession:
    """Routes by URL substring; records calls."""
    def __init__(self, routes, status=200):
        self.routes, self.status, self.calls = routes, status, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        for key, payload in self.routes.items():
            if key in url:
                return SimpleNamespace(status_code=self.status, json=lambda p=payload: p)
        return SimpleNamespace(status_code=404, json=lambda: {})


def client(routes, tmp_path, status=200):
    return HttpClient(session=FakeSession(routes, status), cache_dir=tmp_path / "cache", retries=0)


def test_parcel_by_apn_and_address(tmp_path):
    c = client({"LACounty_Parcel": PARCEL}, tmp_path)
    p = LACountyParcels(c).by_apn("5055-008-012")
    assert p.year_built == 1962 and p.num_units == 4 and p.property_type == "2-4"
    assert p.assessed_total == 650000 and p.situs_zip == "90037"
    assert LACountyParcels(c).by_address("1234 W 41st Pl, Los Angeles").apn == "5055-008-012"
    assert normalize_apn("5055-008-012") == "5055008012" and normalize_apn("12") is None


def test_geohub_lookups(tmp_path):
    c = client({"Political_Boundaries": CITY, "Zoning": ZONING, "FHSZ": FIRE_NONE}, tmp_path)
    g = LAGeoHub(c)
    j = g.jurisdiction(-118.29, 34.0)
    assert j["is_la_city"] is True and j["city"] == "Los Angeles"
    assert g.zoning(-118.29, 34.0)["zone"] == "RD1.5-1"
    f = g.fire_hazard(-118.29, 34.0)
    assert f["very_high"] is False


def test_rentcast_requires_key(tmp_path):
    c = client({"rentcast": RC_PROPERTY}, tmp_path)
    assert RentCast(api_key="", client=c).property_record("x") is None
    rc = RentCast(api_key="k", client=c)
    rec = rc.property_record("1234 W 41st Pl")
    assert rec["num_units"] == 4 and rec["property_type"] == "2-4" and rec["current_annual_tax"] == 8100
    assert c.session.calls[-1][2]["X-Api-Key"] == "k"


def test_hud_by_zip(tmp_path):
    c = client({"huduser": HUD}, tmp_path)
    assert HUDFairMarketRent(token="", client=c).by_zip("90037") is None
    r = HUDFairMarketRent(token="t", client=c).by_zip("90037")
    assert r["fmr"][2] == 2400 and c.session.calls[-1][2]["Authorization"] == "Bearer t"


def test_http_client_caches_and_handles_errors(tmp_path):
    c = client({"ok": {"a": 1}}, tmp_path)
    assert c.get_json("https://x/ok") == {"a": 1}
    assert c.get_json("https://x/ok") == {"a": 1}
    assert len(c.session.calls) == 1            # second hit served from cache
    bad = client({"ok": {"a": 1}}, tmp_path, status=500)
    assert bad.get_json("https://y/ok") is None and "HTTP 500" in bad.last_error
    off = HttpClient(session=FakeSession({}), enabled=False)
    assert off.get_json("https://z") is None


def test_enricher_fills_gaps_and_records_provenance(tmp_path):
    routes = {"LACounty_Parcel": PARCEL, "Political_Boundaries": CITY, "Zoning": ZONING,
              "FHSZ": FIRE_NONE, "rentcast.io/v1/properties": RC_PROPERTY,
              "avm/rent": RC_RENT, "avm/value": RC_VALUE, "huduser": HUD}
    c = client(routes, tmp_path)
    e = Enricher(client=c, rentcast=RentCast(api_key="k", client=c),
                 hud=HUDFairMarketRent(token="t", client=c), enabled=True)
    out = e.enrich({"address_full": "1234 W 41st Pl, Los Angeles, CA 90037", "price": 1450000,
                    "year_built": 1965})
    s, prov = out["subject"], out["provenance"]
    assert s["year_built"] == 1965 and prov["year_built"] == "user"          # user wins
    assert out["extras"]["conflicts"][0]["enrichment"] == 1962                  # but conflict noted
    assert s["num_units"] == 4 and prov["num_units"] == "LA County Assessor parcel"
    assert s["city"] == "Los Angeles" and s["zone"] == "RD1.5-1"
    assert s["in_very_high_fire_hazard_zone"] is False
    assert s["unit_rents"] == [2450.0] * 4 and prov["unit_rents"] == "RentCast rent AVM"
    assert out["extras"]["hud_safmr"]["fmr"][2] == 2400
    assert out["extras"]["value_estimate"]["value"] == 1400000


def test_engine_uses_enrichment_and_survives_outage(tmp_path):
    routes = {"LACounty_Parcel": PARCEL, "Political_Boundaries": CITY, "Zoning": ZONING,
              "FHSZ": FIRE_NONE, "rentcast.io/v1/properties": RC_PROPERTY,
              "avm/rent": RC_RENT, "avm/value": RC_VALUE}
    c = client(routes, tmp_path)
    e = Enricher(client=c, rentcast=RentCast(api_key="k", client=c), hud=HUDFairMarketRent(token="", client=c),
                 enabled=True)
    out = AppraiserEngine(enricher=e).run_full_appraisal({
        "subject": {"address_full": "1234 W 41st Pl, Los Angeles, CA 90037", "price": 1450000}})
    assert out["success"] is True
    assert out["regulatory"]["summary"]["regime"] == "LA_CITY_RSO"
    assert out["subject"]["listing_core"]["num_units"] == 4
    assert out["enrichment"]["provenance"]["zone"] == "LA City GeoHub zoning"
    assert out["sales_comparison"]["success"] is True
    assert out["income"]["success"] is True

    # Everything down: still a clean, explicit result.
    dead = Enricher(client=client({}, tmp_path, status=503), enabled=True)
    out = AppraiserEngine(enricher=dead).run_full_appraisal({
        "subject": {"address_full": "1 Nowhere St, Los Angeles, CA", "price": 900000, "city": "Los Angeles"}})
    assert out["success"] is True
    assert any("parcel: no match" in n for n in out["enrichment"]["notes"])


def test_engine_enrich_false_skips_network():
    out = AppraiserEngine().run_full_appraisal({"enrich": False,
        "subject": {"city": "Los Angeles", "price": 1000000, "year_built": 1970, "num_units": 2,
                    "property_type": "2-4", "unit_rents": [2500, 2500]}})
    assert out["enrichment"]["notes"] == ["enrichment disabled by request"]
