from __future__ import annotations
from pathlib import Path
import subprocess
import re
import shutil
import queue
import threading
import time
from dataclasses import dataclass

from .utils import normalize_siril_path
from .execution import (
    current_control, emit_log, ExecutionCancelled, popen_group_kwargs
)

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

def _run_streaming_process(args, *, input_text: str | None, cwd: Path | None, timeout: int):
    control = current_control()
    proc = subprocess.Popen(
        [str(x) for x in args],
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd else None,
        bufsize=1,
        **popen_group_kwargs(),
    )
    if control:
        control.register(proc)

    lines = []
    q = queue.Queue()
    sentinel = object()

    def reader():
        try:
            if proc.stdout:
                for line in iter(proc.stdout.readline, ''):
                    q.put(line)
        finally:
            q.put(sentinel)

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    try:
        if input_text is not None and proc.stdin:
            proc.stdin.write(input_text)
            proc.stdin.flush()
            proc.stdin.close()

        deadline = time.monotonic() + max(1, int(timeout))
        reader_done = False

        while True:
            while True:
                try:
                    item = q.get_nowait()
                except queue.Empty:
                    break
                if item is sentinel:
                    reader_done = True
                    continue
                lines.append(item)
                emit_log(item.rstrip('\r\n'))

            if control and control.cancelled:
                control._terminate_process_tree(proc)
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                raise ExecutionCancelled('사용자가 Siril/SyQon 작업을 중단했습니다.')

            if time.monotonic() > deadline:
                if control:
                    control._terminate_process_tree(proc)
                else:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                raise subprocess.TimeoutExpired(args, timeout)

            if proc.poll() is not None and reader_done and q.empty():
                break
            time.sleep(0.05)

        # Drain anything queued between the last loop and process exit.
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                break
            if item is sentinel:
                continue
            lines.append(item)
            emit_log(item.rstrip('\r\n'))

        return subprocess.CompletedProcess(
            args=[str(x) for x in args],
            returncode=proc.returncode,
            stdout=''.join(lines),
            stderr='',
        )
    finally:
        if control:
            control.unregister(proc)
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass


def run_script(config: dict, commands: list[str], cwd: Path | None = None, timeout_sec: int | None = None) -> subprocess.CompletedProcess:
    """Run commands through `siril-cli -s -` with live log streaming and cancellation."""
    info = get_siril_info(config)
    timeout = int(timeout_sec if timeout_sec is not None else config.get("siril", {}).get("command_timeout_sec", 180))
    minimum = str(config.get("siril", {}).get("minimum_supported", "1.4.0"))

    cleaned = [str(c).strip() for c in commands if str(c).strip()]
    first = cleaned[0].lower() if cleaned else ""
    if not first.startswith("requires "):
        cleaned.insert(0, f"requires {minimum}")

    script = "\n".join(cleaned).rstrip() + "\n"
    return _run_streaming_process(
        [str(info.executable), "-s", "-"],
        input_text=script,
        cwd=cwd,
        timeout=timeout,
    )

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


def run_script_file(config: dict, script_path: Path, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a real Siril script file with live log streaming and cancellation."""
    info = get_siril_info(config)
    timeout = int(config.get("siril", {}).get("command_timeout_sec", 180))
    return _run_streaming_process(
        [str(info.executable), "-s", str(Path(script_path).resolve())],
        input_text=None,
        cwd=cwd,
        timeout=timeout,
    )

