import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


class V014StructureTests(unittest.TestCase):
    def test_new_project_pipeline_order(self):
        text = (ROOT / "astroauto" / "project.py").read_text(encoding="utf-8")
        self.assertIn('"schema_version": "0.14.0"', text)
        self.assertIn('"processing_preset": "MANUAL_INSPIRED_SYQON"', text)
        self.assertIn('["GRADIENT", "SPCC", "DEBLUR", "DENOISE", "GHS"]', text)
        self.assertIn('"working/05_restore"', text)
        self.assertIn('"working/06_denoise"', text)

    def test_ui_defaults_use_syqon_first(self):
        doc = yaml.safe_load((ROOT / "config" / "ui_defaults.yaml").read_text(encoding="utf-8"))
        self.assertEqual(doc["deblur"]["engine"], "SYQON_PARALLAX")
        self.assertEqual(doc["denoise"]["engine"], "SYQON_PRISM")
        self.assertEqual(
            doc["workflow"]["linear_order"],
            ["GRADIENT", "SPCC", "DEBLUR", "DENOISE", "GHS"],
        )

    def test_launchers_share_common_policy(self):
        common = (ROOT / "run_common.bat").read_text(encoding="utf-8")
        gui = (ROOT / "run_gui.bat").read_text(encoding="utf-8")
        seq = (ROOT / "run_sequence_gui.bat").read_text(encoding="utf-8")
        self.assertIn('.venv\\Scripts\\python.exe', common)
        self.assertTrue('py.exe -3' in common or 'py -3' in common)
        # v0.14.1+ launchers intentionally inline the Windows-safe policy
        # instead of nesting CALL run_common.bat.
        for launcher in (gui, seq):
            self.assertIn('.venv\\Scripts\\python.exe', launcher)
            self.assertTrue('py.exe -3' in launcher or 'py -3' in launcher)
        self.assertIn('gui.py', gui)
        self.assertIn('sequence_gui.py', seq)

    def test_both_guis_use_shared_theme_and_dynamic_log(self):
        main = (ROOT / "gui.py").read_text(encoding="utf-8")
        seq = (ROOT / "sequence_gui.py").read_text(encoding="utf-8")
        for text in (main, seq):
            self.assertIn("apply_astro_theme", text)
            self.assertIn("ttk.Panedwindow", text)
            self.assertIn("MouseWheel", text)
            self.assertIn("_set_log_sash", text)
            self.assertIn("Progressbar", text)
        self.assertIn("SYQON_PARALLAX", main)
        self.assertIn("SYQON_PRISM", main)


if __name__ == "__main__":
    unittest.main()
