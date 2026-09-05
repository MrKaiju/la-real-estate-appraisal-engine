"""End-to-end: the engine must complete from structured input with no network."""
from engine.appraiser_engine import AppraiserEngine

FOURPLEX = {
    "subject": {
        "address_full": "1234 W 41st Pl, Los Angeles, CA 90037",
        "city": "Los Angeles", "price": 1_450_000, "beds": 8, "baths": 4, "sqft": 3_600,
        "lot_size": 6_500, "year_built": 1962, "property_type": "2-4", "num_units": 4,
        "zone": "RD1.5-1", "stories": 2, "wood_frame": True, "tuck_under_parking": True,
        "unit_rents": [2_400, 2_400, 2_400, 2_400], "current_rents": [1_650, 1_700, 2_300, 2_400],
    },
    "financing": {"interest_rate": 0.0725, "min_dscr": 1.20, "max_ltv": 0.75},
    "jurisdiction": {"submarket_class": "transitional", "risk_score": 55},
    "sales_comps": [
        {"price": 1_380_000, "sqft": 3_400, "num_units": 4, "distance_miles": 0.4, "property_type": "2-4"},
        {"price": 1_520_000, "sqft": 3_900, "num_units": 4, "distance_miles": 0.7, "property_type": "2-4"},
        {"price": 1_295_000, "sqft": 3_300, "num_units": 4, "distance_miles": 1.1, "property_type": "2-4"},
    ],
    "house_hack": {"loan_program": "fha", "interest_rate": 0.065, "current_rent_paid": 2_600},
    "report_options": {"generate_html": True},
}


def test_fourplex_runs_end_to_end():
    out = AppraiserEngine().run_full_appraisal(FOURPLEX)
    assert out["success"] is True, out
    assert out["regulatory"]["summary"]["regime"] == "LA_CITY_RSO"
    assert out["income"]["noi"] > 0
    assert out["income"]["operating_expenses"]["property_tax"] == 1_450_000 * 0.0125
    assert out["income"]["noi_stabilized"] > out["income"]["noi"]
    assert out["financing"]["meets_min_dscr"] in (True, False)
    assert out["valuation"]["as_is_value"] > 0
    assert out["sales_comparison"]["success"] is True
    assert out["recommendation"]["final_recommendation"] in ("BUY", "WATCH", "PASS")
    assert out["recommendation"]["components"]["dscr_score"] is not None
    assert out["house_hack"]["verdict"]["label"]
    assert "RSO" in out["narrative"]["full_text"]
    assert "<html" in out["report_outputs"]["html"]
    assert "Prop 13" in out["report_outputs"]["html"]


def test_sfr_condo_path_without_rents_degrades_gracefully():
    out = AppraiserEngine().run_full_appraisal({
        "subject": {"address_full": "1 Main St, Glendale, CA", "city": "Glendale", "price": 900_000,
                    "beds": 3, "baths": 2, "sqft": 1_500, "year_built": 2005, "property_type": "sfr"},
    })
    assert out["success"] is True
    assert out["income"]["success"] is False
    assert out["financing"]["meets_min_dscr"] is None
    assert out["recommendation"]["final_recommendation"] == "PASS"
    assert any("rent" in w.lower() for w in out["warnings"])


def test_manual_rent_comps_drive_income():
    out = AppraiserEngine().run_full_appraisal({
        "subject": {"address_full": "2 Elm St, Los Angeles, CA", "city": "Los Angeles", "price": 1_100_000,
                    "beds": 4, "baths": 2, "sqft": 1_800, "year_built": 1985, "property_type": "2-4", "num_units": 2},
        "manual_rent_comps": [{"beds": 2, "baths": 1, "sqft": 900, "rent": 2_500},
                              {"beds": 2, "baths": 1, "sqft": 950, "rent": 2_650}],
    })
    assert out["success"] is True
    assert out["rental"]["rent_method"] in ("plus_minus_one_bed", "fallback_overall", "overall_only",
                                            "plus_minus_one_bed_with_rent_per_sqft_adjustment")
    assert out["income"]["success"] is True
    assert out["regulatory"]["summary"]["regime"] == "AB1482"


def test_missing_price_is_a_clean_error():
    out = AppraiserEngine().run_full_appraisal({"subject": {"city": "Los Angeles"}})
    assert out["success"] is False and "price" in out["error"]


def test_unsupported_url_without_subject_errors():
    out = AppraiserEngine().run_full_appraisal({"primary_url": "https://example.com/x"})
    assert out["success"] is False
