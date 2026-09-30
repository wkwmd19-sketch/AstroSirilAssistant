import sys
import threading
import time
import unittest

from astroauto.execution import TaskControl, ExecutionCancelled, execution_context
from astroauto.siril import _run_streaming_process


class ExecutionCancelTests(unittest.TestCase):
    def test_live_log_and_cancel(self):
        control = TaskControl()
        logs = []
        outcome = {"cancelled": False, "error": None}

        def worker():
            try:
                with execution_context(control, log_callback=logs.append):
                    _run_streaming_process(
                        [sys.executable, "-u", "-c", "import time; print('READY', flush=True); time.sleep(30)"],
                        input_text=None,
                        cwd=None,
                        timeout=60,
                    )
            except ExecutionCancelled:
                outcome["cancelled"] = True
            except Exception as e:
                outcome["error"] = repr(e)

        th = threading.Thread(target=worker, daemon=True)
        th.start()
        deadline = time.time() + 5
        while time.time() < deadline and not any("READY" in x for x in logs):
            time.sleep(0.05)
        control.cancel()
        th.join(timeout=5)

        self.assertFalse(th.is_alive())
        self.assertTrue(any("READY" in x for x in logs))
        self.assertTrue(outcome["cancelled"], outcome)
        self.assertIsNone(outcome["error"])


if __name__ == "__main__":
    unittest.main()
