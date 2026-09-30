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



def make_linked_comparison_ppm(
    before_fits: Path,
    after_fits: Path,
    before_ppm: Path,
    after_ppm: Path,
    *,
    target_background: float = 0.25,
) -> dict:
    """Create 8-bit PPM Before/After previews with one shared display stretch.

    The transform is derived only from the Before crop and then applied unchanged
    to both images. This is display-only: the FITS files are never modified.
    PPM is used so Tk can show the comparison without an extra imaging package.
    """
    before_fits = Path(before_fits)
    after_fits = Path(after_fits)
    before_ppm = Path(before_ppm)
    after_ppm = Path(after_ppm)
    before_ppm.parent.mkdir(parents=True, exist_ok=True)
    after_ppm.parent.mkdir(parents=True, exist_ok=True)

    def _read_hwc(path: Path) -> np.ndarray:
        with fits.open(path, memmap=True) as hdul:
            hdu = next((h for h in hdul if getattr(h, 'data', None) is not None and h.data.ndim >= 2), None)
            if hdu is None:
                raise ValueError(f'비교 미리보기용 FITS 이미지 데이터를 찾지 못했습니다: {path}')
            arr = np.asarray(hdu.data, dtype=np.float32)

        if arr.ndim == 2:
            arr = np.repeat(arr[..., None], 3, axis=2)
        elif arr.ndim == 3:
            if arr.shape[0] in (1, 3, 4):
                arr = np.moveaxis(arr[:3], 0, -1)
            elif arr.shape[-1] in (1, 3, 4):
                arr = arr[..., :3]
            else:
                raise ValueError(f'지원하지 않는 비교 미리보기 FITS shape입니다: {arr.shape}')
            if arr.shape[-1] == 1:
                arr = np.repeat(arr, 3, axis=2)
        else:
            raise ValueError(f'지원하지 않는 비교 미리보기 FITS 차원입니다: {arr.shape}')
        return np.asarray(arr, dtype=np.float32)

    before = _read_hwc(before_fits)
    after = _read_hwc(after_fits)
    if before.shape != after.shape:
        raise ValueError(
            f'Before/After 비교 이미지 크기가 다릅니다: {before.shape} / {after.shape}'
        )

    # Linked luminance-like reference. A single scalar transform is then applied
    # to every RGB channel so color differences are not independently normalized.
    lum = np.mean(before, axis=2, dtype=np.float32)
    finite = lum[np.isfinite(lum)]
    if finite.size == 0:
        raise ValueError('Before 비교 이미지에 유효한 픽셀이 없습니다.')

    # Sampling keeps percentile/MAD work bounded for larger quick-preview sizes.
    if finite.size > 750_000:
        stride = max(1, finite.size // 750_000)
        finite = finite[::stride]

    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))
    robust_sigma = max(1e-12, 1.4826 * mad)
    low_percentile = float(np.percentile(finite, 0.02))
    black = max(low_percentile, median - 2.8 * robust_sigma)
    white = float(np.percentile(finite, 99.99))
    if not np.isfinite(white) or white <= black + 1e-12:
        white = float(np.max(finite))
    if white <= black + 1e-12:
        white = black + 1.0

    median_norm = (median - black) / (white - black)
    median_norm = float(np.clip(median_norm, 1e-4, 0.9999))
    target_background = float(np.clip(target_background, 0.05, 0.45))
    gamma = float(np.log(target_background) / np.log(median_norm))
    gamma = float(np.clip(gamma, 0.15, 5.0))

    def _to_u8(arr: np.ndarray) -> np.ndarray:
        clean = np.nan_to_num(arr, nan=black, posinf=white, neginf=black)
        x = np.clip((clean - black) / (white - black), 0.0, 1.0)
        x = np.power(x, gamma).astype(np.float32, copy=False)
        return np.clip(np.rint(x * 255.0), 0, 255).astype(np.uint8)

    before_u8 = _to_u8(before)
    after_u8 = _to_u8(after)

    def _write_ppm(path: Path, rgb: np.ndarray) -> None:
        h, w, _ = rgb.shape
        with path.open('wb') as f:
            f.write(f'P6\n{w} {h}\n255\n'.encode('ascii'))
            f.write(np.ascontiguousarray(rgb).tobytes())

    _write_ppm(before_ppm, before_u8)
    _write_ppm(after_ppm, after_u8)

    return {
        'before_ppm': str(before_ppm),
        'after_ppm': str(after_ppm),
        'width': int(before.shape[1]),
        'height': int(before.shape[0]),
        'black': black,
        'white': white,
        'gamma': gamma,
        'target_background': target_background,
        'stretch_source': 'BEFORE_ONLY',
        'linear_fits_unchanged': True,
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



def fits_processing_payload_info(source: Path, bytes_per_sample: int = 4) -> dict:
    """Estimate the RGB/mono 32-bit pixel payload that sirilpy must exchange.

    Siril processing is forced to 32-bit in this workflow, therefore the
    estimated bridge payload intentionally uses 4 bytes/sample regardless of
    the FITS storage bit depth.
    """
    source = Path(source)
    with fits.open(source, memmap=True) as hdul:
        hdu = next((h for h in hdul if getattr(h, 'data', None) is not None and h.data.ndim >= 2), None)
        if hdu is None:
            raise ValueError('FITS 이미지 데이터를 찾지 못했습니다.')
        shape = tuple(int(x) for x in hdu.data.shape)
    height, width = shape[-2], shape[-1]
    planes = int(np.prod(shape[:-2])) if len(shape) > 2 else 1
    payload = width * height * planes * int(bytes_per_sample)
    return {
        'shape': shape,
        'width': width,
        'height': height,
        'planes': planes,
        'bytes_per_sample': int(bytes_per_sample),
        'payload_bytes': int(payload),
        'payload_mib': float(payload) / (1024.0 * 1024.0),
    }


def plan_safe_horizontal_bands(source: Path, max_payload_mib: float = 32.0, overlap: int = 192) -> dict:
    """Plan overlapping full-width bands below a conservative sirilpy payload.

    This is a compatibility path for Windows/SyQon runs where a large loaded
    image stalls before the Python script connects. It preserves native pixel
    scale and uses feathered overlap on reassembly.
    """
    info = fits_processing_payload_info(source, bytes_per_sample=4)
    width, height, planes = info['width'], info['height'], info['planes']
    max_bytes = max(8 * 1024 * 1024, int(float(max_payload_mib) * 1024 * 1024))
    row_bytes = max(1, width * planes * 4)
    max_height = min(height, max_bytes // row_bytes)
    max_height = max(256, int(max_height))
    if max_height % 2:
        max_height -= 1

    overlap = max(64, int(overlap))
    if overlap % 2:
        overlap += 1
    # Leave a useful core region for every inference band.
    overlap = min(overlap, max(64, max_height // 3))

    if height <= max_height:
        bands = [{'index': 1, 'y0': 0, 'y1': height, 'height': height}]
    else:
        bands = []
        y0 = 0
        idx = 1
        while y0 < height:
            y1 = min(height, y0 + max_height)
            if y1 < height and y1 % 2:
                y1 -= 1
            if y1 <= y0:
                raise ValueError('SyQon 안전 분할 높이를 계산하지 못했습니다.')
            bands.append({'index': idx, 'y0': y0, 'y1': y1, 'height': y1-y0})
            idx += 1
            if y1 >= height:
                break
            next_y0 = max(0, y1 - overlap)
            if next_y0 % 2:
                next_y0 -= 1
            if next_y0 <= y0:
                next_y0 = y0 + max(2, (max_height - overlap) // 2 * 2)
            y0 = next_y0

    return {
        **info,
        'max_payload_mib': float(max_payload_mib),
        'max_band_height': int(max_height),
        'overlap': int(overlap),
        'band_count': len(bands),
        'bands': bands,
        'chunked': len(bands) > 1,
    }


def write_horizontal_band_fits(source: Path, destination: Path, y0: int, y1: int) -> Path:
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    y0, y1 = int(y0), int(y1)
    with fits.open(source, memmap=True) as hdul:
        hdu = next((h for h in hdul if getattr(h, 'data', None) is not None and h.data.ndim >= 2), None)
        if hdu is None:
            raise ValueError('FITS 이미지 데이터를 찾지 못했습니다.')
        height = int(hdu.data.shape[-2])
        if not (0 <= y0 < y1 <= height):
            raise ValueError(f'잘못된 band 범위입니다: {y0}:{y1} / {height}')
        data = np.array(hdu.data[..., y0:y1, :], copy=True)
        header = hdu.header.copy()
        if 'CRPIX2' in header:
            try: header['CRPIX2'] = float(header['CRPIX2']) - y0
            except Exception: pass
        header['HISTORY'] = f'AstroSirilAssistant SyQon safe band y={y0}:{y1}'
        fits.PrimaryHDU(data=data, header=header).writeto(
            destination, overwrite=True, output_verify='silentfix'
        )
    return destination


def stitch_horizontal_bands_fits(source_header_file: Path, processed_bands: list[dict], destination: Path) -> Path:
    """Feather overlapping processed bands into one full-resolution FITS."""
    source_header_file, destination = Path(source_header_file), Path(destination)
    if not processed_bands:
        raise ValueError('결합할 SyQon band 결과가 없습니다.')

    with fits.open(source_header_file, memmap=True) as hdul:
        src_hdu = next((h for h in hdul if getattr(h, 'data', None) is not None and h.data.ndim >= 2), None)
        if src_hdu is None:
            raise ValueError('원본 FITS 이미지 데이터를 찾지 못했습니다.')
        shape = tuple(int(x) for x in src_hdu.data.shape)
        header = src_hdu.header.copy()

    out = np.empty(shape, dtype=np.float32)
    previous_end = None
    for i, item in enumerate(processed_bands):
        path = Path(item['path'])
        y0, y1 = int(item['y0']), int(item['y1'])
        with fits.open(path, memmap=True) as hdul:
            hdu = next((h for h in hdul if getattr(h, 'data', None) is not None and h.data.ndim >= 2), None)
            if hdu is None:
                raise ValueError(f'Band 결과 FITS 데이터가 없습니다: {path}')
            data = np.asarray(hdu.data, dtype=np.float32)
        expected = y1 - y0
        if data.shape[-2] != expected or data.shape[-1] != shape[-1]:
            raise ValueError(
                f'Band 결과 크기가 예상과 다릅니다: {path} / {data.shape} / '
                f'expected height={expected}, width={shape[-1]}'
            )

        if i == 0:
            out[..., y0:y1, :] = data
            previous_end = y1
            continue

        if previous_end is None or y0 >= previous_end:
            out[..., y0:y1, :] = data
            previous_end = y1
            continue

        overlap = previous_end - y0
        overlap = min(overlap, data.shape[-2])
        if overlap > 0:
            alpha = np.linspace(0.0, 1.0, overlap, endpoint=True, dtype=np.float32)
            alpha_shape = [1] * out.ndim
            alpha_shape[-2] = overlap
            alpha_shape[-1] = 1
            alpha = alpha.reshape(alpha_shape)
            old = out[..., y0:y0+overlap, :]
            new = data[..., :overlap, :]
            out[..., y0:y0+overlap, :] = old * (1.0 - alpha) + new * alpha
        if y0 + overlap < y1:
            out[..., y0+overlap:y1, :] = data[..., overlap:, :]
        previous_end = max(previous_end, y1)

    header['HISTORY'] = 'AstroSirilAssistant SyQon safe-banded full-image reconstruction'
    destination.parent.mkdir(parents=True, exist_ok=True)
    fits.PrimaryHDU(data=out, header=header).writeto(
        destination, overwrite=True, output_verify='silentfix'
    )
    return destination
