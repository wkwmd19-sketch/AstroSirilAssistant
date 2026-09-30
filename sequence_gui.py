from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import date
import threading
import time

from astroauto.config import load_app_config
from astroauto.sequence_project import create_sequence_project
from astroauto.preprocess_engine import build_preprocess_plan, execute_preprocess
from astroauto.siril import get_siril_info
from astroauto.execution import TaskControl, ExecutionCancelled, execution_context
from astroauto.ui_theme import (
    apply_astro_theme,
    apply_screen_aware_geometry,
    style_text_widget,
    style_canvas,
)

CATEGORIES = [
    ("은하", "GALAXY"),
    ("방출성운", "EMISSION_NEBULA"),
    ("반사성운", "REFLECTION_NEBULA"),
    ("암흑성운", "DARK_NEBULA"),
    ("행성상성운", "PLANETARY_NEBULA"),
    ("초신성잔해", "SUPERNOVA_REMNANT"),
    ("산개성단", "OPEN_CLUSTER"),
    ("구상성단", "GLOBULAR_CLUSTER"),
    ("은하수(하늘)", "MILKYWAY"),
    ("일반 별필드", "GENERAL_STARFIELD"),
]
LABEL_TO_ID = dict(CATEGORIES)

class SequenceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AstroSirilAssistant v0.14.7 · Deep Sky Sequence")
        apply_screen_aware_geometry(self)
        self.palette = apply_astro_theme(self)

        self.cfg = load_app_config()
        self.project_dir: Path | None = None

        self.target = tk.StringVar(value="M31")
        self.capture_date = tk.StringVar(value=date.today().isoformat())
        self.category = tk.StringVar(value="은하")
        self.camera_mode = tk.StringVar(value="AUTO")
        self.input_status = tk.StringVar(value="RAW_UNCALIBRATED")
        self.project_root = tk.StringVar(value=self.cfg["app"]["project_root"])
        self.copy_inputs = tk.BooleanVar(value=False)

        self.paths = {
            "lights": tk.StringVar(),
            "darks": tk.StringVar(),
            "flats": tk.StringVar(),
            "bias": tk.StringVar(),
            "dark_flats": tk.StringVar(),
        }

        self.status = tk.StringVar(value="대기 중")
        self.operation_var = tk.StringVar(value="대기 중")
        self.elapsed_var = tk.StringVar(value="")
        self.logs_visible = False
        self._log_sash_ratio = 0.68
        self._busy = False
        self._busy_started = None
        self._busy_timer_id = None
        self._busy_disabled_widgets = []
        self._current_control = None
        self._current_operation = None
        self._cancel_requested = False

        self._build()

    # ------------------------------------------------------------------
    # Modern responsive shell: same UX policy as run_gui.bat
    # ------------------------------------------------------------------
    def _build(self):
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)

        self.main_pane = ttk.Panedwindow(shell, orient=tk.VERTICAL)
        self.main_pane.pack(fill="both", expand=True)

        holder = ttk.Frame(self.main_pane)
        self.main_pane.add(holder, weight=5)
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            holder,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=24,
        )
        style_canvas(self.canvas, self.palette)
        self.scroll = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scroll.grid(row=0, column=1, sticky="ns")

        f = ttk.Frame(self.canvas, padding=20)
        self.workspace_inner = f
        self.workspace_window_id = self.canvas.create_window((0,0), window=f, anchor="nw")
        f.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_linux_wheel, add="+")
        self.bind_all("<Button-5>", self._on_linux_wheel, add="+")

        # Header
        header = ttk.Frame(f, style="Surface.TFrame", padding=(22,18))
        header.grid(row=0, column=0, sticky="ew", pady=(0,16))
        title_col = ttk.Frame(header, style="Surface.TFrame")
        title_col.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_col, text="AstroSirilAssistant", style="Title.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            title_col,
            text="딥스카이 시퀀스 전처리 · Calibration → Registration → Stack",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2,0))
        ttk.Label(header, text="시퀀스", style="Badge.TLabel").pack(side="right")

        # Source folders
        source = ttk.LabelFrame(f, text="촬영 프레임", style="Card.TLabelframe")
        source.grid(row=1, column=0, sticky="ew", pady=(0,14))
        rows = [
            ("Lights 폴더", "lights"),
            ("Dark 폴더", "darks"),
            ("Flat 폴더", "flats"),
            ("Bias 폴더", "bias"),
            ("Dark-flat 폴더", "dark_flats"),
        ]
        for i, (label, key) in enumerate(rows):
            ttk.Label(source, text=label, width=18).grid(row=i, column=0, sticky="w", pady=6)
            ttk.Entry(source, textvariable=self.paths[key]).grid(
                row=i, column=1, sticky="ew", padx=(8,0), pady=4
            )
            ttk.Button(source, text="선택", command=lambda k=key: self.pick(k)).grid(
                row=i, column=2, padx=(8,0), pady=4
            )
        source.columnconfigure(1, weight=1)

        # Project / camera
        project = ttk.LabelFrame(f, text="프로젝트 / 촬영 정보", style="Card.TLabelframe")
        project.grid(row=2, column=0, sticky="ew", pady=(0,14))

        ttk.Label(project, text="대상명", width=18).grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(project, textvariable=self.target).grid(row=0, column=1, sticky="ew", padx=(8,0), pady=6)

        ttk.Label(project, text="촬영일", width=18).grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(project, textvariable=self.capture_date).grid(row=1, column=1, sticky="ew", padx=(8,0), pady=6)

        ttk.Label(project, text="대상 종류", width=18).grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(
            project, textvariable=self.category, state="readonly",
            values=[x[0] for x in CATEGORIES]
        ).grid(row=2, column=1, sticky="ew", padx=(8,0), pady=6)

        ttk.Label(project, text="카메라", width=18).grid(row=3, column=0, sticky="w", pady=6)
        ttk.Combobox(
            project, textvariable=self.camera_mode, state="readonly",
            values=["AUTO", "OSC", "MONO"]
        ).grid(row=3, column=1, sticky="ew", padx=(8,0), pady=6)

        ttk.Label(project, text="입력 상태", width=18).grid(row=4, column=0, sticky="w", pady=6)
        ttk.Combobox(
            project, textvariable=self.input_status, state="readonly",
            values=["RAW_UNCALIBRATED", "PRECALIBRATED"]
        ).grid(row=4, column=1, sticky="ew", padx=(8,0), pady=6)

        ttk.Label(project, text="저장 위치", width=18).grid(row=5, column=0, sticky="w", pady=6)
        ttk.Entry(project, textvariable=self.project_root).grid(
            row=5, column=1, sticky="ew", padx=(8,0), pady=4
        )
        ttk.Button(project, text="선택", command=self.pick_root).grid(
            row=5, column=2, padx=(8,0), pady=4
        )

        ttk.Checkbutton(
            project,
            text="원본을 프로젝트로 복사 (저장공간 사용량 증가)",
            variable=self.copy_inputs,
        ).grid(row=6, column=1, sticky="w", padx=(8,0), pady=(5,2))
        project.columnconfigure(1, weight=1)

        # Workflow actions
        actions = ttk.LabelFrame(f, text="반자동 실행", style="Card.TLabelframe")
        actions.grid(row=3, column=0, sticky="ew", pady=(0,14))

        buttons = ttk.Frame(actions)
        buttons.pack(fill="x")
        ttk.Button(
            buttons, text="Siril 연결 확인", command=self.doctor
        ).pack(side="left", padx=(0,6))
        ttk.Button(
            buttons, text="1 · 프로젝트 생성", command=self.create_project,
            style="Accent.TButton"
        ).pack(side="left", padx=6)
        ttk.Button(
            buttons, text="2 · 실행 계획 보기", command=self.show_plan
        ).pack(side="left", padx=6)
        ttk.Button(
            buttons, text="3 · 승인 후 실행", command=self.run_real,
            style="Success.TButton"
        ).pack(side="left", padx=6)


        status_card = ttk.Frame(f, style="Surface.TFrame", padding=(16,11))
        status_card.grid(row=4, column=0, sticky="ew", pady=(0,12))
        ttk.Label(status_card, text="상태", style="Subtitle.TLabel").pack(side="left")
        ttk.Label(status_card, textvariable=self.status, style="Subtitle.TLabel").pack(
            side="left", padx=(10,0)
        )

        op = ttk.Frame(f, style="Surface.TFrame", padding=(14, 10))
        op.grid(row=5, column=0, sticky="ew", pady=(2,8))
        ttk.Label(op, textvariable=self.operation_var).pack(side="left")
        self.progress = ttk.Progressbar(op, mode="indeterminate", length=260)
        self.progress.pack(side="left", padx=(12,8), fill="x", expand=True)
        ttk.Label(op, textvariable=self.elapsed_var, width=12).pack(side="left")
        self.cancel_btn = ttk.Button(op, text="중단", command=self.request_cancel, style="Danger.TButton")
        self.cancel_btn.pack(side="left", padx=(8,0))
        self.cancel_btn.state(["disabled"])

        log_toolbar = ttk.Frame(f)
        log_toolbar.grid(row=6, column=0, sticky="ew", pady=(4,14))
        self.log_toggle_btn = ttk.Button(
            log_toolbar, text="▼ 상세 로그 보기", command=self.toggle_logs
        )
        self.log_toggle_btn.pack(side="left")
        self.copy_log_btn = ttk.Button(
            log_toolbar, text="로그 복사", command=self.copy_logs
        )
        self.copy_log_btn.pack(side="left", padx=(6,0))

        f.columnconfigure(0, weight=1)

        self.log_frame = ttk.LabelFrame(
            self.main_pane, text="상세 로그", style="Card.TLabelframe"
        )
        self.out = tk.Text(self.log_frame, wrap="word", height=10)
        style_text_widget(self.out, self.palette)
        self.out.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(self.log_frame, command=self.out.yview)
        sb.pack(side="right", fill="y")
        self.out.configure(yscrollcommand=sb.set)

    # ------------------------------------------------------------------
    # Responsive scroll behavior (same fixed policy as main GUI)
    # ------------------------------------------------------------------
    def _bbox(self):
        try:
            return self.canvas.bbox("all")
        except Exception:
            return None

    def _overflows(self):
        bbox = self._bbox()
        if not bbox:
            return False
        return (bbox[3] - bbox[1]) > self.canvas.winfo_height() + 2

    def _sync_scroll(self):
        bbox = self._bbox()
        if not bbox:
            return
        self.canvas.configure(scrollregion=bbox)
        if self._overflows():
            try:
                self.scroll.state(["!disabled"])
            except Exception:
                pass
        else:
            self.canvas.yview_moveto(0.0)
            try:
                self.scroll.state(["disabled"])
            except Exception:
                pass

    def _on_inner_configure(self, _event=None):
        self._sync_scroll()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.workspace_window_id, width=max(1, event.width))
        self.after_idle(self._sync_scroll)

    def _is_in_workspace(self, widget):
        cur = widget
        while cur is not None:
            if cur in (self.workspace_inner, self.canvas):
                return True
            try:
                cur = cur.master
            except Exception:
                cur = None
        return False

    def _on_mousewheel(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            widget = None
        if not widget or not self._is_in_workspace(widget):
            return None
        if isinstance(widget, ttk.Combobox):
            return None
        if not self._overflows():
            self.canvas.yview_moveto(0.0)
            return "break"

        delta = int(getattr(event, "delta", 0) or 0)
        if not delta:
            return None
        notches = int(delta / 120) if abs(delta) >= 120 else (1 if delta > 0 else -1)
        notches = max(-3, min(3, notches))
        self.canvas.yview_scroll(-notches * 2, "units")
        return "break"

    def _on_linux_wheel(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            widget = None
        if not widget or not self._is_in_workspace(widget):
            return None
        if not self._overflows():
            self.canvas.yview_moveto(0.0)
            return "break"
        self.canvas.yview_scroll(-2 if event.num == 4 else 2, "units")
        return "break"

    # ------------------------------------------------------------------
    # Log pane
    # ------------------------------------------------------------------
    def _set_log_sash(self):
        if not self.logs_visible:
            return
        try:
            if len(self.main_pane.panes()) < 2:
                return
            self.update_idletasks()
            total_h = max(1, self.main_pane.winfo_height())
            desired = int(total_h * self._log_sash_ratio)
            desired = max(180, min(desired, max(180, total_h - 150)))
            self.main_pane.sashpos(0, desired)
        except Exception:
            pass

    def toggle_logs(self):
        if self.logs_visible:
            try:
                total_h = max(1, self.main_pane.winfo_height())
                if len(self.main_pane.panes()) >= 2:
                    self._log_sash_ratio = max(
                        0.45, min(0.85, self.main_pane.sashpos(0) / total_h)
                    )
            except Exception:
                pass
            try:
                self.main_pane.forget(self.log_frame)
            except Exception as e:
                messagebox.showerror("로그 패널 오류", str(e))
                return
            self.logs_visible = False
            self.log_toggle_btn.configure(text="▼ 상세 로그 보기")
            return

        try:
            if str(self.log_frame) not in set(self.main_pane.panes()):
                self.main_pane.add(self.log_frame, weight=2)
        except Exception as e:
            messagebox.showerror("로그 패널 오류", str(e))
            return
        self.logs_visible = True
        self.log_toggle_btn.configure(text="▲ 상세 로그 숨기기")
        self.update_idletasks()
        self._set_log_sash()
        self.after(40, self._set_log_sash)
        self.after(140, self._set_log_sash)

    def show_logs(self):
        if not self.logs_visible:
            self.toggle_logs()
        else:
            self._set_log_sash()

    def copy_logs(self):
        text = self.out.get("1.0", "end-1c")
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status.set("로그를 클립보드에 복사했습니다.")
        except Exception as e:
            messagebox.showerror("로그 복사 오류", str(e))

    def write(self, msg):
        self.out.insert("end", str(msg).rstrip() + "\n")
        self.out.see("end")

    # ------------------------------------------------------------------
    # Busy/progress policy
    # ------------------------------------------------------------------
    def _set_controls_disabled(self, disabled: bool):
        if disabled:
            self._busy_disabled_widgets = []
            for widget in self.winfo_children():
                pass
            # Traverse all descendants and disable action controls only.
            stack = [self]
            while stack:
                parent = stack.pop()
                try:
                    children = parent.winfo_children()
                except Exception:
                    continue
                stack.extend(children)
                for w in children:
                    if w in (getattr(self, "log_toggle_btn", None), getattr(self, "copy_log_btn", None)):
                        continue
                    if w is getattr(self, "cancel_btn", None):
                        continue
                    if isinstance(w, (ttk.Button, ttk.Entry, ttk.Combobox, ttk.Checkbutton)):
                        try:
                            if "disabled" not in w.state():
                                self._busy_disabled_widgets.append(w)
                                w.state(["disabled"])
                        except Exception:
                            pass
        else:
            for w in self._busy_disabled_widgets:
                try:
                    if w.winfo_exists():
                        w.state(["!disabled"])
                except Exception:
                    pass
            self._busy_disabled_widgets = []

    def _tick_elapsed(self):
        if not self._busy or self._busy_started is None:
            return
        sec = int(time.monotonic() - self._busy_started)
        self.elapsed_var.set(f"경과 {sec//60:02d}:{sec%60:02d}")
        self._busy_timer_id = self.after(500, self._tick_elapsed)

    def _begin_busy(self, label):
        if self._busy:
            raise RuntimeError("다른 작업이 실행 중입니다.")
        self._busy = True
        self._busy_started = time.monotonic()
        self._current_operation = label
        self._cancel_requested = False
        self.operation_var.set(f"● 실행 중: {label}")
        self.elapsed_var.set("경과 00:00")
        self.progress.start(12)
        self._set_controls_disabled(True)
        self.cancel_btn.state(["!disabled"])
        self.write(f"\n▶ 실행 시작: {label}")
        self._tick_elapsed()

    def _end_busy(self, label, success=False, cancelled=False):
        if self._busy_timer_id:
            try: self.after_cancel(self._busy_timer_id)
            except Exception: pass
            self._busy_timer_id = None
        self.progress.stop()
        self.cancel_btn.state(["disabled"])
        self._set_controls_disabled(False)
        self._busy = False
        self._current_control = None
        self._current_operation = None
        if cancelled:
            self.operation_var.set(f"■ 중단됨: {label}")
        else:
            self.operation_var.set(f"{'✓ 완료' if success else '✕ 오류'}: {label}")

    def _execution_log_line(self, line):
        line = str(line).rstrip()
        if line:
            self.after(0, lambda s=line: self.write(f"│ {s}"))

    def request_cancel(self):
        if not self._busy or not self._current_control or self._cancel_requested:
            return
        operation = self._current_operation or "현재 작업"
        if not messagebox.askyesno(
            "작업 중단",
            f"{operation}을(를) 중단할까요?\n\n완료되지 않은 출력은 정상 결과로 채택하지 않습니다."
        ):
            return
        self._cancel_requested = True
        self.cancel_btn.state(["disabled"])
        self.operation_var.set(f"■ 중단 요청 중: {operation}")
        self.status.set("중단 요청 중...")
        self.write("■ 사용자 중단 요청 — 실행 중인 Siril 프로세스를 종료합니다.")
        self._current_control.cancel()

    def run_bg(self, fn, operation, on_success=None):
        control = TaskControl()
        try:
            self._begin_busy(operation)
            self._current_control = control
        except Exception as e:
            messagebox.showwarning("실행 중", str(e))
            return

        def worker():
            try:
                with execution_context(control, log_callback=self._execution_log_line):
                    result = fn()
                    if control.cancelled:
                        raise ExecutionCancelled("사용자가 작업을 중단했습니다.")
            except ExecutionCancelled as e:
                def cancelled():
                    self._end_busy(operation, cancelled=True)
                    self.status.set("작업 중단됨")
                    self.write(f"■ 작업 중단 완료: {e}")
                self.after(0, cancelled)
                return
            except Exception as e:
                def fail():
                    self._end_busy(operation, success=False)
                    self.status.set("오류")
                    self.write(f"\n✕ 오류: {operation}\n{e}")
                    self.show_logs()
                    messagebox.showerror("오류", str(e))
                self.after(0, fail)
                return

            def done():
                self._end_busy(operation, success=True)
                if on_success: on_success(result)
            self.after(0, done)
        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Existing sequence workflow
    # ------------------------------------------------------------------
    def pick(self, key):
        path = filedialog.askdirectory()
        if path:
            self.paths[key].set(path)

    def pick_root(self):
        path = filedialog.askdirectory()
        if path:
            self.project_root.set(path)

    def doctor(self):
        def work():
            return get_siril_info(self.cfg)

        def done(info):
            self.write(
                f"Siril 연결 OK\n{info.executable}\nVersion: {info.version}\n"
            )
            self.status.set("Siril 연결 OK")

        self.run_bg(work, "Siril 연결 확인", done)

    def create_project(self):
        if not self.paths["lights"].get():
            messagebox.showwarning("확인", "Lights 폴더를 선택하세요.")
            return

        def work():
            return create_sequence_project(
                root=Path(self.project_root.get()),
                target=self.target.get(),
                capture_date=self.capture_date.get(),
                category=LABEL_TO_ID[self.category.get()],
                lights_dir=Path(self.paths["lights"].get()),
                darks_dir=Path(self.paths["darks"].get()) if self.paths["darks"].get() else None,
                flats_dir=Path(self.paths["flats"].get()) if self.paths["flats"].get() else None,
                bias_dir=Path(self.paths["bias"].get()) if self.paths["bias"].get() else None,
                dark_flats_dir=Path(self.paths["dark_flats"].get()) if self.paths["dark_flats"].get() else None,
                camera_mode=self.camera_mode.get(),
                input_status=self.input_status.get(),
                copy_inputs=self.copy_inputs.get(),
            )

        def done(pdir):
            self.project_dir = pdir
            self.write(f"프로젝트 생성 완료:\n{pdir}\n")
            self.status.set("프로젝트 생성 완료")

        self.run_bg(work, "Sequence 프로젝트 생성", done)

    def show_plan(self):
        if not self.project_dir:
            messagebox.showwarning("확인", "먼저 프로젝트를 생성하세요.")
            return

        def work():
            return build_preprocess_plan(self.project_dir)

        def done(result):
            plan, plan_path, script_path = result
            lines = [
                "=== 반자동 Siril 전처리 계획 ===",
                f"Lights: {plan['counts']['lights']}장",
                f"Dark: {plan['counts']['dark']}장",
                f"Flat: {plan['counts']['flat']}장",
                f"Bias: {plan['counts']['bias']}장",
                f"Dark-flat: {plan['counts']['dark_flat']}장",
                f"Camera: {plan['camera_mode']}",
                "",
                "작업:",
            ]
            lines += [f"- {x}" for x in plan["phases"]]
            if plan["warnings"]:
                lines += ["", "주의:"] + [f"- {x}" for x in plan["warnings"]]
            lines += ["", f"Plan: {plan_path}", f"Script: {script_path}"]
            self.write("\n".join(lines) + "\n")
            self.status.set("실행 계획 준비 완료")
            self.show_logs()

        self.run_bg(work, "Sequence 실행 계획 생성", done)

    def run_real(self):
        if not self.project_dir:
            messagebox.showwarning("확인", "먼저 프로젝트를 생성하세요.")
            return
        ok = messagebox.askyesno(
            "실제 Siril 실행",
            "Calibration / Registration / Stack을 실제로 실행합니다.\n"
            "실행 계획을 확인했나요?"
        )
        if not ok:
            return

        def work():
            return execute_preprocess(self.project_dir, self.cfg, confirmed=True)

        def done(result):
            project, output, plan = result
            self.write(
                f"\n처리 완료!\n출력: {output}\n"
                "다음 작업: Single Image GUI에서 Background / Gradient Correction\n"
            )
            self.status.set("Stack 완료")
            messagebox.showinfo(
                "Sequence 처리 완료",
                f"Stack 완료:\n{output}\n\n"
                "이 결과를 run_gui.bat의 단일 이미지 파이프라인으로 이어갈 수 있습니다."
            )

        self.run_bg(work, "Calibration / Registration / Stack", done)

if __name__ == "__main__":
    SequenceApp().mainloop()
