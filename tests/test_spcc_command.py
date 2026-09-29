import unittest
from astroauto.spcc import build_spcc_command, _quote_arg, _parse_spcc_list_stdout

class SpccCommandTests(unittest.TestCase):
    def test_osc_command(self):
        cmd = build_spcc_command(
            mode="OSC",
            sensor="Sony IMX678",
            osc_filter="DWARF Mini Astro",
            white_reference="Average Spiral Galaxy",
            catalog="AUTO",
            bgtol_lower=-2.8,
            bgtol_upper=2.0,
        )
        self.assertIn('"-oscsensor=Sony IMX678"', cmd)
        self.assertIn('"-oscfilter=DWARF Mini Astro"', cmd)
        self.assertIn('"-whiteref=Average Spiral Galaxy"', cmd)
        self.assertNotIn("-bgtol=", cmd)

    def test_custom_bgtol_is_quoted(self):
        cmd = build_spcc_command(
            mode="OSC",
            sensor="Sony IMX678",
            osc_filter="DWARF Mini Astro",
            white_reference="Average Spiral Galaxy",
            catalog="AUTO",
            bgtol_lower=-3.0,
            bgtol_upper=2.5,
        )
        self.assertIn('"-bgtol=-3,2.5"', cmd)

    def test_list_parser(self):
        sample = """log: Welcome to siril 1.4.4
log: 2026:01:01: Sony IMX678
log: 2026:01:01: Sony IMX585
log: Script execution finished successfully.
"""
        parsed = _parse_spcc_list_stdout(sample)
        self.assertIn("Sony IMX678", parsed)
        self.assertIn("Sony IMX585", parsed)

if __name__ == "__main__":
    unittest.main()
