#!/usr/bin/env python3
"""Apply leaseflow/migrations/*.sql in order to a Supabase project.

Required env:
  SUPABASE_ACCESS_TOKEN  — personal access token
  SUPABASE_PROJECT_REF   — target project ref (e.g. gbdnlnoqkdislrhvfxol)

Also creates the loan-documents storage bucket if missing, via the
Storage API (buckets aren't managed by SQL).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MIGRATIONS = sorted((HERE / "migrations").glob("*.sql"))


def _req(url: str, method: str, token: str, body: dict | None = None,
         headers: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "leaseflow-deploy/1.0",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode(errors="replace")}


def run_sql(pat: str, ref: str, sql: str) -> tuple[int, object]:
    return _req(
        f"https://api.supabase.com/v1/projects/{ref}/database/query",
        "POST", pat, {"query": sql},
    )


def ensure_bucket(service_key: str, supabase_url: str) -> None:
    # Check first
    status, body = _req(
        f"{supabase_url}/storage/v1/bucket",
        "GET", service_key, headers={"apikey": service_key},
    )
    if status == 200 and isinstance(body, list) and any(b.get("id") == "loan-documents" for b in body):
        print("  bucket 'loan-documents' already exists")
        return
    status, body = _req(
        f"{supabase_url}/storage/v1/bucket",
        "POST", service_key,
        body={
            "id": "loan-documents",
            "name": "loan-documents",
            "public": False,
            "file_size_limit": 52428800,
            "allowed_mime_types": [
                "application/pdf", "text/csv", "text/plain",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/json", "image/jpeg", "image/png",
            ],
        },
        headers={"apikey": service_key},
    )
    print(f"  bucket create: HTTP {status} — {body}")


def main() -> int:
    pat = os.environ.get("SUPABASE_ACCESS_TOKEN")
    ref = os.environ.get("SUPABASE_PROJECT_REF")
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not pat or not ref:
        print("ERROR: SUPABASE_ACCESS_TOKEN and SUPABASE_PROJECT_REF are required")
        return 2

    print(f"Target project: {ref}")
    print(f"Migrations dir: {HERE / 'migrations'}")
    print(f"Found {len(MIGRATIONS)} migrations\n")

    for m in MIGRATIONS:
        print(f"→ {m.name}")
        sql = m.read_text()
        status, body = run_sql(pat, ref, sql)
        if status >= 300:
            print(f"  FAILED HTTP {status}: {body}")
            return 1
        print(f"  HTTP {status} OK")

    if supabase_url and service_key:
        print("\n→ Ensuring storage bucket 'loan-documents'")
        ensure_bucket(service_key, supabase_url)
    else:
        print("\nSkipping bucket creation (set SUPABASE_URL + SUPABASE_SERVICE_KEY to enable).")

    print("\n✓ All migrations applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
