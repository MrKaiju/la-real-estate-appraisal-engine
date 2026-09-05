import os
import pytest

os.environ.setdefault("LA_ENGINE_ENRICH", "0")
os.environ.setdefault("LA_ENGINE_CACHE_DIR", "/tmp/la-engine-test-cache")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Belt and braces: any accidental real HTTP call in tests fails loudly."""
    import requests

    def _blocked(*a, **k):
        raise RuntimeError("network access attempted in tests")

    monkeypatch.setattr(requests.Session, "request", _blocked)
