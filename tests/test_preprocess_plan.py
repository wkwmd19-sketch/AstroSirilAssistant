import unittest
from astroauto.preprocess_engine import _arg

class PreprocessPlanTests(unittest.TestCase):
    def test_siril_quoted_arg(self):
        value = _arg("out", "D:/Astro Projects/test")
        self.assertEqual(value, '"-out=D:/Astro Projects/test"')

if __name__ == "__main__":
    unittest.main()
