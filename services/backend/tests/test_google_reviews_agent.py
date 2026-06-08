import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.google_reviews_agent import _build_place_url, _candidate_match_score, _deterministic_summary
from app.google_reviews_agent import _location_queries, _normalize_review, _search_strings


class GoogleReviewsAgentTests(unittest.TestCase):
    def test_candidate_match_prefers_exact_name(self):
        exact = {
            "title": "Arabica Corner Cafe",
            "url": "https://maps.google.com/?q=1",
            "reviewsCount": 200,
            "totalScore": 4.4,
        }
        weak = {
            "title": "Corner Station",
            "url": "https://maps.google.com/?q=2",
            "reviewsCount": 900,
            "totalScore": 4.6,
        }
        self.assertGreater(
            _candidate_match_score("Arabica Corner Cafe", exact),
            _candidate_match_score("Arabica Corner Cafe", weak),
        )

    def test_candidate_match_prefers_city_hint(self):
        khobar = {
            "title": "Namq Cafe",
            "url": "https://maps.google.com/?q=khobar",
            "city": "Al Khobar",
            "address": "Prince Turkey Street, Alkurnaish, Al Khobar 34412, Saudi Arabia",
            "reviewsCount": 200,
        }
        riyadh = {
            "title": "Namq Cafe",
            "url": "https://maps.google.com/?q=riyadh",
            "city": "Riyadh",
            "address": "Anas Ibn Malik Rd, Al Malqa, Riyadh, Saudi Arabia",
            "reviewsCount": 200,
        }
        self.assertGreater(
            _candidate_match_score("Namq Cafe", khobar, city="Al Khobar"),
            _candidate_match_score("Namq Cafe", riyadh, city="Al Khobar"),
        )

    def test_search_strings_add_brand_core(self):
        self.assertEqual(_search_strings("Namq Cafe"), ["Namq Cafe", "Namq"])

    def test_location_queries_normalize_saudi_region(self):
        self.assertEqual(
            _location_queries(region="Eastern Province"),
            ["Eastern Region, Saudi Arabia"],
        )

    def test_deterministic_summary_flags_food_safety_and_service(self):
        place = {"title": "Test Cafe", "total_score": 3.9, "reviews_count": 12}
        reviews = [
            {"rating": 1, "text": "Made me sick after eating here", "response_from_owner_text": None},
            {"rating": 2, "text": "Dirty tables and very slow service", "response_from_owner_text": None},
            {"rating": 5, "text": "Friendly staff and clean place", "response_from_owner_text": "Thanks"},
        ]
        summary = _deterministic_summary("Test Cafe", place, reviews)
        self.assertIn("food_safety_mentions", summary["red_flags"])
        self.assertIn("service_breakdown", summary["red_flags"])
        self.assertIsInstance(summary["health_score"], int)
        self.assertGreaterEqual(summary["health_score"], 0)

    def test_deterministic_summary_anchors_to_place_rating_when_sample_is_tiny(self):
        place = {"title": "Test Cafe", "total_score": 4.6, "reviews_count": 2000}
        reviews = [
            {"rating": 4, "text": "Fine", "response_from_owner_text": "Thanks"},
            {"rating": 4, "text": "Good", "response_from_owner_text": "Thanks"},
            {"rating": 5, "text": "Great", "response_from_owner_text": "Thanks"},
        ]
        summary = _deterministic_summary("Test Cafe", place, reviews)
        self.assertEqual(summary["overall_sentiment"], "positive")

    def test_normalize_review_uses_translated_text_when_primary_text_missing(self):
        review = _normalize_review({
            "reviewId": "abc",
            "text": None,
            "textTranslated": "Great view and coffee",
            "stars": 5,
            "publishedAtDate": "2026-04-15T19:43:50.673Z",
        })
        self.assertEqual(review["text"], "Great view and coffee")

    def test_build_place_url_uses_place_id(self):
        url = _build_place_url("Namq Cafe", "ChIJabc123")
        self.assertIn("query_place_id=ChIJabc123", url)
        self.assertIn("Namq%20Cafe", url)


if __name__ == "__main__":
    unittest.main()
