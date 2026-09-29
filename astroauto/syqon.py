from __future__ import annotations
from pathlib import Path
import os
import re

from .utils import normalize_siril_path

class SyQonError(RuntimeError):
    pass

SCRIPT_NAMES = {
    "PARALLAX": ("Parallax.py", "SyQon-Parallax.py"),
    "PRISM": ("Prism.py", "SyQon-Prism.py"),
}

CLI_REQUIRED_FLAGS = {
    "PARALLAX": ("--star-level", "--sharpen", "--edition"),
    "PRISM": ("--tile-size", "--modulation", "--model"),
}

def _candidate_roots(config: dict | None = None) -> list[Path]:
    config = config or {}
    roots: list[Path] = []

    for raw in config.get("syqon", {}).get("script_roots", []) or []:
        if raw:
            roots.append(Path(os.path.expandvars(os.path.expanduser(str(raw)))))

    home = Path.home()
    env_bases = []
    for key in ("LOCALAPPDATA", "APPDATA"):
        value = os.environ.get(key)
        if value:
            env_bases.append(Path(value))

    for base in env_bases:
        roots.extend([
            base / "org.siril.Siril" / "siril-scripts",
            base / "Siril" / "siril-scripts",
            base / "siril" / "siril-scripts",
            base / "siril-scripts",
        ])

    roots.extend([
        home / "AppData" / "Local" / "org.siril.Siril" / "siril-scripts",
        home / "AppData" / "Roaming" / "org.siril.Siril" / "siril-scripts",
        home / ".local" / "share" / "org.siril.Siril" / "siril-scripts",
        home / "Library" / "Application Support" / "org.siril.Siril" / "siril-scripts",
        home / ".siril" / "siril-scripts",
    ])

    unique = []
    seen = set()
    for root in roots:
        try:
            key = str(root.resolve()).lower()
        except Exception:
            key = str(root).lower()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique

def locate_syqon_script(kind: str, config: dict | None = None) -> Path | None:
    kind = str(kind).upper()
    names = SCRIPT_NAMES.get(kind)
    if not names:
        raise ValueError(f"알 수 없는 SyQon script 종류: {kind}")

    relative_candidates = []
    for name in names:
        relative_candidates.extend([
            Path("SyQon") / name,
            Path("processing") / "SyQon" / name,
            Path("processing") / name,
            Path(name),
        ])

    for root in _candidate_roots(config):
        if not root.exists():
            continue

        for rel in relative_candidates:
            p = root / rel
            if p.is_file():
                return p.resolve()

        # Repository layouts have changed over time. Search exact filenames,
        # but only inside identified siril-scripts roots.
        try:
            for name in names:
                found = next((p for p in root.rglob(name) if p.is_file()), None)
                if found:
                    return found.resolve()
        except Exception:
            pass

    return None

def check_syqon_cli_support(path: Path, kind: str) -> dict:
    kind = str(kind).upper()
    required = CLI_REQUIRED_FLAGS.get(kind, ())
    try:
        source = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"supported": False, "missing": list(required), "error": str(e)}

    missing = [flag for flag in required if flag not in source]
    # `pyscript` can pass argv only when the target script actually reads them.
    has_argv = ("argparse" in source) or ("sys.argv" in source)
    if not has_argv:
        missing.append("argv support")
    return {
        "supported": not missing,
        "missing": missing,
        "error": None,
    }


def detect_syqon(config: dict | None = None) -> dict:
    parallax = locate_syqon_script("PARALLAX", config)
    prism = locate_syqon_script("PRISM", config)
    parallax_cli = check_syqon_cli_support(parallax, "PARALLAX") if parallax else None
    prism_cli = check_syqon_cli_support(prism, "PRISM") if prism else None
    return {
        "parallax": str(parallax) if parallax else None,
        "prism": str(prism) if prism else None,
        "parallax_cli_ready": bool(parallax_cli and parallax_cli["supported"]),
        "prism_cli_ready": bool(prism_cli and prism_cli["supported"]),
        "parallax_cli_missing": parallax_cli["missing"] if parallax_cli else [],
        "prism_cli_missing": prism_cli["missing"] if prism_cli else [],
        "ready": bool(
            parallax and prism
            and parallax_cli and parallax_cli["supported"]
            and prism_cli and prism_cli["supported"]
        ),
    }


def require_syqon_script(kind: str, config: dict | None = None) -> Path:
    kind = str(kind).upper()
    path = locate_syqon_script(kind, config)
    if path:
        cli = check_syqon_cli_support(path, kind)
        if cli["supported"]:
            return path
        raise SyQonError(
            f"SyQon {kind.title()} script는 발견했지만 반자동 호출에 필요한 CLI 옵션이 없습니다.\n\n"
            f"Script: {path}\n"
            f"확인되지 않은 항목: {', '.join(cli['missing'])}\n\n"
            "Siril의 Get Scripts에서 해당 SyQon script를 최신 버전으로 업데이트한 뒤 다시 시도하세요.\n"
            "또는 Engine을 Siril Native로 바꿔 계속 처리할 수 있습니다."
        )

    names = " / ".join(SCRIPT_NAMES[kind])
    raise SyQonError(
        f"SyQon {kind.title()} script를 로컬 Siril script 저장소에서 찾지 못했습니다.\n\n"
        f"찾는 파일: {names}\n"
        "Siril의 Get Scripts에서 SyQon script를 설치/업데이트한 뒤 다시 시도하세요.\n"
        "자동 감지가 되지 않는 사용자 정의 위치라면 config/app.yaml의 "
        "syqon.script_roots에 siril-scripts 폴더 경로를 추가할 수 있습니다.\n\n"
        "원하면 Engine을 Siril Native로 바꿔 계속 처리할 수도 있습니다."
    )

def _script_arg(path: Path) -> str:
    value = normalize_siril_path(path)
    return f'"{value}"'

def _validate_tile_geometry(tile: int, overlap: int, pad: int):
    tile = int(tile)
    overlap = int(overlap)
    pad = int(pad)
    if tile < 64 or tile > 4096:
        raise ValueError("Tile Size는 64~4096 범위로 입력하세요.")
    if overlap < 0 or overlap >= tile:
        raise ValueError("Overlap은 0 이상이며 Tile Size보다 작아야 합니다.")
    if pad < 0 or pad > 2048:
        raise ValueError("Pad는 0~2048 범위로 입력하세요.")
    return tile, overlap, pad

def build_parallax_command(
    script_path: Path,
    *,
    edition: str = "nano",
    correct: bool = True,
    star_level: float = 3.0,
    sharpen: float = 1.0,
    tile: int = 512,
    overlap: int = 64,
    pad: int = 96,
    use_mtf: bool = True,
    mtf_target: float = 0.25,
    linked: bool = False,
    use_gpu: bool = True,
) -> str:
    edition = str(edition).lower()
    if edition not in ("nano", "pro"):
        raise ValueError("Parallax Edition은 nano / pro 중 하나여야 합니다.")

    tile, overlap, pad = _validate_tile_geometry(tile, overlap, pad)
    star_level = float(star_level)
    max_star = 5.0 if edition == "nano" else 7.0
    if star_level < 0 or star_level > max_star:
        raise ValueError(f"{edition.upper()} Star Level은 0~{max_star:g} 범위여야 합니다.")

    sharpen = float(sharpen)
    if sharpen < 0 or sharpen > 2.0:
        raise ValueError("Parallax Sharpen 값은 0~2 범위로 입력하세요.")

    mtf_target = float(mtf_target)
    if mtf_target <= 0 or mtf_target >= 1:
        raise ValueError("MTF Target은 0과 1 사이여야 합니다.")

    args = [
        "pyscript", _script_arg(Path(script_path)),
        "--edition", edition,
        "--star-level", f"{star_level:g}",
        "--sharpen", f"{sharpen:g}",
        "--tile", str(tile),
        "--overlap", str(overlap),
        "--pad", str(pad),
        "--mtf-target", f"{mtf_target:g}",
    ]
    if not correct:
        args.append("--no-correct")
    if not use_mtf:
        args.append("--no-mtf")
    if linked:
        args.append("--linked")
    if not use_gpu:
        args.append("--no-gpu")
    return " ".join(args)

def build_prism_command(
    script_path: Path,
    *,
    tile_size: int = 512,
    overlap: int = 96,
    pad: int = 96,
    modulation: float = 1.0,
    model: str = "mini",
    use_gpu: bool = True,
    stretch_method: str = "statistical",
    stretch_target: float = 0.25,
) -> str:
    tile_size, overlap, pad = _validate_tile_geometry(tile_size, overlap, pad)

    modulation = float(modulation)
    if modulation < 0 or modulation > 1:
        raise ValueError("Prism Modulation은 0~1 범위여야 합니다.")

    model = str(model).lower()
    if model not in ("mini", "deep"):
        raise ValueError("Prism Model은 mini / deep 중 하나여야 합니다.")

    stretch_method = str(stretch_method).lower()
    if stretch_method not in ("statistical", "ihs"):
        raise ValueError("Stretch Method는 statistical / ihs 중 하나여야 합니다.")

    stretch_target = float(stretch_target)
    if stretch_target < 0.01 or stretch_target > 0.50:
        raise ValueError("Stretch Target은 0.01~0.50 범위여야 합니다.")

    args = [
        "pyscript", _script_arg(Path(script_path)),
        "--tile-size", str(tile_size),
        "--overlap", str(overlap),
        "--pad", str(pad),
        "--modulation", f"{modulation:g}",
        "--model", model,
        "--stretch-method", stretch_method,
        "--stretch-target", f"{stretch_target:g}",
    ]
    if not use_gpu:
        args.append("--no-gpu")
    return " ".join(args)

def assert_syqon_process_success(proc, label: str):
    combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise SyQonError(
            f"{label} 실행 실패 (exit={proc.returncode})\n{combined[-5000:]}"
        )

    # Siril can occasionally continue the outer SSF even when a Python script
    # reports a command-level error, so inspect strong failure markers too.
    low = combined.lower()
    fatal_patterns = (
        "traceback (most recent call last)",
        "error: no image loaded",
        "error: no image or sequence loaded",
        "could not connect to siril",
        "model file not found",
        "could not load model",
        "processing error:",
        "script execution failed",
    )
    hit = next((pat for pat in fatal_patterns if pat in low), None)
    if hit:
        raise SyQonError(
            f"{label} 로그에서 실패 신호를 감지했습니다 ({hit}).\n"
            f"{combined[-5000:]}"
        )
