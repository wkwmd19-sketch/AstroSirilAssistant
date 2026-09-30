from __future__ import annotations
from pathlib import Path
import json
import math
import numpy as np
from astropy.io import fits

STRETCH_HISTORY_TERMS = (
    "ght", "generalised hyperbolic", "generalized hyperbolic",
    "asinh", "arcsinh", "histogram transformation", "stretch",
    "mtf", "modified arcsinh"
)

def _clean_numeric(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float64).ravel()
    return arr[np.isfinite(arr)]

def _sample_evenly(arr: np.ndarray, max_samples: int) -> np.ndarray:
    arr = _clean_numeric(arr)
    if arr.size <= max_samples:
        return arr
    step = max(1, arr.size // max_samples)
    sampled = arr[::step]
    return sampled[:max_samples]

def _channel_views(data: np.ndarray):
    data = np.asarray(data)
    if data.ndim == 2:
        return [("K", data)]
    if data.ndim == 3:
        # Common FITS RGB: (3, H, W)
        if data.shape[0] in (3, 4):
            labels = ["R", "G", "B", "A"][:data.shape[0]]
            return list(zip(labels, [data[i] for i in range(data.shape[0])]))
        # Less common: (H, W, 3)
        if data.shape[-1] in (3, 4):
            labels = ["R", "G", "B", "A"][:data.shape[-1]]
            return list(zip(labels, [data[..., i] for i in range(data.shape[-1])]))
    return [("DATA", data)]

def _robust_background_peak(x: np.ndarray, bins: int):
    if x.size == 0:
        return None
    lo, hi = np.percentile(x, [0.1, 99.9])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return float(np.median(x))
    hist, edges = np.histogram(x, bins=bins, range=(lo, hi))
    idx = int(np.argmax(hist))
    return float((edges[idx] + edges[idx + 1]) / 2.0)

def _stats(x: np.ndarray, bins: int, clip_fraction: float):
    if x.size == 0:
        return {}
    q = np.percentile(x, [0.1, 1, 10, 50, 90, 99, 99.9])
    med = float(q[3])
    mad = float(np.median(np.abs(x - med)))

    xmin = float(np.min(x))
    xmax = float(np.max(x))
    span = xmax - xmin
    if span > 0:
        eps = span * clip_fraction
        shadow_clip = float(np.mean(x <= xmin + eps))
        highlight_clip = float(np.mean(x >= xmax - eps))
    else:
        shadow_clip = 1.0
        highlight_clip = 1.0

    return {
        "min": xmin,
        "max": xmax,
        "mean": float(np.mean(x)),
        "median": med,
        "mad": mad,
        "background_peak": _robust_background_peak(x, bins),
        "p001": float(q[0]),
        "p01": float(q[1]),
        "p10": float(q[2]),
        "p50": float(q[3]),
        "p90": float(q[4]),
        "p99": float(q[5]),
        "p999": float(q[6]),
        "shadow_clip_ratio": shadow_clip,
        "highlight_clip_ratio": highlight_clip,
        "sample_count": int(x.size),
    }

def analyze_pixels(path: Path, max_samples: int = 1500000, bins: int = 2048, clip_fraction: float = 0.0001):
    with fits.open(path, memmap=True, do_not_scale_image_data=False) as hdul:
        hdu = next((h for h in hdul if getattr(h, "data", None) is not None), None)
        if hdu is None:
            raise ValueError("FITS에서 이미지 데이터를 찾지 못했습니다.")
        data = np.asarray(hdu.data)
        result = {
            "shape": list(data.shape),
            "dtype": str(data.dtype),
            "channels": {}
        }
        for label, channel in _channel_views(data):
            sample = _sample_evenly(channel, max_samples)
            result["channels"][label] = _stats(sample, bins, clip_fraction)
        return result

def read_header_summary(path: Path):
    with fits.open(path, memmap=True) as hdul:
        hdu = next((h for h in hdul if getattr(h, "data", None) is not None), hdul[0])
        header = hdu.header
        wanted = [
            "OBJECT", "DATE-OBS", "DATE", "EXPTIME", "EXPOSURE", "GAIN", "FILTER",
            "INSTRUME", "TELESCOP", "BAYERPAT", "COPYRGHT", "COPYRIGHT", "BITPIX", "NAXIS",
            "NAXIS1", "NAXIS2", "NAXIS3"
        ]
        summary = {k: header.get(k) for k in wanted if header.get(k) is not None}

        history_cards = header.get("HISTORY", [])
        if isinstance(history_cards, str):
            history = [history_cards]
        else:
            history = [str(v) for v in history_cards] if history_cards else []
        return summary, history

def infer_linearity(history: list[str]):
    joined = "\n".join(history).lower()
    hits = [term for term in STRETCH_HISTORY_TERMS if term in joined]
    if hits:
        return {
            "status": "NONLINEAR",
            "confidence": 0.90,
            "reason": "FITS HISTORY에서 Stretch 관련 기록을 발견했습니다.",
            "evidence": hits,
        }
    return {
        "status": "UNKNOWN",
        "confidence": 0.0,
        "reason": "FITS HISTORY에 명확한 Stretch 기록이 없습니다. 이것만으로 Linear라고 단정하지 않습니다.",
        "evidence": [],
    }

def load_siril_metadata(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
