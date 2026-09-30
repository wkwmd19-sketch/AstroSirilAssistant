from __future__ import annotations
from contextlib import contextmanager
import os
import signal
import subprocess
import threading

class ExecutionCancelled(RuntimeError):
    """Raised when the user cancels the currently running operation."""

class TaskControl:
    def __init__(self):
        self.cancel_event = threading.Event()
        self._lock = threading.RLock()
        self._processes = set()

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def register(self, proc: subprocess.Popen):
        with self._lock:
            self._processes.add(proc)
        if self.cancelled:
            self._terminate_process_tree(proc)

    def unregister(self, proc: subprocess.Popen):
        with self._lock:
            self._processes.discard(proc)

    def cancel(self):
        self.cancel_event.set()
        with self._lock:
            processes = list(self._processes)
        for proc in processes:
            self._terminate_process_tree(proc)

    def _terminate_process_tree(self, proc: subprocess.Popen):
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == 'nt':
                # Siril can launch/host Python processing. Kill the whole tree so
                # a cancelled SyQon task cannot stay alive in the background.
                subprocess.Popen(
                    ['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except Exception:
                    proc.terminate()
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass

_local = threading.local()

@contextmanager
def execution_context(control: TaskControl | None, log_callback=None):
    previous = getattr(_local, 'context', None)
    _local.context = {'control': control, 'log_callback': log_callback}
    try:
        yield
    finally:
        _local.context = previous

def current_control() -> TaskControl | None:
    ctx = getattr(_local, 'context', None) or {}
    return ctx.get('control')

def emit_log(line: str):
    ctx = getattr(_local, 'context', None) or {}
    callback = ctx.get('log_callback')
    if callback and line:
        try:
            callback(str(line))
        except Exception:
            pass

def check_cancelled():
    control = current_control()
    if control and control.cancelled:
        raise ExecutionCancelled('사용자가 작업을 중단했습니다.')

def popen_group_kwargs() -> dict:
    if os.name == 'nt':
        return {'creationflags': getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)}
    return {'start_new_session': True}
