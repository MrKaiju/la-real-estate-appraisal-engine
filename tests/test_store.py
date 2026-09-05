import os
from fastapi.testclient import TestClient

from api.store import DealStore, make_engine
from api import main as api_main

SUBJECT = {"subject": {"address_full": "1234 W 41st Pl, Los Angeles, CA", "city": "Los Angeles", "price": 1450000,
                       "year_built": 1962, "property_type": "2-4", "num_units": 4, "unit_rents": [2400] * 4}}


def test_store_roundtrip(tmp_path):
    store = DealStore(make_engine(f"sqlite:///{tmp_path}/deals.sqlite3"))
    from engine.appraiser_engine import AppraiserEngine
    result = AppraiserEngine().run_full_appraisal({**SUBJECT, "enrich": False})
    deal_id = store.save(SUBJECT, result, owner="d@example.com")
    got = store.get(deal_id)
    assert got["recommendation"] in ("BUY", "WATCH", "PASS") and got["regime"] == "LA_CITY_RSO"
    assert got["result"]["income"]["noi"] > 0
    assert store.list(owner="d@example.com")[0]["id"] == deal_id
    assert store.list(owner="nobody") == []
    assert store.get("missing") is None


def test_deals_endpoints_with_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    api_main._store = DealStore(make_engine(f"sqlite:///{tmp_path}/api.sqlite3"))
    client = TestClient(api_main.app)
    assert client.post("/deals", json={**SUBJECT, "enrich": False}).status_code == 401
    r = client.post("/deals", json={**SUBJECT, "enrich": False}, headers={"X-Api-Key": "secret"})
    assert r.status_code == 201, r.text
    deal_id = r.json()["id"]
    assert client.get(f"/deals/{deal_id}", headers={"X-Api-Key": "secret"}).json()["id"] == deal_id
    assert len(client.get("/deals", headers={"X-Api-Key": "secret"}).json()) == 1
    assert client.get("/deals/nope", headers={"X-Api-Key": "secret"}).status_code == 404
    api_main._store = None
