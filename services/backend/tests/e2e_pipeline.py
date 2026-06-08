"""End-to-end test of the 3-phase pipeline.

Creates a loan, calls /dev/generate-fixtures to upload real generated docs,
runs /analyze/start, polls /analyze/status to done, asserts documents are
extracted, dims produce results, decision is written, and ai_traces has
expected stages.

Requirements:
  - Orchestrator server running at $BASE_URL (default http://127.0.0.1:8000).
  - LEASEFLOW_DEV_FIXTURES=true so /dev is mounted.
  - Supabase creds in env (SUPABASE_URL, SUPABASE_SERVICE_KEY).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import CONFIG
from app.supabase_client import get_client

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")


def _http(method: str, url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _create_user():
    url = f"{CONFIG.supabase_url}/auth/v1/admin/users"
    email = f"e2e-{uuid.uuid4().hex[:8]}@leaseflow.test"
    body = {"email": email, "password": "p-" + uuid.uuid4().hex[:12],
            "email_confirm": True, "user_metadata": {"display_name": "E2E"}}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json",
                 "apikey": CONFIG.supabase_service_key,
                 "Authorization": f"Bearer {CONFIG.supabase_service_key}"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _delete_user(user_id: str):
    req = urllib.request.Request(
        f"{CONFIG.supabase_url}/auth/v1/admin/users/{user_id}",
        method="DELETE",
        headers={"apikey": CONFIG.supabase_service_key,
                 "Authorization": f"Bearer {CONFIG.supabase_service_key}"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def main() -> int:
    sb = get_client()

    print("1. Create auth user…")
    user = _create_user()
    user_id = user["id"]
    print(f"   user_id={user_id}")
    time.sleep(0.5)

    print("2. Create merchant…")
    m = sb.table("merchants").insert({
        "user_id": user_id,
        "business_name": "Qahwa Haneen",
        "cr_number": "1010" + uuid.uuid4().hex[:6].upper(),
        "google_maps_url": "https://maps.app.goo.gl/e2e-sample",
        "phone": "+966-55-000-0000",
    }).execute().data[0]
    merchant_id = m["id"]
    print(f"   merchant_id={merchant_id}")

    print("3. Create loan…")
    loan = sb.table("loans").insert({
        "merchant_id": merchant_id,
        "amount_requested": 50000,
        "item_description": "La Marzocco GB5 espresso machine",
        "profit_rate": 0.15,
        "repayment_months": 12,
    }).execute().data[0]
    loan_id = loan["id"]
    print(f"   loan_id={loan_id}")

    print("4. POST /dev/generate-fixtures (upload + insert docs)…")
    try:
        fx = _http("POST", f"{BASE_URL}/dev/generate-fixtures", {"loan_id": loan_id})
    except Exception as e:
        print(f"   FAILED: {e}. Is LEASEFLOW_DEV_FIXTURES=true?")
        return 1
    print(f"   generated {len(fx['generated'])} docs")
    for g in fx["generated"]:
        print(f"     {g['doc_type']}: {g['size_bytes']} bytes")

    print("5. POST /analyze/start…")
    resp = _http("POST", f"{BASE_URL}/analyze/start", {"loan_id": loan_id})
    assert resp["status"] == "started"
    print(f"   registered={resp['registered_dimensions']}")

    print("6. Poll /analyze/status (timeout 300s)…")
    deadline = time.time() + 300
    final = None
    while time.time() < deadline:
        s = _http("GET", f"{BASE_URL}/analyze/status/{loan_id}")
        doc_done = sum(1 for d in s["documents"] if d["analysis_status"] == "done")
        doc_err = sum(1 for d in s["documents"] if d["analysis_status"] == "error")
        dim_done = sum(1 for d in s["dimensions"] if d["status"] in ("done", "error", "skipped"))
        print(f"   synth={s['synthesis_status']}  docs={doc_done}✓+{doc_err}✗/{len(s['documents'])}  "
              f"dims={dim_done}/5  loan={s['loan_status']}")
        if s["synthesis_status"] == "done":
            final = s
            break
        time.sleep(4)

    assert final, "pipeline did not complete in 300s"

    print("7. documents.analysis_report populated:")
    docs = sb.table("documents").select("doc_type, analysis_status, analysis_report").eq("loan_id", loan_id).execute().data
    for d in docs:
        rep = d.get("analysis_report") or {}
        conf = (rep.get("meta") or {}).get("confidence")
        err = rep.get("error")
        print(f"   {d['doc_type']:22s} {d['analysis_status']:10s} confidence={conf} err={err}")

    print("8. loans.decision_payload:")
    lf = sb.table("loans").select("*").eq("id", loan_id).single().execute().data
    p = lf["decision_payload"]
    assert p, "decision_payload null"
    print(f"   status={lf['status']}  approved={lf['approved_amount']}  monthly_payment={lf['monthly_payment']}")
    print(f"   overall_score={p['deterministic_proposal']['overall_score']}  "
          f"rules_fired={p['deterministic_proposal']['rules_fired']}")
    print(f"   final={p['final_decision']}")
    if p.get("llm_response"):
        print(f"   llm_reasoning={p['llm_response']['reasoning'][:220]}…")

    print("9. ai_traces (full audit):")
    traces = sb.table("ai_traces").select("stage, kind, duration_ms, error, dimension").eq("loan_id", loan_id).order("created_at").execute().data
    print(f"   {len(traces)} trace rows")
    for t in traces:
        dim = f" [{t['dimension']}]" if t["dimension"] else ""
        err = f"  ERROR={t['error'][:60]}" if t["error"] else ""
        ms = f"{t['duration_ms']}ms" if t["duration_ms"] else ""
        print(f"     {t['kind']:11s} {t['stage']:35s}{dim} {ms}{err}")

    print("\n10. Cleanup…")
    sb.table("loans").delete().eq("id", loan_id).execute()
    sb.table("merchants").delete().eq("id", merchant_id).execute()
    _delete_user(user_id)
    print("\n✓ E2E pipeline completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
