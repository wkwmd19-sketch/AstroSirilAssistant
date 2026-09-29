from __future__ import annotations
from pathlib import Path
import subprocess
import re
import shutil
from dataclasses import dataclass

from .utils import normalize_siril_path

@dataclass
class SirilInfo:
    executable: Path
    version: str

class SirilError(RuntimeError):
    pass

def _parse_version(text: str) -> str:
    matches = re.findall(r"(?<!\d)(\d+\.\d+(?:\.\d+)?)(?!\d)", text)
    return matches[-1] if matches else "UNKNOWN"

def find_siril_cli(config: dict) -> Path | None:
    configured = config.get("siril", {}).get("executable")
    if configured:
        p = Path(configured)
        if p.exists():
            return p

    for name in ("siril-cli.exe", "siril-cli"):
        found = shutil.which(name)
        if found:
            return Path(found)

    for raw in config.get("siril", {}).get("candidate_paths", []):
        p = Path(raw)
        if p.exists():
            return p
    return None

def get_siril_info(config: dict) -> SirilInfo:
    exe = find_siril_cli(config)
    if not exe:
        raise SirilError(
            "siril-cli를 찾지 못했습니다. Siril 설치를 확인하거나 "
            "config/app.yaml의 siril.executable에 직접 경로를 지정하세요."
        )
    proc = subprocess.run(
        [str(exe), "--version"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise SirilError(f"Siril 버전 확인 실패: {combined.strip()}")
    return SirilInfo(executable=exe, version=_parse_version(combined))

def run_script(config: dict, commands: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    info = get_siril_info(config)
    timeout = int(config.get("siril", {}).get("command_timeout_sec", 180))
    script = "\n".join(commands).rstrip() + "\n"
    proc = subprocess.run(
        [str(info.executable), "-s", "-"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd else None,
        timeout=timeout
    )
    return proc

def write_jsonmetadata(config: dict, fits_path: Path, output_json: Path):
    fits_s = normalize_siril_path(fits_path)
    out_s = normalize_siril_path(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    commands = [
        "set32bits",
        f'load "{fits_s}"',
        f'jsonmetadata "{fits_s}" -stats_from_loaded "-out={out_s}"',
        "close",
    ]
    proc = run_script(config, commands, cwd=fits_path.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Siril jsonmetadata 실행 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    if not output_json.exists():
        raise SirilError(
            "Siril 명령은 종료되었지만 metadata JSON 파일이 생성되지 않았습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc
