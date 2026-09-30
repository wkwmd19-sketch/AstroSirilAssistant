from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha1
from pathlib import Path
import json
import shutil
import tempfile

from .execution import emit_log
from .siril import run_script, SirilError
from .utils import is_fits, normalize_siril_path

RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2", ".pef",
}
TIFF_EXTENSIONS = {".tif", ".tiff"}
PNG_EXTENSIONS = {".png"}
JPEG_EXTENSIONS = {".jpg", ".jpeg"}
FITS_EXTENSIONS = {".fit", ".fits", ".fts", ".fits.fz"}
SUPPORTED_EXTENSIONS = FITS_EXTENSIONS | RAW_EXTENSIONS | TIFF_EXTENSIONS | PNG_EXTENSIONS | JPEG_EXTENSIONS


@dataclass(frozen=True)
class InputDescriptor:
    format: str
    family: str
    extension: str
    supported: bool
    raw: bool
    fits: bool
    raster: bool
    lossy: bool
    needs_normalization: bool
    likely_linearity: str
    warning: str

    def to_dict(self) -> dict:
        return asdict(self)


def _suffix(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".fits.fz"):
        return ".fits.fz"
    return path.suffix.lower()


def describe_input(path: Path) -> InputDescriptor:
    path = Path(path)
    ext = _suffix(path)
    if is_fits(path):
        compressed = ext == ".fits.fz"
        return InputDescriptor(
            format="FITS.FZ" if compressed else "FITS",
            family="FITS",
            extension=ext,
            supported=True,
            raw=False,
            fits=True,
            raster=False,
            lossy=False,
            needs_normalization=compressed,
            likely_linearity="UNKNOWN",
            warning=(
                "압축 FITS는 원본을 보존하고 작업용 일반 FITS로 풀어서 사용합니다."
                if compressed else ""
            ),
        )
    if ext in RAW_EXTENSIONS:
        return InputDescriptor(
            format=ext.lstrip(".").upper(),
            family="RAW",
            extension=ext,
            supported=True,
            raw=True,
            fits=False,
            raster=False,
            lossy=False,
            needs_normalization=True,
            likely_linearity="LINEAR",
            warning="RAW 원본은 보존하고 Siril/LibRaw로 Debayer한 32-bit 작업용 FITS를 생성합니다.",
        )
    if ext in TIFF_EXTENSIONS:
        return InputDescriptor(
            format="TIFF",
            family="TIFF",
            extension=ext,
            supported=True,
            raw=False,
            fits=False,
            raster=True,
            lossy=False,
            needs_normalization=True,
            likely_linearity="UNKNOWN",
            warning="TIFF는 Linear/Non-linear 상태를 파일 형식만으로 단정하지 않습니다.",
        )
    if ext in PNG_EXTENSIONS:
        return InputDescriptor(
            format="PNG",
            family="PNG",
            extension=ext,
            supported=True,
            raw=False,
            fits=False,
            raster=True,
            lossy=False,
            needs_normalization=True,
            likely_linearity="UNKNOWN",
            warning="PNG는 이미 Stretch된 이미지일 수 있으므로 Linear 상태를 확인합니다.",
        )
    if ext in JPEG_EXTENSIONS:
        return InputDescriptor(
            format="JPEG",
            family="JPEG",
            extension=ext,
            supported=True,
            raw=False,
            fits=False,
            raster=True,
            lossy=True,
            needs_normalization=True,
            likely_linearity="NONLINEAR",
            warning="JPEG는 손실 압축 및 카메라 Tone Curve가 적용된 Non-linear 이미지로 취급합니다.",
        )
    return InputDescriptor(
        format=ext.lstrip(".").upper() or "UNKNOWN",
        family="UNKNOWN",
        extension=ext,
        supported=False,
        raw=False,
        fits=False,
        raster=False,
        lossy=False,
        needs_normalization=False,
        likely_linearity="UNKNOWN",
        warning="지원하지 않는 입력 형식입니다.",
    )


def supported_dialog_patterns() -> str:
    return " ".join(
        [
            "*.fits", "*.fit", "*.fts", "*.fits.fz",
            "*.cr2", "*.cr3", "*.nef", "*.arw", "*.dng", "*.raf", "*.orf", "*.rw2", "*.pef",
            "*.tif", "*.tiff", "*.png", "*.jpg", "*.jpeg",
        ]
    )


def input_signature(path: Path) -> str:
    path = Path(path)
    st = path.stat()
    payload = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8", errors="replace")
    return sha1(payload).hexdigest()[:20]


def _cache_root() -> Path:
    return Path(tempfile.gettempdir()) / "AstroSirilAssistant" / "intake"


def analysis_cache_path(path: Path) -> Path:
    root = _cache_root() / input_signature(path)
    root.mkdir(parents=True, exist_ok=True)
    return root / "analysis_input.fits"


def _find_single_fits(folder: Path) -> Path | None:
    candidates = []
    for p in folder.rglob("*"):
        if p.is_file() and is_fits(p):
            candidates.append(p)
    return sorted(candidates)[0] if len(candidates) == 1 else None


def _run_load_save(config: dict, source: Path, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    stem = destination.with_suffix("")
    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(source)}"',
        f'save "{normalize_siril_path(stem)}"',
        "close",
    ]
    proc = run_script(config, commands, cwd=source.parent)
    if proc.returncode != 0:
        raise SirilError(f"입력 이미지를 FITS로 변환하지 못했습니다.\n{proc.stdout}")
    if not destination.exists():
        alt = stem.with_suffix(".fit")
        if alt.exists():
            alt.replace(destination)
    if not destination.exists():
        raise SirilError(
            "Siril 변환 명령은 종료되었지만 작업용 FITS가 생성되지 않았습니다.\n"
            f"입력: {source}\n예상 출력: {destination}"
        )
    return proc


def _normalize_raw(config: dict, source: Path, destination: Path):
    """Decode one camera RAW with Siril/LibRaw and explicitly request demosaicing.

    Siril's documented `convertraw ... -debayer` path is used in an isolated
    temporary directory so unrelated RAW files cannot be converted accidentally.
    A final load/save pass places the result at a deterministic 32-bit FITS path.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="astroauto_raw_") as tmp:
        tmp_root = Path(tmp)
        stage = tmp_root / "source"
        out = tmp_root / "converted"
        stage.mkdir(parents=True, exist_ok=True)
        out.mkdir(parents=True, exist_ok=True)
        staged = stage / source.name
        shutil.copy2(source, staged)

        emit_log("RAW Decode: Siril/LibRaw + Debayer")
        out_arg = normalize_siril_path(out)
        commands = [
            "set32bits",
            "setext fits",
            f'convertraw astroauto_raw -debayer "-out={out_arg}"',
        ]
        proc = run_script(config, commands, cwd=stage)
        converted = _find_single_fits(out)
        if proc.returncode != 0 or converted is None:
            raise SirilError(
                "RAW Decode/Debayer 결과를 확인하지 못했습니다. 원본 RAW는 변경되지 않았습니다.\n"
                "데이터 무결성을 위해 Debayer 여부가 불명확한 일반 loader fallback은 사용하지 않습니다.\n"
                f"입력: {source}\n"
                f"Siril 로그:\n{proc.stdout}"
            )

        return _run_load_save(config, converted, destination)


def normalize_to_fits(source: Path, config: dict, destination: Path | None = None) -> dict:
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(source)
    desc = describe_input(source)
    if not desc.supported:
        raise ValueError(
            f"지원하지 않는 이미지 형식입니다: {source.suffix or source.name}\n"
            "지원 형식: FITS, CR2/CR3/NEF/ARW/DNG/RAF/ORF/RW2/PEF, TIFF, PNG, JPG/JPEG"
        )

    if desc.fits and not desc.needs_normalization:
        return {
            "required": False,
            "analysis_file": str(source.resolve()),
            "working_format": "FITS",
            "precision": "SOURCE",
            "method": "DIRECT_FITS",
            "debayered": False,
            "source_descriptor": desc.to_dict(),
        }

    destination = Path(destination) if destination else analysis_cache_path(source)
    if destination.exists() and destination.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return {
            "required": True,
            "analysis_file": str(destination.resolve()),
            "working_format": "FITS",
            "precision": "32-bit float",
            "method": "SIRIL_RAW_DEBAYER" if desc.raw else ("SIRIL_FITS_FZ_EXPAND" if desc.extension == ".fits.fz" else "SIRIL_LOAD_SAVE"),
            "debayered": bool(desc.raw),
            "cached": True,
            "source_descriptor": desc.to_dict(),
        }

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    if desc.raw:
        _normalize_raw(config, source, destination)
    else:
        _run_load_save(config, source, destination)

    return {
        "required": True,
        "analysis_file": str(destination.resolve()),
        "working_format": "FITS",
        "precision": "32-bit float",
        "method": "SIRIL_RAW_DEBAYER" if desc.raw else "SIRIL_LOAD_SAVE",
        "debayered": bool(desc.raw),
        "cached": False,
        "source_descriptor": desc.to_dict(),
    }


def source_file_metadata(path: Path, descriptor: InputDescriptor | None = None) -> dict:
    path = Path(path)
    descriptor = descriptor or describe_input(path)
    st = path.stat()
    return {
        "original_path": str(path.resolve()),
        "filename": path.name,
        "format": descriptor.format,
        "family": descriptor.family,
        "extension": descriptor.extension,
        "size_bytes": int(st.st_size),
        "mtime_ns": int(st.st_mtime_ns),
        "lossy": descriptor.lossy,
        "raw": descriptor.raw,
        "normalization_required": descriptor.needs_normalization,
    }


def build_source_metadata(path: Path, descriptor: InputDescriptor, header: dict, siril_metadata: dict | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "source": source_file_metadata(path, descriptor),
        "mapped_fits_header": dict(header or {}),
        "siril_metadata": siril_metadata or {},
    }


def linearity_for_source(descriptor: InputDescriptor, inferred: dict) -> dict:
    """Conservative source-aware linearity policy.

    RAW is decoded as a linear-light working image. JPEG is explicitly treated
    as non-linear/lossy. TIFF/PNG stay UNKNOWN unless FITS history or a later
    user confirmation supplies stronger evidence.
    """
    if descriptor.raw:
        return {
            "status": "LINEAR",
            "confidence": 0.98,
            "reason": "카메라 RAW를 Siril/LibRaw로 Debayer하여 Linear 작업용 FITS로 변환했습니다.",
            "evidence": ["RAW_SOURCE", "SIRIL_DEBAYER"],
        }
    if descriptor.family == "JPEG":
        return {
            "status": "NONLINEAR",
            "confidence": 0.98,
            "reason": "JPEG는 손실 압축 및 일반적인 표시용 Tone Curve가 적용된 형식이므로 Non-linear 입력으로 취급합니다.",
            "evidence": ["JPEG_SOURCE", "LOSSY_DISPLAY_FORMAT"],
        }
    if inferred.get("status") != "UNKNOWN":
        return inferred
    if descriptor.family in {"PNG", "TIFF"}:
        return {
            "status": "UNKNOWN",
            "confidence": 0.0,
            "reason": f"{descriptor.format} 형식만으로 Linear/Non-linear 상태를 단정하지 않습니다. 사용자 확인이 필요할 수 있습니다.",
            "evidence": [f"{descriptor.family}_SOURCE"],
        }
    return inferred


def cleanup_analysis_cache(report: dict | None):
    if not report:
        return
    normalization = report.get("normalization") or {}
    raw = normalization.get("analysis_file")
    if not raw:
        return
    path = Path(raw)
    root = _cache_root().resolve()
    try:
        resolved = path.resolve()
        if root == resolved or root in resolved.parents:
            shutil.rmtree(resolved.parent, ignore_errors=True)
    except Exception:
        pass


def write_source_metadata(path: Path, payload: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path
