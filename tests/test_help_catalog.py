import unittest
from astroauto.help_system import HelpCatalog

class HelpCatalogTests(unittest.TestCase):
    def test_gradient_and_spcc_topics_exist(self):
        c = HelpCatalog()
        self.assertIn("Samples", c.get("gradient.samples")["title"])
        self.assertEqual(c.get("spcc.sensor")["title"], "Sensor")

if __name__ == "__main__":
    unittest.main()
