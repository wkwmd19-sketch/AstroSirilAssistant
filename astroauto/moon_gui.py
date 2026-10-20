"""Standalone Moon analytical-mode dialog integrated into the ASA GUI.

Runs independently of the DSO state machine. External Siril is only used
for camera RAW normalization; image analysis/alignment is handled by moon.py.
"""
from __future__ import annotations

from pathlib import Path
import json
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .moon import collect_inputs, analyze_moon, run_moon


class MoonWindow(tk.Toplevel):
    def __init__(self, master, config: dict):
        super().__init__(master)
        self.config_data = config
        self.plan = None
        self.busy = False
        self.title("ASA · Moon 분석형 보정 (검증판)")
        self.geometry("720x585")
        self.minsize(630, 490)
        self.mode = tk.StringVar(value="stack")
        self.source = tk.StringVar()
        self.pattern = tk.StringVar(value="*.CR3")
        self.dest = tk.StringVar()
        self.status = tk.StringVar(value="원본을 선택한 뒤 분석하세요. 실행 전 계획을 검토해야 합니다.")

        pane = ttk.Frame(self, padding=16)
        pane.pack(fill="both", expand=True)
        ttk.Label(pane, text="Moon · 분석형 달 보정", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(pane, text="달 전용 경로 · 원본 보존 · 분석 후 승인 실행").pack(anchor="w", pady=(2, 12))
        mode_row = ttk.Frame(pane)
        mode_row.pack(fill="x", pady=3)
        ttk.Label(mode_row, text="모드", width=12).pack(side="left")
        for label, value in (("단일 사진", "single"), ("동일 구도 스택", "stack"),
                             ("달 표면 모자이크", "mosaic")):
            ttk.Radiobutton(mode_row, text=label, variable=self.mode, value=value,
                            command=self._reset).pack(side="left", padx=8)

        self._entry(pane, "원본", self.source, self._pick_source)
        self._entry(pane, "파일 패턴", self.pattern)
        self._entry(pane, "출력 폴더", self.dest, self._pick_dest)

        buttons = ttk.Frame(pane)
        buttons.pack(fill="x", pady=(12, 6))
        self.analyze_button = ttk.Button(buttons, text="① 분석 / 계획", command=self._analyze)
        self.analyze_button.pack(side="left", padx=3)
        self.run_button = ttk.Button(buttons, text="② 승인 후 실제 처리",
                                     command=self._run, state="disabled")
        self.run_button.pack(side="left", padx=3)
        ttk.Button(buttons, text="출력 폴더 열기", command=self._open_dest).pack(side="right", padx=3)
        ttk.Label(pane, textvariable=self.status, wraplength=640).pack(anchor="w", pady=6)
        self.log = tk.Text(pane, height=20, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, pady=6)
        self._append("품질 측정 결과는 촬영 노출/초점의 대체물이 아닙니다. "
                     "Stack/Mosaic 정렬 실패 시 안전하게 중단하며 임의로 위치를 만들지 않습니다.")

        for var in (self.source, self.pattern, self.dest):
            var.trace_add("write", lambda *_: self._reset())

    def _entry(self, parent, label, variable, browse=None):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=12).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, padx=5)
        if browse:
            ttk.Button(row, text="찾기", command=browse).pack(side="right")

    def _append(self, value):
        self.log.configure(state="normal")
        self.log.insert("end", str(value) + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _reset(self):
        self.plan = None
        self.run_button.configure(state="disabled")

    def _pick_source(self):
        if self.mode.get() == "single":
            path = filedialog.askopenfilename(parent=self, title="달 원본 1장 선택")
        else:
            path = filedialog.askdirectory(parent=self, title="달 Light 프레임 폴더 선택")
        if path:
            self.source.set(path)
            origin = Path(path)
            default_dir = (origin.parent if origin.is_file() else origin.parent)
            self.dest.set(str(default_dir / ("ASA_Moon_" + self.mode.get().capitalize())))

    def _pick_dest(self):
        path = filedialog.askdirectory(parent=self, title="Moon 결과 폴더 선택")
        if path:
            self.dest.set(path)

    def _set_busy(self, value: bool, message: str):
        self.busy = value
        self.status.set(message)
        self.analyze_button.configure(state="disabled" if value else "normal")
        self.run_button.configure(state="disabled" if value or self.plan is None else "normal")

    def _worker(self, fn, on_success):
        if self.busy:
            return
        self._set_busy(True, "Moon 처리 중입니다. 큰 RAW/모자이크는 시간이 걸릴 수 있습니다.")

        def task():
            try:
                result = fn()
            except Exception as exc:
                msg = str(exc)
                self.after(0, lambda: self._failed(msg))
            else:
                self.after(0, lambda: self._succeeded(result, on_success))
        threading.Thread(target=task, daemon=True).start()

    def _failed(self, message):
        self._set_busy(False, "오류: 처리를 중단했습니다. 입력과 로그를 확인하세요.")
        self._append("오류: " + message)
        messagebox.showerror("Moon 처리 오류", message, parent=self)

    def _succeeded(self, result, callback):
        self._set_busy(False, "작업이 완료됐습니다.")
        callback(result)

    def _analyze(self):
        src = self.source.get().strip()
        dst = self.dest.get().strip()
        if not src or not dst:
            messagebox.showwarning("입력 확인", "원본과 출력 폴더를 지정하세요.", parent=self)
            return
        mode = self.mode.get()
        pattern = self.pattern.get().strip() or "*"

        def work():
            paths = collect_inputs(src, pattern)
            plan = analyze_moon(paths, self.config_data, mode=mode)
            directory = Path(dst)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "Moon_analysis_plan.json").write_text(
                json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            return plan

        def done(plan):
            self.plan = plan
            self.run_button.configure(state="normal")
            self._append(f"\n분석: {plan['mode']} / {len(plan['frames'])}장")
            for frame in plan["frames"]:
                self._append(f"{Path(frame['input']).name} · 품질={frame['quality_score']:.3f}"
                             f" · {frame['selection_suggestion']}")
            for issue in plan["issues"]:
                self._append("주의: " + issue)
            self._append("분석 완료. 실행 전 원본 구도/품질을 확인하고 승인하세요.")
        self._worker(work, done)

    def _run(self):
        if not self.plan:
            return
        count = len(self.plan["frames"])
        if not messagebox.askyesno("Moon 최종 실행 승인",
               f"{self.plan['mode']} 모드 / {count}장\n원본은 보존합니다.\n"
               "정렬 실패 시 중단하며 결과에 육안 검토가 필요합니다.\n실행할까요?",
               parent=self):
            return
        plan = self.plan
        dest = self.dest.get()
        def done(report):
            self._append("\n출력 완료 · QC 육안 확인 필수")
            for path in report["outputs"].values():
                self._append(path)
            self.run_button.configure(state="disabled")
        self._worker(lambda: run_moon(plan, self.config_data, dest, confirmed=True), done)

    def _open_dest(self):
        folder = Path(self.dest.get())
        if not folder.is_dir():
            return
        if os.name == "nt":
            os.startfile(str(folder))
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(folder)])


def open_moon_window(master, config: dict):
    return MoonWindow(master, config)
