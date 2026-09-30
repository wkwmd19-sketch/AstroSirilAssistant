from __future__ import annotations
from pathlib import Path
import shutil
import json
import yaml

from .utils import safe_target_name, is_fits, iso_now
from .input_formats import describe_input
from .config import save_yaml

PROJECT_DIRS = [
    "input/original",
    "input/normalized",
    "input/metadata",
    "input/lights",
    "input/sessions",
    "input/filter_groups",
    "calibration/dark",
    "calibration/bias",
    "calibration/flat",
    "calibration/dark_flat",
    "calibration/masters",
    "working/00_calibrated",
    "working/01_registered",
    "working/02_stacked",
    "working/03_gradient",
    "working/04_color",
    "working/05_restore",
    "working/06_denoise",
    "working/07_stretch",
    "working/08_starnet",
    "working/09_starless",
    "working/10_stars",
    "working/11_recombine",
    "working/12_final",
    "output/fits",
    "output/tiff",
    "output/png",
    "output/preview",
    "logs",
    "temp",
]

def project_name(target: str, capture_date: str) -> str:
    """Current v0.14.4 project directory convention."""
    return f"Auto_{safe_target_name(target)}_{capture_date}"

def legacy_project_name(target: str, capture_date: str) -> str:
    """v0.14.2-and-earlier directory convention, kept for discovery only."""
    return f"{safe_target_name(target)}_{capture_date}_Auto"

def find_existing_project_dir(root: Path, target: str, capture_date: str) -> Path | None:
    root = Path(root)
    candidates = [
        root / project_name(target, capture_date),
        root / legacy_project_name(target, capture_date),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None

def next_available_project_dir(root: Path, target: str, capture_date: str) -> Path:
    """Return a non-existing Auto_<target>_<date>[_NN] project directory."""
    root = Path(root)
    target_clean = safe_target_name(target)
    first = root / project_name(target_clean, capture_date)
    if not first.exists():
        return first

    index = 2
    while True:
        candidate = root / f"Auto_{target_clean}_{capture_date}_{index:02d}"
        if not candidate.exists():
            return candidate
        index += 1

def create_project(root: Path, target: str, capture_date: str, category: str,
                   input_file: Path, copy_input: bool = True,
                   project_dir: Path | None = None,
                   copyright_text: str = "",
                   analysis_report: dict | None = None):
    """Create a single-image project from any supported intake format.

    The user's source file is copied unchanged to ``input/original``. Processing
    always starts from a FITS file in ``input/normalized``. For non-FITS input,
    ``analysis_report`` must contain the normalized FITS produced by the intake
    analysis step. FITS input is copied into both locations to keep the original
    immutable and the working contract uniform.
    """
    input_file = Path(input_file)
    if not input_file.exists():
        raise FileNotFoundError(input_file)

    descriptor = describe_input(input_file)
    if not descriptor.supported:
        raise ValueError(
            f"지원하지 않는 이미지 형식입니다: {input_file.suffix or input_file.name}\n"
            "지원 형식: FITS, CR2/CR3/NEF/ARW/DNG/RAF/ORF/RW2/PEF, TIFF, PNG, JPG/JPEG"
        )

    normalized_source = input_file
    normalization = {}
    source_metadata = {}
    if analysis_report:
        normalization = dict(analysis_report.get("normalization") or {})
        source_metadata = dict(analysis_report.get("source_metadata") or {})
        raw_normalized = normalization.get("analysis_file") or analysis_report.get("analysis_file")
        if raw_normalized:
            normalized_source = Path(raw_normalized)

    if descriptor.needs_normalization:
        if not analysis_report:
            raise ValueError("정규화가 필요한 이미지는 [이미지 분석]을 먼저 실행해야 프로젝트를 생성할 수 있습니다.")
        if not normalized_source.exists() or not is_fits(normalized_source):
            raise FileNotFoundError(
                "분석 단계에서 생성한 작업용 FITS를 찾지 못했습니다. 이미지를 다시 분석하세요."
            )

    pdir = Path(project_dir) if project_dir is not None else root / project_name(target, capture_date)
    if pdir.exists():
        raise FileExistsError(
            "동일한 프로젝트 폴더가 이미 존재합니다.\n"
            f"{pdir}\n\n"
            "기존 프로젝트를 열거나 새 번호 프로젝트를 생성하세요."
        )

    for rel in PROJECT_DIRS:
        (pdir / rel).mkdir(parents=True, exist_ok=True)

    target_clean = safe_target_name(target)
    original_dest = pdir / "input" / "original" / input_file.name
    normalized_dest = pdir / "input" / "normalized" / f"{target_clean}_00_input.fits"

    # v0.15 single-image projects always preserve an immutable source copy.
    # `copy_input=False` is retained for API compatibility but no longer allows
    # non-FITS projects to skip source preservation.
    shutil.copy2(input_file, original_dest)
    input_source_mode = "COPIED"

    if normalized_source.resolve() == input_file.resolve() and descriptor.fits:
        shutil.copy2(input_file, normalized_dest)
    else:
        shutil.copy2(normalized_source, normalized_dest)

    if not normalized_dest.exists() or not is_fits(normalized_dest):
        raise RuntimeError("프로젝트 작업용 FITS 생성에 실패했습니다.")

    metadata_dest = pdir / "input" / "metadata" / "source_metadata.json"
    metadata_payload = source_metadata or {
        "schema_version": "1.0",
        "source": {
            "original_path": str(input_file.resolve()),
            "filename": input_file.name,
            "format": descriptor.format,
            "family": descriptor.family,
            "lossy": descriptor.lossy,
            "raw": descriptor.raw,
        },
    }
    metadata_payload = dict(metadata_payload)
    metadata_payload.setdefault("project", {})
    metadata_payload["project"].update({
        "original_file": str(original_dest),
        "normalized_file": str(normalized_dest),
    })
    metadata_dest.write_text(
        json.dumps(metadata_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    project = {
        "schema_version": "0.15.0",
        "project": {
            "id": pdir.name,
            "target_name": target_clean,
            "root_path": str(pdir),
            "processing_mode": "SEMI_AUTO",
            "processing_preset": "MANUAL_INSPIRED_SYQON",
            "linear_processing_order": ["GRADIENT", "SPCC", "DEBLUR", "DENOISE", "GHS"],
            "created_at": iso_now(),

            "target": {
                "category": category,
                "subtypes": [],
                "features": [],
                "classification_confidence": 1.0 if category != "UNKNOWN" else 0.0,
                "user_confirmed": category != "UNKNOWN",
            },

            "capture": {
                "date": capture_date,
                "camera_type": "UNKNOWN",
                "sensor": "UNKNOWN",
                "filter": {"type": "UNKNOWN", "name": "UNKNOWN"},
                "tracking": {"mode": "UNKNOWN", "confidence": None, "user_confirmed": False},
                "binning": "UNKNOWN",
                "roi": "UNKNOWN",
                "sensor_mode": "UNKNOWN",
            },

            "sessions": {
                "multi_session": False,
                "count": 1,
                "items": [],
                "classified": False,
            },

            "filter_groups": {
                "is_multifilter": False,
                "items": [],
                "classified": False,
            },

            "input_stage": {
                "source_stage": "SINGLE_LIGHT" if descriptor.raw else "UNKNOWN",
                "user_confirmed": bool(descriptor.raw),
            },

            "star_trail": {
                "mode": "UNKNOWN",
                "user_confirmed": False,
                "frame_quality_checked": False,
                "frame_quality_report": None,
                "composition": {
                    "engine": "UNKNOWN",
                    "mode": "MAX_OR_LIGHTEN_PENDING",
                    "gap_check": "PENDING",
                    "artifact_candidates": [],
                },
            },

            "calibration": {
                "input_status": "RAW_UNCALIBRATED" if descriptor.raw else "UNKNOWN",
                "user_confirmed": bool(descriptor.raw),
                "checked": False,
                "recommended_action": "CHECK",
                "used_shared_library": False,
                "library_candidates": [],
                "frames": {
                    "dark": {"available": False, "path": "calibration/dark", "count": 0},
                    "bias": {"available": False, "path": "calibration/bias", "count": 0},
                    "flat": {"available": False, "path": "calibration/flat", "count": 0},
                    "dark_flat": {"available": False, "path": "calibration/dark_flat", "count": 0},
                },
                "masters": {},
                "compatibility": {},
            },

            "quality": {
                "checked": False,
                "metrics": {},
                "candidate_rejects": [],
            },

            "tracking_events": {
                "classified": False,
                "events": [],
            },

            "current_state": "INPUT_IMPORTED",

            "image_state": {
                "linearity": "UNKNOWN",
                "linearity_confidence": 0.0,
                "stretched": None,
                "stars_removed": False,
                "color_calibrated": False,
                "gradient_corrected": False,
                "denoised": False,
                "deblurred": False,
                "recombined": False,
            },

            "input": {
                "source_mode": input_source_mode,
                "original_path": str(input_file.resolve()),
                "original_file": str(original_dest),
                "normalized_file": str(normalized_dest),
                "source_metadata_file": str(metadata_dest),
                "source_format": descriptor.format,
                "source_family": descriptor.family,
                "lossy_source": descriptor.lossy,
                "raw_source": descriptor.raw,
                "normalization": {
                    "required": bool(normalization.get("required", descriptor.needs_normalization)),
                    "working_format": "FITS",
                    "precision": normalization.get("precision", "SOURCE" if descriptor.fits else "32-bit float"),
                    "method": normalization.get("method", "DIRECT_FITS" if descriptor.fits else "UNKNOWN"),
                    "debayered": bool(normalization.get("debayered", descriptor.raw)),
                    "project_file": str(normalized_dest),
                },
            },

            "current_file": str(normalized_dest),

            "paths": {
                "input": "input",
                "input_original": "input/original",
                "input_normalized": "input/normalized",
                "input_metadata": "input/metadata",
                "calibration": "calibration",
                "working": "working",
                "output": "output",
                "logs": "logs",
                "temp": "temp",
            },

            "runtime": {
                "siril_version": None,
                "siril_executable": None,
            },

            "metadata": {
                "copyright": str(copyright_text or "").strip(),
            },

            "next_task": None,
        }
    }

    save_yaml(pdir / "project.yaml", project)
    return pdir

def load_project(project_dir: Path):
    path = Path(project_dir) / "project.yaml"
    if not path.exists():
        raise FileNotFoundError(f"project.yaml을 찾지 못했습니다: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_project(project_dir: Path, data):
    save_yaml(Path(project_dir) / "project.yaml", data)

def find_project_fits(project_dir: Path) -> Path:
    data = load_project(project_dir)
    current = Path(data["project"].get("current_file") or "")
    if current.exists() and is_fits(current):
        return current

    # v0.15 single-image projects keep the canonical working input here.
    normalized_dir = Path(project_dir) / "input" / "normalized"
    if normalized_dir.exists():
        candidates = [p for p in normalized_dir.iterdir() if p.is_file() and is_fits(p)]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise RuntimeError("input/normalized에 FITS가 여러 개 있습니다. project.current_file을 확인하세요.")

    # Legacy project fallback.
    light_dir = Path(project_dir) / "input" / "lights"
    if light_dir.exists():
        candidates = [p for p in light_dir.iterdir() if p.is_file() and is_fits(p)]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise RuntimeError("input/lights에 FITS가 여러 개 있습니다. current_file 또는 Light sequence 규격이 필요합니다.")

    raise FileNotFoundError("프로젝트에서 작업용 FITS 파일을 찾지 못했습니다.")

