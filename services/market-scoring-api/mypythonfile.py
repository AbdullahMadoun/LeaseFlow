import argparse
import json
import math
import os
import random
import time
from datetime import date, datetime

import requests

BASE = "https://api.stats.gov.sa/v1/stats"
SAMA_BASE = "https://www.sama.gov.sa/_layouts/15/SAMA.Internet.WCM/WebMethods.aspx"
SAMA_TIMEOUT = 45
CHROME_BINARY = os.getenv("CHROME_BINARY")
EPSILON = 1e-6


def safe_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_stats_values(name, endpoint, params, value_key=None, filters=None, date_key=None):
    response = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
    response.raise_for_status()
    rows = response.json().get("value", [])

    if filters:
        rows = [
            row
            for row in rows
            if all(row.get(key) == expected for key, expected in filters.items())
        ]

    if not rows:
        print(f"\n{name}\nstatus: {response.status_code}\nrows: 0")
        return []

    if value_key is None:
        if "OBSVALUE_OBSV" in rows[0]:
            value_key = "OBSVALUE_OBSV"
        elif "OBS_VALUE_OBSV" in rows[0]:
            value_key = "OBS_VALUE_OBSV"
        else:
            raise KeyError(f"Could not detect value key for {name}")

    if date_key is None:
        for candidate in ["YEAR_MONTH_TIME", "TIME_PERIOD", "YEAR_TIME"]:
            if candidate in rows[0]:
                date_key = candidate
                break

    values = [
        {
            "date": row.get(date_key),
            "value": safe_float(row.get(value_key)),
        }
        for row in rows
        if value_key in row
    ]

    print(f"\n{name}")
    print("status:", response.status_code)
    print("rows:", len(values))
    print("sample:", values[:2])

    return values


def pct_change(current, previous):
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def latest_stat_value(values, index=0):
    if len(values) <= index or index < 0:
        return None
    return values[index]["value"]


def latest_pos_value(values, key, index=1):
    if index <= 0 or len(values) < index:
        return None
    return values[-index].get(key)


def normalize_centered_minmax(value, history):
    clean_history = [item for item in history if item is not None]
    if value is None or not clean_history:
        return 0.0

    lower = min(clean_history)
    upper = max(clean_history)
    if upper == lower:
        return 0.0

    normalized = ((value - lower) / (upper - lower)) * 2 - 1
    return clamp(normalized, -1.0, 1.0)


def normalize_tanh(value, scale):
    if value is None or scale <= 0:
        return 0.0
    return math.tanh(value / scale)


def logistic_map(value, scale=1.0):
    if scale <= 0:
        return 0.5
    return 1.0 / (1.0 + math.exp(-(value / scale)))


def percentile_rank(value, history):
    clean_history = sorted(item for item in history if item is not None)
    if value is None or not clean_history:
        return 0.0

    count = sum(1 for item in clean_history if item <= value)
    return count / len(clean_history)


def empirical_quantile(history, quantile):
    clean_history = sorted(item for item in history if item is not None)
    if not clean_history:
        return None

    if len(clean_history) == 1:
        return clean_history[0]

    position = clamp(quantile, 0.0, 1.0) * (len(clean_history) - 1)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return clean_history[lower_index]

    lower_value = clean_history[lower_index]
    upper_value = clean_history[upper_index]
    weight = position - lower_index
    return lower_value + weight * (upper_value - lower_value)


def mean(values):
    clean_values = [value for value in values if value is not None]
    if not clean_values:
        return 0.0
    return sum(clean_values) / len(clean_values)


def population_std(values):
    clean_values = [value for value in values if value is not None]
    if len(clean_values) < 2:
        return 0.0
    average = mean(clean_values)
    variance = sum((value - average) ** 2 for value in clean_values) / len(clean_values)
    return math.sqrt(variance)


def add_months(anchor, delta_months):
    zero_based_month = anchor.month - 1 + delta_months
    year = anchor.year + zero_based_month // 12
    month = zero_based_month % 12 + 1
    return date(year, month, 1)


def parse_series_date(value):
    if isinstance(value, date):
        return value.replace(day=1)
    if isinstance(value, int):
        return date(value, 12, 1)
    if isinstance(value, str):
        for fmt in ("%Y / %m", "%b %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date().replace(day=1)
            except ValueError:
                continue
    raise ValueError(f"Unsupported series date format: {value!r}")


def months_since(observed_date, reference_date=None):
    reference = reference_date or date.today().replace(day=1)
    return max(
        0,
        (reference.year - observed_date.year) * 12 + (reference.month - observed_date.month),
    )


def freshness_decay(months_stale, grace_months, zero_weight_months):
    if months_stale <= grace_months:
        return 1.0
    if months_stale >= zero_weight_months:
        return 0.0
    remaining = zero_weight_months - months_stale
    horizon = zero_weight_months - grace_months
    return clamp(remaining / horizon, 0.0, 1.0)


def build_feature_freshness_details(feature_dates):
    details = {}

    for feature_name, metadata in feature_dates.items():
        observed = parse_series_date(metadata["date"])
        months_stale = months_since(observed)

        if metadata["frequency"] == "monthly":
            freshness_factor = freshness_decay(months_stale, grace_months=3, zero_weight_months=24)
        elif metadata["frequency"] == "annual":
            freshness_factor = freshness_decay(months_stale, grace_months=15, zero_weight_months=42)
        else:
            raise ValueError(f"Unsupported frequency: {metadata['frequency']}")

        details[feature_name] = {
            "observed_period": observed.isoformat()[:7],
            "months_stale": months_stale,
            "freshness_factor": freshness_factor,
        }

    return details


def score_market_lending(linear_inputs, context):
    freshness_factors = context.get("freshness_factors", {})
    normalized_inputs = {
        "demand_food_beverages_pos_sales_latest": normalize_centered_minmax(
            linear_inputs["demand_food_beverages_pos_sales_latest"],
            context["pos_sales_history"],
        ),
        "demand_food_beverages_pos_sales_growth_pct": normalize_tanh(
            linear_inputs["demand_food_beverages_pos_sales_growth_pct"],
            10.0,
        ),
        "demand_food_beverages_pos_transactions_latest": normalize_centered_minmax(
            linear_inputs["demand_food_beverages_pos_transactions_latest"],
            context["pos_transactions_history"],
        ),
        "demand_food_beverages_pos_transactions_growth_pct": normalize_tanh(
            linear_inputs["demand_food_beverages_pos_transactions_growth_pct"],
            10.0,
        ),
        "risk_food_inflation_yoy_latest": normalize_tanh(
            linear_inputs["risk_food_inflation_yoy_latest"],
            10.0,
        ),
        "risk_restaurants_inflation_yoy_latest": normalize_tanh(
            linear_inputs["risk_restaurants_inflation_yoy_latest"],
            10.0,
        ),
        "risk_wpi_yoy_latest": normalize_tanh(
            linear_inputs["risk_wpi_yoy_latest"],
            15.0,
        ),
        "risk_gdp_growth_pct": normalize_tanh(
            linear_inputs["risk_gdp_growth_pct"],
            20.0,
        ),
    }
    freshness_adjusted_inputs = {
        key: normalized_inputs[key] * freshness_factors.get(key, 1.0)
        for key in normalized_inputs
    }

    weights = {
        "demand_food_beverages_pos_sales_latest": 0.20,
        "demand_food_beverages_pos_sales_growth_pct": 0.20,
        "demand_food_beverages_pos_transactions_latest": 0.10,
        "demand_food_beverages_pos_transactions_growth_pct": 0.10,
        "risk_food_inflation_yoy_latest": -0.15,
        "risk_restaurants_inflation_yoy_latest": -0.05,
        "risk_wpi_yoy_latest": -0.10,
        "risk_gdp_growth_pct": 0.10,
    }

    weighted_sum = sum(weights[key] * freshness_adjusted_inputs[key] for key in weights)
    score = clamp(50 + 50 * weighted_sum, 0.0, 100.0)
    return {
        "normalized_inputs": normalized_inputs,
        "freshness_adjusted_inputs": freshness_adjusted_inputs,
        "freshness_factors": {key: freshness_factors.get(key, 1.0) for key in normalized_inputs},
        "weights": weights,
        "weighted_sum": weighted_sum,
        "market_lending_score": score,
    }


def fetch_sama_json_via_browser(url):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    if CHROME_BINARY:
        options.binary_location = CHROME_BINARY
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,800")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.set_page_load_timeout(SAMA_TIMEOUT)
        driver.get(url)

        deadline = time.time() + SAMA_TIMEOUT
        while time.time() < deadline:
            if driver.execute_script("return typeof GetStatistcalById") == "function":
                break
            time.sleep(0.5)
        else:
            raise TimeoutError("SAMA page helper did not load")

        driver.execute_script("GetStatistcalById();")

        seen_request_ids = set()
        deadline = time.time() + SAMA_TIMEOUT
        while time.time() < deadline:
            for entry in driver.get_log("performance"):
                message = json.loads(entry["message"])["message"]
                if message.get("method") != "Network.responseReceived":
                    continue

                params = message["params"]
                request_id = params["requestId"]
                if request_id in seen_request_ids:
                    continue
                seen_request_ids.add(request_id)

                response = params["response"]
                if "GetStatistcalById" not in response.get("url", ""):
                    continue
                if response.get("mimeType") != "application/json":
                    continue

                body = driver.execute_cdp_cmd(
                    "Network.getResponseBody",
                    {"requestId": request_id},
                )
                return body["body"]

            time.sleep(1)

        raise TimeoutError("Timed out waiting for SAMA JSON response")
    finally:
        driver.quit()


def fetch_sama_pos():
    url = f'{SAMA_BASE}/GetStatistcalById?id=13755&lang=%22en%22'
    payload = json.loads(fetch_sama_json_via_browser(url))
    inner = json.loads(payload["d"]["Result"])["Result"]
    columns = inner["ColumnsDef"]
    rows = inner["RowsData"]

    date_key = None
    transactions_key = None
    sales_key = None

    for column in columns:
        title = column["ColTitle"].strip().lower()
        if title == "date":
            date_key = column["ColId"]
        elif title == "number of transactions":
            transactions_key = column["ColId"]
        elif title == "sales":
            sales_key = column["ColId"]

    if not date_key or not transactions_key or not sales_key:
        raise KeyError("Could not detect SAMA POS column ids")

    values = [
        {
            "date": row.get(date_key),
            "transactions": safe_float(row.get(transactions_key)),
            "sales": safe_float(row.get(sales_key)),
        }
        for row in rows
    ]

    print("\nSAMA POS Beverage and Food")
    print("status:", 200)
    print("rows:", len(values))
    print("sample:", values[-2:])

    return values


def build_live_market_stream():
    food_cpi_values = fetch_stats_values(
        "Food CPI YoY",
        "DPV_CLI_CHANGE_YEAR",
        {
            "dimensions[]": ["BASKET_LEVELS", "ITEM", "YEAR_MONTH"],
            "BASKET_LEVELS_CODE": "2",
            "ITEM_CODE": "01",
            "$orderby": "YEAR_MONTH_TIME DESC",
            "$top": 3,
            "format": "json",
        },
    )

    restaurants_cpi_values = fetch_stats_values(
        "Restaurants CPI YoY",
        "DPV_CLI_CHANGE_YEAR",
        {
            "dimensions[]": ["BASKET_LEVELS", "ITEM", "YEAR_MONTH"],
            "BASKET_LEVELS_CODE": "2",
            "ITEM_CODE": "11",
            "$orderby": "YEAR_MONTH_TIME DESC",
            "$top": 3,
            "format": "json",
        },
    )

    wpi_values = fetch_stats_values(
        "WPI National YoY",
        "DPV_WS_CHANGE_YEAR",
        {
            "dimensions[]": ["ITEM", "YEAR_MONTH"],
            "$orderby": "YEAR_MONTH_TIME DESC",
            "$top": 12,
            "format": "json",
        },
        value_key="OBSVALUE_OBSV",
        filters={"ITEM_CODE": "-1"},
    )

    gdp_values = fetch_stats_values(
        "GDP",
        "DPV_NA20_EFNA0401",
        {
            "dimensions[]": "YEAR",
            "$orderby": "YEAR_TIME DESC",
            "$top": 5,
            "format": "json",
        },
        value_key="OBS_VALUE_OBSV",
    )

    pos_values = fetch_sama_pos()

    demand_inputs = {
        "food_beverages_pos_sales_latest": latest_pos_value(pos_values, "sales", 1),
        "food_beverages_pos_sales_growth_pct": pct_change(
            latest_pos_value(pos_values, "sales", 1),
            latest_pos_value(pos_values, "sales", 2),
        ),
        "food_beverages_pos_transactions_latest": latest_pos_value(pos_values, "transactions", 1),
        "food_beverages_pos_transactions_growth_pct": pct_change(
            latest_pos_value(pos_values, "transactions", 1),
            latest_pos_value(pos_values, "transactions", 2),
        ),
    }

    risk_inputs = {
        "food_inflation_yoy_latest": latest_stat_value(food_cpi_values, 0),
        "restaurants_inflation_yoy_latest": latest_stat_value(restaurants_cpi_values, 0),
        "wpi_yoy_latest": latest_stat_value(wpi_values, 0),
        "gdp_latest": latest_stat_value(gdp_values, 0),
        "gdp_growth_pct": pct_change(
            latest_stat_value(gdp_values, 0),
            latest_stat_value(gdp_values, 1),
        ),
    }

    linear_model_inputs = {
        **{f"demand_{key}": value for key, value in demand_inputs.items()},
        **{
            "risk_food_inflation_yoy_latest": risk_inputs["food_inflation_yoy_latest"],
            "risk_restaurants_inflation_yoy_latest": risk_inputs["restaurants_inflation_yoy_latest"],
            "risk_wpi_yoy_latest": risk_inputs["wpi_yoy_latest"],
            "risk_gdp_growth_pct": risk_inputs["gdp_growth_pct"],
        },
    }
    feature_dates = {
        "demand_food_beverages_pos_sales_latest": {
            "date": pos_values[-1]["date"],
            "frequency": "monthly",
        },
        "demand_food_beverages_pos_sales_growth_pct": {
            "date": pos_values[-1]["date"],
            "frequency": "monthly",
        },
        "demand_food_beverages_pos_transactions_latest": {
            "date": pos_values[-1]["date"],
            "frequency": "monthly",
        },
        "demand_food_beverages_pos_transactions_growth_pct": {
            "date": pos_values[-1]["date"],
            "frequency": "monthly",
        },
        "risk_food_inflation_yoy_latest": {
            "date": food_cpi_values[0]["date"],
            "frequency": "monthly",
        },
        "risk_restaurants_inflation_yoy_latest": {
            "date": restaurants_cpi_values[0]["date"],
            "frequency": "monthly",
        },
        "risk_wpi_yoy_latest": {
            "date": wpi_values[0]["date"],
            "frequency": "monthly",
        },
        "risk_gdp_growth_pct": {
            "date": gdp_values[0]["date"],
            "frequency": "annual",
        },
    }
    freshness_details = build_feature_freshness_details(feature_dates)

    scoring_context = {
        "pos_sales_history": [row["sales"] for row in pos_values if row.get("sales") is not None],
        "pos_transactions_history": [
            row["transactions"] for row in pos_values if row.get("transactions") is not None
        ],
        "freshness_factors": {
            key: details["freshness_factor"] for key, details in freshness_details.items()
        },
    }

    score_result = score_market_lending(linear_model_inputs, scoring_context)

    return {
        "source": "live_market_data",
        "inputs": linear_model_inputs,
        "score": score_result,
        "histories": scoring_context,
        "series": {
            "food_cpi_values": food_cpi_values,
            "restaurants_cpi_values": restaurants_cpi_values,
            "wpi_values": wpi_values,
            "gdp_values": gdp_values,
            "pos_values_tail": pos_values[-6:],
        },
        "freshness_details": freshness_details,
    }


def build_offline_market_stream(seed):
    rng = random.Random(seed)
    pos_sales_history = []
    pos_transactions_history = []

    for month_index in range(24):
        seasonality = 1.0 + 0.12 * math.sin((2 * math.pi * month_index) / 12.0)
        sales_trend = 1.0 + 0.007 * month_index
        transaction_trend = 1.0 + 0.005 * month_index
        sales_noise = 1.0 + rng.uniform(-0.03, 0.03)
        transaction_noise = 1.0 + rng.uniform(-0.04, 0.04)

        pos_sales_history.append(205_000_000 * seasonality * sales_trend * sales_noise)
        pos_transactions_history.append(18_500_000 * seasonality * transaction_trend * transaction_noise)

    gdp_history = [
        1_070_000_000_000.0,
        1_104_000_000_000.0,
        1_146_000_000_000.0,
        1_182_000_000_000.0,
        1_226_000_000_000.0,
    ]

    linear_model_inputs = {
        "demand_food_beverages_pos_sales_latest": pos_sales_history[-1],
        "demand_food_beverages_pos_sales_growth_pct": pct_change(
            pos_sales_history[-1],
            pos_sales_history[-2],
        ),
        "demand_food_beverages_pos_transactions_latest": pos_transactions_history[-1],
        "demand_food_beverages_pos_transactions_growth_pct": pct_change(
            pos_transactions_history[-1],
            pos_transactions_history[-2],
        ),
        "risk_food_inflation_yoy_latest": 2.7 + rng.uniform(-0.6, 0.6),
        "risk_restaurants_inflation_yoy_latest": 2.4 + rng.uniform(-0.5, 0.5),
        "risk_wpi_yoy_latest": 1.8 + rng.uniform(-0.8, 0.8),
        "risk_gdp_growth_pct": pct_change(gdp_history[-1], gdp_history[-2]),
    }

    scoring_context = {
        "pos_sales_history": pos_sales_history,
        "pos_transactions_history": pos_transactions_history,
        "freshness_factors": {key: 1.0 for key in linear_model_inputs},
    }

    score_result = score_market_lending(linear_model_inputs, scoring_context)

    return {
        "source": "synthetic_market_demo",
        "inputs": linear_model_inputs,
        "score": score_result,
        "histories": scoring_context,
        "freshness_details": {
            key: {
                "observed_period": "synthetic",
                "months_stale": 0,
                "freshness_factor": 1.0,
            }
            for key in linear_model_inputs
        },
    }


def generate_synthetic_cash_history(months, seed, current_market_score):
    if months <= 0:
        raise ValueError("months must be a positive integer")

    rng = random.Random(seed)
    anchor = date.today().replace(day=1)
    market_factor = clamp(current_market_score / 100.0, 0.15, 0.95)

    cash_balance = 26_000_000.0
    minimum_operating_buffer = 8_000_000.0
    vintages = []
    history = []

    for month_index in range(months):
        period = add_months(anchor, month_index - months + 1).isoformat()[:7]
        seasonality = 1.0 + 0.10 * math.sin((2 * math.pi * month_index) / 12.0)
        market_cycle = clamp(
            market_factor
            + 0.10 * math.sin((2 * math.pi * month_index) / 18.0)
            + rng.uniform(-0.05, 0.05),
            0.15,
            0.95,
        )

        planned_disbursements = 4_500_000.0 * (0.65 + 0.90 * market_cycle) * seasonality
        fixed_opex = 780_000.0
        variable_opex = 0.018 * planned_disbursements
        operating_expense = fixed_opex + variable_opex

        repayments = 0.0
        interest_income = 0.0
        charge_offs = 0.0
        next_vintages = []

        for vintage in vintages:
            remaining_principal = vintage["remaining_principal"]
            remaining_months = vintage["remaining_months"]
            monthly_default_rate = vintage["monthly_default_rate"]
            monthly_yield = vintage["monthly_yield"]

            default_amount = remaining_principal * monthly_default_rate
            scheduled_principal = (remaining_principal - default_amount) / remaining_months
            interest_amount = remaining_principal * monthly_yield

            ending_principal = remaining_principal - scheduled_principal - default_amount

            repayments += scheduled_principal
            interest_income += interest_amount
            charge_offs += default_amount

            if remaining_months > 1 and ending_principal > 0:
                next_vintages.append(
                    {
                        "remaining_principal": ending_principal,
                        "remaining_months": remaining_months - 1,
                        "monthly_default_rate": monthly_default_rate,
                        "monthly_yield": monthly_yield,
                    }
                )

        vintages = next_vintages

        planned_total_use = planned_disbursements + operating_expense
        available_for_lending = max(cash_balance - minimum_operating_buffer, 0.0)
        liquidity_multiplier = clamp(
            available_for_lending / max(planned_total_use, 1.0),
            0.20,
            1.0,
        )
        actual_disbursements = planned_disbursements * liquidity_multiplier

        fresh_default_rate = clamp(0.003 + (0.70 - market_cycle) * 0.006, 0.002, 0.010)
        fresh_monthly_yield = 0.012 + (0.55 - market_cycle) * 0.003
        vintages.append(
            {
                "remaining_principal": actual_disbursements,
                "remaining_months": 6,
                "monthly_default_rate": fresh_default_rate,
                "monthly_yield": fresh_monthly_yield,
            }
        )

        funding_support = 0.0
        if cash_balance < minimum_operating_buffer * 0.95:
            funding_support = 2_500_000.0 * (0.90 + 0.20 * rng.random())

        net_cash_flow = (
            repayments
            + interest_income
            + funding_support
            - actual_disbursements
            - operating_expense
            - charge_offs
        )
        cash_balance = max(cash_balance + net_cash_flow, 1_000_000.0)

        history.append(
            {
                "period": period,
                "market_cycle": market_cycle,
                "planned_disbursements": planned_disbursements,
                "actual_disbursements": actual_disbursements,
                "repayments": repayments,
                "interest_income": interest_income,
                "charge_offs": charge_offs,
                "operating_expense": operating_expense,
                "funding_support": funding_support,
                "net_cash_flow": net_cash_flow,
                "ending_cash": cash_balance,
            }
        )

    return history


def score_liquidity_position(cash_history, target_runway_months=6):
    if not cash_history:
        raise ValueError("cash_history must contain at least one observation")
    if target_runway_months <= 0:
        raise ValueError("target_runway_months must be positive")

    cash_balances = [row["ending_cash"] for row in cash_history]
    current_cash = cash_balances[-1]
    cash_mean = mean(cash_balances)
    cash_std = population_std(cash_balances)
    peak_cash = max(cash_balances)
    p10_cash = empirical_quantile(cash_balances, 0.10)

    recent_window = cash_history[-6:]
    avg_disbursements = mean([row["actual_disbursements"] for row in recent_window])
    avg_repayments = mean([row["repayments"] for row in recent_window])
    avg_interest_income = mean([row["interest_income"] for row in recent_window])
    avg_opex = mean([row["operating_expense"] for row in recent_window])
    avg_charge_offs = mean([row["charge_offs"] for row in recent_window])

    stressed_inflows = 0.70 * (avg_repayments + avg_interest_income)
    stressed_outflows = 0.90 * avg_disbursements + 1.10 * avg_opex + 1.25 * avg_charge_offs
    stressed_net_outflow = max(stressed_outflows - stressed_inflows, 1.0)
    stressed_runway_months = current_cash / stressed_net_outflow

    current_drawdown = 0.0 if peak_cash <= 0 else (peak_cash - current_cash) / peak_cash
    cash_zscore = 0.0 if cash_std <= 0 else (current_cash - cash_mean) / cash_std
    tail_buffer_z = 0.0 if cash_std <= 0 else (current_cash - p10_cash) / cash_std

    component_scores = {
        "cash_percentile": percentile_rank(current_cash, cash_balances),
        "cash_zscore": logistic_map(cash_zscore, 0.75),
        "tail_buffer_vs_p10": logistic_map(tail_buffer_z, 0.75),
        "drawdown_resilience": 1.0 - clamp(current_drawdown, 0.0, 1.0),
        "stressed_runway": clamp(stressed_runway_months / target_runway_months, 0.0, 1.0),
    }

    weights = {
        "cash_percentile": 0.25,
        "cash_zscore": 0.20,
        "tail_buffer_vs_p10": 0.15,
        "drawdown_resilience": 0.10,
        "stressed_runway": 0.30,
    }

    liquidity_score = 100.0 * sum(
        weights[name] * component_scores[name] for name in weights
    )

    return {
        "metrics": {
            "current_cash": current_cash,
            "cash_mean": cash_mean,
            "cash_std": cash_std,
            "cash_percentile": component_scores["cash_percentile"],
            "cash_zscore": cash_zscore,
            "cash_p10": p10_cash,
            "drawdown_from_peak_pct": current_drawdown * 100.0,
            "stressed_net_outflow": stressed_net_outflow,
            "stressed_runway_months": stressed_runway_months,
        },
        "component_scores": component_scores,
        "weights": weights,
        "liquidity_score": liquidity_score,
    }


def classify_risk_posture(score):
    if score < 35:
        return "defensive"
    if score < 65:
        return "balanced"
    return "expansionary"


def combine_market_and_liquidity(market_score, liquidity_result, target_runway_months=6):
    if target_runway_months <= 0:
        raise ValueError("target_runway_months must be positive")

    market_factor = clamp(market_score / 100.0, 0.01, 0.99)
    liquidity_factor = clamp(liquidity_result["liquidity_score"] / 100.0, 0.01, 0.99)
    stressed_runway_months = liquidity_result["metrics"]["stressed_runway_months"]
    runway_cap = clamp(stressed_runway_months / target_runway_months, 0.0, 1.0)

    # Liquidity has slightly higher weight because treasury capacity should bind
    # market appetite when the lender is short of deployable cash.
    base_score = math.exp(
        0.40 * math.log(market_factor + EPSILON)
        + 0.60 * math.log(liquidity_factor + EPSILON)
    )
    risk_taking_score = 100.0 * base_score * runway_cap

    return {
        "method": "capacity_constrained_geometric_mean",
        "formula": "100 * (market^0.40 * liquidity^0.60) * runway_cap",
        "assumptions": {
            "market_weight": 0.40,
            "liquidity_weight": 0.60,
            "target_stressed_runway_months": target_runway_months,
        },
        "factors": {
            "market_factor": market_factor,
            "liquidity_factor": liquidity_factor,
            "runway_cap": runway_cap,
        },
        "risk_taking_score": risk_taking_score,
        "risk_posture": classify_risk_posture(risk_taking_score),
        "recommended_new_loan_intensity": clamp(risk_taking_score / 70.0, 0.0, 1.25),
    }


def build_two_stream_model(use_live_market_data, seed, cash_months):
    if cash_months <= 0:
        raise ValueError("cash_months must be a positive integer")

    market_stream = (
        build_live_market_stream()
        if use_live_market_data
        else build_offline_market_stream(seed)
    )
    market_score = market_stream["score"]["market_lending_score"]

    cash_history = generate_synthetic_cash_history(
        months=cash_months,
        seed=seed,
        current_market_score=market_score,
    )
    liquidity_stream = score_liquidity_position(cash_history)
    combined_stream = combine_market_and_liquidity(market_score, liquidity_stream)

    return {
        "market_stream": {
            "source": market_stream["source"],
            "market_lending_score": market_score,
            "weighted_sum": market_stream["score"]["weighted_sum"],
            "inputs": market_stream["inputs"],
            "normalized_inputs": market_stream["score"]["normalized_inputs"],
            "freshness_adjusted_inputs": market_stream["score"]["freshness_adjusted_inputs"],
            "freshness_factors": market_stream["score"]["freshness_factors"],
            "freshness_details": market_stream["freshness_details"],
        },
        "liquidity_stream": {
            "synthetic_history_months": cash_months,
            "liquidity_score": liquidity_stream["liquidity_score"],
            "metrics": liquidity_stream["metrics"],
            "component_scores": liquidity_stream["component_scores"],
            "history_tail": cash_history[-6:],
        },
        "combined_score": combined_stream,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Two-stream lending risk model using market state plus internal liquidity history."
    )
    parser.add_argument(
        "--offline-demo",
        action="store_true",
        help="Use synthetic market data instead of live external APIs.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for the synthetic company cash-history generator.",
    )
    parser.add_argument(
        "--cash-months",
        type=int,
        default=36,
        help="Number of monthly observations to generate for treasury history.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        result = build_two_stream_model(
            use_live_market_data=not args.offline_demo,
            seed=args.seed,
            cash_months=args.cash_months,
        )
    except Exception as exc:
        if args.offline_demo:
            raise

        print("\nLive market fetch failed, falling back to synthetic market demo.")
        print("reason:", str(exc))
        result = build_two_stream_model(
            use_live_market_data=False,
            seed=args.seed,
            cash_months=args.cash_months,
        )
        result["market_stream"]["fallback_reason"] = str(exc)

    print("\nTwo-Stream Lending Risk Model")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
