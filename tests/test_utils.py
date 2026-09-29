import unittest
from astroauto.utils import safe_target_name

class UtilsTests(unittest.TestCase):
    def test_safe_target(self):
        self.assertEqual(safe_target_name("M31"), "M31")
        self.assertEqual(safe_target_name("Heart Nebula"), "Heart_Nebula")
        self.assertEqual(safe_target_name('A:B/C'), "A_B_C")

if __name__ == "__main__":
    unittest.main()
