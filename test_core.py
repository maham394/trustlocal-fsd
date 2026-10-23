import unittest
from core import (
    load_businesses, transparency_score, interpret_query_fallback,
    search_and_rank, validate_model_result
)


class TrustLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.businesses = load_businesses()

    def test_complete_record_scores_100(self):
        record = {
            "price": "PKR 10", "area": "GCUF", "contact_method": "demo form",
            "service_details": "printing", "policies": "sample policy",
            "source_type": "synthetic", "source_reference": "test:1", "last_updated": "2026-01-01"
        }
        self.assertEqual(transparency_score(record)["score"], 100)

    def test_missing_record_fields_get_zero_for_missing_criteria(self):
        record = {"price": "not supplied", "area": "GCUF", "contact_method": "not supplied", "service_details": "printing", "policies": "not supplied"}
        result = transparency_score(record)
        self.assertEqual(result["score"], 35)
        self.assertEqual(result["breakdown"]["price"]["awarded"], 0)

    def test_printing_and_area_query(self):
        parsed = interpret_query_fallback("Affordable printing near GCUF")
        results = search_and_rank(self.businesses, parsed)
        self.assertTrue(results)
        self.assertEqual(results[0]["category"], "printing")
        self.assertEqual(results[0]["area"], "GCUF")

    def test_clothing_budget_query(self):
        parsed = interpret_query_fallback("Budget clothing in D-Ground under 2000")
        self.assertEqual(parsed["category"], "clothing")
        self.assertEqual(parsed["area"], "D-Ground")
        self.assertEqual(parsed["budget_max"], 2000)
        results = search_and_rank(self.businesses, parsed)
        self.assertTrue(all(x["category"] == "clothing" for x in results))

    def test_unmatched_category_returns_no_results(self):
        parsed = interpret_query_fallback("Dentist near GCUF")
        self.assertEqual(search_and_rank(self.businesses, parsed), [])

    def test_budget_excludes_known_over_budget_listing(self):
        parsed = {"category": "clothing", "area": "D-Ground", "budget_max": 700, "preferences": "cheap clothing"}
        self.assertEqual(search_and_rank(self.businesses, parsed), [])

    def test_empty_search_is_not_silently_matched(self):
        parsed = interpret_query_fallback("")
        self.assertEqual(search_and_rank(self.businesses, parsed), [])

    def test_relevance_precedes_transparency(self):
        parsed = {"category": "printing", "area": "GCUF", "budget_max": None, "preferences": "printing near GCUF"}
        results = search_and_rank(self.businesses, parsed)
        self.assertEqual(results[0]["area"], "GCUF")

    def test_invalid_model_listing_id_is_rejected(self):
        payload = {"comparison_summary": "Looks relevant", "verification_questions": ["Confirm price"], "listing_ids": ["invented_id"]}
        self.assertIsNone(validate_model_result(payload, {x["id"] for x in self.businesses}))

    def test_valid_model_output_is_accepted(self):
        payload = {"comparison_summary": "Compare supplied fields", "verification_questions": ["Confirm price"], "listing_ids": ["print_001"]}
        self.assertIsNotNone(validate_model_result(payload, {x["id"] for x in self.businesses}))

    def test_malformed_model_output_is_rejected(self):
        self.assertIsNone(validate_model_result("not json", {x["id"] for x in self.businesses}))


if __name__ == "__main__":
    unittest.main()
