from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cozy_palette_and_styles_are_present():
    text = (ROOT / "astroauto" / "ui_theme.py").read_text(encoding="utf-8")
    assert "Astro Cozy Dark" in text
    assert '"accent": "#83B8D8"' in text
    assert '"success": "#79C6A3"' in text
    assert '"danger": "#D9878D"' in text
    assert '"Danger.TButton"' in text
    assert 'borderwidth=0' in text
    assert 'padding=(16, 14)' in text


def test_both_guis_use_cozy_busy_bar_and_stop_button():
    main = (ROOT / "gui.py").read_text(encoding="utf-8")
    seq = (ROOT / "sequence_gui.py").read_text(encoding="utf-8")
    assert "v0.14.7" in main
    assert "v0.14.7" in seq
    assert 'style="Danger.TButton"' in main
    assert 'style="Danger.TButton"' in seq
    assert 'style="Surface.TFrame", padding=(14, 10)' in main
    assert 'style="Surface.TFrame", padding=(14, 10)' in seq


def test_processing_files_are_not_modified_by_theme_release_marker():
    # The UI polish should not add v0.14.7-specific logic to processing modules.
    for name in ("deblur.py", "denoise.py", "ghs.py", "final_export.py", "siril.py", "syqon.py"):
        text = (ROOT / "astroauto" / name).read_text(encoding="utf-8")
        assert "0.14.7" not in text
