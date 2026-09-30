from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_project_intake_uses_borderless_native_entries():
    text = (ROOT / "gui.py").read_text(encoding="utf-8")
    assert "def _make_intake_entry" in text
    assert 'highlightthickness=0' in text
    assert 'bd=0' in text
    assert 'self.input_entry = self._make_intake_entry' in text
    assert 'self.root_entry = self._make_intake_entry' in text


def test_blank_click_clears_focus_without_editing_values():
    text = (ROOT / "gui.py").read_text(encoding="utf-8")
    assert 'bind_all("<Button-1>", self._on_global_left_click' in text
    assert "def _clear_ui_focus" in text
    assert "def _on_global_left_click" in text
    assert "self.focus_set()" in text


def test_combobox_layout_removes_native_border():
    text = (ROOT / "astroauto" / "ui_theme.py").read_text(encoding="utf-8")
    assert 'style.layout(\n            "TCombobox"' in text
    assert '"sticky": "nswe", "border": "0"' in text
