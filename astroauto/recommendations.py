from __future__ import annotations
from pathlib import Path
import copy
import re

from .config import load_yaml, PACKAGE_ROOT
from .project import load_project, save_project
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl
from .utils import iso_now

REC_FILE = PACKAGE_ROOT / "profiles" / "recommendation_profiles.yaml"
KNOWN_FILE = PACKAGE_ROOT / "profiles" / "known_targets.yaml"

def _norm_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value).upper())

def _load_profiles():
    return load_yaml(REC_FILE)

def _load_known():
    return load_yaml(KNOWN_FILE)

def feature_labels():
    return _load_profiles().get("feature_labels", {})

def category_labels():
    return _load_profiles().get("category_labels", {})

def known_target_match(target_name: str):
    key = _norm_name(target_name)
    raw = _load_known().get("targets", {})
    for canonical, data in raw.items():
        names = [canonical] + list(data.get("aliases", []))
        if key in {_norm_name(x) for x in names}:
            return canonical, copy.deepcopy(data)
    return None, None

def enrich_target_characteristics(project_dir: Path, only_if_empty: bool = True):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    target = p.setdefault("target", {})
    existing_features = list(target.get("features") or [])
    existing_subtypes = list(target.get("subtypes") or [])

    canonical, known = known_target_match(p.get("target_name", ""))
    if not known:
        target.setdefault("profile_source", "CATEGORY_ONLY")
        return project

    if only_if_empty and (existing_features or existing_subtypes):
        target.setdefault("profile_source", "USER_OR_EXISTING")
        return project

    if target.get("category") in (None, "", "UNKNOWN"):
        target["category"] = known.get("category", "UNKNOWN")
    target["subtypes"] = list(dict.fromkeys(existing_subtypes + known.get("subtypes", [])))
    target["features"] = list(dict.fromkeys(existing_features + known.get("features", [])))
    target["profile_source"] = "KNOWN_TARGET_REGISTRY"
    target["profile_name"] = canonical
    if not target.get("user_confirmed", False):
        target["classification_confidence"] = max(
            float(target.get("classification_confidence") or 0.0),
            0.95,
        )

    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "TARGET_CHARACTERISTICS_ENRICH",
        "status": "SUCCESS",
        "target": p.get("target_name"),
        "profile_name": canonical,
        "category": target.get("category"),
        "subtypes": target.get("subtypes"),
        "features": target.get("features"),
    })
    return project

def update_target_characteristics(
    project_dir: Path,
    *,
    category: str,
    features: list[str],
    user_confirmed: bool = True,
):
    pdir = Path(project_dir)
    project = load_project(pdir)
    target = project["project"].setdefault("target", {})
    target["category"] = str(category).upper()
    target["features"] = list(dict.fromkeys(str(x).upper() for x in features))
    target["user_confirmed"] = bool(user_confirmed)
    target["classification_confidence"] = 1.0 if user_confirmed else target.get("classification_confidence", 0.5)
    target["profile_source"] = "USER_CONFIRMED" if user_confirmed else "USER_EDITED"
    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "TARGET_CHARACTERISTICS_UPDATE",
        "status": "SUCCESS",
        "category": target["category"],
        "features": target["features"],
        "user_confirmed": target["user_confirmed"],
    })
    return project

def describe_target(project: dict):
    profiles = _load_profiles()
    flabels = profiles.get("feature_labels", {})
    clabels = profiles.get("category_labels", {})
    p = project["project"]
    target = p.get("target", {})
    category = target.get("category", "UNKNOWN")
    features = target.get("features", [])
    return {
        "target_name": p.get("target_name", ""),
        "category": category,
        "category_label": clabels.get(category, category),
        "subtypes": list(target.get("subtypes", [])),
        "features": list(features),
        "feature_labels": [flabels.get(x, x) for x in features],
        "source": target.get("profile_source", "PROJECT"),
    }

def _clamp(v, low, high):
    return max(low, min(high, v))

def _aggregate_stats(stats: dict):
    channels = list((stats or {}).get("channels", {}).values())
    channels = [x for x in channels if x]
    if not channels:
        return {}

    def avg(name):
        vals = [float(c[name]) for c in channels if c.get(name) is not None]
        return sum(vals) / len(vals) if vals else None

    p001 = avg("p001")
    p50 = avg("p50")
    p99 = avg("p99")
    p999 = avg("p999")
    highlight = avg("highlight_clip_ratio")
    shadow = avg("shadow_clip_ratio")

    span = None
    contrast_fraction = None
    if p001 is not None and p999 is not None:
        span = p999 - p001
        if span > 0 and p50 is not None and p99 is not None:
            contrast_fraction = (p99 - p50) / span

    return {
        "p001": p001,
        "p50": p50,
        "p99": p99,
        "p999": p999,
        "robust_span": span,
        "upper_contrast_fraction": contrast_fraction,
        "highlight_clip_ratio": highlight,
        "shadow_clip_ratio": shadow,
    }

def recommend_starless(project_dir: Path, config: dict):
    pdir = Path(project_dir)
    project = enrich_target_characteristics(pdir, only_if_empty=True)
    p = project["project"]
    target = p.get("target", {})
    category = target.get("category", "UNKNOWN")
    features = list(target.get("features") or [])

    profiles = _load_profiles()
    section = profiles["starless_processing"]
    rec = copy.deepcopy(section.get("default", {}))
    rec.update(copy.deepcopy(section.get("by_category", {}).get(category, {})))

    reasons = [
        f"천체 분류 {profiles.get('category_labels', {}).get(category, category)} 기본 프로필"
    ]

    modifiers = section.get("feature_modifiers", {})
    for feature in features:
        mod = modifiers.get(feature)
        if not mod:
            continue
        rec["clahe_clip_limit"] = float(rec["clahe_clip_limit"]) + float(mod.get("clahe_clip_delta", 0))
        rec["saturation_amount"] = float(rec["saturation_amount"]) + float(mod.get("saturation_delta", 0))
        rec["saturation_background_factor"] = (
            float(rec["saturation_background_factor"]) + float(mod.get("background_factor_delta", 0))
        )
        if mod.get("tile_min") is not None:
            rec["clahe_tile_size"] = max(int(rec["clahe_tile_size"]), int(mod["tile_min"]))
        if mod.get("tile_max") is not None:
            rec["clahe_tile_size"] = min(int(rec["clahe_tile_size"]), int(mod["tile_max"]))
        if mod.get("reason"):
            label = profiles.get("feature_labels", {}).get(feature, feature)
            reasons.append(f"{label}: {mod['reason']}")

    # Small metric-based correction. This is intentionally bounded and secondary
    # to target characteristics, because image statistics alone cannot identify aesthetics.
    current = Path(p["current_file"])
    stats = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )
    metrics = _aggregate_stats(stats)

    highlight = metrics.get("highlight_clip_ratio")
    contrast_fraction = metrics.get("upper_contrast_fraction")

    if highlight is not None and highlight > 0.001:
        rec["clahe_clip_limit"] = float(rec["clahe_clip_limit"]) - 0.10
        rec["saturation_amount"] = float(rec["saturation_amount"]) - 0.01
        reasons.append("현재 이미지에서 하이라이트 clipping 비율이 보여 강도를 소폭 낮춤")

    if contrast_fraction is not None:
        if contrast_fraction < 0.20:
            rec["clahe_clip_limit"] = float(rec["clahe_clip_limit"]) + 0.10
            reasons.append("현재 Starless 이미지의 상위 밝기 대비가 낮아 CLAHE를 소폭 강화")
        elif contrast_fraction > 0.65:
            rec["clahe_clip_limit"] = float(rec["clahe_clip_limit"]) - 0.10
            reasons.append("현재 Starless 이미지의 상위 밝기 대비가 이미 높아 CLAHE를 소폭 완화")

    limits = profiles.get("limits", {})
    sat_lo, sat_hi = limits.get("saturation_amount", [-0.5, 0.6])
    bg_lo, bg_hi = limits.get("saturation_background_factor", [0, 3])
    cl_lo, cl_hi = limits.get("clahe_clip_limit", [0.5, 4])
    ts_lo, ts_hi = limits.get("clahe_tile_size", [4, 32])

    rec["saturation_amount"] = round(_clamp(float(rec["saturation_amount"]), sat_lo, sat_hi), 2)
    rec["saturation_background_factor"] = round(
        _clamp(float(rec["saturation_background_factor"]), bg_lo, bg_hi), 2
    )
    rec["clahe_clip_limit"] = round(
        _clamp(float(rec["clahe_clip_limit"]), cl_lo, cl_hi), 2
    )
    rec["clahe_tile_size"] = int(_clamp(int(rec["clahe_tile_size"]), ts_lo, ts_hi))

    context = describe_target(project)
    result = {
        "schema_version": "0.1",
        "timestamp": iso_now(),
        "stage": "STARLESS_PROCESS",
        "target_context": context,
        "recommended_values": rec,
        "image_metrics": metrics,
        "reasons": reasons,
        "confidence": "STARTING_POINT",
        "notice": "추천값은 천체 특징 + 현재 이미지 통계를 조합한 보수적 시작점이며 정답값이 아닙니다.",
    }

    p.setdefault("recommendations", {})["starless_processing"] = result
    save_project(pdir, project)

    append_jsonl(pdir, {
        "event": "RECOMMEND_STARLESS",
        "status": "SUCCESS",
        **result,
    })
    return result
