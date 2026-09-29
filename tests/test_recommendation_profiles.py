import unittest
from astroauto.recommendations import known_target_match, feature_labels

class RecommendationProfileTests(unittest.TestCase):
    def test_m31_profile(self):
        canonical, data = known_target_match("M31")
        self.assertEqual(canonical, "M31")
        self.assertEqual(data["category"], "GALAXY")
        self.assertIn("BRIGHT_CORE", data["features"])
        self.assertIn("DUST_LANES", data["features"])

    def test_alias(self):
        canonical, data = known_target_match("NGC 224")
        self.assertEqual(canonical, "M31")

    def test_feature_labels(self):
        self.assertEqual(feature_labels()["BRIGHT_CORE"], "밝은 중심핵")

if __name__ == "__main__":
    unittest.main()
