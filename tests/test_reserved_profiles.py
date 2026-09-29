import unittest
from astroauto.workflow import next_task_after_analysis

class ReservedProfileTests(unittest.TestCase):
    def test_planetary_lunar_task(self):
        project = {
            "project": {
                "target": {"category": "PLANETARY_LUNAR"},
                "image_state": {"linearity": "UNKNOWN"},
                "input_stage": {"source_stage": "UNKNOWN"},
                "calibration": {"input_status": "UNKNOWN"},
                "star_trail": {"mode": "UNKNOWN"},
            }
        }
        task = next_task_after_analysis(project)
        self.assertEqual(task["task_id"], "PLANETARY_LUNAR_WORKFLOW_REVIEW")

if __name__ == "__main__":
    unittest.main()
