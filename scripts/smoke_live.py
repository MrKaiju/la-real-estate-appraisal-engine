"""
scripts/smoke_live.py

One-shot live check of every external adapter against a known LA parcel.
Run this from a machine with internet before the first deploy and whenever
an agency republishes a GIS layer:

    python scripts/smoke_live.py "1234 W 41st Pl, Los Angeles, CA 90037"

Prints which sources answered, which fields they filled, and any last_error.
Exit code 1 if the free public layers (parcel, jurisdiction) did not answer.
"""
import json
import sys

from core.enrichment import Enricher

address = sys.argv[1] if len(sys.argv) > 1 else "1234 W 41st Pl, Los Angeles, CA 90037"
e = Enricher(enabled=True)
out = e.enrich({"address_full": address})
print(json.dumps({"provenance": out["provenance"], "notes": out["notes"],
                  "subject": out["subject"]}, indent=2, default=str))
for key in ("parcel", "jurisdiction", "zoning", "fire_hazard", "rentcast_record", "rent_estimate", "hud_safmr"):
    print(f"{key:16s} {'OK' if out['extras'].get(key) else '--'}")
ok = out["extras"].get("parcel") and out["extras"].get("jurisdiction")
sys.exit(0 if ok else 1)
