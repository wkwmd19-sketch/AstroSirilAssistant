import unittest
from astroauto.stars_processing import build_stars_commands

class StarsProcessingTests(unittest.TestCase):
    def test_default_commands(self):
        cmds = build_stars_commands(
            brightness_scale=0.7,
            saturation_enabled=True,
            saturation_amount=0.08,
            saturation_background_factor=0.0,
            saturation_hue_range=6,
        )
        self.assertEqual(cmds, ["satu 0.08 0 6", "fmul 0.7"])

    def test_brightness_only(self):
        cmds = build_stars_commands(
            brightness_scale=0.6,
            saturation_enabled=False,
            saturation_amount=0.08,
            saturation_background_factor=0.0,
            saturation_hue_range=6,
        )
        self.assertEqual(cmds, ["fmul 0.6"])

    def test_identity(self):
        cmds = build_stars_commands(
            brightness_scale=1.0,
            saturation_enabled=False,
            saturation_amount=0,
            saturation_background_factor=0,
            saturation_hue_range=6,
        )
        self.assertEqual(cmds, [])

if __name__ == "__main__":
    unittest.main()
