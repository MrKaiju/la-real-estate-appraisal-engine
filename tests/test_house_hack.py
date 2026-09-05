import pytest
from core.house_hack import HouseHackInputs, analyze, monthly_payment


def test_monthly_payment_matches_standard_formula():
    assert round(monthly_payment(1_000_000, 0.06, 30)) == 5996


def test_fha_duplex_basic():
    out = analyze(HouseHackInputs(
        purchase_price=1_100_000, num_units=2, unit_rents=[3_400, 3_400],
        interest_rate=0.065, current_rent_paid=3_200,
    ))
    assert out["loan"]["program"] == "FHA"
    assert out["loan"]["down_payment"] == 38_500
    assert out["loan"]["within_fha_limit"] is True
    assert out["lender_tests"]["self_sufficiency_test_required"] is False
    assert out["monthly"]["net_housing_cost"] > 0
    assert out["verdict"]["label"] in ("MODEST HACK", "EXPENSIVE", "STRONG HACK")


def test_fha_fourplex_self_sufficiency_fail_blocks():
    out = analyze(HouseHackInputs(
        purchase_price=2_200_000, num_units=4, unit_rents=[2_000, 2_000, 2_000, 2_000],
        interest_rate=0.07,
    ))
    assert out["lender_tests"]["self_sufficiency_test_required"] is True
    assert out["lender_tests"]["self_sufficiency_test_pass"] is False
    assert out["verdict"]["label"] == "BLOCKED"


def test_fha_fourplex_strong_rents_pass():
    out = analyze(HouseHackInputs(
        purchase_price=1_200_000, num_units=4, unit_rents=[3_500, 3_500, 3_500, 3_500],
        interest_rate=0.06,
    ))
    assert out["lender_tests"]["self_sufficiency_test_pass"] is True
    assert out["verdict"]["label"] != "BLOCKED"


def test_over_fha_limit_flagged():
    out = analyze(HouseHackInputs(purchase_price=2_700_000, num_units=4,
                                  unit_rents=[4_000] * 4, interest_rate=0.06))
    assert out["loan"]["within_fha_limit"] is False
    assert out["verdict"]["label"] == "BLOCKED"


def test_conventional_program():
    out = analyze(HouseHackInputs(purchase_price=1_000_000, num_units=2, unit_rents=[3_000, 3_000],
                                  loan_program="conventional"))
    assert out["loan"]["down_payment_pct"] == 0.05
    assert out["loan"]["upfront_mip_financed"] == 0


def test_bad_inputs():
    with pytest.raises(ValueError):
        analyze(HouseHackInputs(purchase_price=1, num_units=5, unit_rents=[1] * 5))
    with pytest.raises(ValueError):
        analyze(HouseHackInputs(purchase_price=1, num_units=2, unit_rents=[1]))
