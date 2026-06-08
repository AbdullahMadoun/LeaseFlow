"""POS CSV extractor — preview + precomputed stats go to the LLM."""
from __future__ import annotations

import io
import json
from datetime import datetime

import pandas as pd

from ..schemas.documents import POSReport
from ._common import CSV_PREVIEW_ROWS, csv_preview_block, extract_with_schema

SYSTEM_PROMPT = """You extract structured data from a KSA F&B merchant's POS
transaction-level CSV export, for a lease-to-own underwriting decision.

Produce JSON matching the POSReport schema.

Rules:
- Amounts in SAR.
- Use the precomputed stats block when given — those are authoritative for
  totals. Your job is to structure them and infer the qualitative fields.
- For peak_hours, pick the 2 busiest 2-hour buckets from the precomputed
  hour histogram (format: "HH:00-HH+2:00").
- For trend_90d: if last-half-period average revenue is materially higher,
  "up" or "slightly_up"; materially lower, "down" / "slightly_down"; else "stable".
- For seasonality: "weekend_heavy" if Fri/Sat revenue >15% above weekday avg,
  "weekday_heavy" if inverse, else "flat".
- Fields that genuinely aren't derivable from the data -> null +
  low_confidence_fields entry.
- If the source is clearly NOT POS transaction data, set confidence=0 and add
  "not_a_pos_export" to meta.extraction_notes.
"""


async def extract_pos_data(
    *,
    csv_bytes: bytes,
    filename: str,
    loan_id: str,
    document_id: str | None = None,
) -> POSReport:
    # Build deterministic pre-computed stats so we don't ask the LLM to count rows
    try:
        stats = _compute_stats(csv_bytes)
    except Exception as e:  # noqa: BLE001
        stats = {"error": f"stats_compute_failed: {e}"[:300]}
    preview, basic = csv_preview_block(csv_bytes)
    payload = (
        f"<<PRECOMPUTED STATS>>\n{json.dumps({**basic, **stats}, default=str)}\n\n"
        f"<<CSV PREVIEW (first {CSV_PREVIEW_ROWS} rows)>>\n{preview}"
    )
    return await extract_with_schema(
        model_cls=POSReport,
        loan_id=loan_id,
        document_id=document_id,
        stage="extract_pos_data",
        system_prompt=SYSTEM_PROMPT,
        user_payload=payload,
        filename=filename,
    )


def _compute_stats(csv_bytes: bytes) -> dict:
    """Deterministically summarise a POS CSV so the LLM doesn't need to count rows."""
    df = pd.read_csv(io.BytesIO(csv_bytes))
    out: dict = {"row_count": len(df)}

    # Find the columns we care about (canonical names from the generator)
    def col(*names):
        for n in names:
            if n in df.columns:
                return n
        return None

    ts_col = col("timestamp", "ts", "datetime")
    ticket_col = col("ticket_total", "total", "amount")
    void_col = col("void", "is_void")
    refund_col = col("refund", "is_refund")
    pay_col = col("payment_method", "payment", "method")

    # One-row-per-line to one-row-per-transaction: dedupe by txn id if present
    tid_col = col("transaction_id", "txn_id")
    if tid_col and ticket_col:
        tickets = df.drop_duplicates(subset=[tid_col])[[tid_col, ticket_col, ts_col, void_col, refund_col, pay_col]].copy() \
            if all([ts_col, void_col is not None, refund_col is not None, pay_col]) \
            else df.drop_duplicates(subset=[tid_col])
    else:
        tickets = df

    if ticket_col:
        tickets[ticket_col] = pd.to_numeric(tickets[ticket_col], errors="coerce")
        valid = tickets[tickets[ticket_col].notna()]
        if void_col:
            valid = valid[valid[void_col].astype(str).isin(["0", "False", "false", "no"])]
        out["total_revenue_sar"] = float(valid[ticket_col].sum())
        out["txn_count"] = int(len(valid))
        out["avg_ticket_sar"] = float(valid[ticket_col].mean()) if len(valid) else None

    if ts_col:
        ts = pd.to_datetime(tickets[ts_col], errors="coerce")
        ts_clean = ts.dropna()
        if len(ts_clean):
            out["period_start"] = ts_clean.min().strftime("%Y-%m-%d")
            out["period_end"] = ts_clean.max().strftime("%Y-%m-%d")
            out["days_covered"] = (ts_clean.max() - ts_clean.min()).days + 1
            # hour histogram
            hour_rev = {}
            if ticket_col:
                tmp = tickets.copy()
                tmp[ts_col] = ts
                tmp[ticket_col] = pd.to_numeric(tmp[ticket_col], errors="coerce")
                tmp = tmp.dropna(subset=[ts_col, ticket_col])
                for h, rev in tmp.groupby(tmp[ts_col].dt.hour)[ticket_col].sum().items():
                    hour_rev[int(h)] = float(rev)
            out["hour_revenue_histogram"] = hour_rev

    if void_col:
        void_vals = df[void_col].astype(str)
        out["void_rate"] = float((void_vals.isin(["1", "True", "true", "yes"])).mean())
    if refund_col:
        refund_vals = df[refund_col].astype(str)
        out["refund_rate"] = float((refund_vals.isin(["1", "True", "true", "yes"])).mean())
    if pay_col and ticket_col:
        grp = df.groupby(pay_col)[ticket_col].sum()
        total = float(grp.sum())
        if total > 0:
            out["payment_mix"] = {
                str(k): round(float(v) / total, 3) for k, v in grp.items()
            }
    return out
