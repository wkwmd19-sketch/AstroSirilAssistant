import tempfile
import unittest
from pathlib import Path

from astroauto.syqon import (
    build_parallax_command,
    build_prism_command,
    detect_syqon,
)


class SyQonV014Tests(unittest.TestCase):
    def test_parallax_default_command(self):
        cmd = build_parallax_command(Path("C:/Scripts/SyQon/Parallax.py"))
        self.assertIn("pyscript", cmd)
        self.assertIn("Parallax.py", cmd)
        self.assertIn("--edition nano", cmd)
        self.assertIn("--star-level 3", cmd)
        self.assertIn("--sharpen 1", cmd)
        self.assertIn("--tile 512", cmd)
        self.assertIn("--overlap 64", cmd)
        self.assertIn("--pad 96", cmd)
        self.assertIn("--mtf-target 0.25", cmd)
        self.assertNotIn("--no-correct", cmd)
        self.assertNotIn("--no-mtf", cmd)
        self.assertNotIn("--no-gpu", cmd)

    def test_parallax_optional_flags(self):
        cmd = build_parallax_command(
            Path("Parallax.py"),
            edition="pro",
            correct=False,
            star_level=7,
            use_mtf=False,
            linked=True,
            use_gpu=False,
        )
        self.assertIn("--edition pro", cmd)
        self.assertIn("--star-level 7", cmd)
        self.assertIn("--no-correct", cmd)
        self.assertIn("--no-mtf", cmd)
        self.assertIn("--linked", cmd)
        self.assertIn("--no-gpu", cmd)

    def test_parallax_nano_star_limit(self):
        with self.assertRaises(ValueError):
            build_parallax_command(Path("Parallax.py"), edition="nano", star_level=5.1)

    def test_prism_default_command(self):
        cmd = build_prism_command(Path("C:/Scripts/SyQon/Prism.py"))
        self.assertIn("Prism.py", cmd)
        self.assertIn("--tile-size 512", cmd)
        self.assertIn("--overlap 96", cmd)
        self.assertIn("--pad 96", cmd)
        self.assertIn("--modulation 1", cmd)
        self.assertIn("--model mini", cmd)
        self.assertIn("--stretch-method statistical", cmd)
        self.assertIn("--stretch-target 0.25", cmd)
        self.assertNotIn("--no-gpu", cmd)

    def test_custom_script_root_detection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            syqon = root / "processing" / "SyQon"
            syqon.mkdir(parents=True)
            (syqon / "Parallax.py").write_text(
                "import argparse\n# --star-level --sharpen --edition\n", encoding="utf-8"
            )
            (syqon / "Prism.py").write_text(
                "import argparse\n# --tile-size --modulation --model\n", encoding="utf-8"
            )
            info = detect_syqon({"syqon": {"script_roots": [str(root)]}})
            self.assertTrue(info["ready"])
            self.assertTrue(info["parallax"].endswith("Parallax.py"))
            self.assertTrue(info["prism"].endswith("Prism.py"))


if __name__ == "__main__":
    unittest.main()
