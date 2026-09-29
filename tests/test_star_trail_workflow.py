import unittest
from astroauto.workflow import next_task_after_analysis

class StarTrailWorkflowTests(unittest.TestCase):
    def test_star_trail_first_task(self):
        project = {
            "project": {
                "target": {"category": "STAR_TRAIL"},
                "image_state": {"linearity": "UNKNOWN"},
                "input_stage": {"source_stage": "UNKNOWN"},
                "calibration": {"input_status": "UNKNOWN"},
                "star_trail": {"mode": "UNKNOWN"},
            }
        }
        task = next_task_after_analysis(project)
        self.assertEqual(task["task_id"], "CONFIRM_STAR_TRAIL_MODE")

if __name__ == "__main__":
    unittest.main()
