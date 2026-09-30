import tempfile
import unittest
from pathlib import Path
from astroauto.project import project_name, legacy_project_name, next_available_project_dir, find_existing_project_dir

class ProjectNamingTests(unittest.TestCase):
    def test_new_prefix(self):
        self.assertEqual(project_name("M31", "2026-09-30"), "Auto_M31_2026-09-30")
        self.assertEqual(legacy_project_name("M31", "2026-09-30"), "M31_2026-09-30_Auto")

    def test_increment(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Auto_M31_2026-09-30").mkdir()
            self.assertEqual(next_available_project_dir(root,"M31","2026-09-30").name,"Auto_M31_2026-09-30_02")

    def test_legacy_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); legacy=root/"M31_2026-09-30_Auto"; legacy.mkdir()
            self.assertEqual(find_existing_project_dir(root,"M31","2026-09-30"), legacy)

if __name__ == "__main__": unittest.main()
