"""End-to-end test covering the payments + validation additions.

Asserts:
  - /analyze/start with empty documents returns 422 (required_documents_missing)
  - A full loan pipeline run creates installments on approval
  - Stream webhook marks an installment paid and bumps loans.amount_paid
  - Status endpoint timing field populates
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import CONFIG
from app.supabase_client import get_client

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")


def _http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read().decode() or "null")


def _http_expect_error(method, url, body=None):
    """Like _http but returns (status, body) even on 4xx/5xx."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def _create_user():
    url = f"{CONFIG.supabase_url}/auth/v1/admin/users"
    email = f"pe-{uuid.uuid4().hex[:8]}@leaseflow.test"
    body = {"email": email, "password": "p-" + uuid.uuid4().hex[:12], "email_confirm": True,
            "user_metadata": {"display_name": "PaymentsE2E"}}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json",
                 "apikey": CONFIG.supabase_service_key,
                 "Authorization": f"Bearer {CONFIG.supabase_service_key}"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _delete_user(user_id):
    req = urllib.request.Request(
        f"{CONFIG.supabase_url}/auth/v1/admin/users/{user_id}",
        method="DELETE",
        headers={"apikey": CONFIG.supabase_service_key,
                 "Authorization": f"Bearer {CONFIG.supabase_service_key}"},
    )
    try: urllib.request.urlopen(req, timeout=10)
    except Exception: pass


def main() -> int:
    sb = get_client()

    # ---- Part 1: empty-docs loan should 422 ----
    print("1. Part 1 — empty-docs loan should 422 from /analyze/start")
    user = _create_user()
    user_id = user["id"]
    time.sleep(0.4)
    m = sb.table("merchants").insert({
        "user_id": user_id,
        "business_name": "PaymentsE2E Cafe",
        "cr_number": "1010" + uuid.uuid4().hex[:6].upper(),
        "google_maps_url": "https://maps.app.goo.gl/pe",
        "phone": "+966-55-000-0001",
    }).execute().data[0]
    mid = m["id"]

    empty_loan = sb.table("loans").insert({
        "merchant_id": mid,
        "amount_requested": 50000,
        "item_description": "Empty-docs test",
        "profit_rate": 0.15,
        "repayment_months": 12,
    }).execute().data[0]
    empty_id = empty_loan["id"]

    code, resp = _http_expect_error("POST", f"{BASE_URL}/analyze/start", {"loan_id": empty_id})
    assert code == 422, f"expected 422, got {code}: {resp}"
    detail = (resp or {}).get("detail") or {}
    assert detail.get("error") == "required_documents_missing", f"wrong error: {resp}"
    print(f"   ✓ got 422: missing_all_of={detail.get('missing_all_of')} missing_any_of={detail.get('missing_any_of')}")

    sb.table("loans").delete().eq("id", empty_id).execute()

    # ---- Part 2: full loan → approval → installments ----
    print("\n2. Part 2 — full loan → approval → installments")
    loan = sb.table("loans").insert({
        "merchant_id": mid,
        "amount_requested": 50000,
        "item_description": "La Marzocco GB5 espresso machine",
        "profit_rate": 0.15,
        "repayment_months": 12,
        "repayment_frequency": "monthly",
    }).execute().data[0]
    lid = loan["id"]
    print(f"   loan_id={lid}")

    code, fx = _http("POST", f"{BASE_URL}/dev/generate-fixtures", {"loan_id": lid})
    assert code == 200
    print(f"   generated {len(fx['generated'])} docs")

    code, start = _http("POST", f"{BASE_URL}/analyze/start", {"loan_id": lid})
    assert code == 200 and start["status"] == "started", start
    print(f"   /analyze/start → {start['status']}")

    # Poll until synthesis=done
    deadline = time.time() + 300
    final = None
    while time.time() < deadline:
        code, s = _http("GET", f"{BASE_URL}/analyze/status/{lid}")
        synth = s["synthesis_status"]
        docs_terminal = sum(1 for d in s["documents"] if d["analysis_status"] in ("done", "error"))
        dims_terminal = sum(1 for d in s["dimensions"] if d["status"] in ("done", "error", "skipped"))
        if synth == "done":
            final = s
            break
        time.sleep(4)
    assert final, "pipeline did not complete in 300s"
    print(f"   final synthesis=done loan_status={final['loan_status']} "
          f"timing={final.get('timing', {}).get('submission_to_decision_s')}s")
    assert final.get("timing", {}).get("submission_to_decision_s") is not None

    # Fetch loan + installments
    lf = sb.table("loans").select("*").eq("id", lid).single().execute().data
    installs = sb.table("installments").select("*").eq("loan_id", lid).order("installment_number").execute().data

    if lf["status"] != "approved":
        # LLM picked manual_review — force an approval so we can still
        # exercise installments + webhook paths. This mimics what an admin
        # manual-approve does: set status + approved_amount, then call
        # the schedule installer directly.
        print(f"   ℹ pipeline ended in {lf['status']} — forcing approval to test payments paths")
        sb.table("loans").update({
            "status": "approved",
            "approved_amount": 50000,
            "monthly_payment": round(50000 * 1.15 / 12, 2),
        }).eq("id", lid).execute()
        # Install the schedule now
        import asyncio as _asyncio
        from app.payments import install_schedule_for_loan
        lf = sb.table("loans").select("*").eq("id", lid).single().execute().data
        _asyncio.get_event_loop().run_until_complete(install_schedule_for_loan(lid, lf))
        installs = sb.table("installments").select("*").eq("loan_id", lid).order("installment_number").execute().data

    assert lf["status"] == "approved"
    assert len(installs) == 12, f"expected 12 monthly installments, got {len(installs)}"
    assert all(i["stream_payment_url"] for i in installs), "missing stream URLs"
    total = sum(float(i["amount_sar"]) for i in installs)
    expected_total = float(lf["approved_amount"]) * (1 + float(lf["profit_rate"]))
    assert abs(total - expected_total) < 0.05, f"total mismatch: {total} vs {expected_total}"
    print(f"   ✓ {len(installs)} installments installed, total={total:.2f} SAR matches total_due={expected_total:.2f}")
    print(f"   sample: #1 due {installs[0]['due_date']} for SAR {installs[0]['amount_sar']}")
    print(f"   link: {installs[0]['stream_payment_url']}")

    # ---- Part 3: simulate Stream webhook for installment #1 ----
    if installs:
        print("\n3. Part 3 — simulate Stream webhook marking installment #1 paid")
        link_id = installs[0]["stream_payment_link_id"]
        amt = float(installs[0]["amount_sar"])
        code, resp = _http("POST", f"{BASE_URL}/webhooks/stream", {
            "event": "payment.completed",
            "link_id": link_id,
            "amount_sar": amt,
            "payment_method": "mada",
            "transaction_ref": "test_txn_001",
        })
        assert code == 200 and resp["status"] == "paid", resp
        print(f"   webhook accepted → installment {resp['updated'][:8]} marked paid")

        time.sleep(0.3)
        inst = sb.table("installments").select("*").eq("id", installs[0]["id"]).single().execute().data
        assert inst["status"] == "paid"
        assert inst["paid_amount_sar"] is not None and float(inst["paid_amount_sar"]) == amt
        assert inst["payment_method"] == "mada"
        print(f"   ✓ installments row reflects paid status, amount_paid_sar={inst['paid_amount_sar']}")

        lf2 = sb.table("loans").select("amount_paid").eq("id", lid).single().execute().data
        assert abs(float(lf2["amount_paid"]) - amt) < 0.01, f"amount_paid not bumped: {lf2}"
        print(f"   ✓ loans.amount_paid bumped to {lf2['amount_paid']}")

        # Idempotency / second webhook attempt — should still work (paid status stays)
        code, resp = _http("POST", f"{BASE_URL}/webhooks/stream", {
            "event": "payment.completed", "link_id": link_id, "amount_sar": amt,
            "payment_method": "mada", "transaction_ref": "test_txn_001_retry",
        })
        assert code == 200

    # ---- Cleanup ----
    print("\n4. Cleanup…")
    sb.table("loans").delete().eq("id", lid).execute()
    sb.table("merchants").delete().eq("id", mid).execute()
    _delete_user(user_id)
    print("\n✓ E2E payments test completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
