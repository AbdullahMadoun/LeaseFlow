"""Expert synthesis — deterministic scorer + LLM (downgrade-only by default).

Pipeline:
  1. Load dim results + current risk policy + current risk snapshot.
  2. Deterministic scorer: weighted avg over registered dims → proposal.
  3. Hard floors: DSCR < 1.0 or SIMAH defaults > 0 → auto-deny.
  4. LLM call (MiniMax) with strict JSON schema; validate on parse.
  5. Apply decision_mode:
       - 'guardrail'    (default): LLM can downgrade but not upgrade.
       - 'llm_primary':           LLM decision stands (subject to hard floors).
  6. Write loans.decision_payload + status + approved_amount + monthly_payment.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .config import CONFIG
from .notifications import send_decision_email
from .schemas import ExpertDecisionPayload, LLMDecision
from .supabase_client import get_client
from .tracing import traced_llm_call, write_event

log = logging.getLogger(__name__)

DECISION_RANK = {"deny": 0, "manual_review": 1, "approve": 2}

SYSTEM_PROMPT = """You are the Expert Synthesis engine for LeaseFlow, a lease-to-own F&B financing platform in KSA.
The company buys the invoice for the merchant, provides the item, then leases it back with a ~15% profit margin.

You will receive:
  - deterministic dimension scores (POS, financial, SIMAH, sentiment, industry)
  - affordability math (DSCR already computed by Python — do NOT recompute)
  - current risk governance snapshot (market appetite)
  - a deterministic proposal from the rules engine

Your job: weigh qualitative signals (trends, flags, narrative) on top of the numbers and produce a final decision.

RULES:
  - Respond ONLY with a JSON object matching the requested schema.
  - Do NOT do arithmetic. The Python rules engine already computed DSCR, scores, and amount bounds.
  - Your 'recommended_amount' must fall within the proposal's amount_bounds unless you downgrade to manual_review or deny.
  - 'reasoning' is 2-3 sentences, specific, tied to the numbers and flags.
  - If a dimension errored or was skipped, note it in risk_flags.
"""


def _load_policy(sb) -> dict[str, Any]:
    row = sb.table("risk_policies").select("rules").order("effective_from", desc=True).limit(1).execute()
    if not row.data:
        raise RuntimeError("No risk_policies row — seed 0004 must run first")
    return row.data[0]["rules"]


def _load_risk_snapshot(sb) -> dict | None:
    row = sb.table("risk_snapshots").select("*").order("captured_at", desc=True).limit(1).execute()
    return row.data[0] if row.data else None


def _load_dim_results(sb, loan_id: str) -> list[dict]:
    row = sb.table("dimension_results").select("*").eq("loan_id", loan_id).execute()
    return row.data or []


def _load_loan(sb, loan_id: str) -> dict:
    row = sb.table("loans").select("*").eq("id", loan_id).single().execute()
    return row.data


def deterministic_scorer(loan: dict, dims: list[dict], policy: dict) -> dict:
    """Compute overall score + rule-based decision + amount bounds."""
    weights = policy["dimension_weights"]
    thresholds = policy["thresholds"]

    done_dims = {d["dimension"]: d for d in dims if d["status"] == "done"}
    if not done_dims:
        return {"decision": "manual_review", "overall_score": 0,
                "amount_bounds": {"min": 0, "max": 0}, "rules_fired": ["no_dimensions_available"],
                "per_dim": {}, "risk_level": "high"}

    # Renormalize weights over dims that completed
    active_w = {name: weights.get(name, 0.0) for name in done_dims}
    total_w = sum(active_w.values())
    if total_w == 0:
        for name in active_w:
            active_w[name] = 1.0 / len(active_w)
    else:
        for name in active_w:
            active_w[name] /= total_w

    overall = sum((done_dims[n]["score"] or 0) * w for n, w in active_w.items())

    approve_min = thresholds["approve_overall_score_min"]
    deny_max = thresholds["deny_overall_score_max"]

    rules_fired = []
    if overall >= approve_min:
        decision = "approve"
        rules_fired.append(f"overall_score>={approve_min}")
    elif overall <= deny_max:
        decision = "deny"
        rules_fired.append(f"overall_score<={deny_max}")
    else:
        decision = "manual_review"
        rules_fired.append("overall_score_in_review_band")

    # Amount bounds: anchor to requested; if financial dim present, clamp to DSCR-safe range
    amount_req = float(loan["amount_requested"])
    amt_min = amount_req * 0.6
    amt_max = amount_req
    fin = done_dims.get("financial_docs")
    if fin and fin.get("result"):
        aff = (fin["result"] or {}).get("features", {}).get("affordability") or {}
        dscr = aff.get("dscr")
        if dscr is not None:
            if dscr >= 1.5:
                amt_max = amount_req  # full amount
                amt_min = amount_req * 0.8
                rules_fired.append("dscr_comfortable")
            elif dscr >= 1.2:
                amt_max = amount_req * 0.85
                amt_min = amount_req * 0.6
                rules_fired.append("dscr_marginal")
            else:
                amt_max = amount_req * 0.6
                amt_min = amount_req * 0.4
                rules_fired.append("dscr_tight")

    simah = done_dims.get("simah")
    if simah and simah.get("result"):
        if (simah["result"] or {}).get("features", {}).get("defaults_count", 0) > 0:
            rules_fired.append("simah_defaults_present")

    risk_level = "low" if overall >= 75 else ("medium" if overall >= 55 else "high")

    per_dim = {n: round(done_dims[n]["score"] or 0, 1) for n in done_dims}

    return {
        "decision": decision,
        "overall_score": round(overall, 1),
        "amount_bounds": {"min": round(amt_min, 2), "max": round(amt_max, 2)},
        "rules_fired": rules_fired,
        "per_dim": per_dim,
        "risk_level": risk_level,
    }


def hard_floors_check(loan: dict, dims: list[dict], policy: dict) -> dict:
    """Unconditional denies regardless of LLM output."""
    violations: list[str] = []
    done_dims = {d["dimension"]: d for d in dims if d["status"] == "done"}

    fin = done_dims.get("financial_docs")
    if fin and fin.get("result"):
        aff = (fin["result"] or {}).get("features", {}).get("affordability") or {}
        dscr = aff.get("dscr")
        if dscr is not None and dscr < 1.0:
            violations.append(f"dscr_below_1.0({dscr})")

    simah = done_dims.get("simah")
    if simah and simah.get("result"):
        defaults = (simah["result"] or {}).get("features", {}).get("defaults_count", 0)
        if defaults > 0:
            violations.append(f"simah_defaults>{0}({defaults})")

    return {"passed": len(violations) == 0, "violations": violations}


async def call_llm(loan: dict, merchant: dict, dims: list[dict], proposal: dict,
                   risk_snapshot: dict | None) -> LLMDecision | None:
    done_dims = {d["dimension"]: d for d in dims if d["status"] == "done"}
    errored = [d["dimension"] for d in dims if d["status"] in ("error", "skipped")]

    user_payload = {
        "loan": {
            "amount_requested": float(loan["amount_requested"]),
            "item_description": loan["item_description"],
            "profit_rate": float(loan["profit_rate"]),
            "repayment_months": int(loan["repayment_months"]),
        },
        "merchant": {
            "business_name": merchant["business_name"],
            "cr_number": merchant["cr_number"],
        },
        "risk_snapshot": {
            "market_status": (risk_snapshot or {}).get("market_status"),
            "risk_appetite": (risk_snapshot or {}).get("risk_appetite"),
            "notes": (risk_snapshot or {}).get("market_notes"),
        } if risk_snapshot else None,
        "deterministic_proposal": proposal,
        "dimensions": {
            name: {
                "score": d["score"],
                "confidence": d["confidence"],
                "narrative": d["narrative"],
                "flags": (d.get("result") or {}).get("flags", []),
                "features": (d.get("result") or {}).get("features", {}),
            }
            for name, d in done_dims.items()
        },
        "errored_dimensions": errored,
    }

    user = (
        "Produce the final decision JSON with this exact shape:\n"
        "{\n"
        '  "decision": "approve" | "deny" | "manual_review",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "recommended_amount": number or null,\n'
        '  "reasoning": "2-3 sentences",\n'
        '  "risk_flags": ["flag1", "flag2"],\n'
        '  "dimension_scores": { "pos": 0-100, "financial": 0-100, "credit": 0-100, "sentiment": 0-100, "industry": 0-100, "overall": 0-100 },\n'
        '  "risk_level": "low" | "medium" | "high"\n'
        "}\n\n"
        "Context:\n```json\n" + json.dumps(user_payload, default=str) + "\n```"
    )

    try:
        raw, _ = await traced_llm_call(
            loan_id=str(loan["id"]),
            stage="expert_synthesis",
            system=SYSTEM_PROMPT, user=user, json_mode=True,
        )
        return LLMDecision(**raw)
    except Exception as e:
        log.warning("LLM synthesis failed, falling back to deterministic", extra={"err": str(e)})
        return None


def apply_guardrail(proposal: dict, llm: LLMDecision | None, mode: str,
                    hard_floors: dict) -> dict:
    """Combine deterministic + LLM into final decision, respecting mode + floors."""
    if not hard_floors["passed"]:
        return {
            "status": "denied",
            "approved_amount": None,
            "override_applied": "hard_floor",
            "reason": "Hard floor violation: " + ", ".join(hard_floors["violations"]),
        }

    det_decision = proposal["decision"]
    amt_bounds = proposal["amount_bounds"]

    if llm is None:
        # No LLM output — fall back to deterministic
        if det_decision == "approve":
            return {"status": "approved", "approved_amount": amt_bounds["max"],
                    "override_applied": "llm_unavailable_deterministic_only"}
        return {"status": "manual_review" if det_decision == "manual_review" else "denied",
                "approved_amount": None,
                "override_applied": "llm_unavailable_deterministic_only"}

    if mode == "llm_primary":
        final = llm.decision
        amt = llm.recommended_amount
    else:  # guardrail — LLM can only downgrade
        if DECISION_RANK[llm.decision] < DECISION_RANK[det_decision]:
            final = llm.decision
            override = "llm_downgrade"
        elif DECISION_RANK[llm.decision] > DECISION_RANK[det_decision]:
            final = det_decision
            override = "llm_upgrade_blocked"
        else:
            final = det_decision
            override = "agreement"
        # Clamp amount to deterministic bounds
        amt = llm.recommended_amount if final == "approve" else None
        if amt is not None:
            amt = max(amt_bounds["min"], min(amt_bounds["max"], amt))
        return {
            "status": _to_loan_status(final),
            "approved_amount": amt if final == "approve" else None,
            "override_applied": override,
        }

    # llm_primary path
    if final == "approve" and amt is not None:
        amt = max(amt_bounds["min"], min(amt_bounds["max"], amt))
    return {
        "status": _to_loan_status(final),
        "approved_amount": amt if final == "approve" else None,
        "override_applied": "llm_primary",
    }


def _to_loan_status(decision: str) -> str:
    return {"approve": "approved", "deny": "denied", "manual_review": "manual_review"}[decision]


async def synthesize(loan_id: str) -> dict:
    """Entry point. Run after all 5 dims done. Writes decision_payload + loan status."""
    sb = get_client()
    loan = _load_loan(sb, loan_id)
    if loan["synthesis_status"] == "done":
        log.info("synthesize: already done", extra={"loan_id": loan_id})
        return loan["decision_payload"]

    merchant = sb.table("merchants").select("*").eq("id", loan["merchant_id"]).single().execute().data
    dims = _load_dim_results(sb, loan_id)
    policy = _load_policy(sb)
    risk_snapshot = _load_risk_snapshot(sb)

    proposal = deterministic_scorer(loan, dims, policy)
    floors = hard_floors_check(loan, dims, policy)

    llm_decision: LLMDecision | None = None
    if floors["passed"]:
        llm_decision = await call_llm(loan, merchant, dims, proposal, risk_snapshot)

    final = apply_guardrail(proposal, llm_decision, CONFIG.decision_mode, floors)

    # monthly payment recompute if approved
    monthly_payment = None
    if final["status"] == "approved" and final.get("approved_amount"):
        amt = float(final["approved_amount"])
        total = amt * (1 + float(loan["profit_rate"]))
        monthly_payment = round(total / int(loan["repayment_months"]), 2)

    payload = ExpertDecisionPayload(
        deterministic_proposal=proposal,
        hard_floors_check=floors,
        llm_response=llm_decision.model_dump() if llm_decision else None,
        final_decision=final,
        risk_snapshot_id=risk_snapshot["id"] if risk_snapshot else None,
        registered_dimensions=loan.get("registered_dimensions") or [],
        dimension_scores=proposal["per_dim"],
        generated_at=datetime.now(timezone.utc).isoformat(),
    ).model_dump()

    sb.table("loans").update({
        "status": final["status"],
        "approved_amount": final.get("approved_amount"),
        "monthly_payment": monthly_payment,
        "decision_payload": payload,
        "synthesis_status": "done",
        "analysis_completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", loan_id).execute()

    log.info("synthesis complete", extra={"loan_id": loan_id, "final": final,
                                           "override": final.get("override_applied")})

    # On approval, install the repayment schedule + create Stream links.
    # Failures here are logged but don't fail the decision — the schedule
    # can be regenerated via admin action.
    if final["status"] == "approved" and final.get("approved_amount"):
        try:
            from .payments import install_schedule_for_loan
            # Reload loan with the fresh approved_amount + monthly_payment
            loan_after = sb.table("loans").select("*").eq("id", loan_id).single().execute().data
            await install_schedule_for_loan(loan_id, loan_after)
        except Exception as e:  # noqa: BLE001
            log.exception("schedule install failed", extra={"loan_id": loan_id})
            from .tracing import write_event
            write_event(loan_id=loan_id, stage="repayment_schedule_error", kind="rule",
                        error=f"{type(e).__name__}: {e}"[:500])

    # Decision email — approved only. Denied + manual_review don't email
    # (the merchant sees the outcome in-app; sending a rejection email is a
    # separate flow we'd want to craft carefully).
    if final["status"] == "approved":
        try:
            email = await _lookup_user_email(merchant["user_id"])
            if email:
                await send_decision_email(email, loan_id, payload, merchant.get("business_name"))
        except Exception as e:  # noqa: BLE001
            log.warning("decision email skipped", extra={"err": str(e)})
    else:
        log.info("decision email skipped — non-approval outcome",
                 extra={"loan_id": loan_id, "status": final["status"]})

    return payload


async def _lookup_user_email(user_id: str) -> str | None:
    """Fetch auth.users.email via the Supabase auth admin REST API.
    Avoids sb.schema('auth') which mutates client state in supabase-py 2.x."""
    import httpx
    url = f"{CONFIG.supabase_url}/auth/v1/admin/users/{user_id}"
    headers = {
        "apikey": CONFIG.supabase_service_key,
        "Authorization": f"Bearer {CONFIG.supabase_service_key}",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=headers)
        if r.status_code >= 300:
            log.warning("auth user lookup non-2xx", extra={"status": r.status_code})
            return None
        return r.json().get("email")
