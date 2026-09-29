import unittest
from astroauto.starless_processing import build_starless_commands

class StarlessProcessingTests(unittest.TestCase):
    def test_default_commands(self):
        cmds = build_starless_commands(
            clahe_enabled=True,
            clahe_clip_limit=1.5,
            clahe_tile_size=12,
            saturation_enabled=True,
            saturation_amount=0.1,
            saturation_background_factor=1.1,
            saturation_hue_range=6,
        )
        self.assertEqual(cmds[0], "clahe 1.5 12")
        self.assertEqual(cmds[1], "satu 0.1 1.1 6")

    def test_saturation_only(self):
        cmds = build_starless_commands(
            clahe_enabled=False,
            clahe_clip_limit=1.5,
            clahe_tile_size=12,
            saturation_enabled=True,
            saturation_amount=0.2,
            saturation_background_factor=1,
            saturation_hue_range=6,
        )
        self.assertEqual(cmds, ["satu 0.2 1 6"])

if __name__ == "__main__":
    unittest.main()
