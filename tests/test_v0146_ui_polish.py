import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V0146UIPolishTests(unittest.TestCase):
    def test_quick_preview_before_after_wiring(self):
        gui = (ROOT / 'gui.py').read_text(encoding='utf-8')
        deblur = (ROOT / 'astroauto' / 'deblur.py').read_text(encoding='utf-8')
        preview = (ROOT / 'astroauto' / 'preview_utils.py').read_text(encoding='utf-8')
        self.assertIn('def _open_before_after_preview', gui)
        self.assertIn('Before · SPCC', gui)
        self.assertIn('After · Parallax', gui)
        self.assertIn('make_linked_comparison_ppm', deblur)
        self.assertIn('"before_preview"', deblur)
        self.assertIn('"after_preview"', deblur)
        self.assertIn('stretch_source', preview)
        self.assertIn("'BEFORE_ONLY'", preview)

    def test_primary_copy_is_compact(self):
        gui = (ROOT / 'gui.py').read_text(encoding='utf-8')
        self.assertIn('text="상태"', gui)
        self.assertIn('text="처리 설정"', gui)
        self.assertIn('text="단일 이미지"', gui)
        self.assertIn('text="입력 FITS"', gui)
        self.assertIn('text="저장 위치"', gui)
        self.assertNotIn('Manual-inspired semi-auto processing', gui)
        self.assertNotIn('로그 Pane 경계선을 드래그', gui)
        self.assertNotIn('pyscript StarNet.py', gui)
        self.assertNotIn('SUBTRACT — Original - Starless', gui)

    def test_sequence_copy_matches_main_style(self):
        seq = (ROOT / 'sequence_gui.py').read_text(encoding='utf-8')
        self.assertIn('text="상태"', seq)
        self.assertIn('text="시퀀스"', seq)
        self.assertIn('text="저장 위치"', seq)
        self.assertNotIn('로그 Pane 경계선을 드래그', seq)


if __name__ == '__main__':
    unittest.main()
