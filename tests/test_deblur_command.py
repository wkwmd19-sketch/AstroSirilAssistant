import unittest
from astroauto.deblur import build_makepsf_command, build_rl_command

class DeblurCommandTests(unittest.TestCase):
    def test_default_psf(self):
        cmd = build_makepsf_command()
        self.assertEqual(cmd, "makepsf stars")

    def test_psf_options(self):
        cmd = build_makepsf_command(
            symmetric_psf=True,
            kernel_size=31,
            savepsf="D:/Astro/test psf.fits",
        )
        self.assertIn("-sym", cmd)
        self.assertIn("-ks=31", cmd)
        self.assertIn('"-savepsf=D:/Astro/test psf.fits"', cmd)

    def test_default_rl(self):
        self.assertEqual(build_rl_command(), "rl -iters=10")

    def test_regularized_rl(self):
        cmd = build_rl_command(
            iterations=8,
            regularization="TV",
            alpha=2500,
            multiplicative=True,
        )
        self.assertIn("-iters=8", cmd)
        self.assertIn("-tv", cmd)
        self.assertIn("-alpha=2500", cmd)
        self.assertIn("-mul", cmd)

if __name__ == "__main__":
    unittest.main()
