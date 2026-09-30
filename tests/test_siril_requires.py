import unittest
from unittest.mock import patch
from pathlib import Path
import subprocess

from astroauto.siril import run_script, SirilInfo

class SirilRequiresTests(unittest.TestCase):
    @patch("astroauto.siril._run_streaming_process")
    @patch("astroauto.siril.get_siril_info")
    def test_requires_is_first_command(self, mocked_info, mocked_stream):
        mocked_info.return_value = SirilInfo(Path("siril-cli.exe"), "1.4.4")
        mocked_stream.return_value = subprocess.CompletedProcess([], 0, "", "")
        cfg = {"siril": {"minimum_supported": "1.4.0", "command_timeout_sec": 30}}
        run_script(cfg, ["set32bits", "close"])
        sent = mocked_stream.call_args.kwargs["input_text"]
        self.assertTrue(sent.startswith("requires 1.4.0\n"))
        self.assertIn("set32bits\n", sent)

if __name__ == "__main__": unittest.main()
