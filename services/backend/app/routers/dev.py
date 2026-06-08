"""Dev-only fixture endpoint.

Only mounted when LEASEFLOW_DEV_FIXTURES=true. Generates a full set of
documents for a given loan and uploads them to Supabase Storage under the
canonical path convention. Frontend colleague or demo uses this to populate
test data with one click — no need for a merchant to actually upload files.
"""
from __future__ import annotations

import io
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from ..config import CONFIG
from ..generators import (
    generate_bank_statement,
    generate_financial_statement,
    generate_invoice,
    generate_pos_data,
)
from ..supabase_client import get_client

log = logging.getLogger(__name__)

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/generate-fixtures")
async def generate_fixtures(body: dict) -> dict:
    """Generate a full doc set for a loan and upload to Storage + insert
    documents rows.

    Body:
      { "loan_id": uuid, "include": ["bank_statement","pos_data","financial_statement","invoice"] (optional) }
    Returns the list of storage paths and documents IDs.
    """
    loan_id = body.get("loan_id")
    if not loan_id:
        raise HTTPException(status_code=400, detail="loan_id is required")
    include = set(body.get("include") or [
        "bank_statement", "financial_statement", "pos_data", "invoice",
    ])

    sb = get_client()
    loan = sb.table("loans").select("*").eq("id", loan_id).single().execute().data
    if not loan:
        raise HTTPException(status_code=404, detail="loan not found")
    merchant = sb.table("merchants").select("*").eq("id", loan["merchant_id"]).single().execute().data

    seed = f"loan:{loan_id}"
    amount = float(loan["amount_requested"])
    business = merchant["business_name"]
    item_desc = loan["item_description"]

    results: list[dict] = []

    def _upload_and_insert(doc_type: str, filename: str, content: bytes) -> dict:
        path = f"{merchant['id']}/{loan_id}/{doc_type}/{uuid.uuid4().hex[:12]}.{filename.split('.')[-1]}"
        try:
            sb.storage.from_(CONFIG.storage_bucket).upload(
                path=path,
                file=content,
                file_options={"upsert": "false", "content-type": _content_type(filename)},
            )
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"upload failed for {doc_type}: {e}") from e
        row = sb.table("documents").insert({
            "loan_id": loan_id,
            "doc_type": doc_type,
            "storage_path": path,
        }).execute().data[0]
        return {"doc_type": doc_type, "document_id": row["id"], "storage_path": path,
                "size_bytes": len(content)}

    if "bank_statement" in include:
        b_bytes, _ = generate_bank_statement(
            seed=seed, business_name=business, months=6,
            monthly_revenue_target_sar=max(30000, amount * 1.5),
        )
        results.append(_upload_and_insert("bank_statement", "bank_statement.pdf", b_bytes))

    if "financial_statement" in include:
        f_bytes, _ = generate_financial_statement(
            seed=seed, business_name=business,
            annual_revenue_sar=max(300000, amount * 12),
        )
        results.append(_upload_and_insert("financial_statement", "financial_statement.pdf", f_bytes))

    if "pos_data" in include:
        p_bytes, _ = generate_pos_data(
            seed=seed, days=90,
            daily_revenue_target_sar=max(1000, amount * 0.03),
        )
        results.append(_upload_and_insert("pos_data", "pos_data.csv", p_bytes))

    if "invoice" in include:
        i_bytes, _ = generate_invoice(
            seed=seed, item_description=item_desc, amount_sar=amount,
        )
        results.append(_upload_and_insert("invoice", "invoice.pdf", i_bytes))

    return {"loan_id": loan_id, "generated": results}


def _content_type(filename: str) -> str:
    if filename.endswith(".pdf"): return "application/pdf"
    if filename.endswith(".csv"): return "text/csv"
    if filename.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "application/octet-stream"
