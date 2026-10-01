"""Regression tests for v0.15.3; requires astropy for actual FITS I/O."""
from pathlib import Path
import json
import tempfile

import numpy as np
import pytest

fits = pytest.importorskip("astropy.io.fits")

from astroauto.analyzer import apply_analysis_to_project
from astroauto.calibration import (
    FRAME_FOLDERS, compare_to_light, import_calibration_folder,
    read_frame_metadata, scan_project_calibration, skip_project_calibration,
)
from astroauto.project import create_project, load_project
from astroauto.state_actions import confirm_calibration_status, confirm_input_stage


def _write_fits(path: Path, exptime=133.2, iso=1600, shape=(3, 4, 5)):
    header = fits.Header()
    header["EXPTIME"] = exptime
    header["ISOSPEED"] = iso
    header["INSTRUME"] = "Canon EOS RP"
    header["XBINNING"] = 1
    header["YBINNING"] = 1
    fits.writeto(path, np.zeros(shape, dtype=np.uint16), header, overwrite=True)


def _make_project(root: Path):
    source = root / "light.fits"
    _write_fits(source)
    project_dir = create_project(root / "projects", "Milkyway", "2026-06-16", "MILKYWAY", source)
    apply_analysis_to_project(project_dir, {
        "source": {"format": "FITS", "family": "FITS"},
        "header": {"INSTRUME": "Canon EOS RP", "EXPTIME": 133.2, "ISOSPEED": 1600},
        "linearity_assessment": {"status": "LINEAR", "confidence": 0.98},
    })
    confirm_input_stage(project_dir, "SINGLE_LIGHT")
    confirm_calibration_status(project_dir, "RAW_UNCALIBRATED")
    return project_dir


def test_unsigned_bzero_header_only_inspection():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "test.fits"
        _write_fits(f)
        assert fits.getheader(f)["BZERO"] == 32768
        meta = read_frame_metadata(f)
        assert meta["shape"] == [3, 4, 5]
        assert meta["exposure_sec"] == pytest.approx(133.2)
        assert meta["iso"] == 1600
        assert meta["instrume"] == "Canon EOS RP"


def test_no_frames_review_skip_and_source_preservation():
    with tempfile.TemporaryDirectory() as td:
        pdir = _make_project(Path(td))
        p0 = load_project(pdir)["project"]
        source_path = Path(p0["current_file"])
        before = source_path.read_bytes()
        assert p0["next_task"]["task_id"] == "CHECK_CALIBRATION_FRAMES"
        project, report = scan_project_calibration(pdir, {"calibration": {"compatibility": {}}})
        assert project["project"]["next_task"]["task_id"] == "REVIEW_CALIBRATION_FRAMES"
        assert all(s["count"] == 0 for s in report["frames"].values())
        assert (pdir / "logs" / "calibration_report.json").exists()
        assert json.loads((pdir / "logs" / "calibration_report.json").read_text(encoding="utf-8"))["light_reference"]["iso"] == 1600
        project = skip_project_calibration(pdir)
        assert project["project"]["current_state"] == "CALIBRATION_SKIPPED"
        assert project["project"]["next_task"]["task_id"] == "GRADIENT_CORRECTION"
        assert project["project"]["next_task"]["current_status"].startswith("SINGLE_LIGHT")
        assert source_path.read_bytes() == before
        with pytest.raises(ValueError):
            skip_project_calibration(pdir)


def test_mixed_dark_exposure_is_not_hidden_by_median():
    with tempfile.TemporaryDirectory() as td:
        pdir = _make_project(Path(td))
        darks = pdir / FRAME_FOLDERS["dark"]
        _write_fits(darks / "dark1.fits", exptime=133.2)
        _write_fits(darks / "dark2.fits", exptime=60.0)
        _, report = scan_project_calibration(pdir, {"calibration": {"compatibility": {}}})
        assert report["frames"]["dark"]["count"] == 2
        assert report["compatibility"]["dark"]["status"] == "INCOMPATIBLE"
        assert "exposure" in report["compatibility"]["dark"]["failures"]


def test_import_preserves_file_and_renames_same_name_conflict():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pdir = _make_project(root)
        source = root / "darks"
        source.mkdir()
        (source / "dark.CR3").write_bytes(b"original-a")
        result = import_calibration_folder(pdir, "dark", source)
        assert result["imported"] == 1
        assert (source / "dark.CR3").read_bytes() == b"original-a"
        result = import_calibration_folder(pdir, "dark", source)
        assert result["imported"] == 0
        assert result["existing"] == 1
        (source / "dark.CR3").write_bytes(b"different-original-b")
        result = import_calibration_folder(pdir, "dark", source)
        assert result["imported"] == 1
        dest = pdir / FRAME_FOLDERS["dark"]
        assert (dest / "dark.CR3").read_bytes() == b"original-a"
        assert (dest / "dark_02.CR3").read_bytes() == b"different-original-b"
        assert load_project(pdir)["project"]["calibration"]["checked"] is False
        with pytest.raises(ValueError):
            import_calibration_folder(pdir, "lights", source)


def test_no_mistaking_iso_for_gain():
    light = {"shape": [3, 4, 5], "gain": None, "iso": 1600, "exposure_sec": 133.2,
             "instrume": "Canon EOS RP", "binning": [1, 1], "temperature_c": None}
    darks = {"available": True, "files": [dict(light, iso=800)],
             "summary": {"shapes": [[3, 4, 5]], "exposure_sec_median": 133.2}}
    scans = {"dark": darks, "flat": {"available": False}, "bias": {"available": False},
             "dark_flat": {"available": False}}
    comp = compare_to_light(light, scans, {"calibration": {"compatibility": {}}})
    assert comp["dark"]["status"] == "INCOMPATIBLE"
    assert "iso" in comp["dark"]["failures"]
