from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_project_intake_is_analysis_then_create():
    gui = (ROOT / "gui.py").read_text(encoding="utf-8")
    assert 'text="이미지 분석"' in gui
    assert 'text="프로젝트 생성"' in gui
    assert 'command=self.analyze_input' in gui
    assert 'command=self.create_project_from_analysis' in gui
    assert 'self.create_project_btn.state(["disabled"])' in gui
    assert '프로젝트 생성 + 분석' not in gui


def test_intake_metadata_autofill_and_unknown_label():
    gui = (ROOT / "gui.py").read_text(encoding="utf-8")
    intake = (ROOT / "astroauto" / "intake.py").read_text(encoding="utf-8")
    assert '"기타 / 직접입력", "UNKNOWN"' in gui
    assert 'target_from_header' in intake
    assert 'capture_date_from_header' in intake
    assert 'infer_category_from_target' in intake
    assert '천체 명칭을 입력해주세요.' in gui


def test_path_fields_readonly_and_status_is_stacked():
    gui = (ROOT / "gui.py").read_text(encoding="utf-8")
    assert 'self.input_entry = ttk.Entry(input_card, textvariable=self.input_var, state="readonly")' in gui
    assert 'self.root_entry = ttk.Entry(input_card, textvariable=self.root_var, state="readonly")' in gui
    assert 'text="상태", style="StatusKey.TLabel"' in gui
    assert 'pack(anchor="w", pady=(4,0))' in gui
    assert '경과 00:00' not in gui


def test_help_is_user_guide_not_ui_policy():
    gui = (ROOT / "gui.py").read_text(encoding="utf-8")
    help_text = (ROOT / "help" / "topics.yaml").read_text(encoding="utf-8")
    assert 'self.help.show_detail("ui.guide")' in gui
    assert 'ui.guide:' in help_text
    assert 'project.copyright:' in help_text


def test_copyright_metadata_is_preserved_and_written_to_final_fits():
    project = (ROOT / "astroauto" / "project.py").read_text(encoding="utf-8")
    final_export = (ROOT / "astroauto" / "final_export.py").read_text(encoding="utf-8")
    assert 'copyright_text: str = ""' in project
    assert '"copyright": str(copyright_text or "").strip()' in project
    assert 'hdu.header["COPYRGHT"]' in final_export
    assert 'copyright_embedded_fits' in final_export


def test_scrollbar_arrows_removed_and_entry_borderless():
    theme = (ROOT / "astroauto" / "ui_theme.py").read_text(encoding="utf-8")
    assert '"children": [("Vertical.Scrollbar.thumb"' in theme
    assert '"children": [("Horizontal.Scrollbar.thumb"' in theme
    assert '"sticky": "nswe", "border": "0"' in theme


def test_known_target_category_and_date_helpers_work_without_full_analysis():
    import sys
    sys.path.insert(0, str(ROOT))
    from astroauto.intake import infer_category_from_target, capture_date_from_header
    assert infer_category_from_target("M31") == "GALAXY"
    assert infer_category_from_target("Heart Nebula") == "EMISSION_NEBULA"
    assert infer_category_from_target("unknown target") == "UNKNOWN"
    assert capture_date_from_header({"DATE-OBS": "2026-09-30T12:34:56.000"}) == "2026-09-30"
