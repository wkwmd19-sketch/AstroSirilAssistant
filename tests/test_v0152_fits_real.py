"""Real Astropy BZERO/BSCALE FITS regression (requires installed Astropy)."""
import pytest
import numpy as np

fits = pytest.importorskip("astropy.io.fits", reason="Real FITS I/O requires astropy")
from astroauto.fits_analysis import analyze_pixels, read_header_summary


def test_unsigned_16bit_rgb_with_bzero_and_bscale(tmp_path):
    image = (np.arange(3 * 12 * 16, dtype=np.uint16).reshape(3, 12, 16) + 3000)
    path = tmp_path / "unsigned_rgb.fits"
    hdu = fits.PrimaryHDU(image)
    hdu.header["INSTRUME"] = "Canon EOS RP"
    hdu.writeto(path)
    with fits.open(path, do_not_scale_image_data=True) as hdul:
        assert hdul[0].header["BITPIX"] == 16
        assert hdul[0].header["BZERO"] == 32768
        assert hdul[0].header["BSCALE"] == 1
    result = analyze_pixels(path, max_samples=1000)
    header, history = read_header_summary(path)
    assert result["shape"] == [3, 12, 16]
    assert list(result["channels"]) == ["R", "G", "B"]
    assert all(channel["sample_count"] == 12 * 16 for channel in result["channels"].values())
    assert header["INSTRUME"] == "Canon EOS RP"
    assert header["BITPIX"] == 16
    assert isinstance(history, list)


def test_float32_mono_fits_still_analyzes(tmp_path):
    image = np.linspace(0.1, 0.9, 60, dtype=np.float32).reshape(6, 10)
    path = tmp_path / "float_mono.fits"
    fits.PrimaryHDU(image).writeto(path)
    result = analyze_pixels(path)
    header, _ = read_header_summary(path)
    assert result["shape"] == [6, 10]
    assert list(result["channels"]) == ["K"]
    assert header["BITPIX"] == -32
