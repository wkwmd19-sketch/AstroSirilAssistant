from __future__ import annotations
from pathlib import Path
import numpy as np
from astropy.io import fits


def make_center_crop_fits(source: Path, destination: Path, max_size: int = 1536) -> dict:
    """Create a same-scale central crop for fast AI preview.

    Spatial resolution is not downsampled, so star profile/Sharpen behavior remains
    representative. Only the field area is reduced.
    """
    source = Path(source)
    destination = Path(destination)
    max_size = max(256, int(max_size))
    destination.parent.mkdir(parents=True, exist_ok=True)

    with fits.open(source, memmap=True) as hdul:
        hdu = next((h for h in hdul if getattr(h, 'data', None) is not None and h.data.ndim >= 2), None)
        if hdu is None:
            raise ValueError('빠른 미리보기용 FITS 이미지 데이터를 찾지 못했습니다.')

        data = hdu.data
        height, width = int(data.shape[-2]), int(data.shape[-1])
        crop_w = min(width, max_size)
        crop_h = min(height, max_size)
        x0 = max(0, (width - crop_w) // 2)
        y0 = max(0, (height - crop_h) // 2)
        x1, y1 = x0 + crop_w, y0 + crop_h

        cropped = np.array(data[..., y0:y1, x0:x1], copy=True)
        header = hdu.header.copy()
        if 'CRPIX1' in header:
            try: header['CRPIX1'] = float(header['CRPIX1']) - x0
            except Exception: pass
        if 'CRPIX2' in header:
            try: header['CRPIX2'] = float(header['CRPIX2']) - y0
            except Exception: pass
        header['HISTORY'] = 'AstroSirilAssistant fast preview center crop'

        fits.PrimaryHDU(data=cropped, header=header).writeto(
            destination, overwrite=True, output_verify='silentfix'
        )

    return {
        'source_width': width,
        'source_height': height,
        'crop_width': crop_w,
        'crop_height': crop_h,
        'x0': x0,
        'y0': y0,
        'destination': str(destination),
        'cropped': crop_w != width or crop_h != height,
    }
