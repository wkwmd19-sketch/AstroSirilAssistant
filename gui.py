from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import date
import threading
import time

from astroauto.config import load_app_config
from astroauto.project import create_project, load_project
from astroauto.analyzer import analyze_project, confirm_linearity
from astroauto.siril import get_siril_info
from astroauto.workflow import format_task
from astroauto.state_actions import (
    confirm_input_stage,
    confirm_calibration_status,
    confirm_star_trail_mode,
)
from astroauto.gradient import preview_gradient, apply_gradient
from astroauto.spcc import (
    fetch_spcc_lists, inspect_wcs, preview_spcc, apply_spcc,
    bgtol_uses_siril_default,
)
from astroauto.help_system import HelpSystem
from astroauto.config import load_yaml, PACKAGE_ROOT
from astroauto.denoise import (
    make_denoise_task, migrate_post_spcc_task,
    preview_denoise, apply_denoise, skip_denoise,
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
    ("은하수", "MILKYWAY"),
    ("일반 별필드", "GENERAL_STARFIELD"),
    ("별 일주사진", "STAR_TRAIL"),
    ("혜성/소행성", "COMET"),
    ("달/행성", "PLANETARY_LUNAR"),
    ("모자이크", "MOSAIC"),
    ("모름/자동판단 대기", "UNKNOWN"),
]
LABEL_TO_ID = dict(CATEGORIES)
ID_TO_LABEL = {v: k for k, v in CATEGORIES}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AstroSirilAssistant v0.6.0")
        self.geometry("1050x820")
        self.minsize(880, 650)
        self.cfg = load_app_config()
        self.ui_defaults = load_yaml(PACKAGE_ROOT / "config" / "ui_defaults.yaml")
        self.help = HelpSystem(self)
        self.project_dir: Path | None = None

        self.input_var = tk.StringVar()
        self.target_var = tk.StringVar(value="M31")
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.category_var = tk.StringVar(value="은하")
        self.root_var = tk.StringVar(value=self.cfg["app"]["project_root"])
        self.status_var = tk.StringVar(value="대기 중")

        gd = self.ui_defaults.get("gradient", {})
        self.gradient_samples = tk.StringVar(value=str(gd.get("samples", 20)))
        self.gradient_tolerance = tk.StringVar(value=str(gd.get("tolerance", 1.0)))
        self.gradient_smooth = tk.StringVar(value=str(gd.get("smooth", 0.5)))
        self.gradient_dither = tk.BooleanVar(value=bool(gd.get("dither", False)))
        self.gradient_preview_signature = None

        sd = self.ui_defaults.get("spcc", {})
        self.spcc_mode = tk.StringVar(value=sd.get("camera_mode", "OSC"))
        self.spcc_sensor = tk.StringVar(value=sd.get("sensor", ""))
        self.spcc_osc_filter = tk.StringVar(value=sd.get("osc_filter", ""))
        self.spcc_osc_lpf = tk.StringVar(value=sd.get("osc_lpf", ""))
        self.spcc_white_ref = tk.StringVar(value=sd.get("white_reference", "Average Spiral Galaxy"))
        self.spcc_catalog = tk.StringVar(value=sd.get("catalog", "AUTO"))
        self.spcc_bgtol_lower = tk.StringVar(value=str(sd.get("bgtol_lower", -2.8)))
        self.spcc_bgtol_upper = tk.StringVar(value=str(sd.get("bgtol_upper", 2.0)))
        self.spcc_preview_signature = None
        self.spcc_widgets = {}

        for var in (
            self.spcc_mode, self.spcc_sensor, self.spcc_osc_filter,
            self.spcc_osc_lpf, self.spcc_white_ref, self.spcc_catalog,
            self.spcc_bgtol_lower, self.spcc_bgtol_upper,
        ):
            var.trace_add("write", self._invalidate_spcc_preview)

        for var in (self.gradient_samples, self.gradient_tolerance, self.gradient_smooth):
            var.trace_add("write", self._invalidate_gradient_preview)
        self.gradient_dither.trace_add("write", self._invalidate_gradient_preview)

        dd = self.ui_defaults.get("denoise", {})
        self.denoise_modulation = tk.StringVar(value=str(dd.get("modulation", 1.0)))
        self.denoise_cosmetic = tk.BooleanVar(value=bool(dd.get("cosmetic_correction", True)))
        self.denoise_da3d = tk.BooleanVar(value=bool(dd.get("da3d", False)))
        self.denoise_independent = tk.BooleanVar(value=bool(dd.get("independent_channels", False)))
        self.denoise_preview_signature = None
        for var in (
            self.denoise_modulation, self.denoise_cosmetic,
            self.denoise_da3d, self.denoise_independent,
        ):
            var.trace_add("write", self._invalidate_denoise_preview)

        self.operation_var = tk.StringVar(value="대기 중")
        self.elapsed_var = tk.StringVar(value="")
        self.logs_visible = False
        self._busy = False
        self._busy_started = None
        self._busy_timer_id = None
        self._busy_disabled_widgets = []

        self._build()

    def _build(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="원본/스택 FITS").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.input_var, width=75).grid(row=0, column=1, sticky="ew")
        ttk.Button(frm, text="찾기", command=self.pick_input).grid(row=0, column=2, padx=5)

        ttk.Label(frm, text="대상명").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.target_var).grid(row=1, column=1, sticky="ew")

        ttk.Label(frm, text="촬영일").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.date_var).grid(row=2, column=1, sticky="ew")

        ttk.Label(frm, text="대상 종류").grid(row=3, column=0, sticky="w", pady=4)
        combo = ttk.Combobox(
            frm, textvariable=self.category_var, state="readonly",
            values=[x[0] for x in CATEGORIES]
        )
        combo.grid(row=3, column=1, sticky="ew")

        ttk.Label(frm, text="프로젝트 루트").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.root_var).grid(row=4, column=1, sticky="ew")
        ttk.Button(frm, text="폴더", command=self.pick_root).grid(row=4, column=2, padx=5)

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Button(btns, text="Siril 연결 확인", command=self.doctor).pack(side="left", padx=4)
        ttk.Button(btns, text="프로젝트 생성 + 분석", command=self.create_and_analyze).pack(side="left", padx=4)
        ttk.Button(btns, text="기존 프로젝트 열기", command=self.open_project).pack(side="left", padx=4)

        ttk.Label(frm, textvariable=self.status_var).grid(row=6, column=0, columnspan=3, sticky="w")

        self.action_box = ttk.LabelFrame(frm, text="다음 작업")
        self.action_box.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(8, 4))

        # Operation / progress area: visible even when detailed logs are collapsed.
        op = ttk.Frame(frm)
        op.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(5, 2))
        ttk.Label(op, textvariable=self.operation_var).pack(side="left")
        self.progress = ttk.Progressbar(op, mode="indeterminate", length=260)
        self.progress.pack(side="left", padx=(12, 8), fill="x", expand=True)
        ttk.Label(op, textvariable=self.elapsed_var, width=12).pack(side="left")

        log_toolbar = ttk.Frame(frm)
        log_toolbar.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(3, 2))
        self.log_toggle_btn = ttk.Button(log_toolbar, text="▼ 상세 로그 보기", command=self.toggle_logs)
        self.log_toggle_btn.pack(side="left")
        self.copy_log_btn = ttk.Button(log_toolbar, text="로그 복사", command=self.copy_logs)
        self.copy_log_btn.pack(side="left", padx=(6,0))

        self.log_frame = ttk.Frame(frm)
        self.log_frame.grid(row=10, column=0, columnspan=4, sticky="nsew", pady=(2,0))
        self.output = tk.Text(self.log_frame, wrap="word", height=20)
        self.output.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(self.log_frame, command=self.output.yview)
        scrollbar.pack(side="right", fill="y")
        self.output.configure(yscrollcommand=scrollbar.set)
        self.log_frame.grid_remove()

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(10, weight=1)
        self.main_frame = frm

    def pick_input(self):
        path = filedialog.askopenfilename(
            title="FITS 선택",
            filetypes=[("FITS", "*.fits *.fit *.fts"), ("All files", "*.*")]
        )
        if path:
            self.input_var.set(path)

    def pick_root(self):
        path = filedialog.askdirectory(title="프로젝트 루트 선택")
        if path:
            self.root_var.set(path)

    def write(self, text, clear=False):
        if clear:
            self.output.delete("1.0", "end")
        self.output.insert("end", text + "\n")
        self.output.see("end")

    def toggle_logs(self):
        if self.logs_visible:
            self.log_frame.grid_remove()
            self.log_toggle_btn.configure(text="▼ 상세 로그 보기")
            self.logs_visible = False
        else:
            self.log_frame.grid()
            self.log_toggle_btn.configure(text="▲ 상세 로그 숨기기")
            self.logs_visible = True

    def show_logs(self):
        if not self.logs_visible:
            self.toggle_logs()

    def copy_logs(self):
        text = self.output.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("로그를 클립보드에 복사했습니다.")

    def _walk_widgets(self, widget):
        for child in widget.winfo_children():
            yield child
            yield from self._walk_widgets(child)

    def _set_processing_controls_disabled(self, disabled: bool):
        if disabled:
            self._busy_disabled_widgets = []
            for w in self._walk_widgets(self):
                if w in (getattr(self, "log_toggle_btn", None), getattr(self, "copy_log_btn", None)):
                    continue
                if isinstance(w, (ttk.Button, ttk.Entry, ttk.Combobox, ttk.Checkbutton)):
                    try:
                        if "disabled" not in w.state():
                            w.state(["disabled"])
                            self._busy_disabled_widgets.append(w)
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

    def _begin_busy(self, label: str):
        if self._busy:
            raise RuntimeError("다른 작업이 실행 중입니다.")
        self._busy = True
        self._busy_started = time.monotonic()
        self.operation_var.set(f"● 실행 중: {label}")
        self.elapsed_var.set("경과 00:00")
        self.progress.start(12)
        self._set_processing_controls_disabled(True)
        self.write(f"\n▶ 실행 시작: {label}\n")
        self._tick_elapsed()

    def _end_busy(self, label: str, success: bool):
        if self._busy_timer_id:
            try:
                self.after_cancel(self._busy_timer_id)
            except Exception:
                pass
            self._busy_timer_id = None
        self.progress.stop()
        self._set_processing_controls_disabled(False)
        self._busy = False
        if success:
            self.operation_var.set(f"✓ 완료: {label}")
        else:
            self.operation_var.set(f"✕ 오류: {label}")

    def run_bg(self, func, operation: str | None = None, on_success=None):
        if operation:
            try:
                self._begin_busy(operation)
            except Exception as e:
                messagebox.showwarning("실행 중", str(e))
                return

        def runner():
            try:
                result = func()
            except Exception as e:
                def fail():
                    if operation:
                        self._end_busy(operation, False)
                    self.status_var.set("오류")
                    self.write(f"\n✕ 오류: {operation or '작업'}\n{e}\n")
                    self.show_logs()
                    messagebox.showerror("오류", str(e))
                self.after(0, fail)
                return

            def done():
                if operation:
                    self._end_busy(operation, True)
                if on_success:
                    on_success(result)
            self.after(0, done)

        threading.Thread(target=runner, daemon=True).start()

    def _show_apply_success(self, title: str, output: Path | str, next_title: str | None = None):
        msg = f"{title}이(가) 정상적으로 완료되었습니다.\\n\\n결과:\\n{output}"
        if next_title:
            msg += f"\\n\\n다음 단계: {next_title}"
        messagebox.showinfo("처리 완료", msg)

    def doctor(self):
        self.status_var.set("Siril 확인 중...")
        def work():
            info = get_siril_info(self.cfg)
            self.after(0, lambda: self.write(
                f"Siril 연결 OK\n경로: {info.executable}\n버전: {info.version}\n"
            ))
            self.after(0, lambda: self.status_var.set("Siril 연결 OK"))
        self.run_bg(work, operation="Siril 연결 확인")

    def create_and_analyze(self):
        input_path = self.input_var.get().strip()
        target = self.target_var.get().strip()
        capture_date = self.date_var.get().strip()
        if not input_path or not target or not capture_date:
            messagebox.showwarning("확인", "FITS, 대상명, 촬영일을 입력하세요.")
            return

        category = LABEL_TO_ID[self.category_var.get()]
        root = Path(self.root_var.get().strip())
        self.status_var.set("프로젝트 생성 및 분석 중...")
        self._clear_actions()
        self.output.delete("1.0", "end")

        def work():
            pdir = create_project(
                root=root,
                target=target,
                capture_date=capture_date,
                category=category,
                input_file=Path(input_path),
                copy_input=True,
            )
            project, report, task = analyze_project(pdir, self.cfg)
            self.project_dir = pdir

            text = (
                f"프로젝트 생성 완료\n{pdir}\n"
                f"캘리브레이션 폴더: {pdir / 'calibration'}\n\n"
                f"Siril: {report['siril']['version']}\n"
                f"이미지 shape: {report['pixel_statistics']['shape']}\n"
                f"Linear 판정: {report['linearity_assessment']['status']}\n"
                f"판정 이유: {report['linearity_assessment']['reason']}\n\n"
                + format_task(task)
                + f"\n\n상세 분석 로그:\n{pdir / 'logs' / 'analysis_report.json'}"
            )
            self.after(0, lambda: self.write(text, clear=True))
            self.after(0, lambda: self.render_task(task))
            self.after(0, lambda: self.status_var.set("분석 완료"))

        self.run_bg(work, operation="프로젝트 생성 + 분석")

    def open_project(self):
        path = filedialog.askdirectory(title="기존 AstroSirilAssistant 프로젝트 선택")
        if not path:
            return
        pdir = Path(path)
        try:
            project = load_project(pdir)
        except Exception as e:
            messagebox.showerror("오류", str(e))
            return

        self.project_dir = pdir
        project = migrate_post_spcc_task(pdir)
        p = project["project"]
        self.target_var.set(p.get("target_name", ""))
        self.category_var.set(ID_TO_LABEL.get(
            p.get("target", {}).get("category", "UNKNOWN"), "모름/자동판단 대기"
        ))
        self.date_var.set(p.get("capture", {}).get("date", self.date_var.get()))
        self.root_var.set(str(pdir.parent))
        current = p.get("current_file")
        if current:
            self.input_var.set(str(current))

        task = p.get("next_task")
        text = (
            f"기존 프로젝트 열기 완료\n{pdir}\n\n"
            f"현재 State: {p.get('current_state')}\n"
            f"현재 파일: {p.get('current_file')}\n"
            f"Linearity: {p.get('image_state', {}).get('linearity')}\n"
        )
        if task:
            text += "\n" + format_task(task)
        self.write(text, clear=True)
        self.render_task(task)
        self.status_var.set("기존 프로젝트 로드 완료")

    def _clear_actions(self):
        for child in self.action_box.winfo_children():
            child.destroy()

    def render_task(self, task):
        self._clear_actions()
        if not task:
            ttk.Label(self.action_box, text="다음 작업 정보가 없습니다.").pack(anchor="w", padx=8, pady=8)
            return

        task_id = task.get("task_id", "")
        ttk.Label(
            self.action_box,
            text=f"{task.get('title', task_id)} — {task.get('summary', '')}",
            wraplength=940,
        ).pack(anchor="w", padx=8, pady=(6, 4))

        controls = ttk.Frame(self.action_box)
        controls.pack(fill="x", padx=8, pady=(0, 8))

        if task_id == "CONFIRM_INPUT_STAGE":
            ttk.Button(
                controls, text="스택된 Linear",
                command=lambda: self.confirm_stage("STACKED_LINEAR")
            ).pack(side="left", padx=3)
            ttk.Button(
                controls, text="스택된 Non-linear",
                command=lambda: self.confirm_stage("STACKED_NONLINEAR")
            ).pack(side="left", padx=3)
            ttk.Button(
                controls, text="개별 Light 1장",
                command=lambda: self.confirm_stage("SINGLE_LIGHT")
            ).pack(side="left", padx=3)
            ttk.Button(
                controls, text="잘 모르겠음",
                command=lambda: messagebox.showinfo(
                    "입력 단계",
                    "이미 스택된 결과인지 확실하지 않다면 원본 생성 경로를 먼저 확인하세요.\n"
                    "이 상태에서는 큰 보정을 자동 실행하지 않습니다."
                )
            ).pack(side="left", padx=3)

        elif task_id == "CONFIRM_LINEARITY":
            ttk.Button(
                controls, text="Linear",
                command=lambda: self.confirm_linear("LINEAR")
            ).pack(side="left", padx=3)
            ttk.Button(
                controls, text="Non-linear",
                command=lambda: self.confirm_linear("NONLINEAR")
            ).pack(side="left", padx=3)

        elif task_id == "CONFIRM_CALIBRATION_STATUS":
            ttk.Button(
                controls, text="미보정 RAW/Light",
                command=lambda: self.confirm_calibration("RAW_UNCALIBRATED")
            ).pack(side="left", padx=3)
            ttk.Button(
                controls, text="이미 캘리브레이션됨",
                command=lambda: self.confirm_calibration("PRECALIBRATED")
            ).pack(side="left", padx=3)

        elif task_id == "CONFIRM_STAR_TRAIL_MODE":
            ttk.Button(
                controls, text="하늘 중심",
                command=lambda: self.confirm_trail("STAR_TRAIL_SKY")
            ).pack(side="left", padx=3)
            ttk.Button(
                controls, text="지상 풍경 포함",
                command=lambda: self.confirm_trail("STAR_TRAIL_LANDSCAPE")
            ).pack(side="left", padx=3)

        elif task_id == "GRADIENT_CORRECTION":
            self._build_gradient_controls(controls)

        elif task_id == "COLOR_CALIBRATION_SPCC":
            self._build_spcc_controls()

        elif task_id == "DENOISE":
            self._build_denoise_controls()

        else:
            ttk.Label(
                controls,
                text="이 단계의 실제 실행 UI는 이후 구현 단계에서 연결됩니다."
            ).pack(side="left", padx=3)

    def _build_gradient_controls(self, parent):
        # v0.5.1 Help UX:
        # - short tooltip appears only when hovering the exact parameter label
        # - one section-level detailed help button avoids visual clutter
        lbl = ttk.Label(parent, text="Samples")
        lbl.pack(side="left", padx=(0,2))
        self.help.tooltip(lbl, "gradient.samples")
        ttk.Entry(parent, textvariable=self.gradient_samples, width=5).pack(side="left", padx=(0,8))

        lbl = ttk.Label(parent, text="Tolerance")
        lbl.pack(side="left", padx=(0,2))
        self.help.tooltip(lbl, "gradient.tolerance")
        ttk.Entry(parent, textvariable=self.gradient_tolerance, width=6).pack(side="left", padx=(0,8))

        lbl = ttk.Label(parent, text="Smooth")
        lbl.pack(side="left", padx=(0,2))
        self.help.tooltip(lbl, "gradient.smooth")
        ttk.Entry(parent, textvariable=self.gradient_smooth, width=6).pack(side="left", padx=(0,8))

        lbl = ttk.Label(parent, text="Dither")
        lbl.pack(side="left", padx=(0,2))
        self.help.tooltip(lbl, "gradient.dither")
        ttk.Checkbutton(parent, variable=self.gradient_dither).pack(side="left", padx=(0,10))

        ttk.Button(parent, text="미리보기", command=self.gradient_preview).pack(side="left", padx=3)
        ttk.Button(parent, text="승인 후 적용", command=self.gradient_apply).pack(side="left", padx=3)

        self.help.section_help_button(
            parent,
            "Background / Gradient Correction 도움말",
            [
                "gradient.samples",
                "gradient.tolerance",
                "gradient.smooth",
                "gradient.dither",
                "gradient.preview",
                "gradient.apply",
            ],
        ).pack(side="right", padx=(12,3))

    def _build_spcc_controls(self):
        self._clear_actions()

        # Header: one detailed help entry for the whole section.
        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))

        title = ttk.Label(
            head,
            text="SPCC Color Calibration",
            font=("", 10, "bold"),
        )
        title.pack(side="left")
        self.help.tooltip(title, "spcc.what")

        ttk.Label(
            head,
            text="Gaia DR3 + Sensor / Filter 기반 색보정",
        ).pack(side="left", padx=(8,0))

        self.help.section_help_button(
            head,
            "SPCC Color Calibration 도움말",
            [
                "spcc.what",
                "spcc.platesolve",
                "spcc.camera_mode",
                "spcc.sensor",
                "spcc.osc_filter",
                "spcc.osc_lpf",
                "spcc.white_reference",
                "spcc.catalog",
                "spcc.bgtol",
                "spcc.list_refresh",
                "spcc.preview",
                "spcc.apply",
            ],
        ).pack(side="right")

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        # Only the exact labels get short hover tooltips.
        def row_label(row, text, topic):
            label = ttk.Label(body, text=text, width=19)
            label.grid(row=row, column=0, sticky="w", pady=3, padx=(0,8))
            self.help.tooltip(label, topic)
            return label

        row_label(0, "Camera Mode", "spcc.camera_mode")
        mode = ttk.Combobox(
            body, textvariable=self.spcc_mode,
            values=["OSC", "MONO"], state="readonly", width=22
        )
        mode.grid(row=0, column=1, sticky="w", pady=3)
        mode.bind("<<ComboboxSelected>>", lambda e: self._refresh_spcc_mode_ui())

        row_label(1, "Sensor", "spcc.sensor")
        sensor = ttk.Combobox(body, textvariable=self.spcc_sensor, width=56)
        sensor.grid(row=1, column=1, sticky="ew", pady=3)
        self.spcc_widgets["sensor"] = sensor

        row_label(2, "OSC Filter", "spcc.osc_filter")
        filt = ttk.Combobox(body, textvariable=self.spcc_osc_filter, width=56)
        filt.grid(row=2, column=1, sticky="ew", pady=3)
        self.spcc_widgets["oscfilter"] = filt

        row_label(3, "OSC LPF", "spcc.osc_lpf")
        lpf = ttk.Combobox(body, textvariable=self.spcc_osc_lpf, width=56)
        lpf.grid(row=3, column=1, sticky="ew", pady=3)
        self.spcc_widgets["osclpf"] = lpf

        row_label(4, "White Reference", "spcc.white_reference")
        wr = ttk.Combobox(body, textvariable=self.spcc_white_ref, width=56)
        wr.grid(row=4, column=1, sticky="ew", pady=3)
        self.spcc_widgets["whiteref"] = wr

        row_label(5, "Gaia Catalog", "spcc.catalog")
        ttk.Combobox(
            body, textvariable=self.spcc_catalog,
            values=["AUTO", "GAIA_ONLINE", "LOCAL_GAIA"],
            state="readonly", width=22
        ).grid(row=5, column=1, sticky="w", pady=3)

        row_label(6, "Background Tol.", "spcc.bgtol")
        tol_frame = ttk.Frame(body)
        tol_frame.grid(row=6, column=1, sticky="w", pady=3)
        ttk.Label(tol_frame, text="Lower").pack(side="left")
        ttk.Entry(tol_frame, textvariable=self.spcc_bgtol_lower, width=7).pack(side="left", padx=(4,12))
        ttk.Label(tol_frame, text="Upper").pack(side="left")
        ttk.Entry(tol_frame, textvariable=self.spcc_bgtol_upper, width=7).pack(side="left", padx=(4,0))
        ttk.Label(
            tol_frame,
            text="  (기본값이면 Siril 기본 -2.8 / +2.0 사용)",
        ).pack(side="left", padx=(8,0))

        ttk.Separator(body, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(8,8)
        )

        buttons = ttk.Frame(body)
        buttons.grid(row=8, column=0, columnspan=2, sticky="w", pady=(0,2))
        ttk.Button(buttons, text="SPCC 목록 불러오기", command=self.load_spcc_lists).pack(side="left", padx=(0,6))
        ttk.Button(buttons, text="Plate Solve 상태", command=self.show_wcs_status).pack(side="left", padx=6)
        ttk.Button(buttons, text="SPCC 미리보기", command=self.spcc_preview).pack(side="left", padx=6)
        ttk.Button(buttons, text="승인 후 적용", command=self.spcc_apply).pack(side="left", padx=6)

        body.columnconfigure(1, weight=1)
        self._refresh_spcc_mode_ui()

    def _refresh_spcc_mode_ui(self):
        mode = self.spcc_mode.get().upper()
        # v0.5 UI's first real test path is OSC. Mono is accepted by engine but
        # RGB filter selectors are planned for the next UI iteration.
        if mode == "MONO":
            self.status_var.set("Mono SPCC는 엔진 지원 / GUI R-G-B 필터 입력은 다음 확장 예정")
        else:
            self.status_var.set("SPCC OSC 설정 준비")

    def _spcc_signature(self):
        return (
            self.spcc_mode.get().strip(),
            self.spcc_sensor.get().strip(),
            self.spcc_osc_filter.get().strip(),
            self.spcc_osc_lpf.get().strip(),
            self.spcc_white_ref.get().strip(),
            self.spcc_catalog.get().strip(),
            self.spcc_bgtol_lower.get().strip(),
            self.spcc_bgtol_upper.get().strip(),
        )

    def _invalidate_spcc_preview(self, *args):
        self.spcc_preview_signature = None

    def _spcc_params(self):
        return {
            "mode": self.spcc_mode.get().upper(),
            "sensor": self.spcc_sensor.get().strip(),
            "osc_filter": self.spcc_osc_filter.get().strip(),
            "osc_lpf": self.spcc_osc_lpf.get().strip(),
            "white_reference": self.spcc_white_ref.get().strip(),
            "catalog": self.spcc_catalog.get().strip(),
            "bgtol_lower": float(self.spcc_bgtol_lower.get()),
            "bgtol_upper": float(self.spcc_bgtol_upper.get()),
        }

    def load_spcc_lists(self):
        if not self._require_project():
            return
        if self.spcc_mode.get().upper() != "OSC":
            messagebox.showinfo(
                "Mono SPCC",
                "v0.5.0 GUI에서는 오늘 테스트할 OSC 경로를 우선 구현했습니다.\n"
                "Mono 엔진은 지원하지만 R/G/B 필터 선택 UI는 다음 확장에서 추가합니다."
            )
            return

        self.status_var.set("Siril SPCC 데이터베이스 읽는 중...")

        def work():
            result = fetch_spcc_lists(self.cfg, mode="OSC")
            lists = result["lists"]
            self.after(0, lambda: self._apply_spcc_lists(lists))
            self.after(0, lambda: self.status_var.set("SPCC 목록 로드 완료"))

        self.run_bg(work, operation="SPCC 목록 불러오기")

    def _apply_spcc_lists(self, lists):
        mapping = {
            "sensor": lists.get("oscsensor", []),
            "oscfilter": lists.get("oscfilter", []),
            "osclpf": [""] + lists.get("osclpf", []),
            "whiteref": lists.get("whiteref", []),
        }
        for key, values in mapping.items():
            widget = self.spcc_widgets.get(key)
            if widget:
                widget["values"] = values

        self.write(
            "\nSPCC 데이터베이스 목록 로드 완료\n"
            f"OSC Sensors: {len(lists.get('oscsensor', []))}\n"
            f"OSC Filters: {len(lists.get('oscfilter', []))}\n"
            f"OSC LPF: {len(lists.get('osclpf', []))}\n"
            f"White References: {len(lists.get('whiteref', []))}\n"
        )

    def show_wcs_status(self):
        if not self._require_project():
            return
        try:
            project = load_project(self.project_dir)
            current = Path(project["project"]["current_file"])
            status = inspect_wcs(current)
            if status["plate_solved"]:
                msg = (
                    "현재 FITS에 WCS Plate Solve 정보가 있습니다.\n\n"
                    f"CTYPE1: {status['ctype1']}\n"
                    f"CTYPE2: {status['ctype2']}\n"
                    f"Center: {status['crval1']}, {status['crval2']}\n\n"
                    "SPCC 실행 시 Siril platesolve가 기존 해를 확인합니다."
                )
            else:
                hints = status["hints"]
                msg = (
                    "현재 FITS에서 완전한 WCS Plate Solve 정보를 확인하지 못했습니다.\n\n"
                    f"RA hint: {hints.get('ra')}\n"
                    f"DEC hint: {hints.get('dec')}\n"
                    f"Focal hint: {hints.get('focal_mm')}\n"
                    f"Pixel hint: {hints.get('pixel_um')}\n\n"
                    "SPCC 미리보기 시 Siril platesolve를 먼저 시도합니다.\n"
                    "메타데이터가 부족하면 Plate Solve 단계에서 오류가 날 수 있습니다."
                )
            messagebox.showinfo("Plate Solve 상태", msg)
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def spcc_preview(self):
        if not self._require_project():
            return
        if self.spcc_mode.get().upper() != "OSC":
            messagebox.showwarning("v0.6.0", "현재 GUI SPCC 미리보기는 OSC 경로를 우선 지원합니다.")
            return
        try:
            params = self._spcc_params()
        except ValueError:
            messagebox.showerror("오류", "SPCC Background Tolerance 숫자 값을 확인하세요.")
            return

        signature = self._spcc_signature()
        if bgtol_uses_siril_default(params["bgtol_lower"], params["bgtol_upper"]):
            self.write("\nSPCC Background Tol.: Siril 기본값(-2.8 / +2.0)을 사용합니다.\n")

        def work():
            return preview_spcc(self.project_dir, self.cfg, **params)

        def done(result):
            jpg, linear_preview, meta = result
            self.spcc_preview_signature = signature
            self.write(
                "\nSPCC 미리보기 완료\n"
                f"표시용 JPEG: {jpg}\n"
                f"Linear SPCC 미리보기 FITS: {linear_preview}\n"
                f"Plate Solve 명령: {meta['plate_solve_command']}\n"
                f"SPCC 명령: {meta['spcc_command']}\n"
            )
            self.status_var.set("SPCC 미리보기 완료")
            self._open_preview(jpg)

        self.run_bg(work, operation="Plate Solve + SPCC 미리보기", on_success=done)

    def spcc_apply(self):
        if not self._require_project():
            return
        if self.spcc_mode.get().upper() != "OSC":
            messagebox.showwarning("v0.6.0", "현재 GUI SPCC 적용은 OSC 경로를 우선 지원합니다.")
            return
        try:
            params = self._spcc_params()
        except ValueError:
            messagebox.showerror("오류", "SPCC Background Tolerance 숫자 값을 확인하세요.")
            return

        if self.spcc_preview_signature != self._spcc_signature():
            messagebox.showwarning(
                "미리보기 필요",
                "현재 SPCC 설정과 동일한 값으로 미리보기를 먼저 확인하세요."
            )
            return

        ok = messagebox.askyesno(
            "SPCC 실제 적용",
            "미리보기와 동일한 설정으로 실제 Linear FITS에 SPCC를 적용합니다.\n\n"
            f"Sensor: {params['sensor']}\n"
            f"OSC Filter: {params['osc_filter'] or '(없음)'}\n"
            f"White Reference: {params['white_reference']}\n"
            f"Catalog: {params['catalog']}\n"
            f"Background Tol: {params['bgtol_lower']} / {params['bgtol_upper']}\n\n"
            "진행할까요?"
        )
        if not ok:
            return

        def work():
            return apply_spcc(self.project_dir, self.cfg, confirmed=True, **params)

        def done(result):
            project, output, log = result
            self.spcc_preview_signature = None
            self._show_project_task(project, f"SPCC 완료\n출력: {output}")
            self.status_var.set("SPCC 완료")
            next_task = project["project"].get("next_task", {})
            self._show_apply_success("SPCC", output, next_task.get("title"))

        self.run_bg(work, operation="Plate Solve + SPCC 실제 적용", on_success=done)

    def _build_denoise_controls(self):
        self._clear_actions()

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))
        title = ttk.Label(head, text="Noise Reduction / Denoise", font=("", 10, "bold"))
        title.pack(side="left")
        self.help.tooltip(title, "denoise.what")
        ttk.Label(head, text="SPCC 완료 Linear 이미지의 노이즈 감소").pack(side="left", padx=(8,0))

        self.help.section_help_button(
            head,
            "Noise Reduction / Denoise 도움말",
            [
                "denoise.what",
                "denoise.modulation",
                "denoise.cosmetic",
                "denoise.da3d",
                "denoise.independent",
                "denoise.preview",
                "denoise.apply",
                "denoise.skip",
            ],
        ).pack(side="right")

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        def row_label(row, text, topic):
            label = ttk.Label(body, text=text, width=20)
            label.grid(row=row, column=0, sticky="w", pady=3, padx=(0,8))
            self.help.tooltip(label, topic)
            return label

        row_label(0, "Modulation", "denoise.modulation")
        ttk.Entry(body, textvariable=self.denoise_modulation, width=8).grid(row=0, column=1, sticky="w", pady=3)

        row_label(1, "Cosmetic Correction", "denoise.cosmetic")
        ttk.Checkbutton(body, variable=self.denoise_cosmetic).grid(row=1, column=1, sticky="w", pady=3)

        row_label(2, "DA3D", "denoise.da3d")
        ttk.Checkbutton(body, variable=self.denoise_da3d).grid(row=2, column=1, sticky="w", pady=3)

        row_label(3, "Independent RGB", "denoise.independent")
        ttk.Checkbutton(body, variable=self.denoise_independent).grid(row=3, column=1, sticky="w", pady=3)

        ttk.Label(
            body,
            text="※ 이미 스택된 이미지이므로 VST는 기본 UI에서 제외했습니다.",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(5,8))

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=2, sticky="w")
        ttk.Button(buttons, text="Denoise 미리보기", command=self.denoise_preview).pack(side="left", padx=(0,6))
        ttk.Button(buttons, text="승인 후 적용", command=self.denoise_apply).pack(side="left", padx=6)
        ttk.Button(buttons, text="Denoise 건너뛰기", command=self.denoise_skip).pack(side="left", padx=6)

    def _denoise_signature(self):
        return (
            self.denoise_modulation.get().strip(),
            bool(self.denoise_cosmetic.get()),
            bool(self.denoise_da3d.get()),
            bool(self.denoise_independent.get()),
        )

    def _invalidate_denoise_preview(self, *args):
        self.denoise_preview_signature = None

    def _denoise_params(self):
        return {
            "modulation": float(self.denoise_modulation.get()),
            "cosmetic_correction": bool(self.denoise_cosmetic.get()),
            "da3d": bool(self.denoise_da3d.get()),
            "independent_channels": bool(self.denoise_independent.get()),
        }

    def denoise_preview(self):
        if not self._require_project():
            return
        try:
            params = self._denoise_params()
        except ValueError:
            messagebox.showerror("오류", "Denoise Modulation 숫자 값을 확인하세요.")
            return

        signature = self._denoise_signature()

        def work():
            return preview_denoise(self.project_dir, self.cfg, **params)

        def done(result):
            jpg, linear_preview, meta = result
            self.denoise_preview_signature = signature
            self.write(
                "\nDenoise 미리보기 완료\n"
                f"표시용 JPEG: {jpg}\n"
                f"Linear Denoise 미리보기 FITS: {linear_preview}\n"
                f"명령: {meta['denoise_command']}\n"
            )
            self.status_var.set("Denoise 미리보기 완료")
            self._open_preview(jpg)

        self.run_bg(work, operation="Denoise 미리보기", on_success=done)

    def denoise_apply(self):
        if not self._require_project():
            return
        try:
            params = self._denoise_params()
        except ValueError:
            messagebox.showerror("오류", "Denoise Modulation 숫자 값을 확인하세요.")
            return

        if self.denoise_preview_signature != self._denoise_signature():
            messagebox.showwarning(
                "미리보기 필요",
                "현재 Denoise 설정과 동일한 값으로 미리보기를 먼저 확인하세요."
            )
            return

        ok = messagebox.askyesno(
            "Denoise 실제 적용",
            "미리보기와 동일한 설정으로 실제 Linear FITS에 Denoise를 적용합니다.\n\n"
            f"Modulation: {params['modulation']}\n"
            f"Cosmetic Correction: {params['cosmetic_correction']}\n"
            f"DA3D: {params['da3d']}\n"
            f"Independent RGB: {params['independent_channels']}\n\n"
            "진행할까요?"
        )
        if not ok:
            return

        def work():
            return apply_denoise(self.project_dir, self.cfg, confirmed=True, **params)

        def done(result):
            project, output, log = result
            self.denoise_preview_signature = None
            self._show_project_task(project, f"Denoise 완료\n출력: {output}")
            self.status_var.set("Denoise 완료")
            next_task = project["project"].get("next_task", {})
            self._show_apply_success("Denoise", output, next_task.get("title"))

        self.run_bg(work, operation="Denoise 실제 적용", on_success=done)

    def denoise_skip(self):
        if not self._require_project():
            return
        ok = messagebox.askyesno(
            "Denoise 건너뛰기",
            "Siril Denoise를 적용하지 않고 다음 처리 준비로 이동할까요?"
        )
        if not ok:
            return
        try:
            project = skip_denoise(self.project_dir)
            self._show_project_task(project, "Denoise 건너뜀")
            self.status_var.set("Denoise 건너뜀")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _gradient_signature(self):
        return (
            self.gradient_samples.get().strip(),
            self.gradient_tolerance.get().strip(),
            self.gradient_smooth.get().strip(),
            bool(self.gradient_dither.get()),
        )

    def _invalidate_gradient_preview(self, *args):
        self.gradient_preview_signature = None

    def _require_project(self):
        if not self.project_dir:
            messagebox.showwarning("확인", "먼저 프로젝트를 생성하거나 열어주세요.")
            return False
        return True

    def _show_project_task(self, project, prefix="처리 완료"):
        p = project["project"]
        task = p.get("next_task")
        text = (
            f"\n{prefix}\n"
            f"State: {p.get('current_state')}\n"
            f"현재 파일: {p.get('current_file')}\n"
        )
        if task:
            text += "\n" + format_task(task)
        self.write(text)
        self.render_task(task)

    def confirm_stage(self, stage):
        if not self._require_project():
            return
        try:
            project = confirm_input_stage(self.project_dir, stage)
            self._show_project_task(project, f"입력 단계 확정: {stage}")
            self.status_var.set(stage)
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def confirm_linear(self, value):
        if not self._require_project():
            return
        try:
            project = confirm_linearity(self.project_dir, value)
            self._show_project_task(project, f"Linearity 확정: {value}")
            self.status_var.set(value)
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def confirm_calibration(self, value):
        if not self._require_project():
            return
        try:
            project = confirm_calibration_status(self.project_dir, value)
            self._show_project_task(project, f"Calibration 상태 확정: {value}")
            self.status_var.set(value)
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def confirm_trail(self, value):
        if not self._require_project():
            return
        try:
            project = confirm_star_trail_mode(self.project_dir, value)
            self._show_project_task(project, f"별 일주 모드 확정: {value}")
            self.status_var.set(value)
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _gradient_values(self):
        return (
            int(self.gradient_samples.get()),
            float(self.gradient_tolerance.get()),
            float(self.gradient_smooth.get()),
            bool(self.gradient_dither.get()),
        )

    def gradient_preview(self):
        if not self._require_project():
            return
        try:
            samples, tolerance, smooth, dither = self._gradient_values()
        except ValueError:
            messagebox.showerror("오류", "Gradient 숫자 값을 확인하세요.")
            return

        signature = self._gradient_signature()

        def work():
            return preview_gradient(
                self.project_dir, self.cfg,
                samples=samples, tolerance=tolerance,
                smooth=smooth, dither=dither,
            )

        def done(result):
            jpg, linear_preview, meta = result
            self.gradient_preview_signature = signature
            self.write(
                "\nGradient 미리보기 생성 완료\n"
                f"표시용 JPEG: {jpg}\n"
                f"Linear 미리보기 FITS: {linear_preview}\n"
                "※ JPEG에는 확인용 AutoStretch가 적용되어 있으며 실제 FITS는 Linear입니다.\n"
            )
            self.status_var.set("Gradient 미리보기 완료")
            self._open_preview(jpg)

        self.run_bg(work, operation="Gradient 미리보기", on_success=done)

    def _open_preview(self, path: Path):
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(path))
            else:
                messagebox.showinfo("미리보기", f"미리보기 파일:\n{path}")
        except Exception:
            messagebox.showinfo("미리보기", f"미리보기 파일:\n{path}")

    def gradient_apply(self):
        if not self._require_project():
            return
        try:
            samples, tolerance, smooth, dither = self._gradient_values()
        except ValueError:
            messagebox.showerror("오류", "Gradient 숫자 값을 확인하세요.")
            return

        if self.gradient_preview_signature != self._gradient_signature():
            messagebox.showwarning(
                "미리보기 필요",
                "현재 파라미터로 미리보기를 먼저 확인해야 실제 적용할 수 있습니다."
            )
            return

        ok = messagebox.askyesno(
            "Gradient 적용",
            "미리보기와 동일한 값으로 실제 Linear FITS에 Gradient Correction을 적용합니다.\n\n"
            f"Samples={samples}\nTolerance={tolerance}\nSmooth={smooth}\nDither={dither}\n\n"
            "진행할까요?"
        )
        if not ok:
            return

        def work():
            return apply_gradient(
                self.project_dir, self.cfg,
                samples=samples, tolerance=tolerance,
                smooth=smooth, dither=dither,
                confirmed=True,
            )

        def done(result):
            project, output, log = result
            self.gradient_preview_signature = None
            self._show_project_task(project, f"Gradient Correction 완료\n출력: {output}")
            self.status_var.set("Gradient Correction 완료")
            next_task = project["project"].get("next_task", {})
            self._show_apply_success("Gradient Correction", output, next_task.get("title"))

        self.run_bg(work, operation="Gradient Correction 실제 적용", on_success=done)

if __name__ == "__main__":
    App().mainloop()
