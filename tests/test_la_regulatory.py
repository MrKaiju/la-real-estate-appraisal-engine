from core.la_regulatory import (
    LASubject, rent_regulation, transfer_tax_on_exit, property_tax_after_purchase,
    soft_story_exposure, density_upside, evaluate,
)


def test_pre_1978_la_city_fourplex_is_rso():
    s = LASubject(city="Los Angeles", year_built=1962, num_units=4, property_type="2-4")
    f = rent_regulation(s)
    assert f.applies is True
    assert f.numbers["regime"] == "LA_CITY_RSO"
    assert f.numbers["formula_cap"] == 0.04


def test_post_1978_la_city_building_falls_to_ab1482():
    s = LASubject(city="Los Angeles", year_built=1990, num_units=6, property_type="5+")
    f = rent_regulation(s)
    assert f.numbers["regime"] == "AB1482"
    assert f.numbers["allowable_increase_current"] == 0.087


def test_new_construction_exempt():
    s = LASubject(city="Glendale", year_built=2020, num_units=8, property_type="5+")
    assert rent_regulation(s).numbers["regime"] == "EXEMPT_NEW_CONSTRUCTION"


def test_sfr_individual_owner_exempt():
    s = LASubject(city="Los Angeles", year_built=1950, num_units=1, property_type="sfr")
    assert rent_regulation(s).numbers["regime"] == "EXEMPT_SFR"


def test_pasadena_has_local_rent_control():
    s = LASubject(city="Pasadena", year_built=1970, num_units=3, property_type="2-4")
    assert rent_regulation(s).numbers["regime"] == "LOCAL_RSO"


def test_ula_tiers():
    la = LASubject(city="Los Angeles")
    assert transfer_tax_on_exit(la, 4_000_000).numbers["ula"] == 0
    t1 = transfer_tax_on_exit(la, 6_000_000).numbers
    assert t1["ula_rate"] == 0.04 and t1["ula"] == 240_000
    t2 = transfer_tax_on_exit(la, 11_000_000).numbers
    assert t2["ula_rate"] == 0.055
    # Outside LA City no ULA and no city base tax
    glendale = transfer_tax_on_exit(LASubject(city="Glendale"), 6_000_000).numbers
    assert glendale["ula"] == 0 and glendale["city"] == 0


def test_prop13_reassessment():
    f = property_tax_after_purchase(1_000_000)
    assert f.numbers["annual_tax"] == 12_500


def test_soft_story_flags_pre78_wood_frame_tuck_under():
    s = LASubject(city="Los Angeles", year_built=1965, num_units=8, stories=2,
                  wood_frame=True, tuck_under_parking=True)
    f = soft_story_exposure(s)
    assert f.applies is True
    assert f.numbers["cost_low"] == 80_000


def test_soft_story_not_for_small_or_new():
    assert soft_story_exposure(LASubject(city="Los Angeles", year_built=1965, num_units=3)).applies is False
    assert soft_story_exposure(LASubject(city="Los Angeles", year_built=1985, num_units=10)).applies is False


def test_sb9_split_eligibility():
    big = density_upside(LASubject(zone="R1-1", lot_sqft=6_000))
    assert big.numbers["lot_split_eligible"] is True
    small = density_upside(LASubject(zone="R1-1", lot_sqft=3_000))
    assert small.numbers["lot_split_eligible"] is False
    mf = density_upside(LASubject(zone="R3-1", lot_sqft=6_000))
    assert "ADU" in mf.headline


def test_evaluate_aggregates():
    s = LASubject(city="Los Angeles", year_built=1962, num_units=4, property_type="2-4",
                  zone="RD1.5-1", lot_sqft=6_500, wood_frame=True, tuck_under_parking=True, stories=2)
    out = evaluate(s, purchase_price=1_400_000, exit_price=5_600_000)
    assert out["summary"]["regime"] == "LA_CITY_RSO"
    assert "LA City RSO applies" in out["summary"]["risk_flags"]
    assert any("ULA" in r for r in out["summary"]["risk_flags"])
    assert out["summary"]["underwriting_rent_growth"] == 0.025
