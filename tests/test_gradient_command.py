import unittest
from astroauto.gradient import _subsky_command, _validate_params

class GradientCommandTests(unittest.TestCase):
    def test_default_command(self):
        self.assertEqual(
            _subsky_command(20, 1.0, 0.5, False),
            "subsky -rbf -samples=20 -tolerance=1 -smooth=0.5"
        )

    def test_dither_command(self):
        self.assertTrue(_subsky_command(20, 1.0, 0.5, True).endswith(" -dither"))

    def test_validation(self):
        self.assertEqual(_validate_params(20, 1.0, 0.5), (20, 1.0, 0.5))
        with self.assertRaises(ValueError):
            _validate_params(1, 1.0, 0.5)

if __name__ == "__main__":
    unittest.main()
