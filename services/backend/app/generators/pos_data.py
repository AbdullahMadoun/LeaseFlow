"""Generate a fake POS transaction-level CSV export."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta
from typing import Any

from ..schemas.documents import ExtractionMeta, POSAggregates, POSDaily, POSReport
from ._common import seed_rng

ITEMS = [
    ("Latte",            18.0),
    ("Cappuccino",       20.0),
    ("Iced Americano",   16.0),
    ("Flat White",       22.0),
    ("Mocha",            24.0),
    ("Matcha Latte",     26.0),
    ("Croissant",        14.0),
    ("Chicken Sandwich", 38.0),
    ("Breakfast Set",    45.0),
    ("Dessert of Day",   28.0),
    ("Bottled Water",    5.0),
]
STAFF_IDS = ["S001", "S002", "S003", "S004", "S005"]


def generate_pos_data(
    *,
    seed: str,
    days: int = 60,
    daily_revenue_target_sar: float = 1800,
    avg_ticket_sar: float = 45,
    void_rate: float = 0.012,
    refund_rate: float = 0.006,
    cash_fraction: float = 0.18,
    weekend_lift: float = 0.35,
    end_date: date | None = None,
) -> tuple[bytes, POSReport]:
    rng = seed_rng(seed, "pos_data")
    end = end_date or date.today()
    start = end - timedelta(days=days - 1)

    daily: list[POSDaily] = []
    rows: list[list[Any]] = []
    rows.append([
        "transaction_id", "timestamp", "branch", "item", "category", "qty",
        "unit_price", "line_total", "ticket_total", "discount", "tax", "void",
        "comp", "refund", "payment_method", "staff",
    ])

    txn_counter = 0
    total_revenue = 0.0
    total_txns = 0
    peak_hour_buckets: dict[int, float] = {}
    cash_sum = 0.0
    card_sum = 0.0
    void_count = 0
    refund_count = 0

    for d_offset in range(days):
        day = start + timedelta(days=d_offset)
        is_weekend = day.weekday() in (4, 5)  # Fri-Sat weekend in KSA
        day_mult = 1 + (weekend_lift if is_weekend else 0) + rng.uniform(-0.12, 0.12)
        day_revenue_target = daily_revenue_target_sar * day_mult
        day_rev = 0.0
        day_txn = 0

        # Build tickets until we hit ~daily_revenue_target
        while day_rev < day_revenue_target:
            txn_counter += 1
            txn_id = f"T{day.strftime('%Y%m%d')}-{txn_counter:05d}"
            hour = rng.choices(
                population=list(range(7, 23)),
                weights=[1, 4, 8, 10, 12, 10, 8, 7, 6, 6, 8, 10, 9, 7, 5, 2],
                k=1,
            )[0]
            minute = rng.randint(0, 59)
            ts = datetime.combine(day, time(hour, minute)).isoformat()
            # items per ticket
            n_items = rng.choices([1, 2, 3, 4], weights=[0.30, 0.40, 0.20, 0.10])[0]
            ticket_items: list[tuple[str, int, float]] = []
            for _ in range(n_items):
                item, price = rng.choice(ITEMS)
                qty = rng.choices([1, 2, 3], weights=[0.8, 0.15, 0.05])[0]
                ticket_items.append((item, qty, price))
            ticket_total = sum(q * p for _, q, p in ticket_items)

            is_void = rng.random() < void_rate
            is_refund = (not is_void) and rng.random() < refund_rate
            payment = "cash" if rng.random() < cash_fraction else rng.choice(["visa", "mada", "mastercard", "apple_pay"])
            staff = rng.choice(STAFF_IDS)

            for item, qty, price in ticket_items:
                line_total = qty * price
                rows.append([
                    txn_id,
                    ts,
                    "MAIN",
                    item,
                    "beverage" if "Latte" in item or "Coffee" in item or "Mocha" in item
                        else "food" if "Sandwich" in item or "Set" in item else "other",
                    qty,
                    f"{price:.2f}",
                    f"{line_total:.2f}",
                    f"{ticket_total:.2f}",
                    "0.00",
                    f"{ticket_total * 0.15:.2f}",
                    "1" if is_void else "0",
                    "0",
                    "1" if is_refund else "0",
                    payment,
                    staff,
                ])

            if not is_void:
                day_rev += ticket_total
                day_txn += 1
                peak_hour_buckets[hour] = peak_hour_buckets.get(hour, 0) + ticket_total
                if payment == "cash":
                    cash_sum += ticket_total
                else:
                    card_sum += ticket_total
            if is_void:
                void_count += 1
            if is_refund:
                refund_count += 1

        daily.append(POSDaily(
            date=day.isoformat(),
            revenue_sar=round(day_rev, 2),
            txn_count=day_txn,
            avg_ticket_sar=round(day_rev / max(1, day_txn), 2),
        ))
        total_revenue += day_rev
        total_txns += day_txn

    # peak hours — top 2 contiguous-ish buckets
    sorted_hours = sorted(peak_hour_buckets.items(), key=lambda x: x[1], reverse=True)[:2]
    peak_hours = [f"{h:02d}:00-{h + 2:02d}:00" for h, _ in sorted(sorted_hours)]

    # trend
    half = len(daily) // 2
    first_avg = sum(d.revenue_sar for d in daily[:half]) / max(1, half)
    second_avg = sum(d.revenue_sar for d in daily[half:]) / max(1, len(daily) - half)
    delta = (second_avg - first_avg) / max(1, first_avg)
    if delta > 0.10: trend = "up"
    elif delta > 0.03: trend = "slightly_up"
    elif delta < -0.10: trend = "down"
    elif delta < -0.03: trend = "slightly_down"
    else: trend = "stable"

    mix_total = cash_sum + card_sum
    cash_mix = cash_sum / max(1, mix_total)

    aggregates = POSAggregates(
        daily_revenue_avg_sar=round(total_revenue / max(1, days), 2),
        monthly_revenue_est_sar=round(total_revenue / max(1, days) * 30, 2),
        avg_ticket_sar=round(total_revenue / max(1, total_txns), 2),
        peak_hours=peak_hours,
        seasonality="weekend_heavy" if weekend_lift > 0.15 else "flat",
        void_rate=round(void_count / max(1, total_txns + void_count), 4),
        refund_rate=round(refund_count / max(1, total_txns), 4),
        cash_card_mix={"cash": round(cash_mix, 2), "card": round(1 - cash_mix, 2)},
        trend_90d=trend,  # type: ignore[arg-type]
    )

    report = POSReport(
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        daily=daily,
        aggregates=aggregates,
        meta=ExtractionMeta(confidence=1.0, source_filename="pos_data.csv"),
    )

    # Render CSV
    out = io.StringIO()
    w = csv.writer(out)
    for r in rows:
        w.writerow(r)
    return out.getvalue().encode("utf-8"), report
