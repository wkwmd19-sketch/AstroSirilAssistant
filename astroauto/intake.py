from __future__ import annotations
from datetime import datetime
from pathlib import Path
import re

from .config import PACKAGE_ROOT, load_yaml

KNOWN_TARGETS = PACKAGE_ROOT / "profiles" / "known_targets.yaml"


def _norm_target(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]+", "", str(value).upper())


def inspect_input_header(path: Path) -> dict:
    from .fits_analysis import read_header_summary
    header, history = read_header_summary(Path(path))
    return {"header": header, "history": history}


def target_from_header(header: dict) -> str:
    value = str(header.get("OBJECT") or "").strip()
    return value


def capture_date_from_header(header: dict) -> str:
    raw = str(header.get("DATE-OBS") or header.get("DATE") or "").strip()
    if not raw:
        return ""
    # Common FITS DATE-OBS forms begin with ISO YYYY-MM-DD. Keep the date only.
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", raw)
    if m:
        return m.group(1)
    # A few writers omit separators.
    m = re.match(r"^(\d{4})(\d{2})(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return ""


def infer_category_from_target(target_name: str) -> str:
    name = (target_name or "").strip()
    if not name:
        return "UNKNOWN"

    data = load_yaml(KNOWN_TARGETS) or {}
    normalized = _norm_target(name)
    for canonical, item in (data.get("targets") or {}).items():
        candidates = [canonical] + list(item.get("aliases") or [])
        if normalized in {_norm_target(x) for x in candidates}:
            return str(item.get("category") or "UNKNOWN")

    upper = name.upper()
    if "GALAXY" in upper or "은하" in name:
        return "GALAXY"
    if "GLOBULAR" in upper or "구상성단" in name:
        return "GLOBULAR_CLUSTER"
    if "OPEN CLUSTER" in upper or "산개성단" in name:
        return "OPEN_CLUSTER"
    if "PLANETARY NEBULA" in upper or "행성상성운" in name:
        return "PLANETARY_NEBULA"
    if "SUPERNOVA" in upper or "초신성" in name:
        return "SUPERNOVA_REMNANT"
    if "COMET" in upper or "혜성" in name:
        return "COMET"
    if any(x in upper for x in ("MOON", "JUPITER", "SATURN", "MARS", "VENUS")):
        return "PLANETARY_LUNAR"
    return "UNKNOWN"


def format_image_info(header: dict) -> str:
    parts: list[str] = []
    w, h = header.get("NAXIS1"), header.get("NAXIS2")
    if w and h:
        parts.append(f"{w}×{h}")
    bitpix = header.get("BITPIX")
    if bitpix is not None:
        try:
            b = int(bitpix)
            parts.append(f"{abs(b)}-bit{' float' if b < 0 else ''}")
        except Exception:
            parts.append(f"BITPIX {bitpix}")
    instrument = header.get("INSTRUME")
    if instrument:
        parts.append(str(instrument))
    telescope = header.get("TELESCOP")
    if telescope and str(telescope) != str(instrument):
        parts.append(str(telescope))
    exposure = header.get("EXPTIME", header.get("EXPOSURE"))
    if exposure is not None:
        try:
            parts.append(f"{float(exposure):g}s")
        except Exception:
            parts.append(f"{exposure}s")
    gain = header.get("GAIN")
    if gain is not None:
        parts.append(f"Gain {gain}")
    filt = header.get("FILTER")
    if filt:
        parts.append(f"Filter {filt}")
    return " · ".join(parts) if parts else "FITS 헤더에서 표시할 촬영 정보를 찾지 못했습니다."
