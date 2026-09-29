import unittest
from astroauto.star_separation import build_starnet_pyscript_command

class StarSeparationCommandTests(unittest.TestCase):
    def test_default_command(self):
        cmd = build_starnet_pyscript_command()
        self.assertIn("pyscript StarNet.py", cmd)
        self.assertIn("--no-linear", cmd)
        self.assertIn("--stride 256", cmd)
        self.assertIn("--no-upsample", cmd)
        self.assertIn("--protect-highlights", cmd)
        self.assertIn("--masks subtract", cmd)

    def test_small_stride_and_native_mask(self):
        cmd = build_starnet_pyscript_command(
            stride_preset="SMALL",
            stride=256,
            upsample=True,
            protect_highlights=False,
            save_native_starmask=True,
        )
        self.assertIn("--stride 128", cmd)
        self.assertIn("--upsample", cmd)
        self.assertIn("--disable-highlights-protection", cmd)
        self.assertIn("--masks subtract,starnet-mask", cmd)

    def test_custom_stride_validation(self):
        with self.assertRaises(ValueError):
            build_starnet_pyscript_command(
                stride_preset="CUSTOM",
                stride=255,
            )

if __name__ == "__main__":
    unittest.main()
