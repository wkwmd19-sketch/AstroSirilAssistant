import unittest
from astroauto.ghs import build_ghs_command

class GhsCommandTests(unittest.TestCase):
    def test_autoghs_default(self):
        cmd = build_ghs_command(
            "AUTO_GHS",
            linked=True,
            shadows_clip=-2.8,
            stretch_amount=1.0,
            b=13,
            lp=0,
            hp=0.7,
            clip_mode="rgbblend",
        )
        self.assertEqual(
            cmd,
            "autoghs -linked -2.8 1 -b=13 -lp=0 -hp=0.7 -clipmode=rgbblend"
        )

    def test_manual_ght(self):
        cmd = build_ghs_command(
            "MANUAL_GHT",
            d=1.2,
            b=2,
            lp=0,
            sp=0.08,
            hp=0.9,
            luminance_mode="HUMAN",
            clip_mode="rgbblend",
        )
        self.assertIn("ght -D=1.2", cmd)
        self.assertIn("-B=2", cmd)
        self.assertIn("-SP=0.08", cmd)
        self.assertIn("-HP=0.9", cmd)
        self.assertIn("-human", cmd)

    def test_manual_order_validation(self):
        with self.assertRaises(ValueError):
            build_ghs_command(
                "MANUAL_GHT",
                d=1,
                b=0,
                lp=0.5,
                sp=0.2,
                hp=0.9,
                luminance_mode="HUMAN",
                clip_mode="rgbblend",
            )

if __name__ == "__main__":
    unittest.main()
