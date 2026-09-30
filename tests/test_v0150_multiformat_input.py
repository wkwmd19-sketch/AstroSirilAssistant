from pathlib import Path
import json
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_supported_single_image_formats_are_classified():
    import sys
    sys.path.insert(0, str(ROOT))
    from astroauto.input_formats import describe_input

    cases = {
        "a.fits": ("FITS", False, False),
        "a.fits.fz": ("FITS", False, False),
        "a.CR3": ("RAW", True, False),
        "a.nef": ("RAW", True, False),
        "a.tiff": ("TIFF", False, False),
        "a.png": ("PNG", False, False),
        "a.jpg": ("JPEG", False, True),
    }
    for name, (family, raw, lossy) in cases.items():
        d = describe_input(Path(name))
        assert d.supported
        assert d.family == family
        assert d.raw is raw
        assert d.lossy is lossy


def test_source_aware_linearity_policy():
    import sys
    sys.path.insert(0, str(ROOT))
    from astroauto.input_formats import describe_input, linearity_for_source

    unknown = {"status": "UNKNOWN", "confidence": 0.0, "reason": "", "evidence": []}
    assert linearity_for_source(describe_input(Path("a.cr3")), unknown)["status"] == "LINEAR"
    assert linearity_for_source(describe_input(Path("a.jpg")), unknown)["status"] == "NONLINEAR"
    assert linearity_for_source(describe_input(Path("a.png")), unknown)["status"] == "UNKNOWN"
    assert linearity_for_source(describe_input(Path("a.tif")), unknown)["status"] == "UNKNOWN"


def test_project_preserves_original_and_uses_normalized_fits():
    import sys
    sys.path.insert(0, str(ROOT))
    from astroauto.project import create_project

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        raw = root / "IMG_0001.CR3"
        raw.write_bytes(b"raw-source-must-be-preserved")
        normalized = root / "analysis_input.fits"
        normalized.write_bytes(b"normalized-fits-placeholder")
        report = {
            "normalization": {
                "required": True,
                "analysis_file": str(normalized),
                "working_format": "FITS",
                "precision": "32-bit float",
                "method": "SIRIL_RAW_DEBAYER",
                "debayered": True,
            },
            "source_metadata": {
                "schema_version": "1.0",
                "source": {"format": "CR3", "family": "RAW"},
            },
        }
        pdir = create_project(
            root=root / "projects",
            target="Moon",
            capture_date="2026-09-30",
            category="PLANETARY_LUNAR",
            input_file=raw,
            analysis_report=report,
        )

        original = pdir / "input" / "original" / raw.name
        working = pdir / "input" / "normalized" / "Moon_00_input.fits"
        metadata = pdir / "input" / "metadata" / "source_metadata.json"
        assert original.read_bytes() == raw.read_bytes()
        assert working.read_bytes() == normalized.read_bytes()
        assert metadata.exists()

        project = yaml.safe_load((pdir / "project.yaml").read_text(encoding="utf-8"))["project"]
        assert project["current_file"] == str(working)
        assert project["input"]["source_format"] == "CR3"
        assert project["input"]["raw_source"] is True
        assert project["input"]["normalization"]["debayered"] is True
        payload = json.loads(metadata.read_text(encoding="utf-8"))
        assert payload["project"]["original_file"] == str(original)
        assert payload["project"]["normalized_file"] == str(working)


def test_nonfits_project_requires_prior_analysis():
    import sys
    sys.path.insert(0, str(ROOT))
    from astroauto.project import create_project

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        jpg = root / "moon.jpg"
        jpg.write_bytes(b"jpg")
        try:
            create_project(
                root=root / "projects",
                target="Moon",
                capture_date="2026-09-30",
                category="PLANETARY_LUNAR",
                input_file=jpg,
            )
        except ValueError as exc:
            assert "이미지 분석" in str(exc)
        else:
            raise AssertionError("JPG project must require prior analysis")


def test_gui_exposes_multiformat_picker_and_analysis_contract():
    gui = (ROOT / "gui.py").read_text(encoding="utf-8")
    assert '("카메라 RAW", "*.cr2 *.cr3 *.nef *.arw *.dng' in gui
    assert '("TIFF / PNG / JPEG", "*.tif *.tiff *.png *.jpg *.jpeg")' in gui
    assert "analysis_report=self._intake_analysis_report" in gui
    assert "cleanup_analysis_cache" in gui
    assert "입력 형식:" in gui
    assert "작업 형식:" in gui


def test_raw_normalizer_uses_documented_convertraw_debayer_path():
    text = (ROOT / "astroauto" / "input_formats.py").read_text(encoding="utf-8")
    assert "convertraw astroauto_raw -debayer" in text
    assert '"set32bits"' in text
    assert '"setext fits"' in text


def test_milky_way_and_lunar_names_do_not_fall_back_to_galaxy():
    import sys
    sys.path.insert(0, str(ROOT))
    from astroauto.intake import infer_category_from_target
    assert infer_category_from_target("은하수") == "MILKYWAY"
    assert infer_category_from_target("Milky Way") == "MILKYWAY"
    assert infer_category_from_target("달") == "PLANETARY_LUNAR"
    assert infer_category_from_target("Moon") == "PLANETARY_LUNAR"


def test_raw_normalizer_has_no_ambiguous_loader_fallback():
    text = (ROOT / "astroauto" / "input_formats.py").read_text(encoding="utf-8")
    assert "데이터 무결성을 위해 Debayer 여부가 불명확한 일반 loader fallback은 사용하지 않습니다." in text
    assert "convertraw astroauto_raw -debayer" in text


def test_compressed_fits_is_expanded_before_project_processing():
    import sys
    sys.path.insert(0, str(ROOT))
    from astroauto.input_formats import describe_input
    d = describe_input(Path("stack.fits.fz"))
    assert d.family == "FITS"
    assert d.fits is True
    assert d.needs_normalization is True
    assert d.format == "FITS.FZ"
