from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import date
import threading

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
        self.title("AstroSirilAssistant v0.4.2")
        self.geometry("1050x820")
        self.minsize(880, 650)
        self.cfg = load_app_config()
        self.project_dir: Path | None = None

        self.input_var = tk.StringVar()
        self.target_var = tk.StringVar(value="M31")
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.category_var = tk.StringVar(value="은하")
        self.root_var = tk.StringVar(value=self.cfg["app"]["project_root"])
        self.status_var = tk.StringVar(value="대기 중")

        self.gradient_samples = tk.StringVar(value="20")
        self.gradient_tolerance = tk.StringVar(value="1.0")
        self.gradient_smooth = tk.StringVar(value="0.5")
        self.gradient_dither = tk.BooleanVar(value=False)
        self.gradient_preview_signature = None

        for var in (self.gradient_samples, self.gradient_tolerance, self.gradient_smooth):
            var.trace_add("write", self._invalidate_gradient_preview)
        self.gradient_dither.trace_add("write", self._invalidate_gradient_preview)

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

        self.output = tk.Text(frm, wrap="word", height=25)
        self.output.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(4,0))

        scrollbar = ttk.Scrollbar(frm, command=self.output.yview)
        scrollbar.grid(row=8, column=3, sticky="ns")
        self.output.configure(yscrollcommand=scrollbar.set)

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(8, weight=1)

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

    def run_bg(self, func):
        def runner():
            try:
                func()
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("오류", str(e)))
                self.after(0, lambda: self.status_var.set("오류"))
        threading.Thread(target=runner, daemon=True).start()

    def doctor(self):
        self.status_var.set("Siril 확인 중...")
        def work():
            info = get_siril_info(self.cfg)
            self.after(0, lambda: self.write(
                f"Siril 연결 OK\n경로: {info.executable}\n버전: {info.version}\n"
            ))
            self.after(0, lambda: self.status_var.set("Siril 연결 OK"))
        self.run_bg(work)

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

        self.run_bg(work)

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

        else:
            ttk.Label(
                controls,
                text="이 단계의 실제 실행 UI는 이후 구현 단계에서 연결됩니다."
            ).pack(side="left", padx=3)

    def _build_gradient_controls(self, parent):
        ttk.Label(parent, text="Samples").pack(side="left", padx=(0,2))
        ttk.Entry(parent, textvariable=self.gradient_samples, width=5).pack(side="left", padx=(0,8))

        ttk.Label(parent, text="Tolerance").pack(side="left", padx=(0,2))
        ttk.Entry(parent, textvariable=self.gradient_tolerance, width=6).pack(side="left", padx=(0,8))

        ttk.Label(parent, text="Smooth").pack(side="left", padx=(0,2))
        ttk.Entry(parent, textvariable=self.gradient_smooth, width=6).pack(side="left", padx=(0,8))

        ttk.Checkbutton(parent, text="Dither", variable=self.gradient_dither).pack(side="left", padx=(0,8))

        ttk.Button(parent, text="미리보기", command=self.gradient_preview).pack(side="left", padx=3)
        ttk.Button(parent, text="승인 후 적용", command=self.gradient_apply).pack(side="left", padx=3)

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

        self.status_var.set("Gradient 미리보기 생성 중...")
        signature = self._gradient_signature()

        def work():
            jpg, linear_preview, meta = preview_gradient(
                self.project_dir, self.cfg,
                samples=samples, tolerance=tolerance,
                smooth=smooth, dither=dither,
            )
            self.gradient_preview_signature = signature
            self.after(0, lambda: self.write(
                "\nGradient 미리보기 생성 완료\n"
                f"표시용 JPEG: {jpg}\n"
                f"Linear 미리보기 FITS: {linear_preview}\n"
                "※ JPEG에는 확인용 AutoStretch가 적용되어 있으며 실제 FITS는 Linear입니다.\n"
            ))
            self.after(0, lambda: self.status_var.set("Gradient 미리보기 완료"))
            self.after(0, lambda: self._open_preview(jpg))

        self.run_bg(work)

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

        self.status_var.set("Gradient Correction 실행 중...")

        def work():
            project, output, log = apply_gradient(
                self.project_dir, self.cfg,
                samples=samples, tolerance=tolerance,
                smooth=smooth, dither=dither,
                confirmed=True,
            )
            self.gradient_preview_signature = None
            self.after(0, lambda: self._show_project_task(
                project,
                f"Gradient Correction 완료\n출력: {output}"
            ))
            self.after(0, lambda: self.status_var.set("Gradient Correction 완료"))

        self.run_bg(work)

if __name__ == "__main__":
    App().mainloop()
