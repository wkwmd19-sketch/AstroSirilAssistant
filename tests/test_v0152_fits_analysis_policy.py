"""Dependency-light policy regression for scaled FITS analysis.

The actual FITS round-trip is in test_v0152_fits_real.py and runs in the
user's installed Astropy environment. This test works without Astropy.
"""
from pathlib import Path
import ast
import math
import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / "astroauto" / "fits_analysis.py"


def _function(name):
    module = ast.parse(SOURCE.read_text(encoding="utf-8"))
    return next(item for item in module.body if isinstance(item, ast.FunctionDef) and item.name == name)


def test_pixel_and_header_reads_disable_memmap_for_scaled_fits():
    for func_name in ("analyze_pixels", "read_header_summary"):
        node = _function(func_name)
        opens = [n for n in ast.walk(node) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == "open"
                 and isinstance(n.func.value, ast.Name) and n.func.value.id == "fits"]
        assert len(opens) == 1, func_name
        keywords = {item.arg: item.value for item in opens[0].keywords}
        assert "memmap" in keywords
        assert isinstance(keywords["memmap"], ast.Constant)
        assert keywords["memmap"].value is False


def test_large_array_is_sampled_before_float64_conversion():
    """Run the sampling functions in isolation to avoid an Astropy dependency."""
    funcs = [_function("_clean_numeric"), _function("_sample_evenly")]
    module = ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[]))
    namespace = {"np": np, "math": math}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    sample = namespace["_sample_evenly"](np.arange(100000, dtype=np.uint16), 1000)
    assert sample.size <= 1000
    assert sample.dtype == np.float64
    assert sample[0] == 0
    assert sample[-1] < 100000


def test_sample_limit_rejects_non_positive():
    funcs = [_function("_clean_numeric"), _function("_sample_evenly")]
    module = ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[]))
    namespace = {"np": np, "math": math}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    try:
        namespace["_sample_evenly"](np.arange(8), 0)
    except ValueError as exc:
        assert "max_samples" in str(exc)
    else:
        raise AssertionError("invalid sample limit did not fail")
