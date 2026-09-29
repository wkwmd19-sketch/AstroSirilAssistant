import unittest
from astroauto.final_export import final_basename, _validate

class FinalExportTests(unittest.TestCase):
    def test_final_basename(self):
        self.assertEqual(final_basename("M31"), "M31_final_Auto")

    def test_validate_defaults(self):
        opts = _validate(
            export_fits=True,
            export_tiff16=True,
            export_png16=True,
            tiff_deflate=True,
            fits_checksum=True,
            preview_jpeg_quality=95,
        )
        self.assertTrue(opts["export_fits"])
        self.assertTrue(opts["tiff_deflate"])
        self.assertEqual(opts["preview_jpeg_quality"], 95)

    def test_require_one_export(self):
        with self.assertRaises(ValueError):
            _validate(
                export_fits=False,
                export_tiff16=False,
                export_png16=False,
                tiff_deflate=True,
                fits_checksum=True,
                preview_jpeg_quality=95,
            )

if __name__ == "__main__":
    unittest.main()
