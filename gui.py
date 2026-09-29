from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import date
import threading

from astroauto.config import load_app_config
from astroauto.project import create_project
from astroauto.analyzer import analyze_project
from astroauto.siril import get_siril_info
from astroauto.workflow import format_task

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
    ("모름/자동판단 대기", "UNKNOWN"),
]
LABEL_TO_ID = dict(CATEGORIES)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AstroSirilAssistant v0.3.1")
        self.geometry("900x700")
        self.cfg = load_app_config()

        self.input_var = tk.StringVar()
        self.target_var = tk.StringVar(value="M31")
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.category_var = tk.StringVar(value="은하")
        self.root_var = tk.StringVar(value=self.cfg["app"]["project_root"])
        self.status_var = tk.StringVar(value="대기 중")

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
        combo = ttk.Combobox(frm, textvariable=self.category_var, state="readonly",
                             values=[x[0] for x in CATEGORIES])
        combo.grid(row=3, column=1, sticky="ew")

        ttk.Label(frm, text="프로젝트 루트").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.root_var).grid(row=4, column=1, sticky="ew")
        ttk.Button(frm, text="폴더", command=self.pick_root).grid(row=4, column=2, padx=5)

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Button(btns, text="Siril 연결 확인", command=self.doctor).pack(side="left", padx=4)
        ttk.Button(btns, text="프로젝트 생성 + 분석", command=self.create_and_analyze).pack(side="left", padx=4)

        ttk.Label(frm, textvariable=self.status_var).grid(row=6, column=0, columnspan=3, sticky="w")

        self.output = tk.Text(frm, wrap="word", height=30)
        self.output.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(8,0))

        scrollbar = ttk.Scrollbar(frm, command=self.output.yview)
        scrollbar.grid(row=7, column=3, sticky="ns")
        self.output.configure(yscrollcommand=scrollbar.set)

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(7, weight=1)

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

    def write(self, text):
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
            self.after(0, lambda: self.write(f"Siril 연결 OK\n경로: {info.executable}\n버전: {info.version}\n"))
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
        self.output.delete("1.0", "end")

        def work():
            pdir = create_project(
                root=root, target=target, capture_date=capture_date,
                category=category, input_file=Path(input_path), copy_input=True
            )
            project, report, task = analyze_project(pdir, self.cfg)
            text = (
                f"프로젝트 생성 완료\n{pdir}\n캘리브레이션 폴더: {pdir / 'calibration'}\n\n"
                f"Siril: {report['siril']['version']}\n"
                f"이미지 shape: {report['pixel_statistics']['shape']}\n"
                f"Linear 판정: {report['linearity_assessment']['status']}\n"
                f"판정 이유: {report['linearity_assessment']['reason']}\n\n"
                + format_task(task)
                + f"\n\n상세 분석 로그:\n{pdir / 'logs' / 'analysis_report.json'}"
            )
            self.after(0, lambda: self.write(text))
            self.after(0, lambda: self.status_var.set("분석 완료"))

        self.run_bg(work)

if __name__ == "__main__":
    App().mainloop()
