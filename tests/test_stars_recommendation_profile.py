import unittest
import yaml
from astroauto.config import PACKAGE_ROOT

class StarsRecommendationProfileTests(unittest.TestCase):
    def test_m31_expected_profile_math(self):
        profiles = yaml.safe_load(
            (PACKAGE_ROOT / "profiles" / "recommendation_profiles.yaml").read_text(encoding="utf-8")
        )
        base = profiles["stars_processing"]["by_category"]["GALAXY"]["brightness_scale"]
        mods = profiles["stars_processing"]["feature_modifiers"]

        # M31 known registry includes FAINT_OUTER_STRUCTURE + HIGH_DYNAMIC_RANGE.
        expected = base + mods["FAINT_OUTER_STRUCTURE"]["brightness_delta"] + mods["HIGH_DYNAMIC_RANGE"]["brightness_delta"]
        self.assertAlmostEqual(expected, 0.60, places=6)

if __name__ == "__main__":
    unittest.main()
