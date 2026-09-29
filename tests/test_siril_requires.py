import unittest
from unittest.mock import patch
from pathlib import Path

from astroauto.siril import run_script, SirilInfo

class SirilRequiresTests(unittest.TestCase):
    @patch("astroauto.siril.subprocess.run")
    @patch("astroauto.siril.get_siril_info")
    def test_requires_is_first_command(self, mocked_info, mocked_run):
        mocked_info.return_value = SirilInfo(Path("siril-cli.exe"), "1.4.4")
        mocked_run.return_value.returncode = 0
        mocked_run.return_value.stdout = ""
        mocked_run.return_value.stderr = ""

        cfg = {
            "siril": {
                "minimum_supported": "1.4.0",
                "command_timeout_sec": 30,
            }
        }
        run_script(cfg, ["set32bits", "close"])

        sent = mocked_run.call_args.kwargs["input"]
        self.assertTrue(sent.startswith("requires 1.4.0\n"))
        self.assertIn("set32bits\n", sent)

if __name__ == "__main__":
    unittest.main()
