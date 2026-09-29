from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import date
import threading

from astroauto.config import load_app_config
from astroauto.sequence_project import create_sequence_project
from astroauto.preprocess_engine import build_preprocess_plan, execute_preprocess
from astroauto.siril import get_siril_info

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
        self.title("AstroSirilAssistant v0.4 - Deep Sky Sequence")
        self.geometry("980x790")
        self.cfg = load_app_config()
        self.project_dir = None

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
        self._build()

    def _build(self):
        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)

        rows = [
            ("Lights 폴더", "lights"),
            ("Dark 폴더", "darks"),
            ("Flat 폴더", "flats"),
            ("Bias 폴더", "bias"),
            ("Dark-flat 폴더", "dark_flats"),
        ]
        for i, (label, key) in enumerate(rows):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(f, textvariable=self.paths[key], width=72).grid(row=i, column=1, sticky="ew")
            ttk.Button(f, text="선택", command=lambda k=key: self.pick(k)).grid(row=i, column=2, padx=4)

        r = 5
        ttk.Label(f, text="대상명").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.target).grid(row=r, column=1, sticky="ew")
        r += 1
        ttk.Label(f, text="촬영일").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.capture_date).grid(row=r, column=1, sticky="ew")
        r += 1
        ttk.Label(f, text="대상 종류").grid(row=r, column=0, sticky="w")
        ttk.Combobox(f, textvariable=self.category, state="readonly",
                     values=[x[0] for x in CATEGORIES]).grid(row=r, column=1, sticky="ew")
        r += 1
        ttk.Label(f, text="카메라").grid(row=r, column=0, sticky="w")
        ttk.Combobox(f, textvariable=self.camera_mode, state="readonly",
                     values=["AUTO", "OSC", "MONO"]).grid(row=r, column=1, sticky="ew")
        r += 1
        ttk.Label(f, text="입력 Calibration 상태").grid(row=r, column=0, sticky="w")
        ttk.Combobox(f, textvariable=self.input_status, state="readonly",
                     values=["RAW_UNCALIBRATED", "PRECALIBRATED"]).grid(row=r, column=1, sticky="ew")
        r += 1
        ttk.Label(f, text="프로젝트 루트").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.project_root).grid(row=r, column=1, sticky="ew")
        ttk.Button(f, text="선택", command=self.pick_root).grid(row=r, column=2, padx=4)
        r += 1

        ttk.Checkbutton(
            f,
            text="원본을 프로젝트로 복사 (용량이 매우 커질 수 있음)",
            variable=self.copy_inputs,
        ).grid(row=r, column=1, sticky="w", pady=4)
        r += 1

        b = ttk.Frame(f)
        b.grid(row=r, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Button(b, text="Siril 확인", command=self.doctor).pack(side="left", padx=3)
        ttk.Button(b, text="1. 프로젝트 생성", command=self.create_project).pack(side="left", padx=3)
        ttk.Button(b, text="2. 실행 계획 보기", command=self.show_plan).pack(side="left", padx=3)
        ttk.Button(b, text="3. 승인 후 실제 실행", command=self.run_real).pack(side="left", padx=3)
        r += 1

        ttk.Label(f, textvariable=self.status).grid(row=r, column=0, columnspan=3, sticky="w")
        r += 1

        self.out = tk.Text(f, wrap="word", height=26)
        self.out.grid(row=r, column=0, columnspan=3, sticky="nsew", pady=(6,0))
        f.columnconfigure(1, weight=1)
        f.rowconfigure(r, weight=1)

    def pick(self, key):
        path = filedialog.askdirectory()
        if path:
            self.paths[key].set(path)

    def pick_root(self):
        path = filedialog.askdirectory()
        if path:
            self.project_root.set(path)

    def write(self, msg):
        self.out.insert("end", msg + "\n")
        self.out.see("end")

    def bg(self, fn):
        def worker():
            try:
                fn()
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("오류", str(e)))
                self.after(0, lambda: self.status.set("오류"))
        threading.Thread(target=worker, daemon=True).start()

    def doctor(self):
        self.status.set("Siril 확인 중...")
        def work():
            info = get_siril_info(self.cfg)
            self.after(0, lambda: self.write(f"Siril 연결 OK\n{info.executable}\nVersion: {info.version}\n"))
            self.after(0, lambda: self.status.set("Siril 연결 OK"))
        self.bg(work)

    def create_project(self):
        if not self.paths["lights"].get():
            messagebox.showwarning("확인", "Lights 폴더를 선택하세요.")
            return
        self.status.set("프로젝트 생성 중...")
        def work():
            pdir = create_sequence_project(
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
            self.project_dir = pdir
            self.after(0, lambda: self.write(f"프로젝트 생성 완료:\n{pdir}\n"))
            self.after(0, lambda: self.status.set("프로젝트 생성 완료"))
        self.bg(work)

    def show_plan(self):
        if not self.project_dir:
            messagebox.showwarning("확인", "먼저 프로젝트를 생성하세요.")
            return
        self.status.set("계획 생성 중...")
        def work():
            plan, plan_path, script_path = build_preprocess_plan(self.project_dir)
            text = [
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
            text += [f"- {x}" for x in plan["phases"]]
            if plan["warnings"]:
                text += ["", "주의:"] + [f"- {x}" for x in plan["warnings"]]
            text += ["", f"Plan: {plan_path}", f"Script: {script_path}"]
            self.after(0, lambda: self.write("\n".join(text) + "\n"))
            self.after(0, lambda: self.status.set("실행 계획 준비 완료"))
        self.bg(work)

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
        self.status.set("Siril 실제 처리 중...")
        def work():
            project, output, plan = execute_preprocess(self.project_dir, self.cfg, confirmed=True)
            self.after(0, lambda: self.write(
                f"\n처리 완료!\n출력: {output}\n다음 작업: Background / Gradient Correction\n"
            ))
            self.after(0, lambda: self.status.set("Stack 완료"))
        self.bg(work)

if __name__ == "__main__":
    SequenceApp().mainloop()
