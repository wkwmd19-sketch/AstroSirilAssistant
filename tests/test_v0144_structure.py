import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


class V0144StructureTests(unittest.TestCase):
    def test_flow_summary_and_restoration_labels(self):
        gui = (ROOT / 'gui.py').read_text(encoding='utf-8')
        self.assertIn('현재 단계 :', gui)
        self.assertIn('다음 작업 :', gui)
        self.assertIn('"DEBLUR": (', gui)
        self.assertIn('Prism Noise Reduction', gui)
        self.assertIn('전체 처리 + 결과 확인', gui)
        self.assertIn('결과 승인', gui)

    def test_full_preview_candidate_is_promoted(self):
        deblur = (ROOT / 'astroauto' / 'deblur.py').read_text(encoding='utf-8')
        gui = (ROOT / 'gui.py').read_text(encoding='utf-8')
        self.assertIn('def promote_deblur_preview', deblur)
        self.assertIn('"reused_full_preview": True', deblur)
        self.assertIn('promote_deblur_preview(', gui)

    def test_syqon_full_run_safety_config(self):
        cfg = yaml.safe_load((ROOT / 'config' / 'app.yaml').read_text(encoding='utf-8'))
        self.assertEqual(cfg['syqon']['startup_watchdog_sec'], 90)
        self.assertTrue(cfg['syqon']['even_geometry_guard'])
        siril = (ROOT / 'astroauto' / 'siril.py').read_text(encoding='utf-8')
        preview = (ROOT / 'astroauto' / 'preview_utils.py').read_text(encoding='utf-8')
        self.assertIn('SirilStartupTimeout', siril)
        self.assertIn('def make_even_geometry_fits', preview)
        self.assertIn('def restore_original_geometry_fits', preview)


if __name__ == '__main__':
    unittest.main()
