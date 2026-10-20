"""Synthetic Moon-pipeline regression tests (no telescope required)."""
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
fits = pytest.importorskip("astropy.io.fits")

from astroauto.moon import (
    _subject_mask, _stack, _mosaic, assess_frame,
    analyze_moon, collect_inputs, run_moon,
)


def fake_disk(size=320):
    image = np.zeros((size, size, 3), np.float32) + 0.005
    cv2.circle(image, (size // 2, size // 2), size // 3,
               (0.75, 0.74, 0.72), -1)
    rng = np.random.default_rng(132)
    for _ in range(115):
        x, y = rng.integers(0, size, 2)
        if (x - size // 2) ** 2 + (y - size // 2) ** 2 < (size // 3 - 8) ** 2:
            cv2.circle(image, (int(x), int(y)), int(rng.integers(2, 8)),
                       (0.42, 0.43, 0.42), 1)
    return image


def test_lunar_segmentation_and_quality():
    sample = fake_disk()
    mask, coverage = _subject_mask(sample.mean(axis=-1))
    assert 0.15 < coverage < 0.6
    assert mask.sum() > 1000
    q = assess_frame(sample)
    assert q["quality_score"] > 0
    assert q["moon_coverage"] > 0.1


def test_stack_aligns_small_translation_without_moving_reference():
    first = fake_disk()
    h, w = first.shape[:2]
    translated = cv2.warpAffine(first, np.float32([[1, 0, 9], [0, 1, -6]]), (w, h))
    metrics = [assess_frame(first), assess_frame(translated)]
    best = max(m["quality_score"] for m in metrics)
    for m in metrics:
        m["quality_ratio"] = m["quality_score"] / best
    result, report = _stack([first, translated], metrics)
    assert result.shape == first.shape
    assert len(report["accepted"]) == 2
    # Disc center must stay close to original after alignment.
    gray = result.mean(axis=2)
    pos = np.unravel_index(np.argmax(cv2.GaussianBlur(gray, (15, 15), 3)), gray.shape)
    assert abs(pos[0] - h // 2) < 55
    assert abs(pos[1] - w // 2) < 55


def test_mosaic_refuses_unmatchable_panels():
    rng = np.random.default_rng(7)
    blank = np.zeros((256, 256, 3), np.float32)
    unrelated = np.full_like(blank, rng.random(), dtype=np.float32)
    with pytest.raises(RuntimeError, match="연결할 수 없는"):
        _mosaic([blank, unrelated])


def test_mosaic_two_overlapping_realistic_tiles():
    # A mostly lunar surface with many unique craters/texture features.
    rng = np.random.default_rng(43)
    surface = rng.random((380, 630), dtype=np.float32) * 0.12 + 0.45
    surface = cv2.GaussianBlur(surface, (3, 3), 0.65)
    for i in range(160):
        x = int(rng.integers(10, 620))
        y = int(rng.integers(10, 370))
        cv2.circle(surface, (x, y), int(rng.integers(2, 13)),
                   float(rng.uniform(0.15, 0.35)), 2)
    one = np.repeat(surface[:, :390, None], 3, axis=2)
    two = np.repeat(surface[:, 220:, None], 3, axis=2)
    mosaic, report = _mosaic([one, two])
    assert mosaic.ndim == 3 and mosaic.shape[2] == 3
    assert mosaic.shape[1] >= 550
    assert report["matches"][0]["inliers"] >= 18


def test_single_full_saves_outputs_and_input_is_unchanged(tmp_path):
    image = fake_disk()
    root = tmp_path / "Moon_Source.fits"
    fits.writeto(root, np.moveaxis(image, -1, 0), overwrite=False)
    original_bytes = root.read_bytes()
    assert collect_inputs(root) == [root]
    plan = analyze_moon([root], {}, mode="single")
    assert plan["frames"][0]["selection_suggestion"] == "KEEP"
    with pytest.raises(PermissionError):
        run_moon(plan, {}, tmp_path / "out")
    report = run_moon(plan, {}, tmp_path / "out", confirmed=True)
    assert report["status"] == "FINISHED_WITH_REVIEW_REQUIRED"
    for path in report["outputs"].values():
        assert Path(path).is_file()
    with pytest.raises(FileExistsError):
        run_moon(plan, {}, tmp_path / "out", confirmed=True)
    assert root.read_bytes() == original_bytes


def test_cli_has_moon_modes_and_confirmation():
    from app import build_parser
    parser = build_parser()
    args = parser.parse_args([
        "moon-analyze", "--source", "lights", "--mode", "mosaic",
        "--output", "out"
    ])
    assert args.mode == "mosaic"
    args = parser.parse_args(["moon-run", "--plan", "plan.json", "--output", "out"])
    assert args.yes is False
