import unittest
from astroauto.denoise import build_denoise_command

class DenoiseCommandTests(unittest.TestCase):
    def test_default_command(self):
        self.assertEqual(build_denoise_command(), "denoise -mod=1")

    def test_optional_flags(self):
        cmd = build_denoise_command(
            modulation=0.7,
            cosmetic_correction=False,
            da3d=True,
            independent_channels=True,
        )
        self.assertIn("-mod=0.7", cmd)
        self.assertIn("-nocosmetic", cmd)
        self.assertIn("-da3d", cmd)
        self.assertIn("-indep", cmd)

    def test_invalid_modulation(self):
        with self.assertRaises(ValueError):
            build_denoise_command(modulation=1.1)

if __name__ == "__main__":
    unittest.main()
