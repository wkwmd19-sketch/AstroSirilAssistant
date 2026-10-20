"""Moon-only analytical processing engine (FITS or Siril-normalized camera RAW).

Never overwrites an input file. No star registration or DSO background extraction.
OpenCV is optional for other ASA workflows and required only when this engine runs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import math
from typing import Sequence

import numpy as np


MODES = ("single", "stack", "mosaic")
EXTENSIONS = {".fit", ".fits", ".fts", ".cr2", ".cr3", ".nef",
              ".arw", ".dng", ".raf", ".orf", ".rw2", ".pef",
              ".tif", ".tiff", ".png", ".jpg", ".jpeg"}


def _cv():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Moon 모드에는 opencv-python-headless가 필요합니다: pip install opencv-python-headless") from exc
    return cv2


def _json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def collect_inputs(source: str | Path, pattern: str = "*") -> list[Path]:
    source = Path(source)
    if source.is_file():
        paths = [source]
    elif source.is_dir():
        paths = sorted(p for p in source.glob(pattern) if p.is_file() and p.suffix.lower() in EXTENSIONS)
    else:
        raise FileNotFoundError(source)
    if not paths or any(p.suffix.lower() not in EXTENSIONS for p in paths):
        raise ValueError("지원하는 달 이미지(FITS/RAW/TIFF/PNG/JPEG)를 찾지 못했습니다.")
    return paths


def _read_image(path: Path, config: dict) -> tuple[np.ndarray, str]:
    """Read a working RGB float32 array; RAW uses ASA's existing Siril normalization."""
    from astropy.io import fits
    from .input_formats import describe_input, normalize_to_fits

    description = describe_input(path)
    if not description.supported:
        raise ValueError(f"지원하지 않는 파일: {path}")
    normalized = path
    if description.needs_normalization:
        normalized = Path(normalize_to_fits(path, config)["analysis_file"])
    with fits.open(normalized, memmap=False) as hdul:
        hdu = next((h for h in hdul if getattr(h, "data", None) is not None), None)
        if hdu is None:
            raise ValueError(f"이미지 데이터를 찾지 못했습니다: {path}")
        raw = np.asarray(hdu.data, dtype=np.float32)
    if raw.ndim == 2:
        rgb = np.repeat(raw[..., None], 3, axis=2)
    elif raw.ndim == 3 and raw.shape[0] == 3:
        rgb = np.moveaxis(raw, 0, -1)
    elif raw.ndim == 3 and raw.shape[-1] == 3:
        rgb = raw
    else:
        raise ValueError(f"Moon 모드는 mono/RGB 2D 이미지만 처리합니다: {path.name}: {raw.shape}")
    if min(rgb.shape[:2]) < 64:
        raise ValueError(f"Moon 이미지가 너무 작습니다: {path.name}")
    return np.nan_to_num(rgb, nan=0.0, posinf=0.0, neginf=0.0), str(normalized)


def _gray(rgb: np.ndarray) -> np.ndarray:
    return np.asarray(rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152
                      + rgb[..., 2] * 0.0722, dtype=np.float32)


def _to_display(gray: np.ndarray) -> np.ndarray:
    cv2 = _cv()
    h, w = gray.shape
    scale = min(1.0, 1024.0 / max(h, w))
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else gray
    lo, hi = np.percentile(small, [1, 99.8])
    if hi <= lo:
        return np.zeros_like(small, dtype=np.uint8)
    return np.clip((small - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)


def _subject_mask(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """Detect disk OR lunar panel without assuming the Moon is centered."""
    cv2 = _cv()
    thumb = _to_display(gray)
    _, binary = cv2.threshold(thumb, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if n < 2:
        return np.zeros(gray.shape, dtype=np.uint8), 0.0
    label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    small = (labels == label).astype(np.uint8)
    coverage = float(np.count_nonzero(small) / small.size)
    mask = cv2.resize(small, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_NEAREST)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return mask, coverage


def assess_frame(rgb: np.ndarray) -> dict:
    """Bounded signal/quality measurements; they are not aesthetic truth."""
    cv2 = _cv()
    gray = _gray(rgb)
    small = _to_display(gray)
    mask, coverage = _subject_mask(gray)
    small_mask = cv2.resize(mask, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    if small_mask.mean() < 0.003:
        raise ValueError("달 표면을 식별할 수 없습니다. 대상 또는 촬영 구도를 확인하세요.")
    lap = cv2.Laplacian(cv2.GaussianBlur(small, (3, 3), 0.5), cv2.CV_32F)
    texture = float(np.std(lap[small_mask]))
    outside = small[~small_mask]
    if len(outside) < 100:
        outside = small.ravel()[:max(100, small.size // 10)]
    sky_med = float(np.median(outside))
    sky_sigma = float(1.4826 * np.median(np.abs(outside - sky_med)))
    moon_vals = small[small_mask]
    peak = float(np.percentile(moon_vals, 99.9))
    bright = float(np.mean(moon_vals >= 254))
    score = texture / max(2.0, sky_sigma)
    return {
        "shape": list(rgb.shape),
        "moon_coverage": round(coverage, 4),
        "texture_score": round(texture, 4),
        "background_noise": round(sky_sigma, 4),
        "quality_score": round(score, 5),
        "highlight_clip_proxy": round(bright, 5),
        "peak_display": round(peak, 2),
        "limitations": "정규화된 표시 영상 기반 품질 추정. 실제 센서 RAW 포화량과 동일하지 않음",
    }


def analyze_moon(inputs: Sequence[str | Path], config: dict, *, mode: str) -> dict:
    mode = mode.lower()
    if mode not in MODES:
        raise ValueError(f"지원하지 않는 Moon mode: {mode}")
    paths = [Path(p) for p in inputs]
    if mode == "single" and len(paths) != 1:
        raise ValueError("Moon Single 모드는 사진 1장만 받습니다.")
    if mode != "single" and len(paths) < 2:
        raise ValueError("Moon Stack/Mosaic 모드는 사진 2장 이상이 필요합니다.")
    frames = []
    for path in paths:
        pixels, normalized = _read_image(path, config)
        frame = assess_frame(pixels)
        frame.update({"input": str(path.resolve()), "working_file": normalized})
        frames.append(frame)
        del pixels
    scores = np.array([f["quality_score"] for f in frames])
    best = float(np.max(scores))
    for f in frames:
        f["quality_ratio"] = round(f["quality_score"] / max(best, 1e-9), 4)
        f["selection_suggestion"] = (
            "KEEP" if mode in ("single", "mosaic") or f["quality_ratio"] >= 0.60
            else "REVIEW_BLUR"
        )
    shapes = {tuple(f["shape"][:2]) for f in frames}
    issues = []
    if mode == "stack" and len(shapes) != 1:
        issues.append("동일한 프레임 크기가 아닙니다. Stack 정렬은 실행할 수 없습니다.")
    if mode == "mosaic":
        issues.append("모자이크 겹침/연결성은 실행 단계에서 특징점 정합으로 검증합니다.")
    if any(f["highlight_clip_proxy"] > 0.04 for f in frames):
        issues.append("밝은 표면의 clipping 가능성: 원본 노출 검토 권장.")
    if mode != "mosaic" and any(f["moon_coverage"] > 0.85 for f in frames):
        issues.append("달이 프레임 대부분을 차지합니다. 자동 마스킹/배경 판단이 제한될 수 있습니다.")
    return {
        "schema": "ASA_MOON_1",
        "mode": mode,
        "frames": frames,
        "recommendations": {
            "selected_indices": [i for i, f in enumerate(frames)
                                 if f["selection_suggestion"] == "KEEP"],
            "no_calibration_policy": "사용자가 제공하지 않은 Dark/Bias/Flat은 합성하지 않습니다.",
            "preserve_originals": True,
        },
        "issues": issues,
        "status": "ANALYZED",
    }


def _luma_align_view(rgb: np.ndarray, max_side: int = 1000) -> tuple[np.ndarray, float]:
    cv2 = _cv()
    gray = _gray(rgb)
    scale = min(1.0, max_side / max(gray.shape))
    if scale < 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    lo, hi = np.percentile(gray, [5, 99.5])
    return np.clip((gray - lo) / max(1e-9, hi - lo), 0, 1).astype(np.float32), scale


def _stack(frames: Sequence[np.ndarray], metrics: Sequence[dict]) -> tuple[np.ndarray, dict]:
    cv2 = _cv()
    best = int(np.argmax([m["quality_score"] for m in metrics]))
    reference = frames[best]
    base, scale = _luma_align_view(reference)
    if len({f.shape for f in frames}) != 1:
        raise ValueError("Moon Stack: 모든 프레임의 해상도가 같아야 합니다.")
    accepted = []
    rejected = []
    sum_rgb = np.zeros_like(reference, dtype=np.float64)
    weights = np.zeros(reference.shape[:2], dtype=np.float32)
    for index, image in enumerate(frames):
        if metrics[index]["quality_ratio"] < 0.60:
            rejected.append({"index": index, "reason": "QUALITY_TOO_LOW"})
            continue
        if index == best:
            aligned = image
            valid = np.ones(image.shape[:2], np.float32)
            correlation = 1.0
        else:
            moving, other_scale = _luma_align_view(image)
            if moving.shape != base.shape or abs(other_scale - scale) > 1e-5:
                rejected.append({"index": index, "reason": "RESOLUTION_MISMATCH"})
                continue
            warp = np.eye(2, 3, dtype=np.float32)
            try:
                correlation, warp = cv2.findTransformECC(
                    base, moving, warp, cv2.MOTION_EUCLIDEAN,
                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 180, 1e-6),
                    inputMask=None, gaussFiltSize=5)
                if correlation < 0.75:
                    raise ValueError(f"correlation={correlation:.3f}")
                warp[:, 2] /= scale
                if np.linalg.norm(warp[:, 2]) > 0.35 * max(image.shape[:2]):
                    raise ValueError("정렬 이동량 비정상")
                size = (image.shape[1], image.shape[0])
                aligned = cv2.warpAffine(
                    image, warp, size,
                    flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                    borderMode=cv2.BORDER_CONSTANT)
                valid = cv2.warpAffine(
                    np.ones(image.shape[:2], np.float32), warp, size,
                    flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP,
                    borderMode=cv2.BORDER_CONSTANT)
            except (cv2.error, ValueError) as exc:
                rejected.append({"index": index, "reason": f"REGISTRATION_FAILED: {exc}"})
                continue
        sum_rgb += np.asarray(aligned, np.float64) * valid[..., None]
        weights += valid
        accepted.append({"index": index, "correlation": round(float(correlation), 4)})
    if not accepted:
        raise RuntimeError("달 정렬에 성공한 프레임이 없습니다.")
    out = (sum_rgb / np.maximum(weights[..., None], 1)).astype(np.float32)
    if len(accepted) == 1 and len(frames) > 1:
        raise RuntimeError("정렬된 프레임이 1장뿐입니다. 스태킹 결과를 확정하지 않고 중단합니다.")
    return out, {"accepted": accepted, "rejected": rejected, "reference_index": best}


def _orb_features(image: np.ndarray):
    cv2 = _cv()
    gray = _to_display(_gray(image))
    orb = cv2.ORB_create(nfeatures=7000, fastThreshold=10)
    points, descriptor = orb.detectAndCompute(gray, None)
    return gray, points, descriptor


def _mosaic(frames: Sequence[np.ndarray]) -> tuple[np.ndarray, dict]:
    """Conservative connected-panel affine stitch: never guess missing overlaps."""
    cv2 = _cv()
    n = len(frames)
    features = [_orb_features(f) for f in frames]
    shapes = [f.shape[:2] for f in frames]
    scales = [min(1.0, 1024.0 / max(s)) for s in shapes]
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    transforms = {0: np.eye(3, dtype=np.float64)}
    matches_report = []
    pending = set(range(1, n))
    while pending:
        gained = False
        for j in list(pending):
            _, pts_j, d_j = features[j]
            if d_j is None or len(pts_j) < 15:
                continue
            best_match = None
            for i in list(transforms):
                _, pts_i, d_i = features[i]
                if d_i is None or len(pts_i) < 15:
                    continue
                pairs = matcher.knnMatch(d_j, d_i, k=2)
                good = [a for a, b in pairs if a.distance < 0.72 * b.distance]
                if len(good) < 20:
                    continue
                src = np.float32([pts_j[m.queryIdx].pt for m in good])
                dst = np.float32([pts_i[m.trainIdx].pt for m in good])
                affine, inlier = cv2.estimateAffinePartial2D(
                    src, dst, method=cv2.RANSAC,
                    ransacReprojThreshold=3.0, maxIters=3500)
                if affine is None or inlier is None:
                    continue
                count = int(inlier.sum())
                if count < 18 or count / len(good) < 0.40:
                    continue
                # Feature coordinates are from a 1024px thumbnail.
                affine = affine.astype(np.float64)
                affine[0, 2] /= scales[i]
                affine[1, 2] /= scales[i]
                affine[0, :2] *= scales[j] / scales[i]
                affine[1, :2] *= scales[j] / scales[i]
                h = np.eye(3, dtype=np.float64)
                h[:2] = affine
                if not 0.90 < math.sqrt(abs(np.linalg.det(h[:2, :2]))) < 1.10:
                    continue
                if best_match is None or count > best_match[0]:
                    best_match = (count, i, h, len(good))
            if best_match:
                count, i, relative, total = best_match
                transforms[j] = transforms[i] @ relative
                matches_report.append({"panel": j, "to_panel": i,
                                       "inliers": count, "candidate_matches": total})
                pending.remove(j)
                gained = True
        if not gained:
            raise RuntimeError(
                "Moon Mosaic: 연결할 수 없는 패널이 있습니다: "
                + ", ".join(str(i + 1) for i in sorted(pending))
                + ". 겹침이 충분한 원본만 선택하거나 수동 정렬하세요."
            )
    corners = []
    for i, (height, width) in enumerate(shapes):
        corners_i = np.float64([[0, 0, 1], [width, 0, 1], [width, height, 1], [0, height, 1]])
        corners.extend((transforms[i] @ corners_i.T).T[:, :2])
    corners = np.asarray(corners)
    origin = np.floor(corners.min(axis=0)).astype(int)
    boundary = np.ceil(corners.max(axis=0)).astype(int)
    width, height = (boundary - origin).astype(int)
    if width <= 0 or height <= 0 or width * height > 100_000_000:
        raise RuntimeError("모자이크 캔버스가 너무 큽니다. 잘못된 정합이거나 메모리 한계를 넘었습니다.")
    offset = np.eye(3)
    offset[:2, 2] = -origin
    accum = np.zeros((height, width, 3), dtype=np.float64)
    weights = np.zeros((height, width), dtype=np.float32)
    for i, frame in enumerate(frames):
        matrix = (offset @ transforms[i])[:2]
        warped = cv2.warpAffine(frame, matrix, (width, height))
        source_mask = np.ones(frame.shape[:2], dtype=np.uint8)
        valid = cv2.warpAffine(source_mask, matrix, (width, height), flags=cv2.INTER_NEAREST)
        feather = cv2.GaussianBlur(valid.astype(np.float32), (0, 0), sigmaX=5.0)
        feather = feather * (valid != 0)
        accum += warped.astype(np.float64) * feather[..., None]
        weights += feather
    output = (accum / np.maximum(weights[..., None], 1e-6)).astype(np.float32)
    return output, {"matches": matches_report, "size": [width, height],
                    "holes_possible": bool(np.any(weights == 0)),
                    "warning": "프레임별 밝기·색 차이와 모자이크 이음새는 수동 점검 필요"}


def _render(rgb: np.ndarray, mode: str) -> tuple[np.ndarray, dict]:
    """Conservative lunar local contrast; no fabricated PSF/deconvolution."""
    cv2 = _cv()
    gray = _gray(rgb)
    mask, coverage = _subject_mask(gray)
    if coverage < 0.003:
        raise RuntimeError("달 영역을 안정적으로 검출하지 못했습니다.")
    region = gray[mask > 0]
    sky = gray[mask == 0]
    bg = float(np.median(sky)) if sky.size > 500 else float(np.percentile(gray, 2))
    white = float(np.percentile(region, 99.85))
    if white <= bg:
        raise ValueError("달과 배경의 명암 구분이 불가능합니다.")
    normalized = np.clip((rgb - bg) / (white - bg), 0, 1)
    lum = _gray(normalized)
    color = np.median(normalized[mask > 0], axis=0)
    gains = np.clip(np.mean(color) / np.maximum(color, 1e-4), 0.85, 1.15)
    normalized = np.clip(normalized * gains.reshape(1, 1, 3), 0, 1)
    lum = _gray(normalized)
    # Clip-limit is deliberately low; CLAHE only contributes a small fraction.
    scaled = np.uint16(np.rint(lum * 65535))
    detail = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(12, 12)).apply(scaled)
    local = detail.astype(np.float32) / 65535.0
    soft = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 2.0)
    target = np.clip(lum * 0.84 + local * 0.16, 0, 1)
    boost = (lum + (target - lum) * soft)
    ratio = np.clip(boost / np.maximum(lum, 0.025), 0.85, 1.15)
    normalized = np.clip(normalized * ratio[..., None], 0, 1)
    quality = assess_frame(rgb)
    if quality["background_noise"] > 12:
        mild = cv2.GaussianBlur(normalized, (3, 3), 0.45)
        normalized = normalized * (1 - 0.13 * soft[..., None]) + mild * (0.13 * soft[..., None])
    # No blind deconvolution: PSF cannot be trusted for a single lunar exposure.
    return normalized.astype(np.float32), {
        "moon_coverage": coverage, "background": bg, "white": white,
        "color_gain": [round(float(x), 4) for x in gains],
        "clahe_blend": 0.16,
        "deconvolution": "SKIPPED_UNMEASURED_PSF",
        "noise_policy": "edge-preserving / conservative",
    }


def run_moon(plan: dict, config: dict, output_dir: str | Path, *, confirmed: bool = False) -> dict:
    if not confirmed:
        raise PermissionError("Moon 적용은 사용자 승인(--yes) 후에만 실행할 수 있습니다.")
    cv2 = _cv()
    output_dir = Path(output_dir)
    inputs = [Path(f["input"]) for f in plan["frames"]]
    if any(not x.is_file() for x in inputs):
        raise FileNotFoundError("원본 파일이 없어 Moon 작업을 실행할 수 없습니다.")
    mode = plan["mode"]
    if mode not in MODES:
        raise ValueError("분석 계획의 Moon 모드가 잘못됐습니다.")
    if output_dir.resolve() in [p.resolve() for p in inputs]:
        raise ValueError("원본 파일 경로에 덮어쓰기를 할 수 없습니다.")
    # Refuse silently changed source shape/quality; plan is evidence, not a command list.
    images = []
    for i, path in enumerate(inputs):
        image, _ = _read_image(path, config)
        if list(image.shape) != plan["frames"][i]["shape"]:
            raise RuntimeError(f"분석 이후 입력 영상 크기가 달라졌습니다: {path}")
        images.append(image)
    metrics = plan["frames"]
    if mode == "single":
        merged = images[0]
        registration = {"accepted": [{"index": 0}], "rejected": []}
    elif mode == "stack":
        merged, registration = _stack(images, metrics)
    else:
        merged, registration = _mosaic(images)
    # Processing is performed *after* the geometric operation.
    processed, corrections = _render(merged, mode)
    from astropy.io import fits
    output_dir.mkdir(parents=True, exist_ok=True)
    linear_file = output_dir / "Moon_combined_linear.fits"
    final_file = output_dir / "Moon_final.fits"
    tiff_file = output_dir / "Moon_final_16bit.tif"
    preview_file = output_dir / "Moon_preview.png"
    report_file = output_dir / "Moon_processing_report.json"
    for target in (linear_file, final_file, tiff_file, preview_file, report_file):
        if target.exists():
            raise FileExistsError(f"결과를 보호하기 위해 기존 파일을 덮어쓰지 않습니다: {target}")
    fits.writeto(linear_file, np.moveaxis(merged, -1, 0).astype(np.float32),
                 overwrite=False)
    fits.writeto(final_file, np.moveaxis(processed, -1, 0).astype(np.float32),
                 overwrite=False)
    img16 = np.uint16(np.rint(np.clip(processed, 0, 1) * 65535))
    if not cv2.imwrite(str(tiff_file), img16[..., ::-1]):
        raise RuntimeError("16-bit TIFF 저장에 실패했습니다.")
    h, w = img16.shape[:2]
    scale = min(1.0, 1600.0 / max(h, w))
    u8 = np.uint8(np.rint(img16 * (255.0 / 65535)))
    if scale < 1:
        u8 = cv2.resize(u8, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if not cv2.imwrite(str(preview_file), u8[..., ::-1]):
        raise RuntimeError("PNG 미리보기 저장에 실패했습니다.")
    report = {
        "schema": "ASA_MOON_1",
        "mode": mode,
        "inputs": [str(p) for p in inputs],
        "status": "FINISHED_WITH_REVIEW_REQUIRED",
        "registration": registration,
        "processing": corrections,
        "outputs": {
            "linear_fits": str(linear_file), "final_fits": str(final_file),
            "tiff16": str(tiff_file), "preview_png": str(preview_file),
        },
        "human_review": [
            "달 크레이터 주변 링잉/과한 평활화 검사",
            "표면 하이라이트 포화 및 컬러 캐스트 검사",
            "모자이크 경계/이음새와 누락 영역 검사" if mode == "mosaic" else "달 경계의 색수차 검사",
        ],
    }
    _json_write(report_file, report)
    return report
