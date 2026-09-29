import unittest
from astroauto.calibration import _near, _decision

class CalibrationLogicTests(unittest.TestCase):
    def test_near(self):
        self.assertTrue(_near(30.0, 30.2, 0.05, 0.5))
        self.assertFalse(_near(30.0, 35.0, 0.05, 0.5))
        self.assertIsNone(_near(None, 30.0, 0.05, 0.5))

    def test_decision(self):
        self.assertEqual(
            _decision({"dimensions": True, "gain": None}, {"gain"})["status"],
            "COMPATIBLE_WITH_UNKNOWNS"
        )
        self.assertEqual(
            _decision({"dimensions": False}, set())["status"],
            "INCOMPATIBLE"
        )

if __name__ == "__main__":
    unittest.main()
