"""
api/store.py

Saved deals. SQLite by default (zero-config local and Fly volume), Postgres
when DATABASE_URL points at one. Schema is deliberately small: the full
engine result is stored as JSON alongside the few columns worth querying.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (Column, DateTime, Float, MetaData, String, Table, Text, create_engine,
                        insert, select, desc)
from sqlalchemy.engine import Engine

metadata = MetaData()

deals = Table(
    "deals", metadata,
    Column("id", String(16), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("owner", String(120), nullable=True),
    Column("address", String(300), nullable=True),
    Column("city", String(120), nullable=True),
    Column("price", Float, nullable=True),
    Column("num_units", Float, nullable=True),
    Column("recommendation", String(16), nullable=True),
    Column("regime", String(32), nullable=True),
    Column("engine_version", String(16), nullable=True),
    Column("rules_as_of", String(16), nullable=True),
    Column("request_json", Text, nullable=False),
    Column("result_json", Text, nullable=False),
)


def make_engine(url: Optional[str] = None) -> Engine:
    url = url or os.getenv("DATABASE_URL", "sqlite:///./data/deals.sqlite3")
    if url.startswith("postgres://"):          # Fly/Heroku style scheme
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("sqlite:///") and not url.endswith(":memory:"):
        os.makedirs(os.path.dirname(url[len("sqlite:///"):]) or ".", exist_ok=True)
    engine = create_engine(url, future=True)
    metadata.create_all(engine)
    return engine


class DealStore:
    def __init__(self, engine: Optional[Engine] = None):
        self.engine = engine or make_engine()

    def save(self, request: Dict[str, Any], result: Dict[str, Any], owner: Optional[str] = None) -> str:
        deal_id = secrets.token_urlsafe(9)[:12]
        subj = (result.get("subject") or {})
        core = subj.get("listing_core") or {}
        row = {
            "id": deal_id,
            "created_at": datetime.now(timezone.utc),
            "owner": owner,
            "address": subj.get("address_raw"),
            "city": subj.get("city"),
            "price": core.get("price"),
            "num_units": core.get("num_units"),
            "recommendation": (result.get("recommendation") or {}).get("final_recommendation"),
            "regime": ((result.get("regulatory") or {}).get("summary") or {}).get("regime"),
            "engine_version": result.get("engine_version"),
            "rules_as_of": (result.get("regulatory") or {}).get("as_of"),
            "request_json": json.dumps(request, default=str),
            "result_json": json.dumps({k: v for k, v in result.items() if k != "report_outputs"}, default=str),
        }
        with self.engine.begin() as conn:
            conn.execute(insert(deals).values(**row))
        return deal_id

    def get(self, deal_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(select(deals).where(deals.c.id == deal_id)).mappings().first()
        if not row:
            return None
        return {**_summary(row), "request": json.loads(row["request_json"]),
                "result": json.loads(row["result_json"])}

    def list(self, owner: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        q = select(deals).order_by(desc(deals.c.created_at)).limit(limit)
        if owner:
            q = q.where(deals.c.owner == owner)
        with self.engine.connect() as conn:
            return [_summary(r) for r in conn.execute(q).mappings()]


def _summary(row) -> Dict[str, Any]:
    return {k: (row[k].isoformat() if k == "created_at" else row[k])
            for k in ("id", "created_at", "owner", "address", "city", "price", "num_units",
                      "recommendation", "regime", "engine_version", "rules_as_of")}
