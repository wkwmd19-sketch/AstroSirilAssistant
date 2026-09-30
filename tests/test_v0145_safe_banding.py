import tempfile
import unittest
from pathlib import Path
import numpy as np
from astropy.io import fits

from astroauto.preview_utils import (
    fits_processing_payload_info,
    plan_safe_horizontal_bands,
    write_horizontal_band_fits,
    stitch_horizontal_bands_fits,
)


class V0145SafeBandTests(unittest.TestCase):
    def test_large_rgb_image_is_split_under_payload_limit(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'in.fits'
            data = np.zeros((3, 1744, 3714), dtype=np.float32)
            fits.PrimaryHDU(data=data).writeto(p)
            info = fits_processing_payload_info(p)
            plan = plan_safe_horizontal_bands(p, max_payload_mib=32, overlap=192)
            self.assertGreater(info['payload_mib'], 32)
            self.assertTrue(plan['chunked'])
            self.assertGreaterEqual(plan['band_count'], 2)
            for b in plan['bands']:
                payload = 3714 * b['height'] * 3 * 4 / (1024*1024)
                self.assertLessEqual(payload, 32.1)

    def test_band_stitch_reconstructs_original_geometry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / 'src.fits'
            h, w = 900, 1200
            yy = np.arange(h, dtype=np.float32)[None, :, None]
            data = np.repeat(yy, w, axis=2)
            data = np.repeat(data, 3, axis=0)
            fits.PrimaryHDU(data=data).writeto(src)
            plan = plan_safe_horizontal_bands(src, max_payload_mib=3.0, overlap=96)
            processed = []
            for b in plan['bands']:
                bp = root / f"b{b['index']}.fits"
                write_horizontal_band_fits(src, bp, b['y0'], b['y1'])
                processed.append({**b, 'path': str(bp)})
            out = root / 'out.fits'
            stitch_horizontal_bands_fits(src, processed, out)
            with fits.open(out) as hdul:
                result = hdul[0].data
            self.assertEqual(result.shape, data.shape)
            self.assertTrue(np.allclose(result, data, atol=1e-5))


if __name__ == '__main__':
    unittest.main()
