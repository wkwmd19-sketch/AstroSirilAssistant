import unittest
from astroauto.recombine import build_pm_expression, build_pm_command

class RecombineCommandTests(unittest.TestCase):
    def test_expression(self):
        self.assertEqual(
            build_pm_expression(0.6),
            "$Main$ + $Stars$ * 0.6",
        )

    def test_default_command(self):
        self.assertEqual(
            build_pm_command(1.0, False),
            'pm "$Main$ + $Stars$ * 1" -nosum',
        )

    def test_rescale_command(self):
        self.assertEqual(
            build_pm_command(0.8, True),
            'pm "$Main$ + $Stars$ * 0.8" -nosum -rescale 0 1',
        )

    def test_weight_validation(self):
        with self.assertRaises(ValueError):
            build_pm_command(2.1, False)

if __name__ == "__main__":
    unittest.main()
