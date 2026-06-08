from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path


VAT_RATE = 0.15
DAYPARTS = ("breakfast", "lunch", "afternoon", "dinner", "late_night")


CITY_CONFIGS = {
    "Riyadh": {"weight": 0.28, "demand_factor": 1.25, "wallet_bias": 0.08, "rent_factor": 1.18, "event_factor": 1.20, "temp_mean": 29.0, "temp_amp": 12.0},
    "Jeddah": {"weight": 0.18, "demand_factor": 1.18, "wallet_bias": 0.10, "rent_factor": 1.12, "event_factor": 1.12, "temp_mean": 31.0, "temp_amp": 7.0},
    "Makkah": {"weight": 0.10, "demand_factor": 1.08, "wallet_bias": 0.05, "rent_factor": 0.98, "event_factor": 1.28, "temp_mean": 32.0, "temp_amp": 9.0},
    "Madinah": {"weight": 0.08, "demand_factor": 0.96, "wallet_bias": 0.04, "rent_factor": 0.92, "event_factor": 1.10, "temp_mean": 30.0, "temp_amp": 10.0},
    "Dammam": {"weight": 0.11, "demand_factor": 1.02, "wallet_bias": 0.07, "rent_factor": 1.00, "event_factor": 1.00, "temp_mean": 30.0, "temp_amp": 10.0},
    "Khobar": {"weight": 0.08, "demand_factor": 0.95, "wallet_bias": 0.09, "rent_factor": 1.05, "event_factor": 1.02, "temp_mean": 29.0, "temp_amp": 9.0},
    "Abha": {"weight": 0.05, "demand_factor": 0.82, "wallet_bias": 0.03, "rent_factor": 0.82, "event_factor": 0.90, "temp_mean": 19.0, "temp_amp": 6.0},
    "AlUla": {"weight": 0.04, "demand_factor": 0.78, "wallet_bias": 0.05, "rent_factor": 0.88, "event_factor": 1.18, "temp_mean": 24.0, "temp_amp": 10.0},
    "Taif": {"weight": 0.08, "demand_factor": 0.88, "wallet_bias": 0.03, "rent_factor": 0.85, "event_factor": 0.96, "temp_mean": 22.0, "temp_amp": 8.0},
}


ARCHETYPES = {
    "specialty_coffee_kiosk": {
        "weight": 0.19, "base_orders": (95, 230), "base_ticket": (14.0, 28.0),
        "dayparts": {"breakfast": 0.34, "lunch": 0.16, "afternoon": 0.27, "dinner": 0.17, "late_night": 0.06},
        "weekday": [0.96, 0.98, 1.00, 1.03, 1.18, 1.24, 0.94],
        "channel": {"dine_in": 0.18, "takeaway": 0.66, "delivery": 0.16},
        "quality_refund_base": 0.007, "cogs_ratio": (0.26, 0.34), "rent_ratio": (0.09, 0.14), "payroll_ratio": (0.14, 0.22),
        "platform_fee_rate": (0.10, 0.16), "card_fee_rate": (0.010, 0.019), "wallet_fee_rate": (0.005, 0.012),
        "promo_frequency": 0.18, "weather_sensitivity": 0.80, "ideal_temp": 24.0, "weekend_dine_in_boost": 0.04,
        "allowed_promos": ("coffee_pastry_combo", "loyalty_redemption", "traffic_discount"),
        "channel_ticket_mult": {"dine_in": 1.10, "takeaway": 0.92, "delivery": 1.04},
    },
    "neighborhood_cafe": {
        "weight": 0.18, "base_orders": (70, 180), "base_ticket": (20.0, 40.0),
        "dayparts": {"breakfast": 0.20, "lunch": 0.15, "afternoon": 0.26, "dinner": 0.25, "late_night": 0.14},
        "weekday": [0.92, 0.95, 0.99, 1.02, 1.18, 1.28, 0.96],
        "channel": {"dine_in": 0.34, "takeaway": 0.42, "delivery": 0.24},
        "quality_refund_base": 0.009, "cogs_ratio": (0.28, 0.37), "rent_ratio": (0.10, 0.17), "payroll_ratio": (0.18, 0.27),
        "platform_fee_rate": (0.12, 0.19), "card_fee_rate": (0.010, 0.019), "wallet_fee_rate": (0.005, 0.012),
        "promo_frequency": 0.15, "weather_sensitivity": 0.72, "ideal_temp": 25.0, "weekend_dine_in_boost": 0.10,
        "allowed_promos": ("coffee_pastry_combo", "loyalty_redemption", "free_delivery"),
        "channel_ticket_mult": {"dine_in": 1.14, "takeaway": 0.95, "delivery": 1.08},
    },
    "bakery_patisserie": {
        "weight": 0.12, "base_orders": (75, 195), "base_ticket": (16.0, 30.0),
        "dayparts": {"breakfast": 0.31, "lunch": 0.14, "afternoon": 0.23, "dinner": 0.22, "late_night": 0.10},
        "weekday": [0.98, 1.00, 1.01, 1.02, 1.16, 1.20, 0.93],
        "channel": {"dine_in": 0.14, "takeaway": 0.71, "delivery": 0.15},
        "quality_refund_base": 0.006, "cogs_ratio": (0.30, 0.40), "rent_ratio": (0.08, 0.13), "payroll_ratio": (0.13, 0.21),
        "platform_fee_rate": (0.09, 0.16), "card_fee_rate": (0.010, 0.019), "wallet_fee_rate": (0.005, 0.012),
        "promo_frequency": 0.21, "weather_sensitivity": 0.65, "ideal_temp": 23.0, "weekend_dine_in_boost": 0.02,
        "allowed_promos": ("coffee_pastry_combo", "clearance", "loyalty_redemption"),
        "channel_ticket_mult": {"dine_in": 1.02, "takeaway": 0.94, "delivery": 1.07},
    },
    "quick_service_restaurant": {
        "weight": 0.22, "base_orders": (120, 340), "base_ticket": (20.0, 42.0),
        "dayparts": {"breakfast": 0.08, "lunch": 0.34, "afternoon": 0.16, "dinner": 0.28, "late_night": 0.14},
        "weekday": [1.05, 1.07, 1.06, 1.05, 1.10, 1.16, 0.96],
        "channel": {"dine_in": 0.30, "takeaway": 0.41, "delivery": 0.29},
        "quality_refund_base": 0.010, "cogs_ratio": (0.31, 0.39), "rent_ratio": (0.09, 0.15), "payroll_ratio": (0.15, 0.24),
        "platform_fee_rate": (0.12, 0.19), "card_fee_rate": (0.010, 0.019), "wallet_fee_rate": (0.005, 0.012),
        "promo_frequency": 0.17, "weather_sensitivity": 0.60, "ideal_temp": 27.0, "weekend_dine_in_boost": 0.05,
        "allowed_promos": ("traffic_discount", "bundle_meal", "free_delivery"),
        "channel_ticket_mult": {"dine_in": 1.00, "takeaway": 0.93, "delivery": 1.12},
    },
    "casual_dining_restaurant": {
        "weight": 0.15, "base_orders": (55, 150), "base_ticket": (38.0, 82.0),
        "dayparts": {"breakfast": 0.02, "lunch": 0.22, "afternoon": 0.12, "dinner": 0.44, "late_night": 0.20},
        "weekday": [0.90, 0.93, 0.97, 1.00, 1.23, 1.34, 0.98],
        "channel": {"dine_in": 0.52, "takeaway": 0.18, "delivery": 0.30},
        "quality_refund_base": 0.011, "cogs_ratio": (0.28, 0.36), "rent_ratio": (0.11, 0.18), "payroll_ratio": (0.19, 0.30),
        "platform_fee_rate": (0.12, 0.20), "card_fee_rate": (0.010, 0.019), "wallet_fee_rate": (0.005, 0.012),
        "promo_frequency": 0.10, "weather_sensitivity": 0.68, "ideal_temp": 26.0, "weekend_dine_in_boost": 0.18,
        "allowed_promos": ("bundle_meal", "traffic_discount", "loyalty_redemption"),
        "channel_ticket_mult": {"dine_in": 1.18, "takeaway": 0.88, "delivery": 1.09},
    },
    "delivery_first_kitchen": {
        "weight": 0.14, "base_orders": (85, 260), "base_ticket": (22.0, 50.0),
        "dayparts": {"breakfast": 0.04, "lunch": 0.24, "afternoon": 0.13, "dinner": 0.35, "late_night": 0.24},
        "weekday": [0.98, 1.00, 1.02, 1.03, 1.08, 1.12, 1.00],
        "channel": {"dine_in": 0.03, "takeaway": 0.16, "delivery": 0.81},
        "quality_refund_base": 0.017, "cogs_ratio": (0.32, 0.42), "rent_ratio": (0.05, 0.09), "payroll_ratio": (0.14, 0.23),
        "platform_fee_rate": (0.16, 0.24), "card_fee_rate": (0.010, 0.019), "wallet_fee_rate": (0.005, 0.012),
        "promo_frequency": 0.22, "weather_sensitivity": 0.35, "ideal_temp": 29.0, "weekend_dine_in_boost": 0.00,
        "allowed_promos": ("free_delivery", "traffic_discount", "bundle_meal"),
        "channel_ticket_mult": {"dine_in": 1.00, "takeaway": 0.90, "delivery": 1.14},
    },
}


SCENARIOS = {
    "stable_healthy_operator": {"weight": 0.22, "growth_daily": (0.0000, 0.0003), "quality_shift": 0.08, "capacity_shift": 0.08, "promo_shift": -0.02, "cash_stress_bias": -0.18, "refund_shift": -0.002, "owner_support": 0.75, "deposit_delay_shift": -1, "leakage_rate": 0.0},
    "fast_growing_store": {"weight": 0.12, "growth_daily": (0.0005, 0.0012), "quality_shift": 0.03, "capacity_shift": -0.05, "promo_shift": 0.03, "cash_stress_bias": -0.04, "refund_shift": 0.001, "owner_support": 0.70, "deposit_delay_shift": 0, "leakage_rate": 0.0},
    "seasonal_cafe": {"weight": 0.09, "growth_daily": (-0.0001, 0.0002), "quality_shift": 0.02, "capacity_shift": 0.02, "promo_shift": 0.00, "cash_stress_bias": -0.02, "refund_shift": 0.000, "owner_support": 0.62, "deposit_delay_shift": 0, "leakage_rate": 0.0},
    "promotion_dependent_merchant": {"weight": 0.11, "growth_daily": (-0.0001, 0.0002), "quality_shift": -0.01, "capacity_shift": 0.00, "promo_shift": 0.10, "cash_stress_bias": 0.02, "refund_shift": 0.002, "owner_support": 0.56, "deposit_delay_shift": 0, "leakage_rate": 0.0},
    "capacity_constrained_lunch_business": {"weight": 0.08, "growth_daily": (0.0000, 0.0004), "quality_shift": -0.03, "capacity_shift": -0.18, "promo_shift": -0.01, "cash_stress_bias": 0.03, "refund_shift": 0.004, "owner_support": 0.45, "deposit_delay_shift": 0, "leakage_rate": 0.0},
    "delivery_heavy_operator": {"weight": 0.10, "growth_daily": (-0.0001, 0.0003), "quality_shift": -0.02, "capacity_shift": 0.03, "promo_shift": 0.05, "cash_stress_bias": 0.02, "refund_shift": 0.005, "owner_support": 0.52, "deposit_delay_shift": 0, "leakage_rate": 0.0},
    "margin_squeezed_merchant": {"weight": 0.09, "growth_daily": (-0.0003, 0.0001), "quality_shift": -0.03, "capacity_shift": -0.02, "promo_shift": 0.02, "cash_stress_bias": 0.10, "refund_shift": 0.001, "owner_support": 0.38, "deposit_delay_shift": 1, "leakage_rate": 0.0},
    "liquidity_stressed_merchant": {"weight": 0.08, "growth_daily": (-0.0004, 0.0000), "quality_shift": -0.05, "capacity_shift": -0.06, "promo_shift": 0.02, "cash_stress_bias": 0.24, "refund_shift": 0.003, "owner_support": 0.22, "deposit_delay_shift": 1, "leakage_rate": 0.0},
    "cash_leakage_or_settlement_mismatch": {"weight": 0.05, "growth_daily": (-0.0002, 0.0002), "quality_shift": -0.01, "capacity_shift": 0.00, "promo_shift": 0.01, "cash_stress_bias": 0.08, "refund_shift": 0.001, "owner_support": 0.28, "deposit_delay_shift": 2, "leakage_rate": 0.03},
    "recovery_merchant": {"weight": 0.06, "growth_daily": (0.0002, 0.0008), "quality_shift": -0.02, "capacity_shift": 0.01, "promo_shift": 0.01, "cash_stress_bias": 0.06, "refund_shift": 0.001, "owner_support": 0.55, "deposit_delay_shift": 0, "leakage_rate": 0.0},
}


PROMOTIONS = {
    "traffic_discount": {"traffic_lift": (0.08, 0.22), "discount_rate": (0.08, 0.18), "basket_lift": (0.00, 0.03), "complexity": 0.28},
    "bundle_meal": {"traffic_lift": (0.05, 0.16), "discount_rate": (0.05, 0.11), "basket_lift": (0.04, 0.08), "complexity": 0.18},
    "coffee_pastry_combo": {"traffic_lift": (0.04, 0.12), "discount_rate": (0.04, 0.09), "basket_lift": (0.06, 0.12), "complexity": 0.14},
    "loyalty_redemption": {"traffic_lift": (0.01, 0.05), "discount_rate": (0.02, 0.06), "basket_lift": (0.00, 0.02), "complexity": 0.08},
    "free_delivery": {"traffic_lift": (0.05, 0.14), "discount_rate": (0.02, 0.05), "basket_lift": (0.02, 0.05), "complexity": 0.20},
    "clearance": {"traffic_lift": (0.00, 0.04), "discount_rate": (0.10, 0.24), "basket_lift": (-0.08, -0.02), "complexity": 0.10},
}


ADJECTIVES = ["Amber", "Basil", "Cedar", "Crown", "Desert", "Golden", "Harbor", "Juniper", "Linen", "Maple", "Nomad", "Olive", "Palm", "Pearl", "Saffron", "Sage", "Silver", "Sunset", "Velvet", "Wadi"]
NOUNS_BY_ARCHETYPE = {
    "specialty_coffee_kiosk": ["Roasters", "Bean Bar", "Brew Lab", "Drip House"],
    "neighborhood_cafe": ["Cafe", "Social House", "Corner", "Lounge"],
    "bakery_patisserie": ["Bakehouse", "Oven", "Patisserie", "Dough Room"],
    "quick_service_restaurant": ["Kitchen", "Bites", "Express", "Grill"],
    "casual_dining_restaurant": ["Table", "Kitchen", "Eatery", "Bistro"],
    "delivery_first_kitchen": ["Cloud Kitchen", "Delivery Lab", "Kitchen Co", "Express"],
}


RAMADAN_WINDOWS = {2025: (date(2025, 3, 1), date(2025, 3, 29)), 2026: (date(2026, 2, 18), date(2026, 3, 19))}
EID_FITR_WINDOWS = {2025: (date(2025, 3, 30), date(2025, 4, 2)), 2026: (date(2026, 3, 20), date(2026, 3, 22))}
EID_ADHA_WINDOWS = {2025: (date(2025, 6, 5), date(2025, 6, 8)), 2026: (date(2026, 5, 27), date(2026, 5, 30))}


@dataclass
class DayContext:
    current_date: date
    city: str
    is_weekend: bool
    payday_factor: float
    school_break: bool
    regime: str
    special_event_factor: float
    temp_c: float
    storm_level: float
    heat_index: float
    cool_index: float
    month_seasonality: float


@dataclass
class Merchant:
    merchant_id: str
    legal_name: str
    vat_number: str
    city: str
    archetype: str
    scenario: str
    base_daily_orders: float
    base_ticket: float
    quality_score: float
    capacity_index: float
    growth_daily: float
    digital_propensity: float
    wallet_bias: float
    delivery_share_target: float
    rent_monthly: float
    payroll_monthly: float
    utilities_monthly: float
    cogs_ratio: float
    platform_fee_rate: float
    card_fee_rate: float
    wallet_fee_rate: float
    cash_deposit_frequency: int
    cash_deposit_threshold: float
    card_lag: int
    wallet_lag: int
    opening_balance: float
    loan_payment: float
    owner_support: float
    owner_support_limit: float
    weather_sensitivity: float
    seasonality_amp: float
    scenario_refund_shift: float
    scenario_promo_shift: float
    leakage_rate: float
    weekday_strength: float
    initial_cogs_due: float
    initial_tax_due: float


@dataclass
class MerchantState:
    closing_balance: float
    health_index: float = 1.0
    cash_stress: float = 0.0
    promo_pressure: float = 0.0
    cash_on_hand: float = 0.0
    recent_queue: float = 0.0
    scheduled_inflows: defaultdict = field(default_factory=lambda: defaultdict(float))
    scheduled_outflows: defaultdict = field(default_factory=lambda: defaultdict(float))
    scheduled_refunds: defaultdict = field(default_factory=lambda: defaultdict(float))
    monthly_cogs: defaultdict = field(default_factory=lambda: defaultdict(float))
    monthly_vat: defaultdict = field(default_factory=lambda: defaultdict(float))
    carryover: defaultdict = field(default_factory=lambda: defaultdict(float))
    owner_injections: float = 0.0


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def round_money(value: float) -> float:
    return round(value + 1e-9, 2)


def daterange(start_date: date, end_date: date) -> list[date]:
    days = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)
    return days


def month_key(current_date: date) -> str:
    return f"{current_date.year:04d}-{current_date.month:02d}"


def previous_month_start(current_date: date) -> date:
    first = current_date.replace(day=1)
    previous_last = first - timedelta(days=1)
    return previous_last.replace(day=1)


def weighted_choice(rng: random.Random, weighted_items: list[tuple[str, float]]) -> str:
    total = sum(weight for _, weight in weighted_items)
    threshold = rng.random() * total
    cumulative = 0.0
    for item, weight in weighted_items:
        cumulative += weight
        if cumulative >= threshold:
            return item
    return weighted_items[-1][0]


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    adjusted = {key: max(0.0001, value) for key, value in weights.items()}
    total = sum(adjusted.values())
    return {key: value / total for key, value in adjusted.items()}


def poisson_sample(lam: float, rng: random.Random) -> int:
    if lam <= 0:
        return 0
    if lam < 30:
        limit = math.exp(-lam)
        k = 0
        product = 1.0
        while product > limit:
            k += 1
            product *= rng.random()
        return k - 1
    return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))


def negative_binomial_sample(mean: float, dispersion: float, rng: random.Random) -> int:
    if mean <= 0:
        return 0
    shape = max(0.8, dispersion)
    scale = mean / shape
    lam = rng.gammavariate(shape, scale)
    return poisson_sample(lam, rng)


def allocate_counts(total: int, weights: dict[str, float]) -> dict[str, int]:
    if total <= 0:
        return {key: 0 for key in weights}
    normalized = normalize_weights(weights)
    raw = {key: total * value for key, value in normalized.items()}
    counts = {key: int(math.floor(value)) for key, value in raw.items()}
    remainder = total - sum(counts.values())
    if remainder > 0:
        residuals = sorted(((raw[key] - counts[key], key) for key in counts), reverse=True)
        for _, key in residuals[:remainder]:
            counts[key] += 1
    return counts


def generate_merchant_name(archetype: str, city: str, index: int, rng: random.Random) -> str:
    adjective = rng.choice(ADJECTIVES)
    noun = rng.choice(NOUNS_BY_ARCHETYPE[archetype])
    city_token = city.replace("Al", "Al ").split()[0]
    return f"{adjective} {city_token} {noun} {index:03d}"


def generate_vat_number(rng: random.Random) -> str:
    middle = "".join(str(rng.randint(0, 9)) for _ in range(13))
    return f"3{middle}3"


def build_city_day_contexts(dates: list[date], seed: int) -> dict[str, dict[date, DayContext]]:
    contexts: dict[str, dict[date, DayContext]] = {city: {} for city in CITY_CONFIGS}
    for city_index, (city, config) in enumerate(CITY_CONFIGS.items()):
        rng = random.Random(seed + city_index * 10_000)
        for current_date in dates:
            day_of_year = current_date.timetuple().tm_yday
            seasonal_wave = math.sin((2 * math.pi * (day_of_year - 172)) / 365.25)
            temp_c = config["temp_mean"] + config["temp_amp"] * seasonal_wave + rng.gauss(0.0, 1.5)

            storm_probability = 0.02
            if current_date.month in (3, 4, 11):
                storm_probability += 0.05
            if city in {"Abha", "Taif"} and current_date.month in (7, 8):
                storm_probability += 0.06
            storm_level = rng.uniform(0.25, 0.85) if rng.random() < storm_probability else 0.0

            regime = "normal"
            if current_date in (date(2025, 2, 22), date(2026, 2, 22)):
                regime = "founding_day"
            if current_date in (date(2025, 3, 11), date(2026, 3, 11)):
                regime = "flag_day"
            if current_date in (date(2025, 9, 23), date(2026, 9, 23)):
                regime = "national_day"
            for start, end in RAMADAN_WINDOWS.values():
                if start <= current_date <= end:
                    regime = "ramadan"
            for start, end in EID_FITR_WINDOWS.values():
                if start <= current_date <= end:
                    regime = "eid_fitr"
            for start, end in EID_ADHA_WINDOWS.values():
                if start <= current_date <= end:
                    regime = "eid_adha"

            special_event_factor = 1.0
            if rng.random() < 0.025 * config["event_factor"]:
                special_event_factor += rng.uniform(0.08, 0.22)
            if regime in {"founding_day", "national_day"}:
                special_event_factor += 0.18
            if regime == "eid_fitr":
                special_event_factor += 0.32
            if regime == "eid_adha":
                special_event_factor += 0.24
            if city in {"Makkah", "Madinah"} and regime in {"ramadan", "eid_fitr", "eid_adha"}:
                special_event_factor += 0.10
            if city == "AlUla" and current_date.month in (1, 2):
                special_event_factor += 0.10

            contexts[city][current_date] = DayContext(
                current_date=current_date,
                city=city,
                is_weekend=current_date.weekday() in (4, 5),
                payday_factor=1.08 if current_date.day in (26, 27, 28) else (0.97 if current_date.day in (1, 2) else 1.0),
                school_break=(current_date.month in (7, 8) or (current_date.month == 12 and current_date.day >= 20) or (current_date.month == 1 and current_date.day <= 5)),
                regime=regime,
                special_event_factor=special_event_factor,
                temp_c=temp_c,
                storm_level=storm_level,
                heat_index=max(0.0, temp_c - 37.0) / 10.0,
                cool_index=max(0.0, 22.0 - temp_c) / 10.0,
                month_seasonality=math.cos((2 * math.pi * (day_of_year - 20)) / 365.25),
            )
    return contexts


def generate_merchants(
    count: int,
    rng: random.Random,
    *,
    fixed_city: str | None = None,
    fixed_archetype: str | None = None,
    fixed_scenario: str | None = None,
    fixed_legal_name: str | None = None,
) -> list[Merchant]:
    city_weights = [(city, config["weight"]) for city, config in CITY_CONFIGS.items()]
    archetype_weights = [(name, config["weight"]) for name, config in ARCHETYPES.items()]
    scenario_weights = [(name, config["weight"]) for name, config in SCENARIOS.items()]
    merchants: list[Merchant] = []
    for index in range(1, count + 1):
        city = fixed_city or weighted_choice(rng, city_weights)
        archetype = fixed_archetype or weighted_choice(rng, archetype_weights)
        scenario = fixed_scenario or weighted_choice(rng, scenario_weights)
        city_cfg = CITY_CONFIGS[city]
        arch_cfg = ARCHETYPES[archetype]
        scen_cfg = SCENARIOS[scenario]

        if scenario == "seasonal_cafe" and archetype not in {"specialty_coffee_kiosk", "neighborhood_cafe", "bakery_patisserie"}:
            archetype = rng.choice(["specialty_coffee_kiosk", "neighborhood_cafe", "bakery_patisserie"])
            arch_cfg = ARCHETYPES[archetype]
        if scenario == "delivery_heavy_operator" and archetype not in {"delivery_first_kitchen", "quick_service_restaurant"}:
            archetype = rng.choice(["delivery_first_kitchen", "quick_service_restaurant"])
            arch_cfg = ARCHETYPES[archetype]

        merchant_id = f"M{index:04d}"
        legal_name = fixed_legal_name or generate_merchant_name(archetype, city, index, rng)
        vat_number = generate_vat_number(rng)
        base_daily_orders = rng.uniform(*arch_cfg["base_orders"]) * city_cfg["demand_factor"]
        if scenario == "fast_growing_store":
            base_daily_orders *= 1.08
        if scenario == "liquidity_stressed_merchant":
            base_daily_orders *= 0.88

        estimated_monthly_sales = base_daily_orders * rng.uniform(*arch_cfg["base_ticket"]) * 30.0 * 0.84
        rent_monthly = round_money(estimated_monthly_sales * rng.uniform(*arch_cfg["rent_ratio"]) * city_cfg["rent_factor"])
        payroll_monthly = round_money(estimated_monthly_sales * rng.uniform(*arch_cfg["payroll_ratio"]))
        utilities_monthly = round_money(estimated_monthly_sales * rng.uniform(0.018, 0.035))
        monthly_fixed = rent_monthly + payroll_monthly + utilities_monthly

        opening_balance_factor = rng.uniform(0.7, 2.2) - scen_cfg["cash_stress_bias"] + (0.5 if scenario == "stable_healthy_operator" else 0.0)
        opening_balance = round_money(max(monthly_fixed * opening_balance_factor, monthly_fixed * 0.35))
        has_loan = rng.random() < 0.42

        merchants.append(
            Merchant(
                merchant_id=merchant_id,
                legal_name=legal_name,
                vat_number=vat_number,
                city=city,
                archetype=archetype,
                scenario=scenario,
                base_daily_orders=base_daily_orders,
                base_ticket=rng.uniform(*arch_cfg["base_ticket"]) * rng.uniform(0.95, 1.08),
                quality_score=clamp(0.95 + scen_cfg["quality_shift"] + rng.uniform(-0.08, 0.08), 0.75, 1.20),
                capacity_index=clamp(1.0 + scen_cfg["capacity_shift"] + rng.uniform(-0.10, 0.12), 0.72, 1.35),
                growth_daily=rng.uniform(*scen_cfg["growth_daily"]),
                digital_propensity=clamp(0.77 + city_cfg["wallet_bias"] + rng.uniform(-0.08, 0.08), 0.60, 0.94),
                wallet_bias=clamp(0.18 + city_cfg["wallet_bias"] + rng.uniform(-0.06, 0.08), 0.08, 0.38),
                delivery_share_target=clamp(arch_cfg["channel"]["delivery"] + rng.uniform(-0.05, 0.06) + (0.16 if scenario == "delivery_heavy_operator" else 0.0), 0.05, 0.88),
                rent_monthly=rent_monthly,
                payroll_monthly=payroll_monthly,
                utilities_monthly=utilities_monthly,
                cogs_ratio=clamp(rng.uniform(*arch_cfg["cogs_ratio"]) + (0.03 if scenario == "margin_squeezed_merchant" else 0.0), 0.22, 0.48),
                platform_fee_rate=clamp(rng.uniform(*arch_cfg["platform_fee_rate"]) + (0.02 if scenario == "delivery_heavy_operator" else 0.0), 0.08, 0.27),
                card_fee_rate=rng.uniform(*arch_cfg["card_fee_rate"]),
                wallet_fee_rate=rng.uniform(*arch_cfg["wallet_fee_rate"]),
                cash_deposit_frequency=int(clamp(round(rng.uniform(1.5, 4.5) + scen_cfg["deposit_delay_shift"]), 1, 7)),
                cash_deposit_threshold=round_money(base_daily_orders * rng.uniform(*arch_cfg["base_ticket"]) * rng.uniform(0.35, 0.90)),
                card_lag=int(clamp(round(rng.uniform(1.0, 2.4)), 1, 3)),
                wallet_lag=int(clamp(round(rng.uniform(0.0, 1.4)), 0, 2)),
                opening_balance=opening_balance,
                loan_payment=round_money(monthly_fixed * rng.uniform(0.10, 0.28)) if has_loan else 0.0,
                owner_support=scen_cfg["owner_support"],
                owner_support_limit=round_money(monthly_fixed * rng.uniform(0.25, 0.90)),
                weather_sensitivity=clamp(arch_cfg["weather_sensitivity"] * rng.uniform(0.85, 1.18), 0.25, 1.00),
                seasonality_amp=clamp(rng.uniform(0.04, 0.12) + (0.10 if scenario == "seasonal_cafe" else 0.0), 0.03, 0.22),
                scenario_refund_shift=scen_cfg["refund_shift"],
                scenario_promo_shift=scen_cfg["promo_shift"],
                leakage_rate=scen_cfg["leakage_rate"] * rng.uniform(0.8, 1.2),
                weekday_strength=rng.uniform(0.95, 1.08),
                initial_cogs_due=round_money(estimated_monthly_sales * 0.88 * clamp(rng.uniform(*arch_cfg["cogs_ratio"]), 0.22, 0.48)),
                initial_tax_due=round_money(estimated_monthly_sales * 0.88 * 0.018),
            )
        )
    return merchants


def daypart_weights(merchant: Merchant, context: DayContext) -> dict[str, float]:
    weights = dict(ARCHETYPES[merchant.archetype]["dayparts"])
    if context.regime == "ramadan":
        if merchant.archetype in {"specialty_coffee_kiosk", "bakery_patisserie"}:
            weights = {"breakfast": 0.04, "lunch": 0.08, "afternoon": 0.24, "dinner": 0.34, "late_night": 0.30}
        elif merchant.archetype == "delivery_first_kitchen":
            weights = {"breakfast": 0.02, "lunch": 0.10, "afternoon": 0.14, "dinner": 0.40, "late_night": 0.34}
        else:
            weights = {"breakfast": 0.03, "lunch": 0.10, "afternoon": 0.16, "dinner": 0.42, "late_night": 0.29}
    elif context.regime in {"eid_fitr", "eid_adha"}:
        weights["dinner"] *= 1.18
        weights["late_night"] *= 1.22
        weights["breakfast"] *= 0.75
    return normalize_weights(weights)


def overall_demand_multiplier(merchant: Merchant, context: DayContext, day_index: int) -> float:
    arch_cfg = ARCHETYPES[merchant.archetype]
    weekday_factor = arch_cfg["weekday"][context.current_date.weekday()] * merchant.weekday_strength
    trend_factor = 1.0 + merchant.growth_daily * day_index
    seasonal_factor = 1.0 + merchant.seasonality_amp * context.month_seasonality

    temperature_distance = abs(context.temp_c - arch_cfg["ideal_temp"])
    weather_factor = 1.0 - merchant.weather_sensitivity * (temperature_distance / 90.0) - 0.06 * context.storm_level
    if merchant.archetype == "delivery_first_kitchen":
        weather_factor += 0.04 * context.heat_index
    if merchant.archetype in {"specialty_coffee_kiosk", "neighborhood_cafe", "bakery_patisserie"}:
        weather_factor += 0.03 * context.cool_index - 0.02 * context.heat_index
    weather_factor = clamp(weather_factor, 0.72, 1.16)

    regime_factor = 1.0
    if context.regime == "ramadan":
        regime_factor = 0.94 if merchant.archetype in {"quick_service_restaurant", "casual_dining_restaurant"} else 0.98
    elif context.regime == "eid_fitr":
        regime_factor = 1.20
    elif context.regime == "eid_adha":
        regime_factor = 1.12
    elif context.regime in {"founding_day", "national_day"}:
        regime_factor = 1.08
    elif context.regime == "flag_day":
        regime_factor = 1.02

    school_break_factor = 1.0
    if context.school_break and merchant.archetype in {"specialty_coffee_kiosk", "neighborhood_cafe", "casual_dining_restaurant"}:
        school_break_factor = 1.05

    return clamp(
        weekday_factor * trend_factor * seasonal_factor * weather_factor * regime_factor * context.payday_factor * context.special_event_factor * school_break_factor * merchant.quality_score,
        0.45,
        2.20,
    )


def choose_promotion(merchant: Merchant, context: DayContext, state: MerchantState, rng: random.Random) -> dict[str, float | str]:
    arch_cfg = ARCHETYPES[merchant.archetype]
    promo_probability = arch_cfg["promo_frequency"] + merchant.scenario_promo_shift
    promo_probability += 0.03 if context.current_date.weekday() in (1, 2) else 0.0
    promo_probability += 0.05 if context.regime in {"ramadan", "national_day", "founding_day"} else 0.0
    promo_probability += 0.03 if state.cash_stress > 0.55 else 0.0
    promo_probability -= min(0.08, state.promo_pressure * 0.02)
    promo_probability = clamp(promo_probability, 0.04, 0.42)
    if rng.random() > promo_probability:
        return {"name": "none", "traffic_lift": 0.0, "discount_rate": 0.0, "basket_lift": 0.0, "complexity": 0.0}

    promo_name = rng.choice(arch_cfg["allowed_promos"])
    promo_cfg = PROMOTIONS[promo_name]
    fatigue = 1.0 - min(0.25, state.promo_pressure * 0.025)
    return {
        "name": promo_name,
        "traffic_lift": rng.uniform(*promo_cfg["traffic_lift"]) * fatigue,
        "discount_rate": rng.uniform(*promo_cfg["discount_rate"]),
        "basket_lift": rng.uniform(*promo_cfg["basket_lift"]),
        "complexity": promo_cfg["complexity"],
    }


def channel_weights(merchant: Merchant, context: DayContext, daypart: str) -> dict[str, float]:
    base = dict(ARCHETYPES[merchant.archetype]["channel"])
    base["delivery"] = clamp(base["delivery"] + (merchant.delivery_share_target - ARCHETYPES[merchant.archetype]["channel"]["delivery"]), 0.02, 0.90)
    if context.heat_index > 0.0 or context.storm_level > 0.0:
        base["delivery"] += 0.10 * max(context.heat_index, context.storm_level)
        base["dine_in"] -= 0.06 * max(context.heat_index, context.storm_level)
    if context.regime == "ramadan":
        base["delivery"] += 0.06
        base["takeaway"] += 0.03
        base["dine_in"] -= 0.05
    if merchant.archetype == "casual_dining_restaurant" and daypart in {"dinner", "late_night"}:
        base["dine_in"] += 0.12
    if merchant.archetype == "quick_service_restaurant" and daypart == "lunch":
        base["takeaway"] += 0.06
    if merchant.archetype == "specialty_coffee_kiosk" and daypart == "breakfast":
        base["takeaway"] += 0.08
    if context.is_weekend:
        base["dine_in"] += ARCHETYPES[merchant.archetype]["weekend_dine_in_boost"]
    return normalize_weights(base)


def tender_weights(merchant: Merchant, context: DayContext, channel: str, avg_ticket: float) -> dict[str, float]:
    digital_total = clamp(merchant.digital_propensity, 0.55, 0.95)
    wallet = clamp(0.12 + merchant.wallet_bias + (0.05 if channel in {"delivery", "takeaway"} else 0.0), 0.06, 0.40)
    cash = clamp((1.0 - digital_total) + (0.08 if avg_ticket < merchant.base_ticket * 0.9 else 0.0), 0.03, 0.32)
    if channel == "delivery":
        cash *= 0.35
        wallet += 0.05
    if context.payday_factor > 1.0:
        wallet += 0.02
        cash -= 0.01
    if merchant.scenario == "cash_leakage_or_settlement_mismatch":
        cash += 0.04
    cash = clamp(cash, 0.02, 0.40)
    wallet = clamp(wallet, 0.07, 0.42)
    card = max(0.05, 1.0 - cash - wallet)
    return normalize_weights({"cash": cash, "card": card, "wallet": wallet})


def maybe_outage(merchant: Merchant, context: DayContext, rng: random.Random) -> bool:
    outage_probability = 0.0025
    if merchant.scenario in {"capacity_constrained_lunch_business", "recovery_merchant"}:
        outage_probability += 0.0015
    if context.regime in {"eid_fitr", "eid_adha"}:
        outage_probability += 0.001
    return rng.random() < outage_probability


def schedule_future_refunds(merchant: Merchant, state: MerchantState, current_date: date, total_future_refunds: float, tender_share: dict[str, float]) -> None:
    if total_future_refunds <= 0:
        return
    lag_weights = normalize_weights({"1": 0.30, "2": 0.24, "3": 0.18, "5": 0.16, "7": 0.12})
    lag_allocations = allocate_counts(100, lag_weights)
    remaining = total_future_refunds
    items = list(lag_allocations.items())
    for index, (lag_text, count) in enumerate(items):
        lag = int(lag_text)
        if count <= 0:
            continue
        refund_amount = round_money(remaining if index == len(items) - 1 else total_future_refunds * (count / 100.0))
        remaining = round_money(max(0.0, remaining - refund_amount))
        if refund_amount <= 0:
            continue
        refund_date = current_date + timedelta(days=lag)
        state.scheduled_refunds[refund_date] += refund_amount
        digital_exposure = tender_share["card"] + tender_share["wallet"] + tender_share["cash"] * 0.35
        reversal_date = refund_date + timedelta(days=0 if tender_share["cash"] < 0.15 else 1)
        state.scheduled_outflows[reversal_date] += round_money(refund_amount * digital_exposure)


def process_cash_deposit(merchant: Merchant, state: MerchantState, current_date: date) -> None:
    if state.cash_on_hand <= 0:
        return
    day_number = (current_date - date(2025, 1, 1)).days
    should_deposit = state.cash_on_hand >= merchant.cash_deposit_threshold or day_number % merchant.cash_deposit_frequency == 0 or current_date.weekday() == 3
    if not should_deposit:
        return
    leakage = round_money(state.cash_on_hand * merchant.leakage_rate)
    depositable = max(0.0, state.cash_on_hand - leakage)
    deposit_amount = round_money(depositable * 0.92)
    if deposit_amount <= 0:
        state.cash_on_hand = 0.0
        return
    state.scheduled_inflows[current_date] += deposit_amount
    state.cash_on_hand = round_money(max(0.0, state.cash_on_hand - deposit_amount - leakage))


def due_obligations_for_day(merchant: Merchant, state: MerchantState, current_date: date) -> list[tuple[str, float]]:
    due: list[tuple[str, float]] = []
    previous_month = month_key(previous_month_start(current_date))
    if current_date.day == 1:
        due.append(("rent", round_money(merchant.rent_monthly + state.carryover["rent"])))
    if current_date.day == 7:
        due.append(("supplier", round_money(state.monthly_cogs.get(previous_month, merchant.initial_cogs_due) + state.carryover["supplier"])))
    if current_date.day == 12 and merchant.loan_payment > 0:
        due.append(("loan", round_money(merchant.loan_payment + state.carryover["loan"])))
    if current_date.day == 15:
        due.append(("tax", round_money(state.monthly_vat.get(previous_month, merchant.initial_tax_due) + state.carryover["tax"])))
    if current_date.day == 27:
        due.append(("payroll", round_money(merchant.payroll_monthly + state.carryover["payroll"])))
    return [(obligation_type, amount) for obligation_type, amount in due if amount > 0]


def process_obligation_payments(
    merchant: Merchant,
    state: MerchantState,
    current_date: date,
    opening_balance: float,
    inflows_before: float,
    outflows_before: float,
    due_items: list[tuple[str, float]],
    rng: random.Random,
) -> tuple[list[tuple[str, str, str, float, float, str]], float, float]:
    rows: list[tuple[str, str, str, float, float, str]] = []
    paid_total = 0.0
    owner_injection = 0.0
    reserve_buffer = (merchant.rent_monthly + merchant.payroll_monthly + merchant.utilities_monthly) / 55.0
    reserve_buffer *= 1.0 + state.cash_stress * 0.8
    priority_order = {"payroll": 1, "rent": 2, "loan": 3, "tax": 4, "supplier": 5}
    for obligation_type, amount_due in sorted(due_items, key=lambda item: priority_order[item[0]]):
        available = round_money(max(0.0, opening_balance + inflows_before + owner_injection - outflows_before - paid_total - reserve_buffer))
        if available < amount_due:
            shortage = round_money(amount_due - available)
            if shortage > 0 and merchant.owner_support > rng.random():
                if obligation_type in {"rent", "payroll", "loan"} or state.cash_stress < 0.55:
                    injected = min(shortage, merchant.owner_support_limit - owner_injection)
                    if injected > 0:
                        owner_injection = round_money(owner_injection + injected)
                        available = round_money(available + injected)

        payment_bias = 1.0
        if merchant.scenario in {"liquidity_stressed_merchant", "margin_squeezed_merchant"} and obligation_type in {"supplier", "tax"}:
            payment_bias = rng.uniform(0.50, 0.95)
        if merchant.scenario == "cash_leakage_or_settlement_mismatch" and obligation_type == "supplier":
            payment_bias = rng.uniform(0.40, 0.85)

        affordable = round_money(max(0.0, opening_balance + inflows_before + owner_injection - outflows_before - paid_total - reserve_buffer))
        amount_paid = round_money(min(amount_due * payment_bias, affordable))
        if (
            amount_paid < amount_due * 0.08
            and merchant.scenario in {"liquidity_stressed_merchant", "cash_leakage_or_settlement_mismatch", "margin_squeezed_merchant"}
            and obligation_type in {"supplier", "tax", "loan"}
        ):
            amount_paid = 0.0
        if amount_paid >= amount_due - 0.01:
            amount_paid = round_money(amount_due)
            status = "paid"
            state.carryover[obligation_type] = 0.0
        elif amount_paid <= 0.0:
            amount_paid = 0.0
            status = "overdue"
            state.carryover[obligation_type] = round_money(amount_due)
        else:
            status = "partial"
            state.carryover[obligation_type] = round_money(amount_due - amount_paid)

        rows.append((merchant.merchant_id, current_date.isoformat(), obligation_type, amount_due, amount_paid, status))
        paid_total = round_money(paid_total + amount_paid)
    return rows, paid_total, owner_injection


def simulate_dataset(
    merchants: list[Merchant],
    dates: list[date],
    city_day_contexts: dict[str, dict[date, DayContext]],
    seed: int,
) -> tuple[dict[str, list[tuple]], dict]:
    merchants_rows: list[tuple] = []
    latent_rows: list[tuple] = []
    sales_rows: list[tuple] = []
    payments_rows: list[tuple] = []
    bank_rows: list[tuple] = []
    obligations_rows: list[tuple] = []

    archetype_counter = Counter()
    scenario_counter = Counter()
    city_counter = Counter()
    totals = defaultdict(float)
    bank_identity_error = 0.0
    payment_identity_error = 0.0
    sales_identity_error = 0.0

    for merchant_index, merchant in enumerate(merchants):
        merchant_rng = random.Random(seed + (merchant_index + 1) * 13_579)
        state = MerchantState(
            closing_balance=merchant.opening_balance,
            health_index=clamp(1.0 + (merchant.quality_score - 1.0) * 0.8, 0.82, 1.18),
            cash_stress=clamp(SCENARIOS[merchant.scenario]["cash_stress_bias"] + 0.20, 0.02, 0.72),
        )

        merchants_rows.append((merchant.merchant_id, merchant.legal_name, merchant.vat_number, merchant.city))
        latent_rows.append(
            (
                merchant.merchant_id,
                merchant.archetype,
                merchant.scenario,
                round(merchant.base_daily_orders, 2),
                round(merchant.base_ticket, 2),
                round(merchant.digital_propensity, 4),
                round(merchant.wallet_bias, 4),
                round(merchant.delivery_share_target, 4),
                round(merchant.quality_score, 4),
                round(merchant.capacity_index, 4),
                merchant.rent_monthly,
                merchant.payroll_monthly,
                merchant.utilities_monthly,
                round(merchant.cogs_ratio, 4),
                merchant.opening_balance,
                merchant.loan_payment,
            )
        )
        archetype_counter[merchant.archetype] += 1
        scenario_counter[merchant.scenario] += 1
        city_counter[merchant.city] += 1

        for day_index, current_date in enumerate(dates):
            context = city_day_contexts[merchant.city][current_date]
            arch_cfg = ARCHETYPES[merchant.archetype]
            promotion = choose_promotion(merchant, context, state, merchant_rng)
            outage_flag = maybe_outage(merchant, context, merchant_rng)
            staffing_factor = clamp(1.02 + (merchant.quality_score - 1.0) - state.cash_stress * 0.15 + merchant_rng.uniform(-0.06, 0.06), 0.76, 1.22)
            demand_multiplier = overall_demand_multiplier(merchant, context, day_index) * (1.0 + promotion["traffic_lift"])
            if outage_flag:
                demand_multiplier *= 0.72
                staffing_factor *= 0.82

            gross_sales = 0.0
            discounts = 0.0
            captured_sales_before_refunds = 0.0
            immediate_refunds = 0.0
            orders_count = 0
            queue_signal = 0.0
            delivery_net_sales = 0.0
            tender_amounts = {"cash": 0.0, "card": 0.0, "wallet": 0.0}
            collectible_total = 0.0

            for daypart, weight in daypart_weights(merchant, context).items():
                daypart_mean = merchant.base_daily_orders * weight * demand_multiplier * state.health_index
                if merchant.scenario == "capacity_constrained_lunch_business" and daypart == "lunch":
                    daypart_mean *= 1.18
                if merchant.scenario == "recovery_merchant" and day_index < len(dates) * 0.30:
                    daypart_mean *= 0.88
                if merchant.scenario == "recovery_merchant" and day_index > len(dates) * 0.65:
                    daypart_mean *= 1.08

                arrivals = negative_binomial_sample(daypart_mean, dispersion=12.0, rng=merchant_rng)
                base_capacity = merchant.base_daily_orders * weight * merchant.capacity_index * staffing_factor
                if merchant.scenario == "capacity_constrained_lunch_business" and daypart == "lunch":
                    base_capacity *= 0.72
                if context.regime == "ramadan" and daypart in {"dinner", "late_night"}:
                    base_capacity *= 1.10
                effective_capacity = max(0, int(round(base_capacity)))
                fulfilled = min(arrivals, effective_capacity)
                orders_count += fulfilled
                queue_pressure = 0.0 if effective_capacity <= 0 else max(0.0, arrivals - effective_capacity) / effective_capacity
                queue_signal += queue_pressure * weight
                if fulfilled <= 0:
                    continue

                for channel, channel_orders in allocate_counts(fulfilled, channel_weights(merchant, context, daypart)).items():
                    if channel_orders <= 0:
                        continue
                    base_avg_ticket = merchant.base_ticket * arch_cfg["channel_ticket_mult"][channel]
                    if daypart == "breakfast":
                        base_avg_ticket *= 0.92
                    elif daypart == "afternoon":
                        base_avg_ticket *= 0.98
                    elif daypart == "dinner":
                        base_avg_ticket *= 1.08
                    elif daypart == "late_night":
                        base_avg_ticket *= 1.05
                    if context.regime == "ramadan" and daypart in {"dinner", "late_night"}:
                        base_avg_ticket *= 1.10
                    if context.regime in {"eid_fitr", "eid_adha"} and channel == "dine_in":
                        base_avg_ticket *= 1.07
                    if context.heat_index > 0.0 and merchant.archetype in {"specialty_coffee_kiosk", "neighborhood_cafe"}:
                        base_avg_ticket *= 1.02

                    avg_ticket = base_avg_ticket * (1.0 + promotion["basket_lift"]) * merchant_rng.uniform(0.92, 1.10)
                    gross_line = round_money(channel_orders * avg_ticket)
                    base_discount_rate = merchant_rng.uniform(0.003, 0.018)
                    promo_discount_rate = promotion["discount_rate"]
                    if promotion["name"] == "clearance" and daypart not in {"afternoon", "dinner"}:
                        promo_discount_rate *= 0.30
                    if promotion["name"] == "free_delivery" and channel != "delivery":
                        promo_discount_rate *= 0.25
                    if promotion["name"] == "coffee_pastry_combo" and merchant.archetype not in {"specialty_coffee_kiosk", "neighborhood_cafe", "bakery_patisserie"}:
                        promo_discount_rate *= 0.35
                    discounts_line = round_money(gross_line * clamp(base_discount_rate + promo_discount_rate, 0.0, 0.34))
                    net_line = round_money(gross_line - discounts_line)

                    refund_rate = arch_cfg["quality_refund_base"] + merchant.scenario_refund_shift + queue_pressure * 0.025 + promotion["complexity"] * 0.006 + (0.018 if outage_flag else 0.0) + (0.006 if channel == "delivery" else 0.0)
                    refund_rate -= (merchant.quality_score - 1.0) * 0.015
                    refund_rate = clamp(refund_rate, 0.003, 0.085)
                    immediate_line_refund = round_money(net_line * refund_rate * (0.18 if channel == "delivery" else 0.28))
                    delayed_refund_pool = round_money(net_line * refund_rate - immediate_line_refund)

                    tender_split = tender_weights(merchant, context, channel, avg_ticket)
                    collectible_line = round_money(max(0.0, net_line - immediate_line_refund))
                    for tender, share in tender_split.items():
                        tender_amounts[tender] += collectible_line * share
                    collectible_total += collectible_line

                    if delayed_refund_pool > 0:
                        schedule_future_refunds(merchant, state, current_date, delayed_refund_pool, tender_split)

                    gross_sales += gross_line
                    discounts += discounts_line
                    captured_sales_before_refunds += net_line
                    immediate_refunds += immediate_line_refund
                    if channel == "delivery":
                        delivery_net_sales += collectible_line

            pending_refunds = round_money(state.scheduled_refunds.pop(current_date, 0.0))
            refunds_amount = round_money(immediate_refunds + pending_refunds)
            net_sales = round_money(gross_sales - discounts - refunds_amount)
            vat_amount = round_money(max(0.0, net_sales) * VAT_RATE)

            if collectible_total > 0:
                target_collect = round_money(max(0.0, captured_sales_before_refunds - immediate_refunds))
                scale = target_collect / collectible_total
                for tender in tender_amounts:
                    tender_amounts[tender] = round_money(tender_amounts[tender] * scale)
            total_collected = round_money(tender_amounts["cash"] + tender_amounts["card"] + tender_amounts["wallet"])
            avg_ticket_value = 0.0 if orders_count <= 0 else round_money((gross_sales - discounts) / orders_count)

            sales_rows.append((merchant.merchant_id, current_date.isoformat(), round_money(gross_sales), round_money(discounts), net_sales, vat_amount, refunds_amount, orders_count, avg_ticket_value))
            payments_rows.append((merchant.merchant_id, current_date.isoformat(), tender_amounts["cash"], tender_amounts["card"], tender_amounts["wallet"], total_collected))

            payment_identity_error = max(payment_identity_error, abs(total_collected - round_money(tender_amounts["cash"] + tender_amounts["card"] + tender_amounts["wallet"])))
            sales_identity_error = max(sales_identity_error, abs(net_sales - round_money(gross_sales - discounts - refunds_amount)))

            state.monthly_cogs[month_key(current_date)] += round_money((gross_sales - discounts) * merchant.cogs_ratio)
            state.monthly_vat[month_key(current_date)] += vat_amount
            state.cash_on_hand = round_money(state.cash_on_hand + tender_amounts["cash"])
            process_cash_deposit(merchant, state, current_date)

            if tender_amounts["card"] > 0:
                settle_date = current_date + timedelta(days=merchant.card_lag)
                state.scheduled_inflows[settle_date] += round_money(tender_amounts["card"])
                state.scheduled_outflows[settle_date] += round_money(tender_amounts["card"] * merchant.card_fee_rate)
            if tender_amounts["wallet"] > 0:
                settle_date = current_date + timedelta(days=merchant.wallet_lag)
                state.scheduled_inflows[settle_date] += round_money(tender_amounts["wallet"])
                state.scheduled_outflows[settle_date] += round_money(tender_amounts["wallet"] * merchant.wallet_fee_rate)
            if delivery_net_sales > 0:
                state.scheduled_outflows[current_date + timedelta(days=1)] += round_money(delivery_net_sales * merchant.platform_fee_rate)
            if current_date.weekday() == 0:
                state.scheduled_outflows[current_date] += round_money(merchant.utilities_monthly / 4.2)
            if current_date.weekday() == 2:
                state.scheduled_outflows[current_date] += round_money((merchant.rent_monthly + merchant.payroll_monthly) * 0.003)

            opening_balance = round_money(state.closing_balance)
            inflows = round_money(state.scheduled_inflows.pop(current_date, 0.0))
            outflows = round_money(state.scheduled_outflows.pop(current_date, 0.0))
            due_items = due_obligations_for_day(merchant, state, current_date)
            obligation_records, obligation_paid, owner_injection = process_obligation_payments(merchant, state, current_date, opening_balance, inflows, outflows, due_items, merchant_rng)
            if owner_injection > 0:
                inflows = round_money(inflows + owner_injection)
                state.owner_injections = round_money(state.owner_injections + owner_injection)
            outflows = round_money(outflows + obligation_paid)
            closing_balance = round_money(opening_balance + inflows - outflows)
            if closing_balance < 0.0:
                emergency_injection = round_money(abs(closing_balance) + merchant.utilities_monthly / 10.0)
                inflows = round_money(inflows + emergency_injection)
                closing_balance = round_money(opening_balance + inflows - outflows)
                state.owner_injections = round_money(state.owner_injections + emergency_injection)

            for record in obligation_records:
                obligations_rows.append(record)
                totals["obligations_due"] += record[3]
                totals["obligations_paid"] += record[4]

            bank_rows.append((merchant.merchant_id, current_date.isoformat(), opening_balance, inflows, outflows, closing_balance))
            bank_identity_error = max(bank_identity_error, abs(closing_balance - round_money(opening_balance + inflows - outflows)))

            totals["gross_sales"] += gross_sales
            totals["net_sales"] += net_sales
            totals["payments_collected"] += total_collected
            totals["bank_inflows"] += inflows
            totals["bank_outflows"] += outflows

            state.closing_balance = closing_balance
            health_target = 1.0 + (merchant.quality_score - 1.0) * 0.6 - queue_signal * 0.18 - (0.12 if outage_flag else 0.0)
            if merchant.scenario == "recovery_merchant":
                health_target += 0.10 * (day_index / max(1, len(dates) - 1))
            state.health_index = clamp(0.86 * state.health_index + 0.14 * health_target, 0.68, 1.28)
            liquidity_signal = 1.0 - clamp(closing_balance / max(1.0, merchant.rent_monthly + merchant.payroll_monthly), 0.0, 1.4)
            state.cash_stress = clamp(0.85 * state.cash_stress + 0.15 * liquidity_signal, 0.0, 0.98)
            state.promo_pressure = clamp(state.promo_pressure * 0.72 + (1.0 if promotion["name"] != "none" else 0.0), 0.0, 6.0)
            state.recent_queue = queue_signal

    summary = {
        "seed": seed,
        "date_range": {"start": dates[0].isoformat(), "end": dates[-1].isoformat()},
        "merchant_count": len(merchants_rows),
        "row_counts": {
            "merchants": len(merchants_rows),
            "merchant_latent_profiles": len(latent_rows),
            "sales_daily": len(sales_rows),
            "payments_daily": len(payments_rows),
            "bank_daily": len(bank_rows),
            "obligations": len(obligations_rows),
        },
        "totals": {key: round_money(value) for key, value in totals.items()},
        "validation": {
            "bank_identity_max_abs_error": round_money(bank_identity_error),
            "payment_identity_max_abs_error": round_money(payment_identity_error),
            "sales_identity_max_abs_error": round_money(sales_identity_error),
        },
        "population_mix": {
            "cities": dict(sorted(city_counter.items())),
            "archetypes": dict(sorted(archetype_counter.items())),
            "scenarios": dict(sorted(scenario_counter.items())),
        },
    }
    return {
        "merchants": merchants_rows,
        "merchant_latent_profiles": latent_rows,
        "sales_daily": sales_rows,
        "payments_daily": payments_rows,
        "bank_daily": bank_rows,
        "obligations": obligations_rows,
    }, summary


def write_csv(path: Path, headers: list[str], rows: list[tuple]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def write_sqlite(path: Path, tables: dict[str, list[tuple]]) -> None:
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE merchants (
              merchant_id TEXT PRIMARY KEY,
              legal_name TEXT,
              vat_number TEXT,
              city TEXT
            );

            CREATE TABLE sales_daily (
              merchant_id TEXT,
              sales_date TEXT,
              gross_sales REAL,
              discounts REAL,
              net_sales REAL,
              vat_amount REAL,
              refunds_amount REAL,
              orders_count INTEGER,
              avg_ticket REAL,
              PRIMARY KEY (merchant_id, sales_date)
            );

            CREATE TABLE payments_daily (
              merchant_id TEXT,
              payment_date TEXT,
              cash_amount REAL,
              card_amount REAL,
              wallet_amount REAL,
              total_collected REAL,
              PRIMARY KEY (merchant_id, payment_date)
            );

            CREATE TABLE bank_daily (
              merchant_id TEXT,
              balance_date TEXT,
              opening_balance REAL,
              inflows REAL,
              outflows REAL,
              closing_balance REAL,
              PRIMARY KEY (merchant_id, balance_date)
            );

            CREATE TABLE obligations (
              merchant_id TEXT,
              due_date TEXT,
              obligation_type TEXT,
              amount_due REAL,
              amount_paid REAL,
              status TEXT
            );
            """
        )
        cursor.executemany("INSERT INTO merchants VALUES (?, ?, ?, ?)", tables["merchants"])
        cursor.executemany("INSERT INTO sales_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tables["sales_daily"])
        cursor.executemany("INSERT INTO payments_daily VALUES (?, ?, ?, ?, ?, ?)", tables["payments_daily"])
        cursor.executemany("INSERT INTO bank_daily VALUES (?, ?, ?, ?, ?, ?)", tables["bank_daily"])
        cursor.executemany("INSERT INTO obligations VALUES (?, ?, ?, ?, ?, ?)", tables["obligations"])
        connection.commit()
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a simulated restaurant/cafe POS financial dataset.")
    parser.add_argument("--start-date", default="2025-01-01", help="Inclusive start date in YYYY-MM-DD.")
    parser.add_argument("--end-date", default="2026-03-31", help="Inclusive end date in YYYY-MM-DD.")
    parser.add_argument("--scope", choices=("single_business", "portfolio"), default="single_business", help="Generate one operator by default, or a wider merchant portfolio.")
    parser.add_argument("--merchants", type=int, default=1, help="Number of merchants to generate. Use 1 for a single restaurant/cafe dataset.")
    parser.add_argument("--city", choices=sorted(CITY_CONFIGS), help="Optional fixed city for all generated merchants.")
    parser.add_argument("--archetype", choices=sorted(ARCHETYPES), help="Optional fixed business archetype. Useful for choosing cafe vs restaurant behavior.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), help="Optional fixed operating scenario.")
    parser.add_argument("--legal-name", help="Optional fixed legal name for the generated business.")
    parser.add_argument("--seed", type=int, default=20260415, help="Random seed.")
    parser.add_argument("--output-dir", default=None, help="Directory for CSV, SQLite, and summary outputs. Defaults to this package's generated_output folder.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    if end_date < start_date:
        raise ValueError("end-date must be on or after start-date")
    if args.merchants <= 0:
        raise ValueError("merchants must be positive")
    if args.scope == "single_business" and args.merchants != 1:
        raise ValueError("single_business scope requires --merchants 1")

    output_dir = Path(args.output_dir) if args.output_dir else Path(__file__).resolve().parent / "generated_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    dates = daterange(start_date, end_date)
    city_contexts = build_city_day_contexts(dates, args.seed)
    merchants = generate_merchants(
        args.merchants,
        rng,
        fixed_city=args.city,
        fixed_archetype=args.archetype,
        fixed_scenario=args.scenario,
        fixed_legal_name=args.legal_name,
    )
    tables, summary = simulate_dataset(merchants, dates, city_contexts, args.seed)
    summary["dataset_scope"] = args.scope
    summary["intended_analysis_unit"] = "single_business_time_series" if args.scope == "single_business" else "merchant_portfolio"
    if merchants:
        summary["business_profile"] = {
            "merchant_id": merchants[0].merchant_id if args.scope == "single_business" else None,
            "legal_name": merchants[0].legal_name if args.scope == "single_business" else None,
            "city": merchants[0].city if args.scope == "single_business" else None,
            "archetype": merchants[0].archetype if args.scope == "single_business" else None,
            "scenario": merchants[0].scenario if args.scope == "single_business" else None,
        }

    write_csv(output_dir / "merchants.csv", ["merchant_id", "legal_name", "vat_number", "city"], tables["merchants"])
    write_csv(
        output_dir / "merchant_latent_profiles.csv",
        [
            "merchant_id",
            "archetype",
            "scenario",
            "base_daily_orders",
            "base_ticket",
            "digital_propensity",
            "wallet_bias",
            "delivery_share_target",
            "quality_score",
            "capacity_index",
            "rent_monthly",
            "payroll_monthly",
            "utilities_monthly",
            "cogs_ratio",
            "opening_balance",
            "loan_payment",
        ],
        tables["merchant_latent_profiles"],
    )
    write_csv(
        output_dir / "sales_daily.csv",
        ["merchant_id", "sales_date", "gross_sales", "discounts", "net_sales", "vat_amount", "refunds_amount", "orders_count", "avg_ticket"],
        tables["sales_daily"],
    )
    write_csv(
        output_dir / "payments_daily.csv",
        ["merchant_id", "payment_date", "cash_amount", "card_amount", "wallet_amount", "total_collected"],
        tables["payments_daily"],
    )
    write_csv(
        output_dir / "bank_daily.csv",
        ["merchant_id", "balance_date", "opening_balance", "inflows", "outflows", "closing_balance"],
        tables["bank_daily"],
    )
    write_csv(
        output_dir / "obligations.csv",
        ["merchant_id", "due_date", "obligation_type", "amount_due", "amount_paid", "status"],
        tables["obligations"],
    )
    write_sqlite(output_dir / "restaurant_pos_simulated.sqlite", tables)

    with (output_dir / "generation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
