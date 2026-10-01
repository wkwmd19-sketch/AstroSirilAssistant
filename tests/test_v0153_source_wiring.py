"""Dependency-independent wiring checks for the new calibration GUI stage."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gui_contains_real_calibration_controls():
    content = (ROOT / "gui.py").read_text(encoding="utf-8")
    tree = ast.parse(content)
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "App")
    methods = {node.name for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert {"_build_calibration_controls", "import_calibration_frames",
            "check_calibration_frames", "skip_calibration_frames"} <= methods
    assert '"REVIEW_CALIBRATION_FRAMES"' in content


def test_all_updated_python_files_compile():
    for file in ("gui.py", "app.py", "astroauto/calibration.py", "astroauto/workflow.py"):
        ast.parse((ROOT / file).read_text(encoding="utf-8"))


def test_calibration_fits_inspection_is_header_only():
    tree = ast.parse((ROOT / "astroauto" / "calibration.py").read_text(encoding="utf-8"))
    method = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "read_frame_metadata")
    calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "open"
             and isinstance(node.func.value, ast.Name) and node.func.value.id == "fits"]
    assert len(calls) == 1
    opts = {x.arg: x.value for x in calls[0].keywords}
    assert isinstance(opts["memmap"], ast.Constant) and opts["memmap"].value is False
    assert isinstance(opts["do_not_scale_image_data"], ast.Constant)
    assert opts["do_not_scale_image_data"].value is True
    assert not any(isinstance(node, ast.Attribute) and node.attr == "data" for node in ast.walk(method))
