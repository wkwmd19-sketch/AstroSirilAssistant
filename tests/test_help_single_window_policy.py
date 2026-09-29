import unittest
from astroauto.help_system import HelpSystem

class HelpPolicyTests(unittest.TestCase):
    def test_section_help_api_exists(self):
        self.assertTrue(hasattr(HelpSystem, "show_section"))
        self.assertTrue(hasattr(HelpSystem, "section_help_button"))

if __name__ == "__main__":
    unittest.main()
