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



def make_even_geometry_fits(source: Path, destination: Path) -> dict:
    """Create an even-width/even-height FITS copy when required by AI tiling.

    Only the bottom/right edge is padded, so the original pixel coordinates and
    WCS CRPIX values stay unchanged. Edge replication avoids introducing a hard
    black border into restoration/deblur inference.
    """
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with fits.open(source, memmap=True) as hdul:
        hdu = next((h for h in hdul if getattr(h, 'data', None) is not None and h.data.ndim >= 2), None)
        if hdu is None:
            raise ValueError('FITS 이미지 데이터를 찾지 못했습니다.')

        data = hdu.data
        height, width = int(data.shape[-2]), int(data.shape[-1])
        pad_right = width % 2
        pad_bottom = height % 2

        if not pad_right and not pad_bottom:
            return {
                'source_width': width,
                'source_height': height,
                'prepared_width': width,
                'prepared_height': height,
                'pad_right': 0,
                'pad_bottom': 0,
                'padded': False,
                'destination': str(source),
            }

        pad_spec = [(0, 0)] * data.ndim
        pad_spec[-2] = (0, pad_bottom)
        pad_spec[-1] = (0, pad_right)
        prepared = np.pad(np.asarray(data), pad_spec, mode='edge')
        header = hdu.header.copy()
        header['HISTORY'] = 'AstroSirilAssistant even-geometry guard for SyQon preview'
        fits.PrimaryHDU(data=prepared, header=header).writeto(
            destination, overwrite=True, output_verify='silentfix'
        )

    return {
        'source_width': width,
        'source_height': height,
        'prepared_width': width + pad_right,
        'prepared_height': height + pad_bottom,
        'pad_right': pad_right,
        'pad_bottom': pad_bottom,
        'padded': True,
        'destination': str(destination),
    }


def restore_original_geometry_fits(source: Path, destination: Path, width: int, height: int) -> Path:
    """Crop a guarded AI result back to the exact original image dimensions."""
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    width, height = int(width), int(height)

    with fits.open(source, memmap=True) as hdul:
        hdu = next((h for h in hdul if getattr(h, 'data', None) is not None and h.data.ndim >= 2), None)
        if hdu is None:
            raise ValueError('복원 결과 FITS 이미지 데이터를 찾지 못했습니다.')
        data = np.array(hdu.data[..., :height, :width], copy=True)
        header = hdu.header.copy()
        header['HISTORY'] = 'AstroSirilAssistant restored original geometry after SyQon guard'
        fits.PrimaryHDU(data=data, header=header).writeto(
            destination, overwrite=True, output_verify='silentfix'
        )
    return destination
