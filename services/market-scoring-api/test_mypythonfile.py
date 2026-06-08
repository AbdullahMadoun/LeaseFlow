import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("mypythonfile.py")
SPEC = importlib.util.spec_from_file_location("market_model", MODULE_PATH)
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)


class MarketScoringTests(unittest.TestCase):
    def test_market_score_penalizes_higher_restaurant_inflation(self):
        context = {
            "pos_sales_history": [100.0, 110.0, 120.0, 130.0],
            "pos_transactions_history": [10.0, 11.0, 12.0, 13.0],
        }
        base_inputs = {
            "demand_food_beverages_pos_sales_latest": 130.0,
            "demand_food_beverages_pos_sales_growth_pct": 8.0,
            "demand_food_beverages_pos_transactions_latest": 13.0,
            "demand_food_beverages_pos_transactions_growth_pct": 6.0,
            "risk_food_inflation_yoy_latest": 2.5,
            "risk_restaurants_inflation_yoy_latest": 2.0,
            "risk_wpi_yoy_latest": 1.5,
            "risk_gdp_growth_pct": 4.0,
        }

        low_restaurant_inflation = MODEL.score_market_lending(base_inputs, context)
        stressed_inputs = dict(base_inputs)
        stressed_inputs["risk_restaurants_inflation_yoy_latest"] = 7.0
        high_restaurant_inflation = MODEL.score_market_lending(stressed_inputs, context)

        self.assertLess(
            high_restaurant_inflation["market_lending_score"],
            low_restaurant_inflation["market_lending_score"],
        )

    def test_stale_features_reduce_market_data_confidence(self):
        freshness_details = MODEL.build_feature_freshness_details(
            {
                "demand_food_beverages_pos_sales_latest": {
                    "date": "2023 / 12",
                    "frequency": "monthly",
                },
                "risk_gdp_growth_pct": {
                    "date": 2022,
                    "frequency": "annual",
                },
            }
        )

        self.assertLess(
            freshness_details["demand_food_beverages_pos_sales_latest"]["freshness_factor"],
            0.25,
        )
        self.assertLess(
            freshness_details["risk_gdp_growth_pct"]["freshness_factor"],
            0.25,
        )


class LiquidityScoringTests(unittest.TestCase):
    def test_liquidity_score_drops_when_cash_is_depleted(self):
        base_history = MODEL.generate_synthetic_cash_history(36, seed=42, current_market_score=55.0)
        depleted_history = [dict(row) for row in base_history]

        for row in depleted_history[-6:]:
            row["ending_cash"] *= 0.35

        base_result = MODEL.score_liquidity_position(base_history)
        depleted_result = MODEL.score_liquidity_position(depleted_history)

        self.assertLess(depleted_result["liquidity_score"], base_result["liquidity_score"])
        self.assertLess(
            depleted_result["metrics"]["stressed_runway_months"],
            base_result["metrics"]["stressed_runway_months"],
        )

    def test_invalid_cash_history_raises(self):
        with self.assertRaises(ValueError):
            MODEL.score_liquidity_position([])


class CombinedScoreTests(unittest.TestCase):
    def test_combined_score_is_monotonic_in_market_and_liquidity(self):
        low_liquidity = {
            "liquidity_score": 30.0,
            "metrics": {"stressed_runway_months": 3.0},
        }
        high_liquidity = {
            "liquidity_score": 70.0,
            "metrics": {"stressed_runway_months": 8.0},
        }

        weak_market = MODEL.combine_market_and_liquidity(40.0, high_liquidity)
        strong_market = MODEL.combine_market_and_liquidity(70.0, high_liquidity)
        weak_liquidity = MODEL.combine_market_and_liquidity(60.0, low_liquidity)
        strong_liquidity = MODEL.combine_market_and_liquidity(60.0, high_liquidity)

        self.assertLess(weak_market["risk_taking_score"], strong_market["risk_taking_score"])
        self.assertLess(weak_liquidity["risk_taking_score"], strong_liquidity["risk_taking_score"])

    def test_runway_cap_binds_the_final_score(self):
        weak_runway = {
            "liquidity_score": 80.0,
            "metrics": {"stressed_runway_months": 2.5},
        }
        strong_runway = {
            "liquidity_score": 80.0,
            "metrics": {"stressed_runway_months": 8.0},
        }

        weak_result = MODEL.combine_market_and_liquidity(65.0, weak_runway)
        strong_result = MODEL.combine_market_and_liquidity(65.0, strong_runway)

        self.assertLess(weak_result["risk_taking_score"], strong_result["risk_taking_score"])


class ModelShapeTests(unittest.TestCase):
    def test_offline_model_stays_in_range_across_many_seeds(self):
        for seed in range(25):
            for cash_months in (12, 24, 36, 60):
                result = MODEL.build_two_stream_model(
                    use_live_market_data=False,
                    seed=seed,
                    cash_months=cash_months,
                )
                scores = (
                    result["market_stream"]["market_lending_score"],
                    result["liquidity_stream"]["liquidity_score"],
                    result["combined_score"]["risk_taking_score"],
                )

                self.assertTrue(all(0.0 <= score <= 100.0 for score in scores))
                self.assertIn(
                    result["combined_score"]["risk_posture"],
                    {"defensive", "balanced", "expansionary"},
                )

    def test_invalid_cash_months_raise(self):
        with self.assertRaises(ValueError):
            MODEL.build_two_stream_model(use_live_market_data=False, seed=1, cash_months=0)


if __name__ == "__main__":
    unittest.main()
