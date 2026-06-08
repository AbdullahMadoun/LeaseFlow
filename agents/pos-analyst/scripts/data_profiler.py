"""Deterministic Phase 1: profile every input file. No LLM calls here.

Runs OUTSIDE the sandbox (in the API container) because the profile is small,
trusted, and the agent must read it before writing any code. We import pandas
locally — the API image carries it.
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any

import pandas as pd

from models import ColumnProfile, DataProfile, FileProfile, utcnow_iso

# Heuristic mapping from canonical role to candidate column-name patterns.
_ROLE_PATTERNS: dict[str, list[str]] = {
    "merchant_id":    [r"^merchant[_ ]?id$", r"^store[_ ]?id$", r"^branch[_ ]?id$"],
    "merchant_name":  [r"^merchant$", r"^merchant[_ ]?name$", r"^legal[_ ]?name$", r"^brand$"],
    "transaction_id": [r"^trans(action)?[_ ]?id$", r"^txn[_ ]?id$", r"^order[_ ]?id$",
                       r"^receipt[_ ]?id$", r"^invoice[_ ]?id$", r"^bill[_ ]?id$"],
    "branch":         [r"^branch$", r"^store$", r"^location$", r"^outlet$", r"^shop$", r"^site$"],
    "city":           [r"^city$", r"^town$", r"^region$", r"^area$"],
    "item":           [r"^item$", r"^product$", r"^sku$", r"^menu[_ ]?item$",
                       r"^item[_ ]?name$", r"^product[_ ]?name$"],
    "category":       [r"^category$", r"^cat$", r"^menu[_ ]?category$", r"^section$",
                       r"^department$", r"^group$"],
    "qty":            [r"^qty$", r"^quantity$", r"^count$", r"^units?$"],
    "unit_price":     [r"^unit[_ ]?price$", r"^price$", r"^rate$", r"^item[_ ]?price$"],
    "line_total":     [r"^line[_ ]?total$", r"^subtotal$", r"^line[_ ]?amount$",
                       r"^row[_ ]?total$"],
    "ticket_total":   [r"^total$", r"^amount$", r"^grand[_ ]?total$",
                       r"^net[_ ]?total$", r"^bill[_ ]?total$"],
    "discount":       [r"^discount$", r"^disc$", r"^promo$", r"^promo[_ ]?amount$"],
    "tax":            [r"^tax$", r"^vat$", r"^gst$"],
    "void":           [r"^void(ed)?$", r"^cancel(led|ed)?$", r"^is[_ ]?void$"],
    "comp":           [r"^comp(ed|limentary)?$"],
    "refund":         [r"^refund(ed)?$"],
    "payment_method": [r"^payment[_ ]?method$", r"^pay[_ ]?type$", r"^tender(_type)?$",
                       r"^payment$"],
    "staff":          [r"^staff$", r"^server$", r"^waiter$", r"^cashier$", r"^employee$",
                       r"^user$"],
    "timestamp":      [r"^created[_ ]?at$", r"^timestamp$", r"^date[_ ]?time$",
                       r"^txn[_ ]?date$", r"^order[_ ]?time$", r"^datetime$"],
    "date":           [r"^date$", r"^business[_ ]?date$", r"^txn[_ ]?date$", r"^.*[_ ]date$"],
    "channel":        [r"^channel$", r"^order[_ ]?type$", r"^service[_ ]?type$",
                       r"^dine[_ ]?in$", r"^takeaway$", r"^delivery$"],
    "currency":       [r"^currency$", r"^ccy$"],
    "table":          [r"^table$", r"^table[_ ]?id$", r"^table[_ ]?no$"],
    "gross_sales":    [r"^gross[_ ]?sales$", r"^gross[_ ]?revenue$"],
    "discounts":      [r"^discounts$", r"^discount[_ ]?amount$"],
    "net_sales":      [r"^net[_ ]?sales$", r"^net[_ ]?revenue$"],
    "vat_amount":     [r"^vat[_ ]?amount$", r"^tax[_ ]?amount$"],
    "refund_amount":  [r"^refunds?[_ ]?amount$", r"^refunds?$"],
    "orders_count":   [r"^orders?[_ ]?count$", r"^transactions?[_ ]?count$"],
    "avg_ticket":     [r"^avg[_ ]?ticket$", r"^average[_ ]?ticket$"],
    "cash_amount":    [r"^cash[_ ]?amount$", r"^cash$"],
    "card_amount":    [r"^card[_ ]?amount$", r"^cards?[_ ]?amount$"],
    "wallet_amount":  [r"^wallet[_ ]?amount$", r"^ewallet[_ ]?amount$"],
    "total_collected":[r"^total[_ ]?collected$", r"^collections?$"],
    "opening_balance":[r"^opening[_ ]?balance$"],
    "inflows":        [r"^inflows?$", r"^credits?$"],
    "outflows":       [r"^outflows?$", r"^debits?$"],
    "closing_balance":[r"^closing[_ ]?balance$", r"^ending[_ ]?balance$"],
    "obligation_type":[r"^obligation[_ ]?type$", r"^liability[_ ]?type$"],
    "amount_due":     [r"^amount[_ ]?due$", r"^due[_ ]?amount$"],
    "amount_paid":    [r"^amount[_ ]?paid$", r"^paid[_ ]?amount$"],
    "status":         [r"^status$", r"^state$"],
}


def _detect_roles(columns: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    lowered = {c: c.strip().lower().replace(" ", "_") for c in columns}
    for role, patterns in _ROLE_PATTERNS.items():
        for orig, low in lowered.items():
            if any(re.match(p, low) for p in patterns):
                out.setdefault(role, orig)
                break
    return out


def _try_load(path: Path) -> tuple[pd.DataFrame, str]:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path), "excel"
    if suffix == ".jsonl":
        return pd.read_json(path, lines=True), "jsonl"
    if suffix == ".json":
        try:
            return pd.read_json(path), "json"
        except ValueError:
            return pd.read_json(path, lines=True), "jsonl"
    if suffix == ".parquet":
        return pd.read_parquet(path), "parquet"

    # CSV-ish: try comma, semicolon, tab, pipe.
    last_err: Exception | None = None
    for sep in [",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(path, sep=sep, low_memory=False, encoding="utf-8", on_bad_lines="warn")
            if df.shape[1] > 1 or sep == ",":
                return df, f"csv(sep={sep!r})"
        except (UnicodeDecodeError, pd.errors.ParserError) as e:
            last_err = e
            continue
    # Last resort: latin-1
    try:
        return pd.read_csv(path, sep=",", low_memory=False, encoding="latin-1"), "csv(latin-1)"
    except Exception as e:
        raise RuntimeError(f"Could not parse {path.name}: {last_err or e}") from e


def _profile_columns(df: pd.DataFrame) -> list[ColumnProfile]:
    out: list[ColumnProfile] = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        dtype = str(s.dtype)
        n_missing = int(s.isna().sum())
        n_unique: int | None
        try:
            n_unique = int(s.nunique(dropna=True))
        except TypeError:
            n_unique = None
        examples: list[str] = []
        try:
            non_null = s.dropna()
            sample = non_null.head(3).astype(str).tolist() if len(non_null) else []
            examples = [x[:120] for x in sample]
        except Exception:
            examples = []
        col_min: str | None = None
        col_max: str | None = None
        if pd.api.types.is_numeric_dtype(s) and n - n_missing > 0:
            col_min = f"{s.min()}"
            col_max = f"{s.max()}"
        elif pd.api.types.is_datetime64_any_dtype(s) and n - n_missing > 0:
            col_min = str(s.min())
            col_max = str(s.max())
        out.append(ColumnProfile(
            name=str(col), dtype=dtype, n_missing=n_missing,
            n_unique=n_unique, examples=examples, min=col_min, max=col_max,
        ))
    return out


def _detect_time_range(df: pd.DataFrame, roles: dict[str, str]) -> dict[str, str] | None:
    candidate_col = roles.get("timestamp") or roles.get("date")
    if not candidate_col or candidate_col not in df.columns:
        # try to coerce any datetime-looking column
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                candidate_col = col
                break
            if df[col].dtype == object:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        coerced = pd.to_datetime(df[col], errors="raise", utc=False)
                    if coerced.notna().sum() >= max(10, int(0.5 * len(df))):
                        candidate_col = col
                        df[col] = coerced
                        break
                except Exception:
                    continue
    if not candidate_col or candidate_col not in df.columns:
        return None
    s = df[candidate_col]
    if not pd.api.types.is_datetime64_any_dtype(s):
        try:
            s = pd.to_datetime(s, errors="coerce")
        except Exception:
            return None
    s = s.dropna()
    if s.empty:
        return None
    return {"column": candidate_col, "min": str(s.min()), "max": str(s.max())}


def _quality_flags(df: pd.DataFrame, roles: dict[str, str]) -> list[str]:
    flags: list[str] = []
    n = len(df)

    if df.duplicated().any():
        flags.append(f"{int(df.duplicated().sum())} fully-duplicate rows")

    qty_col = roles.get("qty")
    void_col = roles.get("void")
    if qty_col and qty_col in df.columns:
        s = pd.to_numeric(df[qty_col], errors="coerce")
        n_neg = int((s < 0).sum())
        if n_neg > 0:
            if not void_col:
                flags.append(f"{n_neg} rows have negative {qty_col} but no void/refund column was detected — likely implicit voids")
            else:
                voided = df[void_col].astype(str).str.lower().isin({"true", "1", "yes", "y", "void", "voided"})
                if int(((s < 0) & ~voided).sum()) > 0:
                    flags.append(f"{n_neg} negative {qty_col} rows, of which {int(((s < 0) & ~voided).sum())} are not flagged as voids")

    for price_role in ("unit_price", "ticket_total", "line_total"):
        col = roles.get(price_role)
        if col and col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            n_zero = int((s == 0).sum())
            n_neg = int((s < 0).sum())
            if n_neg > 0:
                flags.append(f"{n_neg} rows have negative {col}")
            if n_zero / max(n, 1) > 0.05:
                flags.append(f"{n_zero} ({n_zero / n:.0%}) rows have zero {col}")

    ts = roles.get("timestamp") or roles.get("date")
    if ts and ts in df.columns:
        try:
            tcol = pd.to_datetime(df[ts], errors="coerce")
            future = int((tcol > pd.Timestamp.utcnow()).sum())
            if future > 0:
                flags.append(f"{future} rows have future {ts} values")
        except Exception:
            pass

    branch_col = roles.get("branch")
    if branch_col and branch_col in df.columns:
        counts = df[branch_col].value_counts(dropna=True)
        thin = counts[counts < 100]
        if len(thin) > 0:
            flags.append(f"{len(thin)} branch(es) with <100 transactions: {list(thin.index[:10])}")

    cur_col = roles.get("currency")
    if cur_col and cur_col in df.columns and df[cur_col].dropna().nunique() > 1:
        flags.append(f"multiple currencies present: {sorted(df[cur_col].dropna().unique().tolist())[:5]}")

    merchant_col = roles.get("merchant_id")
    date_col = roles.get("date") or roles.get("timestamp")
    if merchant_col and merchant_col in df.columns and date_col and date_col in df.columns:
        dup_key_rows = int(df.duplicated(subset=[merchant_col, date_col]).sum())
        if dup_key_rows > 0:
            flags.append(f"{dup_key_rows} duplicate merchant-date rows")

    sales_cols = [roles.get("gross_sales"), roles.get("discounts"), roles.get("net_sales")]
    refund_col = roles.get("refund_amount")
    if all(col and col in df.columns for col in sales_cols):
        gross = pd.to_numeric(df[roles["gross_sales"]], errors="coerce")
        discounts = pd.to_numeric(df[roles["discounts"]], errors="coerce")
        net = pd.to_numeric(df[roles["net_sales"]], errors="coerce")
        refunds = pd.to_numeric(df[refund_col], errors="coerce") if refund_col and refund_col in df.columns else 0.0
        expected_net = gross - discounts - refunds
        mismatched = int(((expected_net - net).abs() > 0.05).fillna(False).sum())
        if mismatched > 0:
            flags.append(f"{mismatched} rows violate gross - discounts - refunds = net_sales")

    payment_cols = [roles.get("cash_amount"), roles.get("card_amount"), roles.get("wallet_amount"), roles.get("total_collected")]
    if all(col and col in df.columns for col in payment_cols):
        cash = pd.to_numeric(df[roles["cash_amount"]], errors="coerce")
        card = pd.to_numeric(df[roles["card_amount"]], errors="coerce")
        wallet = pd.to_numeric(df[roles["wallet_amount"]], errors="coerce")
        total = pd.to_numeric(df[roles["total_collected"]], errors="coerce")
        mismatched = int((((cash + card + wallet) - total).abs() > 0.05).fillna(False).sum())
        if mismatched > 0:
            flags.append(f"{mismatched} rows violate cash + card + wallet = total_collected")

    bank_cols = [roles.get("opening_balance"), roles.get("inflows"), roles.get("outflows"), roles.get("closing_balance")]
    if all(col and col in df.columns for col in bank_cols):
        opening = pd.to_numeric(df[roles["opening_balance"]], errors="coerce")
        inflows = pd.to_numeric(df[roles["inflows"]], errors="coerce")
        outflows = pd.to_numeric(df[roles["outflows"]], errors="coerce")
        closing = pd.to_numeric(df[roles["closing_balance"]], errors="coerce")
        mismatched = int((((opening + inflows - outflows) - closing).abs() > 0.05).fillna(False).sum())
        if mismatched > 0:
            flags.append(f"{mismatched} rows violate opening_balance + inflows - outflows = closing_balance")
        negative_balances = int((closing < 0).fillna(False).sum())
        if negative_balances > 0:
            flags.append(f"{negative_balances} rows have negative closing_balance")

    return flags


def _cross_file_notes(file_profiles: list[FileProfile]) -> list[str]:
    notes: list[str] = []
    if len(file_profiles) <= 1:
        return notes

    all_cols = [tuple(c.name for c in fp.columns) for fp in file_profiles]
    if len(set(all_cols)) == 1:
        notes.append("All files share an identical schema — can be concatenated.")
    else:
        notes.append("Files have differing schemas — concatenation will require column alignment.")

    merchant_files = [fp.filename for fp in file_profiles if "merchant_id" in fp.detected_role]
    if len(merchant_files) >= 2:
        notes.append(f"Shared merchant key detected across files: {', '.join(merchant_files)}.")

    date_files = [fp.filename for fp in file_profiles if "date" in fp.detected_role or "timestamp" in fp.detected_role]
    if len(date_files) >= 2:
        notes.append(f"Multiple files carry date-aligned facts: {', '.join(date_files)}.")

    has_sales = any("gross_sales" in fp.detected_role for fp in file_profiles)
    has_payments = any("total_collected" in fp.detected_role for fp in file_profiles)
    has_bank = any("closing_balance" in fp.detected_role for fp in file_profiles)
    has_obligations = any("obligation_type" in fp.detected_role or "amount_due" in fp.detected_role for fp in file_profiles)
    if has_sales and has_payments and has_bank and has_obligations:
        notes.append(
            "This looks like a daily financial schema (sales, collections, bank balances, obligations), "
            "not raw receipt-level POS tickets. Reconcile inter-table identities before deeper analysis."
        )

    merchant_dim = next((fp for fp in file_profiles if {"merchant_id", "merchant_name", "city"} <= set(fp.detected_role)), None)
    if merchant_dim is not None:
        notes.append(f"{merchant_dim.filename} appears to be the merchant dimension table.")

    return notes


def profile_file(path: Path) -> FileProfile:
    df, fmt = _try_load(path)
    cols = [str(c) for c in df.columns]
    roles = _detect_roles(cols)
    time_range = _detect_time_range(df, roles)
    flags = _quality_flags(df, roles)
    return FileProfile(
        filename=path.name,
        n_rows=int(len(df)),
        n_cols=int(df.shape[1]),
        columns=_profile_columns(df),
        n_duplicate_rows=int(df.duplicated().sum()),
        detected_role=roles,
        quality_flags=flags,
        time_range=time_range,
        load_format=fmt,
    )


def profile_job(job_id: str, files: list[Path]) -> DataProfile:
    file_profiles = [profile_file(p) for p in files]
    return DataProfile(
        job_id=job_id,
        files=file_profiles,
        cross_file_notes=_cross_file_notes(file_profiles),
        generated_at=utcnow_iso(),
    )


def render_profile_for_prompt(profile: DataProfile, max_chars: int = 6000) -> str:
    """Compact, human-readable rendering for the LLM context window."""
    lines: list[str] = [f"# Data profile (job {profile.job_id})", ""]
    for fp in profile.files:
        lines.append(f"## {fp.filename}  —  {fp.n_rows:,} rows × {fp.n_cols} cols  (loaded as {fp.load_format})")
        if fp.time_range:
            lines.append(f"- Time range ({fp.time_range['column']}): {fp.time_range['min']} → {fp.time_range['max']}")
        if fp.detected_role:
            roles_str = ", ".join(f"{k}=`{v}`" for k, v in fp.detected_role.items())
            lines.append(f"- Detected roles: {roles_str}")
        if fp.n_duplicate_rows:
            lines.append(f"- Duplicate rows: {fp.n_duplicate_rows:,}")
        if fp.quality_flags:
            lines.append("- Quality flags:")
            for q in fp.quality_flags:
                lines.append(f"  * {q}")
        lines.append("- Columns:")
        for col in fp.columns:
            extras: list[str] = [f"dtype={col.dtype}", f"missing={col.n_missing:,}"]
            if col.n_unique is not None:
                extras.append(f"unique={col.n_unique:,}")
            if col.min is not None:
                extras.append(f"min={col.min}")
            if col.max is not None:
                extras.append(f"max={col.max}")
            if col.examples:
                extras.append(f"e.g. {col.examples}")
            lines.append(f"  - `{col.name}`: " + "; ".join(extras))
        lines.append("")
    if profile.cross_file_notes:
        lines.append("## Cross-file notes")
        for n in profile.cross_file_notes:
            lines.append(f"- {n}")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... [profile truncated]"
    return text
