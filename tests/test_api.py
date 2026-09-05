from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_appraise_structured():
    r = client.post("/appraise", json={
        "subject": {"address_full": "1234 W 41st Pl, Los Angeles, CA", "city": "Los Angeles", "price": 1450000,
                    "year_built": 1962, "property_type": "2-4", "num_units": 4, "unit_rents": [2400] * 4},
    })
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["recommendation"]["final_recommendation"] in ("BUY", "WATCH", "PASS")


def test_appraise_validation_error():
    r = client.post("/appraise", json={"subject": {"city": "Los Angeles"}})
    assert r.status_code == 422


def test_house_hack_endpoint():
    r = client.post("/house-hack", json={"purchase_price": 1100000, "num_units": 2, "unit_rents": [3400, 3400]})
    assert r.status_code == 200 and r.json()["verdict"]["label"]


def test_regulatory_endpoint():
    r = client.post("/regulatory", json={"city": "Los Angeles", "year_built": 1962, "num_units": 4,
                                         "purchase_price": 1450000, "exit_price": 5600000})
    assert r.status_code == 200
    assert r.json()["summary"]["regime"] == "LA_CITY_RSO"


def test_html_report_endpoint():
    r = client.post("/appraise/report.html", json={
        "subject": {"city": "Los Angeles", "price": 1450000, "year_built": 1962, "property_type": "2-4",
                    "num_units": 4, "unit_rents": [2400] * 4}})
    assert r.status_code == 200 and "<html" in r.text
