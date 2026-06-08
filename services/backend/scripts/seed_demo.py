#!/usr/bin/env python3
"""Seed 3 golden demo merchants with real decisions.

Creates:
  1. Qahwa Haneen — specialty coffee, strong application → APPROVED
  2. Awful Coffee  — weak credit, SIMAH default → DENIED (hard floor)
  3. Iffy Burger  — mixed signals → MANUAL_REVIEW

For each persona:
  - Creates auth user with deterministic email/password
  - Inserts merchants row with a CR number tuned to the desired SIMAH outcome
  - Inserts loans row with persona-specific amount + item
  - Calls the local generators with persona-specific params (different monthly
    revenue, volatility, bounces etc.) to produce realistic fake PDFs/CSVs
  - Uploads docs to Supabase Storage + inserts documents rows
  - POSTs /analyze/start on the orchestrator
  - Polls /analyze/status until synthesis=done
  - Records the loan_id + final decision

Outputs handoff/DEMO_CREDENTIALS.md with login creds + loan URLs.

Usage:
    BASE_URL=https://leaseflow.api.imdad.website \\
    SEED_PASSWORD='demo123!' \\
    python3 seed_demo.py

BASE_URL defaults to http://127.0.0.1:8000 (when run on the VM).
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import CONFIG
from app.generators import (
    generate_bank_statement,
    generate_financial_statement,
    generate_invoice,
    generate_pos_data,
)
from app.supabase_client import get_client

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
PASSWORD = os.environ.get("SEED_PASSWORD", "demo123!")
BUCKET = CONFIG.storage_bucket

PERSONAS = [
    {
        "key": "qahwa",
        "email": "ghazal.abdulrazzak@gmail.com",
        "business_name": "Qahwa Haneen Specialty Coffee",
        "cr_number": "1010000000",             # SIMAH: credit=787, defaults=0, active=1
        "google_maps_url": "https://maps.app.goo.gl/qahwa-haneen-demo",
        "phone": "+966-55-111-0001",
        "loan": {
            "amount_requested": 50000,
            "item_description": "La Marzocco GB5 espresso machine",
            "profit_rate": 0.15,
            "repayment_months": 12,
            "repayment_frequency": "monthly",
        },
        "gen_params": {
            "bank":     {"months": 6, "monthly_revenue_target_sar": 95000,
                         "volatility": 0.12, "expense_ratio": 0.65, "bounces": 0},
            "fin":      {"annual_revenue_sar": 1_140_000, "gross_margin": 0.55,
                         "opex_ratio": 0.28, "debt_to_equity": 0.50},
            "pos":      {"days": 90, "daily_revenue_target_sar": 3200,
                         "avg_ticket_sar": 42, "void_rate": 0.008,
                         "refund_rate": 0.004, "cash_fraction": 0.12,
                         "weekend_lift": 0.30},
            "invoice":  {"item_description": "La Marzocco GB5 espresso machine",
                         "amount_sar": 50000},
        },
        "expected_outcome": "approved",
    },
    {
        "key": "awful",
        "email": "gzrazak@gmail.com",
        "business_name": "Awful Coffee Corner",
        "cr_number": "1010000085",             # SIMAH: credit=470, defaults=1 → HARD FLOOR
        "google_maps_url": "https://maps.app.goo.gl/awful-coffee-demo",
        "phone": "+966-55-111-0002",
        "loan": {
            "amount_requested": 80000,
            "item_description": "Industrial coffee roaster 20kg capacity",
            "profit_rate": 0.15,
            "repayment_months": 12,
            "repayment_frequency": "monthly",
        },
        "gen_params": {
            "bank":     {"months": 6, "monthly_revenue_target_sar": 22000,
                         "volatility": 0.45, "expense_ratio": 0.95, "bounces": 4,
                         "overdrafts": 2},
            "fin":      {"annual_revenue_sar": 264000, "gross_margin": 0.38,
                         "opex_ratio": 0.45, "debt_to_equity": 2.1},
            "pos":      {"days": 90, "daily_revenue_target_sar": 780,
                         "avg_ticket_sar": 32, "void_rate": 0.035,
                         "refund_rate": 0.022, "cash_fraction": 0.55,
                         "weekend_lift": 0.05},
            "invoice":  {"item_description": "Industrial coffee roaster 20kg",
                         "amount_sar": 80000},
        },
        "expected_outcome": "denied",
    },
    {
        "key": "iffy",
        "email": "a-madoun@hotmail.com",
        "business_name": "Iffy Burger",
        "cr_number": "1010000010",             # SIMAH: credit=639, defaults=0, inq=4
        "google_maps_url": "https://maps.app.goo.gl/iffy-burger-demo",
        "phone": "+966-55-111-0003",
        "loan": {
            "amount_requested": 60000,
            "item_description": "Commercial griddle + hood ventilation system",
            "profit_rate": 0.15,
            "repayment_months": 12,
            "repayment_frequency": "monthly",
        },
        "gen_params": {
            "bank":     {"months": 6, "monthly_revenue_target_sar": 58000,
                         "volatility": 0.28, "expense_ratio": 0.82, "bounces": 1},
            "fin":      {"annual_revenue_sar": 696000, "gross_margin": 0.48,
                         "opex_ratio": 0.36, "debt_to_equity": 1.25},
            "pos":      {"days": 90, "daily_revenue_target_sar": 1900,
                         "avg_ticket_sar": 55, "void_rate": 0.018,
                         "refund_rate": 0.011, "cash_fraction": 0.28,
                         "weekend_lift": 0.22},
            "invoice":  {"item_description": "Commercial griddle + hood",
                         "amount_sar": 60000},
        },
        "expected_outcome": "manual_review",
    },
]


def _http(method: str, path: str, body: dict | None = None, *, base=BASE_URL, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}


def _auth_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "apikey": CONFIG.supabase_service_key,
        "Authorization": f"Bearer {CONFIG.supabase_service_key}",
    }


def _find_user_by_email(email: str) -> str | None:
    """Supabase auth admin /users?email= IGNORES the filter and returns the
    full list. Paginate + filter client-side."""
    per_page = 200
    for page in range(1, 10):
        url = f"{CONFIG.supabase_url}/auth/v1/admin/users?page={page}&per_page={per_page}"
        req = urllib.request.Request(url, headers=_auth_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                users = (json.loads(r.read().decode()).get("users") or [])
        except Exception:
            return None
        for u in users:
            if (u.get("email") or "").lower() == email.lower():
                return u["id"]
        if len(users) < per_page:
            return None
    return None


def ensure_user(email: str, display_name: str) -> str:
    """Create an auth user (or return existing). Returns user_id."""
    existing = _find_user_by_email(email)
    if existing:
        return existing
    url = f"{CONFIG.supabase_url}/auth/v1/admin/users"
    body = json.dumps({
        "email": email, "password": PASSWORD, "email_confirm": True,
        "user_metadata": {"display_name": display_name},
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers=_auth_headers())
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())["id"]


def delete_existing_merchant(sb, email: str) -> None:
    """Nuke any prior demo data for this email (idempotent reseed)."""
    uid = _find_user_by_email(email)
    if not uid:
        return
    rows = sb.table("merchants").select("id").eq("user_id", uid).execute().data or []
    for m in rows:
        sb.table("loans").delete().eq("merchant_id", m["id"]).execute()
        sb.table("merchants").delete().eq("id", m["id"]).execute()
    try:
        req = urllib.request.Request(
            f"{CONFIG.supabase_url}/auth/v1/admin/users/{uid}",
            method="DELETE", headers=_auth_headers(),
        )
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass


def upload_docs(sb, merchant_id: str, loan_id: str, params: dict) -> list[dict]:
    """Generate + upload all 4 doc types for a persona. Returns documents rows."""
    seed = f"demo-{merchant_id}-{loan_id}"
    bn = params.get("business_name", "Demo")

    jobs = [
        ("bank_statement", "bank_statement.pdf", "application/pdf",
         lambda: generate_bank_statement(seed=seed, business_name=bn, **params["bank"])[0]),
        ("financial_statement", "financial_statement.pdf", "application/pdf",
         lambda: generate_financial_statement(seed=seed, business_name=bn, **params["fin"])[0]),
        ("pos_data", "pos_data.csv", "text/csv",
         lambda: generate_pos_data(seed=seed, **params["pos"])[0]),
        ("invoice", "invoice.pdf", "application/pdf",
         lambda: generate_invoice(seed=seed, **params["invoice"])[0]),
    ]

    inserted = []
    for doc_type, filename, content_type, gen in jobs:
        bytes_ = gen()
        ext = filename.rsplit(".", 1)[-1]
        path = f"{merchant_id}/{loan_id}/{doc_type}/{uuid.uuid4().hex[:12]}.{ext}"
        sb.storage.from_(BUCKET).upload(
            path=path, file=bytes_,
            file_options={"content-type": content_type, "upsert": "false"},
        )
        row = sb.table("documents").insert({
            "loan_id": loan_id, "doc_type": doc_type, "storage_path": path,
        }).execute().data[0]
        inserted.append({"doc_type": doc_type, "document_id": row["id"],
                         "storage_path": path, "size_bytes": len(bytes_)})
        print(f"    uploaded {doc_type:22s} {len(bytes_):>7d} bytes  ->  {path}")
    return inserted


def seed_persona(sb, p: dict) -> dict:
    print(f"\n=== {p['business_name']} ({p['key']}) ===")
    print("  1. cleanup prior data")
    delete_existing_merchant(sb, p["email"])

    print("  2. create auth user")
    uid = ensure_user(p["email"], p["business_name"])
    time.sleep(0.6)                   # let profile trigger fire

    print("  3. insert merchant")
    m = sb.table("merchants").insert({
        "user_id": uid,
        "business_name": p["business_name"],
        "cr_number": p["cr_number"],
        "google_maps_url": p["google_maps_url"],
        "phone": p["phone"],
    }).execute().data[0]
    mid = m["id"]

    print("  4. insert loan")
    loan = sb.table("loans").insert({
        "merchant_id": mid, **p["loan"],
    }).execute().data[0]
    lid = loan["id"]

    print("  5. generate + upload docs")
    params_with_name = {**p["gen_params"], "business_name": p["business_name"]}
    upload_docs(sb, mid, lid, params_with_name)

    print(f"  6. POST /analyze/start ({BASE_URL})")
    code, resp = _http("POST", "/analyze/start", {"loan_id": lid})
    if code != 200:
        raise RuntimeError(f"analyze/start failed {code}: {resp}")
    print(f"     {resp.get('status')}  registered_dims={resp.get('registered_dimensions')}")

    print("  7. poll /analyze/status (timeout 300s)")
    deadline = time.time() + 300
    while time.time() < deadline:
        code, s = _http("GET", f"/analyze/status/{lid}")
        docs_ok = sum(1 for d in (s or {}).get("documents", []) if d["analysis_status"] == "done")
        docs_err = sum(1 for d in (s or {}).get("documents", []) if d["analysis_status"] == "error")
        dims_done = sum(1 for d in (s or {}).get("dimensions", []) if d["status"] in ("done", "error", "skipped"))
        print(f"     synth={s.get('synthesis_status')}  docs={docs_ok}✓+{docs_err}✗/{len(s.get('documents', []))}  dims={dims_done}/5")
        if s.get("synthesis_status") == "done":
            break
        time.sleep(5)
    else:
        raise RuntimeError(f"pipeline did not finish in 300s for {p['key']}")

    print("  8. fetch final decision")
    loan_final = sb.table("loans").select("*").eq("id", lid).single().execute().data
    final = (loan_final.get("decision_payload") or {}).get("final_decision") or {}
    timing = (loan_final.get("decision_payload") or {}).get("generated_at")
    print(f"     status          = {loan_final['status']}")
    print(f"     approved_amount = {loan_final.get('approved_amount')}")
    print(f"     monthly_payment = {loan_final.get('monthly_payment')}")
    print(f"     override        = {final.get('override_applied')}")

    # Did we hit the expected outcome?
    actual = loan_final["status"]
    expected = p["expected_outcome"]
    mark = "✓" if actual == expected else "⚠"
    print(f"     {mark}  expected={expected}  got={actual}")

    return {
        "key": p["key"],
        "email": p["email"],
        "password": PASSWORD,
        "business_name": p["business_name"],
        "cr_number": p["cr_number"],
        "merchant_id": mid,
        "loan_id": lid,
        "expected_outcome": expected,
        "actual_outcome": actual,
        "approved_amount": loan_final.get("approved_amount"),
        "monthly_payment": loan_final.get("monthly_payment"),
    }


def write_credentials_doc(results: list[dict]) -> None:
    out = ["# Demo Credentials", "",
           "Three pre-seeded golden merchants with real pipeline-produced decisions.",
           "Use these to demo LeaseFlow without waiting on the live pipeline.", "",
           f"All passwords: `{PASSWORD}`  (same for each)", "",
           "| # | Persona | Email | Outcome | Amount | Monthly |",
           "|---|---|---|---|---|---|"]
    for r in results:
        amt = f"SAR {r['approved_amount']:,.0f}" if r["approved_amount"] else "—"
        mp  = f"SAR {r['monthly_payment']:,.0f}" if r["monthly_payment"] else "—"
        mark = "" if r["actual_outcome"] == r["expected_outcome"] else " ⚠"
        out.append(f"| {r['key']} | {r['business_name']} | `{r['email']}` | "
                   f"**{r['actual_outcome']}**{mark} | {amt} | {mp} |")
    out.append("")
    out.append("## Details")
    for r in results:
        out.append(f"\n### {r['business_name']}")
        out.append(f"- login: `{r['email']}` / `{PASSWORD}`")
        out.append(f"- CR: `{r['cr_number']}`")
        out.append(f"- merchant_id: `{r['merchant_id']}`")
        out.append(f"- loan_id: `{r['loan_id']}`")
        out.append(f"- expected → actual: `{r['expected_outcome']}` → `{r['actual_outcome']}`")
    doc_path = Path(__file__).resolve().parent.parent.parent / "handoff" / "DEMO_CREDENTIALS.md"
    doc_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nwrote {doc_path}")


def main() -> int:
    sb = get_client()
    print(f"BASE_URL = {BASE_URL}")
    print(f"supabase = {CONFIG.supabase_url}")
    print()

    code, h = _http("GET", "/health")
    if code != 200:
        print(f"ERROR: /health failed {code}: {h}")
        return 1
    print(f"orchestrator /health ok: env={h.get('env')} model={h.get('llm_model')}")

    results = []
    for p in PERSONAS:
        try:
            results.append(seed_persona(sb, p))
        except Exception as e:
            print(f"  FAILED {p['key']}: {type(e).__name__}: {e}")
            results.append({
                "key": p["key"], "email": p["email"], "password": PASSWORD,
                "business_name": p["business_name"], "cr_number": p["cr_number"],
                "merchant_id": None, "loan_id": None,
                "expected_outcome": p["expected_outcome"], "actual_outcome": f"ERROR: {e}",
                "approved_amount": None, "monthly_payment": None,
            })

    write_credentials_doc(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
