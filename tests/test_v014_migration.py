import tempfile
import unittest
from pathlib import Path
import yaml

from astroauto.denoise import migrate_post_spcc_task
from astroauto.deblur import migrate_post_denoise_task


def write_project(root: Path, state: str, next_task: str, *, deblurred=False):
    doc = {
        "schema_version": "0.13.1",
        "project": {
            "current_state": state,
            "current_file": str(root / "dummy.fits"),
            "image_state": {
                "linearity": "LINEAR",
                "stretched": False,
                "deblurred": deblurred,
                "denoised": state == "DENOISED",
                "color_calibrated": True,
            },
            "next_task": {"task_id": next_task},
        },
    }
    (root / "project.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


class V014MigrationTests(unittest.TestCase):
    def test_color_calibrated_old_project_moves_to_restoration(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_project(root, "COLOR_CALIBRATED", "DENOISE")
            project = migrate_post_spcc_task(root)
            self.assertEqual(project["project"]["next_task"]["task_id"], "DEBLUR")
            self.assertEqual(
                project["project"]["processing_preset"], "MANUAL_INSPIRED_SYQON"
            )

    def test_already_denoised_old_project_keeps_legacy_progress(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_project(root, "DENOISED", "DEBLUR")
            project = migrate_post_denoise_task(root)
            self.assertEqual(project["project"]["current_state"], "DENOISED")
            self.assertEqual(project["project"]["next_task"]["task_id"], "DEBLUR")
            self.assertIn(
                "LEGACY_ORDER",
                project["project"]["next_task"]["current_status"],
            )


if __name__ == "__main__":
    unittest.main()
