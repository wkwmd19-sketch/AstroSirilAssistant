import sys
import time
import unittest

from astroauto.siril import _run_streaming_process, SirilStartupTimeout


class SirilStartupWatchdogTests(unittest.TestCase):
    def test_watchdog_stops_stalled_python_stage(self):
        started = time.monotonic()
        with self.assertRaises(SirilStartupTimeout):
            _run_streaming_process(
                [sys.executable, "-u", "-c",
                 "import time; print('Python module is up-to-date', flush=True); time.sleep(10)"],
                input_text=None, cwd=None, timeout=20,
                startup_watchdog={
                    "timeout_sec": 1,
                    "arm_markers": ["python module is up-to-date"],
                    "ready_markers": ["connected to siril"],
                    "message": "startup stalled",
                },
            )
        self.assertLess(time.monotonic() - started, 5)

    def test_watchdog_disarms_when_processing_starts(self):
        proc = _run_streaming_process(
            [sys.executable, "-u", "-c",
             "print('Python module is up-to-date', flush=True); print('Connected to Siril.', flush=True)"],
            input_text=None, cwd=None, timeout=10,
            startup_watchdog={
                "timeout_sec": 1,
                "arm_markers": ["python module is up-to-date"],
                "ready_markers": ["connected to siril"],
            },
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Connected to Siril", proc.stdout)


if __name__ == "__main__":
    unittest.main()
