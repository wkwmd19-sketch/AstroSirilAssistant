from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import date
import threading
import time

from astroauto.config import load_app_config
from astroauto.ui_theme import apply_astro_theme, apply_screen_aware_geometry, style_text_widget, style_canvas
from astroauto.syqon import detect_syqon
from astroauto.project import (
    create_project, load_project, project_name, next_available_project_dir,
    find_existing_project_dir,
)
from astroauto.analyzer import analyze_project, confirm_linearity
from astroauto.siril import get_siril_info
from astroauto.execution import TaskControl, ExecutionCancelled, execution_context
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
from astroauto.deblur import (
    make_deblur_task, migrate_post_denoise_task,
    preview_deblur, apply_deblur, promote_deblur_preview, skip_deblur,
)
from astroauto.ghs import (
    migrate_ready_for_ghs,
    preview_ghs, apply_ghs,
    begin_additional_ghs, finish_ghs,
)
from astroauto.star_separation import (
    migrate_ready_for_starnet,
    preview_star_separation, apply_star_separation,
    skip_star_separation,
)
from astroauto.starless_processing import (
    migrate_ready_for_starless,
    preview_starless_processing, apply_starless_processing,
    skip_starless_processing,
)
from astroauto.recommendations import (
    enrich_target_characteristics, recommend_starless, recommend_stars,
    update_target_characteristics, feature_labels,
)
from astroauto.stars_processing import (
    migrate_ready_for_stars,
    preview_stars_processing, apply_stars_processing,
    skip_stars_processing,
)
from astroauto.recombine import (
    migrate_ready_for_recombine,
    preview_recombine, apply_recombine,
    recommend_recombine,
)
from astroauto.final_export import (
    migrate_ready_for_final_export,
    preview_final_export, apply_final_export,
    final_basename,
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

STAGE_FLOW_INFO = {
    "CONFIRM_INPUT_STAGE": (
        "입력 FITS가 스택 결과인지 개별 Light인지 확인해 안전한 처리 시작점을 정하는 단계입니다.",
        "Linearity 확인",
    ),
    "CONFIRM_LINEARITY": (
        "이미지가 아직 Linear 상태인지 확인해 중복 Stretch 같은 잘못된 처리를 방지하는 단계입니다.",
        "Calibration 상태 확인",
    ),
    "CONFIRM_CALIBRATION_STATUS": (
        "입력 이미지의 캘리브레이션 여부를 확인해 필요한 전처리 경로를 결정하는 단계입니다.",
        "Background / Gradient Correction",
    ),
    "CONFIRM_STAR_TRAIL_MODE": (
        "별 일주사진의 하늘 중심 또는 지상 풍경 포함 처리 경로를 선택하는 단계입니다.",
        "Star Trail Workflow",
    ),
    "GRADIENT_CORRECTION": (
        "배경의 밝기와 색 불균형을 정리해 이후 보정이 안정적으로 진행되도록 준비하는 단계입니다.",
        "SPCC Color Calibration",
    ),
    "COLOR_CALIBRATION_SPCC": (
        "별과 천체 정보를 기준으로 전체 이미지의 색 균형을 맞추는 단계입니다.",
        "Restoration / Deblur",
    ),
    "DEBLUR": (
        "별 형태와 수차를 보정하고 미세 구조를 복원해 디테일을 살리는 단계입니다.",
        "Prism Noise Reduction",
    ),
    "DENOISE": (
        "미세 구조를 최대한 유지하면서 배경과 색 노이즈를 줄이는 단계입니다.",
        "GHS Stretch",
    ),
    "GHS_STRETCH": (
        "희미한 천체 신호를 보존하면서 Linear 이미지를 눈에 보이는 밝기로 펼치는 단계입니다.",
        "StarNet",
    ),
    "GHS_REVIEW": (
        "Stretch 결과를 확인하고 필요하면 작은 추가 Stretch를 적용하는 단계입니다.",
        "StarNet",
    ),
    "STAR_SEPARATION": (
        "별과 천체 본체를 분리해 각각 독립적으로 보정할 수 있도록 만드는 단계입니다.",
        "Starless Processing",
    ),
    "STARLESS_PROCESS": (
        "별이 제거된 천체 본체의 구조와 대비, 색을 다듬는 단계입니다.",
        "Stars Processing",
    ),
    "STARS_PROCESS": (
        "별의 밝기와 색을 조절해 천체 본체와 자연스럽게 어울리도록 만드는 단계입니다.",
        "Pixel Math Recombine",
    ),
    "PIXEL_MATH_RECOMBINE": (
        "보정한 천체 본체와 별 레이어를 다시 합쳐 최종 이미지의 균형을 맞추는 단계입니다.",
        "Final / Export",
    ),
    "FINALIZE_EXPORT": (
        "최종 이미지를 확인하고 FITS, TIFF, PNG 결과물로 안전하게 저장하는 단계입니다.",
        "기본 파이프라인 완료",
    ),
    "PIPELINE_COMPLETE": (
        "한 장의 스택 천체사진에 대한 반자동 보정과 최종 출력이 완료되었습니다.",
        "완료",
    ),
}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AstroSirilAssistant v0.14.7")
        self._apply_screen_aware_geometry()
        self.cfg = load_app_config()
        self.palette = apply_astro_theme(self)
        self.ui_defaults = load_yaml(PACKAGE_ROOT / "config" / "ui_defaults.yaml")
        self.help = HelpSystem(self)
        self.project_dir: Path | None = None

        self.input_var = tk.StringVar()
        self.target_var = tk.StringVar(value="M31")
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.category_var = tk.StringVar(value="은하")
        self.root_var = tk.StringVar(value=self.cfg["app"]["project_root"])
        self.status_var = tk.StringVar(value="대기 중")
        self.current_stage_var = tk.StringVar(value="현재 단계 : 프로젝트를 생성하거나 열어주세요.")
        self.next_stage_var = tk.StringVar(value="다음 작업 : —")

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
        dn = dd.get("native", {})
        dp = dd.get("prism", {})
        self.denoise_engine = tk.StringVar(value=dd.get("engine", "SYQON_PRISM"))

        # SyQon Prism
        self.prism_model = tk.StringVar(value=str(dp.get("model", "mini")))
        self.prism_tile = tk.StringVar(value=str(dp.get("tile_size", 512)))
        self.prism_overlap = tk.StringVar(value=str(dp.get("overlap", 96)))
        self.prism_pad = tk.StringVar(value=str(dp.get("pad", 96)))
        self.prism_modulation = tk.StringVar(value=str(dp.get("modulation", 1.0)))
        self.prism_use_gpu = tk.BooleanVar(value=bool(dp.get("use_gpu", True)))
        self.prism_stretch_method = tk.StringVar(value=str(dp.get("stretch_method", "statistical")))
        self.prism_stretch_target = tk.StringVar(value=str(dp.get("stretch_target", 0.25)))

        # Siril Native fallback
        self.denoise_modulation = tk.StringVar(value=str(dn.get("modulation", 1.0)))
        self.denoise_cosmetic = tk.BooleanVar(value=bool(dn.get("cosmetic_correction", True)))
        self.denoise_da3d = tk.BooleanVar(value=bool(dn.get("da3d", False)))
        self.denoise_independent = tk.BooleanVar(value=bool(dn.get("independent_channels", False)))
        self.denoise_preview_signature = None

        for var in (
            self.denoise_engine,
            self.prism_model, self.prism_tile, self.prism_overlap,
            self.prism_pad, self.prism_modulation, self.prism_use_gpu,
            self.prism_stretch_method, self.prism_stretch_target,
            self.denoise_modulation, self.denoise_cosmetic,
            self.denoise_da3d, self.denoise_independent,
        ):
            var.trace_add("write", self._invalidate_denoise_preview)

        bd = self.ui_defaults.get("deblur", {})
        bn = bd.get("native", {})
        bp = bd.get("parallax", {})
        self.deblur_engine = tk.StringVar(value=bd.get("engine", "SYQON_PARALLAX"))

        # SyQon Parallax
        self.parallax_edition = tk.StringVar(value=str(bp.get("edition", "nano")))
        self.parallax_correct = tk.BooleanVar(value=bool(bp.get("correct", True)))
        self.parallax_star_level = tk.StringVar(value=str(bp.get("star_level", 3.0)))
        self.parallax_sharpen = tk.StringVar(value=str(bp.get("sharpen", 1.0)))
        self.parallax_tile = tk.StringVar(value=str(bp.get("tile", 512)))
        self.parallax_overlap = tk.StringVar(value=str(bp.get("overlap", 64)))
        self.parallax_pad = tk.StringVar(value=str(bp.get("pad", 96)))
        self.parallax_use_mtf = tk.BooleanVar(value=bool(bp.get("use_mtf", True)))
        self.parallax_mtf_target = tk.StringVar(value=str(bp.get("mtf_target", 0.25)))
        self.parallax_linked = tk.BooleanVar(value=bool(bp.get("linked", False)))
        self.parallax_use_gpu = tk.BooleanVar(value=bool(bp.get("use_gpu", True)))

        # Siril RL fallback
        self.deblur_symmetric = tk.BooleanVar(value=bool(bn.get("symmetric_psf", False)))
        self.deblur_kernel = tk.StringVar(
            value="" if bn.get("kernel_size") in (None, "") else str(bn.get("kernel_size"))
        )
        self.deblur_iterations = tk.StringVar(value=str(bn.get("iterations", 10)))
        self.deblur_regularization = tk.StringVar(value=str(bn.get("regularization", "NONE")))
        self.deblur_alpha = tk.StringVar(value=str(bn.get("alpha", 3000)))
        self.deblur_multiplicative = tk.BooleanVar(value=bool(bn.get("multiplicative", False)))
        self.deblur_preview_signature = None
        self.deblur_preview_mode = None
        self.deblur_full_candidate = None
        self.deblur_full_preview_meta = None

        for var in (
            self.deblur_engine,
            self.parallax_edition, self.parallax_correct, self.parallax_star_level,
            self.parallax_sharpen, self.parallax_tile, self.parallax_overlap,
            self.parallax_pad, self.parallax_use_mtf, self.parallax_mtf_target,
            self.parallax_linked, self.parallax_use_gpu,
            self.deblur_symmetric, self.deblur_kernel,
            self.deblur_iterations, self.deblur_regularization,
            self.deblur_alpha, self.deblur_multiplicative,
        ):
            var.trace_add("write", self._invalidate_deblur_preview)

        gs = self.ui_defaults.get("ghs", {})
        ga = gs.get("auto", {})
        gm = gs.get("manual", {})
        self.ghs_method = tk.StringVar(value=gs.get("method", "AUTO_GHS"))

        self.ghs_auto_linked = tk.BooleanVar(value=bool(ga.get("linked", True)))
        self.ghs_auto_shadows = tk.StringVar(value=str(ga.get("shadows_clip", -2.8)))
        self.ghs_auto_d = tk.StringVar(value=str(ga.get("stretch_amount", 1.0)))
        self.ghs_auto_b = tk.StringVar(value=str(ga.get("b", 13.0)))
        self.ghs_auto_lp = tk.StringVar(value=str(ga.get("lp", 0.0)))
        self.ghs_auto_hp = tk.StringVar(value=str(ga.get("hp", 0.7)))
        self.ghs_auto_clip = tk.StringVar(value=str(ga.get("clip_mode", "rgbblend")))

        self.ghs_manual_d = tk.StringVar(value=str(gm.get("d", 1.0)))
        self.ghs_manual_b = tk.StringVar(value=str(gm.get("b", 0.0)))
        self.ghs_manual_lp = tk.StringVar(value=str(gm.get("lp", 0.0)))
        self.ghs_manual_sp = tk.StringVar(value=str(gm.get("sp", 0.0)))
        self.ghs_manual_hp = tk.StringVar(value=str(gm.get("hp", 1.0)))
        self.ghs_manual_lum = tk.StringVar(value=str(gm.get("luminance_mode", "HUMAN")))
        self.ghs_manual_clip = tk.StringVar(value=str(gm.get("clip_mode", "rgbblend")))

        self.ghs_preview_signature = None
        for var in (
            self.ghs_method,
            self.ghs_auto_linked, self.ghs_auto_shadows, self.ghs_auto_d,
            self.ghs_auto_b, self.ghs_auto_lp, self.ghs_auto_hp, self.ghs_auto_clip,
            self.ghs_manual_d, self.ghs_manual_b, self.ghs_manual_lp,
            self.ghs_manual_sp, self.ghs_manual_hp, self.ghs_manual_lum,
            self.ghs_manual_clip,
        ):
            var.trace_add("write", self._invalidate_ghs_preview)

        sn = self.ui_defaults.get("starnet", {})
        self.starnet_stride_preset = tk.StringVar(value=str(sn.get("stride_preset", "STANDARD")))
        self.starnet_custom_stride = tk.StringVar(value=str(sn.get("stride", 256)))
        self.starnet_upsample = tk.BooleanVar(value=bool(sn.get("upsample", False)))
        self.starnet_protect_highlights = tk.BooleanVar(value=bool(sn.get("protect_highlights", True)))
        self.starnet_native_mask = tk.BooleanVar(value=bool(sn.get("save_native_starmask", False)))
        self.starnet_preview_signature = None
        self.starnet_preview_meta = None
        self.starnet_preview_starless_jpg = None
        self.starnet_preview_stars_jpg = None
        self.starnet_starless_view_btn = None
        self.starnet_stars_view_btn = None

        for var in (
            self.starnet_stride_preset, self.starnet_custom_stride,
            self.starnet_upsample, self.starnet_protect_highlights,
            self.starnet_native_mask,
        ):
            var.trace_add("write", self._invalidate_starnet_preview)

        sl = self.ui_defaults.get("starless_processing", {})
        self.starless_clahe_enabled = tk.BooleanVar(value=bool(sl.get("clahe_enabled", True)))
        self.starless_clahe_clip = tk.StringVar(value=str(sl.get("clahe_clip_limit", 1.5)))
        self.starless_tile = tk.StringVar(value=str(sl.get("clahe_tile_size", 12)))
        self.starless_sat_enabled = tk.BooleanVar(value=bool(sl.get("saturation_enabled", True)))
        self.starless_sat_amount = tk.StringVar(value=str(sl.get("saturation_amount", 0.10)))
        self.starless_sat_bg = tk.StringVar(value=str(sl.get("saturation_background_factor", 1.10)))
        self.starless_sat_hue = tk.StringVar(value=str(sl.get("saturation_hue_range", 6)))
        self.starless_preview_signature = None
        self.starless_recommendation = None
        self.starless_recommendation_var = tk.StringVar(value="추천값을 계산하지 않았습니다.")

        for var in (
            self.starless_clahe_enabled, self.starless_clahe_clip, self.starless_tile,
            self.starless_sat_enabled, self.starless_sat_amount,
            self.starless_sat_bg, self.starless_sat_hue,
        ):
            var.trace_add("write", self._invalidate_starless_preview)

        st = self.ui_defaults.get("stars_processing", {})
        self.stars_brightness = tk.StringVar(value=str(st.get("brightness_scale", 0.70)))
        self.stars_sat_enabled = tk.BooleanVar(value=bool(st.get("saturation_enabled", True)))
        self.stars_sat_amount = tk.StringVar(value=str(st.get("saturation_amount", 0.08)))
        self.stars_sat_bg = tk.StringVar(value=str(st.get("saturation_background_factor", 0.0)))
        self.stars_sat_hue = tk.StringVar(value=str(st.get("saturation_hue_range", 6)))
        self.stars_preview_signature = None
        self.stars_recommendation = None
        self.stars_recommendation_var = tk.StringVar(value="추천값을 계산하지 않았습니다.")

        for var in (
            self.stars_brightness, self.stars_sat_enabled,
            self.stars_sat_amount, self.stars_sat_bg, self.stars_sat_hue,
        ):
            var.trace_add("write", self._invalidate_stars_preview)

        rc = self.ui_defaults.get("recombine", {})
        self.recombine_star_weight = tk.StringVar(value=str(rc.get("star_weight", 1.0)))
        self.recombine_rescale = tk.BooleanVar(value=bool(rc.get("rescale_output", False)))
        self.recombine_preview_signature = None
        self.recombine_preview_meta = None
        self.recombine_recommendation = None
        self.recombine_recommendation_var = tk.StringVar(value="추천값을 계산하지 않았습니다.")

        for var in (
            self.recombine_star_weight,
            self.recombine_rescale,
        ):
            var.trace_add("write", self._invalidate_recombine_preview)

        fe = self.ui_defaults.get("final_export", {})
        self.final_export_fits = tk.BooleanVar(value=bool(fe.get("export_fits", True)))
        self.final_export_tiff = tk.BooleanVar(value=bool(fe.get("export_tiff16", True)))
        self.final_export_png = tk.BooleanVar(value=bool(fe.get("export_png16", True)))
        self.final_tiff_deflate = tk.BooleanVar(value=bool(fe.get("tiff_deflate", True)))
        self.final_fits_checksum = tk.BooleanVar(value=bool(fe.get("fits_checksum", True)))
        self.final_preview_quality = tk.StringVar(value=str(fe.get("preview_jpeg_quality", 95)))
        self.final_preview_meta = None
        self.final_preview_source = None

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
        self._long_running_notice_sent = False

        self._build()

    def _apply_screen_aware_geometry(self):
        apply_screen_aware_geometry(self)

    def _build(self):
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)

        self.main_pane = ttk.Panedwindow(shell, orient=tk.VERTICAL)
        self.main_pane.pack(fill="both", expand=True)

        self.workspace_holder = ttk.Frame(self.main_pane)
        self.main_pane.add(self.workspace_holder, weight=5)
        self.workspace_holder.rowconfigure(0, weight=1)
        self.workspace_holder.columnconfigure(0, weight=1)

        self.workspace_canvas = tk.Canvas(
            self.workspace_holder,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=24,
        )
        style_canvas(self.workspace_canvas, self.palette)

        self.workspace_scrollbar = ttk.Scrollbar(
            self.workspace_holder,
            orient="vertical",
            command=self.workspace_canvas.yview,
        )
        self.workspace_canvas.configure(yscrollcommand=self.workspace_scrollbar.set)
        self.workspace_canvas.grid(row=0, column=0, sticky="nsew")
        self.workspace_scrollbar.grid(row=0, column=1, sticky="ns")

        frm = ttk.Frame(self.workspace_canvas, padding=20)
        self.workspace_inner = frm
        self.workspace_window_id = self.workspace_canvas.create_window(
            (0, 0), window=frm, anchor="nw"
        )

        frm.bind("<Configure>", self._on_workspace_inner_configure)
        self.workspace_canvas.bind("<Configure>", self._on_workspace_canvas_configure)

        self.bind_all("<MouseWheel>", self._on_workspace_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_workspace_linux_wheel, add="+")
        self.bind_all("<Button-5>", self._on_workspace_linux_wheel, add="+")

        # Modern application header.
        header = ttk.Frame(frm, style="Surface.TFrame", padding=(22, 18))
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 16))
        title_col = ttk.Frame(header, style="Surface.TFrame")
        title_col.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_col, text="AstroSirilAssistant", style="Title.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            title_col,
            text="Siril + SyQon 기반 천체사진 반자동 보정",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2,0))
        ttk.Label(header, text="단일 이미지", style="Badge.TLabel").pack(side="right")

        # Input / project card.
        input_card = ttk.LabelFrame(frm, text="프로젝트 입력", style="Card.TLabelframe")
        input_card.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0,14))

        ttk.Label(input_card, text="입력 FITS").grid(row=0, column=0, sticky="w", pady=7)
        ttk.Entry(input_card, textvariable=self.input_var, width=75).grid(row=0, column=1, sticky="ew", padx=(10,0), pady=3)
        ttk.Button(input_card, text="찾기", command=self.pick_input).grid(row=0, column=2, padx=(10,0), pady=3)

        ttk.Label(input_card, text="대상명").grid(row=1, column=0, sticky="w", pady=7)
        ttk.Entry(input_card, textvariable=self.target_var).grid(row=1, column=1, sticky="ew", padx=(10,0), pady=3)

        ttk.Label(input_card, text="촬영일").grid(row=2, column=0, sticky="w", pady=7)
        ttk.Entry(input_card, textvariable=self.date_var).grid(row=2, column=1, sticky="ew", padx=(10,0), pady=3)

        ttk.Label(input_card, text="대상 종류").grid(row=3, column=0, sticky="w", pady=7)
        combo = ttk.Combobox(
            input_card, textvariable=self.category_var, state="readonly",
            values=[x[0] for x in CATEGORIES]
        )
        combo.grid(row=3, column=1, sticky="ew", padx=(10,0), pady=3)

        ttk.Label(input_card, text="저장 위치").grid(row=4, column=0, sticky="w", pady=7)
        ttk.Entry(input_card, textvariable=self.root_var).grid(row=4, column=1, sticky="ew", padx=(10,0), pady=3)
        ttk.Button(input_card, text="폴더", command=self.pick_root).grid(row=4, column=2, padx=(10,0), pady=3)
        input_card.columnconfigure(1, weight=1)

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0,14))
        ttk.Button(btns, text="Siril 연결 확인", command=self.doctor).pack(side="left", padx=(0,6))
        ttk.Button(
            btns, text="프로젝트 생성 + 분석",
            command=self.create_and_analyze, style="Accent.TButton"
        ).pack(side="left", padx=6)
        ttk.Button(btns, text="기존 프로젝트 열기", command=self.open_project).pack(side="left", padx=6)
        ttk.Button(
            btns, text="SyQon 설치 확인", command=self.check_syqon_installation
        ).pack(side="left", padx=6)
        ttk.Button(
            btns,
            text="도움말",
            command=lambda: self.help.show_detail("ui.dynamic"),
            style="Quiet.TButton",
        ).pack(side="right", padx=(6,0))

        status_card = ttk.Frame(frm, style="Surface.TFrame", padding=(16,11))
        status_card.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0,12))
        ttk.Label(
            status_card, text="상태", style="Subtitle.TLabel"
        ).pack(side="left")
        ttk.Label(
            status_card, textvariable=self.status_var, style="Subtitle.TLabel"
        ).pack(side="left", padx=(10,0))

        flow_card = ttk.Frame(frm, style="Surface.TFrame", padding=(16, 12))
        flow_card.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0,14))
        ttk.Label(
            flow_card, textvariable=self.current_stage_var, wraplength=1120, style="FlowCurrent.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            flow_card, textvariable=self.next_stage_var, style="FlowNext.TLabel",
        ).pack(anchor="w", pady=(4,0))

        self.action_box = ttk.LabelFrame(
            frm, text="처리 설정", style="Card.TLabelframe"
        )
        self.action_box.grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=(0, 12)
        )

        op = ttk.Frame(frm, style="Surface.TFrame", padding=(14, 10))
        op.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(2, 8))
        ttk.Label(op, textvariable=self.operation_var).pack(side="left")
        self.progress = ttk.Progressbar(op, mode="indeterminate", length=260)
        self.progress.pack(side="left", padx=(12, 8), fill="x", expand=True)
        ttk.Label(op, textvariable=self.elapsed_var, width=12).pack(side="left")
        self.cancel_btn = ttk.Button(
            op, text="중단", command=self.request_cancel, style="Danger.TButton"
        )
        self.cancel_btn.pack(side="left", padx=(8,0))
        self.cancel_btn.state(["disabled"])

        log_toolbar = ttk.Frame(frm)
        log_toolbar.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(4, 14))
        self.log_toggle_btn = ttk.Button(
            log_toolbar,
            text="▼ 상세 로그 보기",
            command=self.toggle_logs,
        )
        self.log_toggle_btn.pack(side="left")
        self.copy_log_btn = ttk.Button(
            log_toolbar,
            text="로그 복사",
            command=self.copy_logs,
        )
        self.copy_log_btn.pack(side="left", padx=(6,0))

        frm.columnconfigure(0, weight=0)
        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(2, weight=0)
        self.main_frame = frm

        self.log_frame = ttk.LabelFrame(
            self.main_pane, text="상세 로그", style="Card.TLabelframe"
        )
        self.output = tk.Text(self.log_frame, wrap="word", height=10)
        style_text_widget(self.output, self.palette)
        self.output.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(self.log_frame, command=self.output.yview)
        scrollbar.pack(side="right", fill="y")
        self.output.configure(yscrollcommand=scrollbar.set)

    def _workspace_bbox(self):
        try:
            return self.workspace_canvas.bbox("all")
        except Exception:
            return None

    def _workspace_overflows(self):
        bbox = self._workspace_bbox()
        if not bbox:
            return False
        content_h = max(0, bbox[3] - bbox[1])
        viewport_h = max(1, self.workspace_canvas.winfo_height())
        return content_h > viewport_h + 2

    def _sync_workspace_scroll_state(self):
        """Keep short pages pinned to the top; only enable scrolling on overflow."""
        try:
            bbox = self._workspace_bbox()
            if not bbox:
                return

            self.workspace_canvas.configure(scrollregion=bbox)

            if self._workspace_overflows():
                try:
                    self.workspace_scrollbar.state(["!disabled"])
                except Exception:
                    pass
            else:
                # Critical v0.11.1 fix:
                # Canvas can otherwise move a short page inside a taller viewport,
                # creating a huge blank region above the controls.
                self.workspace_canvas.yview_moveto(0.0)
                try:
                    self.workspace_scrollbar.state(["disabled"])
                except Exception:
                    pass
        except Exception:
            pass

    def _on_workspace_inner_configure(self, _event=None):
        self._sync_workspace_scroll_state()

    def _on_workspace_canvas_configure(self, event):
        # Make controls follow the available width rather than retaining a
        # fixed content width.
        try:
            self.workspace_canvas.itemconfigure(
                self.workspace_window_id,
                width=max(1, event.width),
            )
        except Exception:
            pass
        self.after_idle(self._sync_workspace_scroll_state)

    def _is_in_workspace(self, widget):
        """Return True only for widgets inside the scrollable workflow area."""
        current = widget
        while current is not None:
            if current in (self.workspace_inner, self.workspace_canvas, self.workspace_holder):
                return True
            try:
                current = current.master
            except Exception:
                current = None
        return False

    def _wheel_target_is_editable_combo(self, widget):
        # Do not hijack the wheel while the pointer is directly over a Combobox.
        # That widget may have its own platform-specific behavior.
        return isinstance(widget, ttk.Combobox)

    def _on_workspace_mousewheel(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            widget = None

        if not widget or not self._is_in_workspace(widget):
            return None
        if self._wheel_target_is_editable_combo(widget):
            return None
        if not self._workspace_overflows():
            self.workspace_canvas.yview_moveto(0.0)
            return "break"

        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return None

        # Windows normally reports +/-120 per notch. High-resolution wheels
        # can report smaller deltas, so preserve direction with a minimum step.
        if abs(delta) >= 120:
            notches = max(-3, min(3, int(delta / 120)))
        else:
            notches = 1 if delta > 0 else -1

        # Canvas yscrollincrement=24: 2 units ≈ 48 px per wheel notch.
        self.workspace_canvas.yview_scroll(-notches * 2, "units")
        return "break"

    def _on_workspace_linux_wheel(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            widget = None

        if not widget or not self._is_in_workspace(widget):
            return None
        if self._wheel_target_is_editable_combo(widget):
            return None
        if not self._workspace_overflows():
            self.workspace_canvas.yview_moveto(0.0)
            return "break"

        step = -2 if event.num == 4 else 2
        self.workspace_canvas.yview_scroll(step, "units")
        return "break"

    def _ensure_action_visible(self):
        try:
            self.update_idletasks()
            self._sync_workspace_scroll_state()

            # A page shorter than the viewport must NEVER be auto-scrolled.
            if not self._workspace_overflows():
                self.workspace_canvas.yview_moveto(0.0)
                return

            bbox = self._workspace_bbox()
            if not bbox:
                return

            content_h = max(1, bbox[3] - bbox[1])
            viewport_h = max(1, self.workspace_canvas.winfo_height())
            max_top = max(0, content_h - viewport_h)

            action_y = max(0, self.action_box.winfo_y() - 12)
            action_h = self.action_box.winfo_height()

            view_top = self.workspace_canvas.canvasy(0)
            view_bottom = view_top + viewport_h

            if action_y < view_top or action_y + action_h > view_bottom:
                target_top = max(0, min(max_top, action_y))
                self.workspace_canvas.yview_moveto(target_top / content_h)
        except Exception:
            pass

    def pick_input(self):
        path = filedialog.askopenfilename(
            title="FITS 선택",
            filetypes=[("FITS", "*.fits *.fit *.fts"), ("All files", "*.*")]
        )
        if path:
            self.input_var.set(path)

    def pick_root(self):
        path = filedialog.askdirectory(title="저장 위치 선택")
        if path:
            self.root_var.set(path)

    def write(self, text, clear=False):
        if clear:
            self.output.delete("1.0", "end")
        self.output.insert("end", text + "\n")
        self.output.see("end")

    def _set_log_sash(self):
        """Give the log pane a visible height after Tk finishes geometry layout."""
        if not self.logs_visible:
            return
        try:
            panes = self.main_pane.panes()
            if len(panes) < 2:
                return

            self.update_idletasks()
            total_h = max(1, self.main_pane.winfo_height())

            # Keep both panes usable. On a normal window this opens the log at
            # roughly 32% of the window height.
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
                    current = self.main_pane.sashpos(0)
                    self._log_sash_ratio = max(0.45, min(0.85, current / total_h))
            except Exception:
                pass

            try:
                self.main_pane.forget(self.log_frame)
            except Exception as e:
                messagebox.showerror("로그 패널 오류", f"로그 패널을 닫지 못했습니다.\n{e}")
                return

            self.log_toggle_btn.configure(text="▼ 상세 로그 보기")
            self.logs_visible = False
            return

        try:
            # Only add it when it is not already managed.
            if str(self.log_frame) not in set(self.main_pane.panes()):
                self.main_pane.add(self.log_frame, weight=2)
        except Exception as e:
            messagebox.showerror("로그 패널 오류", f"로그 패널을 열지 못했습니다.\n{e}")
            return

        self.log_toggle_btn.configure(text="▲ 상세 로그 숨기기")
        self.logs_visible = True

        # `after_idle` in v0.11.0 ran before the PanedWindow had finished its
        # second-pane geometry on some Windows systems. Re-apply the sash after
        # actual timed layout passes so the pane cannot remain 1 px tall.
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
                if w in (
                    getattr(self, "log_toggle_btn", None),
                    getattr(self, "copy_log_btn", None),
                    getattr(self, "cancel_btn", None),
                ):
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
        if sec >= 300 and not self._long_running_notice_sent:
            self._long_running_notice_sent = True
            self.write(
                "\n⏱ 장시간 작업이 계속되고 있습니다. "
                "상세 로그에서 진행 상황을 확인하거나 [중단]을 사용할 수 있습니다.\n"
            )
        self._busy_timer_id = self.after(500, self._tick_elapsed)

    def _begin_busy(self, label: str):
        if self._busy:
            raise RuntimeError("다른 작업이 실행 중입니다.")
        self._busy = True
        self._busy_started = time.monotonic()
        self._current_operation = label
        self._cancel_requested = False
        self._long_running_notice_sent = False
        self.operation_var.set(f"● 실행 중: {label}")
        self.elapsed_var.set("경과 00:00")
        self.progress.start(12)
        self._set_processing_controls_disabled(True)
        self.cancel_btn.state(["!disabled"])
        self.write(f"\n▶ 실행 시작: {label}\n")
        self._tick_elapsed()

    def _end_busy(self, label: str, success: bool = False, cancelled: bool = False):
        if self._busy_timer_id:
            try:
                self.after_cancel(self._busy_timer_id)
            except Exception:
                pass
            self._busy_timer_id = None
        self.progress.stop()
        self.cancel_btn.state(["disabled"])
        self._set_processing_controls_disabled(False)
        self._busy = False
        self._current_control = None
        self._current_operation = None
        if cancelled:
            self.operation_var.set(f"■ 중단됨: {label}")
        elif success:
            self.operation_var.set(f"✓ 완료: {label}")
        else:
            self.operation_var.set(f"✕ 오류: {label}")

    def _execution_log_line(self, line: str):
        line = str(line).rstrip()
        if not line:
            return
        def apply_line():
            self.write(f"│ {line}")
            low = line.lower()
            stage = None
            if any(x in low for x in ("cuda", "gpu", "directml")):
                stage = "GPU / AI 처리"
            elif "model" in low and any(x in low for x in ("load", "loading", "loaded")):
                stage = "모델 로딩"
            elif any(x in low for x in ("tile", "inference", "processing")):
                stage = "AI 처리"
            elif any(x in low for x in ("saving", "save ", "writing")):
                stage = "결과 저장"
            if stage and self._busy and self._current_operation:
                self.operation_var.set(f"● 실행 중: {self._current_operation} · {stage}")
        self.after(0, apply_line)

    def request_cancel(self):
        if not self._busy or not self._current_control or self._cancel_requested:
            return
        operation = self._current_operation or "현재 작업"
        stronger = any(x in operation for x in ("실제 적용", "실제 실행", "Finalize", "Export"))
        detail = (
            "완료되지 않은 출력은 정상 결과로 채택하지 않으며 프로젝트 상태는 완료로 갱신하지 않습니다."
            if stronger else
            "완료되지 않은 미리보기/임시 파일은 재사용하지 않습니다."
        )
        if not messagebox.askyesno(
            "작업 중단",
            f"{operation}을(를) 중단할까요?\n\n{detail}"
        ):
            return
        self._cancel_requested = True
        self.cancel_btn.state(["disabled"])
        self.operation_var.set(f"■ 중단 요청 중: {operation}")
        self.status_var.set("중단 요청 중...")
        self.write("\n■ 사용자 중단 요청 — 실행 중인 Siril/SyQon 프로세스를 종료합니다.\n")
        self._current_control.cancel()

    def run_bg(self, func, operation: str | None = None, on_success=None):
        control = TaskControl()
        if operation:
            try:
                self._begin_busy(operation)
                self._current_control = control
            except Exception as e:
                messagebox.showwarning("실행 중", str(e))
                return

        def runner():
            try:
                with execution_context(control, log_callback=self._execution_log_line):
                    result = func()
                    if control.cancelled:
                        raise ExecutionCancelled("사용자가 작업을 중단했습니다.")
            except ExecutionCancelled as e:
                def cancelled():
                    if operation:
                        self._end_busy(operation, cancelled=True)
                    self.status_var.set("작업 중단됨")
                    self.write(f"\n■ 작업 중단 완료: {operation or '작업'}\n{e}\n")
                self.after(0, cancelled)
                return
            except Exception as e:
                def fail():
                    if operation:
                        self._end_busy(operation, success=False)
                    self.status_var.set("오류")
                    self.write(f"\n✕ 오류: {operation or '작업'}\n{e}\n")
                    self.show_logs()
                    messagebox.showerror("오류", str(e))
                self.after(0, fail)
                return

            def done():
                if operation:
                    self._end_busy(operation, success=True)
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

    def _project_collision_dialog(self, existing: Path, fresh: Path):
        result = {"value": None}
        win = tk.Toplevel(self)
        win.title("동일 프로젝트가 이미 존재합니다")
        win.transient(self)
        win.resizable(False, False)
        win.grab_set()

        outer = ttk.Frame(win, style="Surface.TFrame", padding=22)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text="같은 대상명과 촬영일의 프로젝트가 이미 있습니다.",
            font=("Segoe UI Semibold", 11),
        ).pack(anchor="w")
        ttk.Label(outer, text="기존 프로젝트:", style="Muted.TLabel").pack(anchor="w", pady=(14,3))
        ttk.Label(outer, text=str(existing), wraplength=650).pack(anchor="w")
        ttk.Label(outer, text="새 프로젝트:", style="Muted.TLabel").pack(anchor="w", pady=(10,3))
        ttk.Label(outer, text=str(fresh), wraplength=650).pack(anchor="w")
        ttk.Label(
            outer,
            text="기존 프로젝트는 변경하지 않습니다. 원하는 작업을 선택하세요.",
            wraplength=650,
        ).pack(anchor="w", pady=(14,14))

        row = ttk.Frame(outer, style="Surface.TFrame")
        row.pack(fill="x")
        def choose(value):
            result["value"] = value
            win.destroy()
        ttk.Button(
            row, text="기존 프로젝트 열기", command=lambda: choose("OPEN")
        ).pack(side="left")
        ttk.Button(
            row, text="새 프로젝트 만들기", style="Accent.TButton",
            command=lambda: choose("NEW")
        ).pack(side="left", padx=8)
        ttk.Button(row, text="취소", command=lambda: choose(None)).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", lambda: choose(None))

        win.update_idletasks()
        x = self.winfo_rootx() + max(20, (self.winfo_width() - win.winfo_width()) // 2)
        y = self.winfo_rooty() + max(20, (self.winfo_height() - win.winfo_height()) // 3)
        win.geometry(f"+{x}+{y}")
        self.wait_window(win)
        return result["value"]

    def create_and_analyze(self):
        input_path = self.input_var.get().strip()
        target = self.target_var.get().strip()
        capture_date = self.date_var.get().strip()
        if not input_path or not target or not capture_date:
            messagebox.showwarning("확인", "FITS, 대상명, 촬영일을 입력하세요.")
            return

        category = LABEL_TO_ID[self.category_var.get()]
        root = Path(self.root_var.get().strip())
        existing_pdir = find_existing_project_dir(root, target, capture_date)
        requested_pdir = None

        if existing_pdir is not None:
            fresh_pdir = next_available_project_dir(root, target, capture_date)
            choice = self._project_collision_dialog(existing_pdir, fresh_pdir)
            if choice is None:
                self.status_var.set("대기 중")
                return
            if choice == "OPEN":
                self._load_project_from_path(existing_pdir)
                return
            requested_pdir = fresh_pdir

        self.status_var.set("프로젝트 생성 및 분석 중...")
        self.output.delete("1.0", "end")

        def work():
            pdir = create_project(
                root=root,
                target=target,
                capture_date=capture_date,
                category=category,
                input_file=Path(input_path),
                copy_input=True,
                project_dir=requested_pdir,
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

    def _load_project_from_path(self, pdir: Path):
        pdir = Path(pdir)
        try:
            project = load_project(pdir)
        except Exception as e:
            messagebox.showerror("오류", str(e))
            return False

        self.project_dir = pdir
        project = migrate_post_spcc_task(pdir)
        project = migrate_post_denoise_task(pdir)
        project = migrate_ready_for_ghs(pdir)
        project = migrate_ready_for_starnet(pdir)
        project = enrich_target_characteristics(pdir, only_if_empty=True)
        project = migrate_ready_for_starless(pdir)
        project = migrate_ready_for_stars(pdir)
        project = migrate_ready_for_recombine(pdir)
        project = migrate_ready_for_final_export(pdir)
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
        return True

    def open_project(self):
        path = filedialog.askdirectory(title="기존 AstroSirilAssistant 프로젝트 선택")
        if not path:
            return
        self._load_project_from_path(Path(path))

    def _clear_actions(self):
        for child in self.action_box.winfo_children():
            child.destroy()

    def _update_stage_summary(self, task):
        if not task:
            self.current_stage_var.set("현재 단계 : 다음 처리 단계 정보가 없습니다.")
            self.next_stage_var.set("다음 작업 : —")
            return
        task_id = str(task.get("task_id", ""))
        desc, next_name = STAGE_FLOW_INFO.get(
            task_id,
            (task.get("summary", "현재 처리 단계를 확인하는 중입니다."), "—"),
        )
        if task_id == "DEBLUR" and "LEGACY_ORDER" in str(task.get("current_status", "")):
            next_name = "GHS Stretch"
        self.current_stage_var.set(f"현재 단계 : {desc}")
        self.next_stage_var.set(f"다음 작업 : {next_name}")

    def render_task(self, task):
        self._update_stage_summary(task)
        self._clear_actions()
        if not task:
            ttk.Label(self.action_box, text="처리할 작업이 없습니다.").pack(anchor="w", padx=8, pady=8)
            return

        task_id = task.get("task_id", "")
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

        elif task_id == "DEBLUR":
            self._build_deblur_controls()

        elif task_id == "GHS_STRETCH":
            self._build_ghs_controls()

        elif task_id == "GHS_REVIEW":
            self._build_ghs_review_controls()

        elif task_id == "STAR_SEPARATION":
            self._build_starnet_controls()

        elif task_id == "STARLESS_PROCESS":
            self._build_starless_controls()

        elif task_id == "STARS_PROCESS":
            self._build_stars_controls()

        elif task_id == "PIXEL_MATH_RECOMBINE":
            self._build_recombine_controls()

        elif task_id == "FINALIZE_EXPORT":
            self._build_final_export_controls()

        elif task_id == "PIPELINE_COMPLETE":
            self._build_pipeline_complete_controls()

        else:
            ttk.Label(
                controls,
                text="이 단계의 실제 실행 UI는 이후 구현 단계에서 연결됩니다."
            ).pack(side="left", padx=3)

        self.after_idle(self._ensure_action_visible)

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
        ttk.Button(buttons, text="목록 새로고침", command=self.load_spcc_lists).pack(side="left", padx=(0,6))
        ttk.Button(buttons, text="Plate Solve 확인", command=self.show_wcs_status).pack(side="left", padx=6)
        ttk.Button(buttons, text="미리보기", command=self.spcc_preview).pack(side="left", padx=6)
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

    def check_syqon_installation(self):
        info = detect_syqon(self.cfg)
        lines = [
            "SyQon script 자동 감지 결과",
            "",
            f"Parallax: {info.get('parallax') or '미감지'}",
            f"  CLI 자동호출: {'OK' if info.get('parallax_cli_ready') else '업데이트 필요/미감지'}",
            f"Prism: {info.get('prism') or '미감지'}",
            f"  CLI 자동호출: {'OK' if info.get('prism_cli_ready') else '업데이트 필요/미감지'}",
        ]
        if info.get("ready"):
            lines += ["", "Parallax / Prism script가 모두 감지되었습니다."]
            self.status_var.set("SyQon Parallax / Prism 감지 완료")
            messagebox.showinfo("SyQon 설치 확인", "\n".join(lines))
        else:
            lines += [
                "",
                "미감지된 항목은 Siril의 Get Scripts에서 설치/업데이트하세요.",
                "사용자 정의 script 위치라면 config/app.yaml의 syqon.script_roots에 경로를 추가할 수 있습니다.",
                "SyQon을 사용하지 못하는 경우 각 단계에서 Siril Native 엔진을 선택할 수 있습니다.",
            ]
            self.status_var.set("SyQon 일부 미감지")
            messagebox.showwarning("SyQon 설치 확인", "\n".join(lines))
        self.write("\n" + "\n".join(lines) + "\n")

    # ------------------------------------------------------------------
    # Denoise / Prism
    # ------------------------------------------------------------------
    def _build_denoise_controls(self):
        self._clear_actions()

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))
        title = ttk.Label(head, text="Noise Reduction / Denoise", font=("", 10, "bold"))
        title.pack(side="left")
        self.help.tooltip(title, "denoise.what")

        self.help.section_help_button(
            head,
            "Noise Reduction / Denoise 도움말",
            [
                "denoise.what", "denoise.engine", "denoise.prism",
                "denoise.prism.modulation", "denoise.prism.geometry",
                "denoise.prism.stretch", "denoise.native",
                "denoise.preview", "denoise.apply", "denoise.skip",
            ],
        ).pack(side="right")

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        ttk.Label(body, text="처리 엔진", width=22).grid(row=0, column=0, sticky="w", pady=4)
        engine = ttk.Combobox(
            body,
            textvariable=self.denoise_engine,
            values=["SYQON_PRISM", "SIRIL_NATIVE"],
            state="readonly",
            width=22,
        )
        engine.grid(row=0, column=1, sticky="w", pady=4)
        engine.bind("<<ComboboxSelected>>", lambda e: self._refresh_denoise_ui())

        self.prism_frame = ttk.LabelFrame(
            body, text="SyQon Prism Mini", style="Card.TLabelframe"
        )
        self.prism_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6,5))

        def p_label(row, text, topic):
            w = ttk.Label(self.prism_frame, text=text, width=21)
            w.grid(row=row, column=0, sticky="w", pady=3)
            self.help.tooltip(w, topic)

        p_label(0, "모델", "denoise.prism")
        ttk.Combobox(
            self.prism_frame, textvariable=self.prism_model,
            values=["mini", "deep"], state="readonly", width=12
        ).grid(row=0, column=1, sticky="w", pady=3)

        p_label(1, "Modulation", "denoise.prism.modulation")
        ttk.Entry(
            self.prism_frame, textvariable=self.prism_modulation, width=10
        ).grid(row=1, column=1, sticky="w", pady=3)

        p_label(2, "Tile / Overlap / Pad", "denoise.prism.geometry")
        geom = ttk.Frame(self.prism_frame)
        geom.grid(row=2, column=1, sticky="w", pady=3)
        ttk.Entry(geom, textvariable=self.prism_tile, width=7).pack(side="left")
        ttk.Entry(geom, textvariable=self.prism_overlap, width=7).pack(side="left", padx=5)
        ttk.Entry(geom, textvariable=self.prism_pad, width=7).pack(side="left")

        p_label(3, "Temporary Stretch", "denoise.prism.stretch")
        stretch = ttk.Frame(self.prism_frame)
        stretch.grid(row=3, column=1, sticky="w", pady=3)
        ttk.Combobox(
            stretch, textvariable=self.prism_stretch_method,
            values=["statistical", "ihs"], state="readonly", width=12
        ).pack(side="left")
        ttk.Entry(stretch, textvariable=self.prism_stretch_target, width=8).pack(side="left", padx=5)

        p_label(4, "GPU", "denoise.prism")
        ttk.Checkbutton(
            self.prism_frame, text="사용", variable=self.prism_use_gpu
        ).grid(row=4, column=1, sticky="w", pady=3)


        self.native_denoise_frame = ttk.LabelFrame(
            body, text="Siril Native Fallback", style="Card.TLabelframe"
        )
        self.native_denoise_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6,5))

        def n_label(row, text, topic):
            w = ttk.Label(self.native_denoise_frame, text=text, width=21)
            w.grid(row=row, column=0, sticky="w", pady=3)
            self.help.tooltip(w, topic)

        n_label(0, "Modulation", "denoise.native")
        ttk.Entry(
            self.native_denoise_frame, textvariable=self.denoise_modulation, width=8
        ).grid(row=0, column=1, sticky="w", pady=3)
        n_label(1, "Cosmetic Correction", "denoise.native")
        ttk.Checkbutton(
            self.native_denoise_frame, variable=self.denoise_cosmetic
        ).grid(row=1, column=1, sticky="w", pady=3)
        n_label(2, "DA3D", "denoise.native")
        ttk.Checkbutton(
            self.native_denoise_frame, variable=self.denoise_da3d
        ).grid(row=2, column=1, sticky="w", pady=3)
        n_label(3, "Independent RGB", "denoise.native")
        ttk.Checkbutton(
            self.native_denoise_frame, variable=self.denoise_independent
        ).grid(row=3, column=1, sticky="w", pady=3)

        buttons = ttk.Frame(body)
        buttons.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8,0))
        ttk.Button(
            buttons, text="미리보기", command=self.denoise_preview,
            style="Accent.TButton"
        ).pack(side="left", padx=(0,6))
        ttk.Button(
            buttons, text="승인 후 적용", command=self.denoise_apply,
            style="Success.TButton"
        ).pack(side="left", padx=6)
        ttk.Button(
            buttons, text="이 단계 건너뛰기", command=self.denoise_skip
        ).pack(side="left", padx=6)

        body.columnconfigure(1, weight=1)
        self._refresh_denoise_ui()

    def _refresh_denoise_ui(self):
        engine = self.denoise_engine.get().upper()
        if not hasattr(self, "prism_frame"):
            return
        if engine == "SYQON_PRISM":
            self.prism_frame.grid()
            self.native_denoise_frame.grid_remove()
        else:
            self.native_denoise_frame.grid()
            self.prism_frame.grid_remove()

    def _denoise_signature(self):
        return (
            self.denoise_engine.get().strip().upper(),
            self.prism_model.get().strip(),
            self.prism_tile.get().strip(),
            self.prism_overlap.get().strip(),
            self.prism_pad.get().strip(),
            self.prism_modulation.get().strip(),
            bool(self.prism_use_gpu.get()),
            self.prism_stretch_method.get().strip(),
            self.prism_stretch_target.get().strip(),
            self.denoise_modulation.get().strip(),
            bool(self.denoise_cosmetic.get()),
            bool(self.denoise_da3d.get()),
            bool(self.denoise_independent.get()),
        )

    def _invalidate_denoise_preview(self, *args):
        self.denoise_preview_signature = None

    def _denoise_params(self):
        engine = self.denoise_engine.get().strip().upper()
        if engine == "SYQON_PRISM":
            return {
                "engine": engine,
                "model": self.prism_model.get().strip().lower(),
                "tile_size": int(self.prism_tile.get()),
                "overlap": int(self.prism_overlap.get()),
                "pad": int(self.prism_pad.get()),
                "modulation": float(self.prism_modulation.get()),
                "use_gpu": bool(self.prism_use_gpu.get()),
                "stretch_method": self.prism_stretch_method.get().strip().lower(),
                "stretch_target": float(self.prism_stretch_target.get()),
            }
        return {
            "engine": "SIRIL_NATIVE",
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
            messagebox.showerror("오류", "Denoise 숫자 값을 확인하세요.")
            return

        signature = self._denoise_signature()

        def work():
            return preview_denoise(self.project_dir, self.cfg, **params)

        def done(result):
            jpg, linear_preview, meta = result
            self.denoise_preview_signature = signature
            self.write(
                "\nDenoise 미리보기 완료\n"
                f"Engine: {meta['engine']}\n"
                f"표시용 JPEG: {jpg}\n"
                f"Linear Preview FITS: {linear_preview}\n"
                f"Script: {meta.get('script_path')}\n"
                f"명령: {meta['engine_command']}\n"
            )
            self.status_var.set(f"Denoise 미리보기 완료 · {meta['engine']}")
            self._open_preview(jpg)

        self.run_bg(work, operation="Noise Reduction 미리보기", on_success=done)

    def denoise_apply(self):
        if not self._require_project():
            return
        try:
            params = self._denoise_params()
        except ValueError:
            messagebox.showerror("오류", "Denoise 숫자 값을 확인하세요.")
            return

        if self.denoise_preview_signature != self._denoise_signature():
            messagebox.showwarning(
                "미리보기 필요",
                "현재 Denoise 설정과 동일한 값으로 미리보기를 먼저 확인하세요."
            )
            return

        ok = messagebox.askyesno(
            "Denoise 실제 적용",
            "미리보기와 동일한 설정으로 Linear FITS에 Noise Reduction을 적용합니다.\n\n"
            f"Engine: {params['engine']}\n"
            f"Parameters: {params}\n\n"
            "진행할까요?"
        )
        if not ok:
            return

        def work():
            return apply_denoise(self.project_dir, self.cfg, confirmed=True, **params)

        def done(result):
            project, output, log = result
            self.denoise_preview_signature = None
            self._show_project_task(
                project,
                f"Denoise 완료\nEngine: {log.get('engine')}\n출력: {output}"
            )
            self.status_var.set("Denoise 완료")
            next_task = project["project"].get("next_task", {})
            self._show_apply_success(
                f"Denoise · {log.get('engine')}", output, next_task.get("title")
            )

        self.run_bg(work, operation="Noise Reduction 실제 적용", on_success=done)

    def denoise_skip(self):
        if not self._require_project():
            return
        ok = messagebox.askyesno(
            "Denoise 건너뛰기",
            "Noise Reduction을 적용하지 않고 다음 Linear 처리 단계로 이동할까요?"
        )
        if not ok:
            return
        try:
            project = skip_denoise(self.project_dir)
            self._show_project_task(project, "Denoise 건너뜀")
            self.status_var.set("Denoise 건너뜀")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    # ------------------------------------------------------------------
    # Restoration / Parallax
    # ------------------------------------------------------------------
    def _build_deblur_controls(self):
        self._clear_actions()

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))
        title = ttk.Label(head, text="Restoration / Deblur", font=("", 10, "bold"))
        title.pack(side="left")
        self.help.tooltip(title, "deblur.what")

        self.help.section_help_button(
            head,
            "Restoration / Deblur 도움말",
            [
                "deblur.what", "deblur.engine", "deblur.parallax",
                "deblur.parallax.star", "deblur.parallax.sharpen",
                "deblur.parallax.geometry", "deblur.parallax.mtf",
                "deblur.native", "deblur.preview", "deblur.apply", "deblur.skip",
            ],
        ).pack(side="right")

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        ttk.Label(body, text="처리 엔진", width=22).grid(row=0, column=0, sticky="w", pady=4)
        engine = ttk.Combobox(
            body,
            textvariable=self.deblur_engine,
            values=["SYQON_PARALLAX", "SIRIL_RL"],
            state="readonly",
            width=22,
        )
        engine.grid(row=0, column=1, sticky="w", pady=4)
        engine.bind("<<ComboboxSelected>>", lambda e: self._refresh_deblur_ui())

        self.parallax_frame = ttk.LabelFrame(
            body, text="SyQon Parallax Nano", style="Card.TLabelframe"
        )
        self.parallax_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6,5))

        def p_label(row, text, topic):
            w = ttk.Label(self.parallax_frame, text=text, width=21)
            w.grid(row=row, column=0, sticky="w", pady=3)
            self.help.tooltip(w, topic)

        p_label(0, "Edition", "deblur.parallax")
        ttk.Combobox(
            self.parallax_frame, textvariable=self.parallax_edition,
            values=["nano", "pro"], state="readonly", width=10
        ).grid(row=0, column=1, sticky="w", pady=3)

        p_label(1, "Aberration Correction", "deblur.parallax")
        ttk.Checkbutton(
            self.parallax_frame, variable=self.parallax_correct
        ).grid(row=1, column=1, sticky="w", pady=3)

        p_label(2, "Star Level", "deblur.parallax.star")
        ttk.Entry(
            self.parallax_frame, textvariable=self.parallax_star_level, width=10
        ).grid(row=2, column=1, sticky="w", pady=3)
        ttk.Label(
            self.parallax_frame, text="Nano: 0~5 / Pro: 0~7", style="Muted.TLabel"
        ).grid(row=2, column=2, sticky="w", padx=(8,0))

        p_label(3, "Sharpen", "deblur.parallax.sharpen")
        ttk.Entry(
            self.parallax_frame, textvariable=self.parallax_sharpen, width=10
        ).grid(row=3, column=1, sticky="w", pady=3)

        p_label(4, "Tile / Overlap / Pad", "deblur.parallax.geometry")
        geom = ttk.Frame(self.parallax_frame)
        geom.grid(row=4, column=1, sticky="w", pady=3)
        ttk.Entry(geom, textvariable=self.parallax_tile, width=7).pack(side="left")
        ttk.Entry(geom, textvariable=self.parallax_overlap, width=7).pack(side="left", padx=5)
        ttk.Entry(geom, textvariable=self.parallax_pad, width=7).pack(side="left")

        p_label(5, "Temporary MTF", "deblur.parallax.mtf")
        mtf = ttk.Frame(self.parallax_frame)
        mtf.grid(row=5, column=1, sticky="w", pady=3)
        ttk.Checkbutton(mtf, text="사용", variable=self.parallax_use_mtf).pack(side="left")
        ttk.Entry(mtf, textvariable=self.parallax_mtf_target, width=8).pack(side="left", padx=5)
        ttk.Checkbutton(mtf, text="Linked", variable=self.parallax_linked).pack(side="left", padx=5)

        p_label(6, "GPU", "deblur.parallax")
        ttk.Checkbutton(
            self.parallax_frame, text="사용", variable=self.parallax_use_gpu
        ).grid(row=6, column=1, sticky="w", pady=3)


        self.native_deblur_frame = ttk.LabelFrame(
            body, text="Siril Richardson-Lucy Fallback", style="Card.TLabelframe"
        )
        self.native_deblur_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6,5))

        def n_label(row, text, topic):
            w = ttk.Label(self.native_deblur_frame, text=text, width=21)
            w.grid(row=row, column=0, sticky="w", pady=3)
            self.help.tooltip(w, topic)

        n_label(0, "PSF Source", "deblur.native")
        ttk.Label(
            self.native_deblur_frame, text="Detected Stars (자동)"
        ).grid(row=0, column=1, sticky="w", pady=3)
        n_label(1, "Symmetric PSF", "deblur.native")
        ttk.Checkbutton(
            self.native_deblur_frame, variable=self.deblur_symmetric
        ).grid(row=1, column=1, sticky="w", pady=3)
        n_label(2, "PSF Kernel Size", "deblur.native")
        ttk.Entry(
            self.native_deblur_frame, textvariable=self.deblur_kernel, width=10
        ).grid(row=2, column=1, sticky="w", pady=3)
        n_label(3, "RL Iterations", "deblur.native")
        ttk.Entry(
            self.native_deblur_frame, textvariable=self.deblur_iterations, width=10
        ).grid(row=3, column=1, sticky="w", pady=3)
        n_label(4, "Regularization", "deblur.native")
        reg = ttk.Combobox(
            self.native_deblur_frame,
            textvariable=self.deblur_regularization,
            values=["NONE", "TV", "FH"],
            state="readonly",
            width=12,
        )
        reg.grid(row=4, column=1, sticky="w", pady=3)
        reg.bind("<<ComboboxSelected>>", lambda e: self._refresh_deblur_ui())
        n_label(5, "Alpha", "deblur.native")
        self.deblur_alpha_entry = ttk.Entry(
            self.native_deblur_frame, textvariable=self.deblur_alpha, width=10
        )
        self.deblur_alpha_entry.grid(row=5, column=1, sticky="w", pady=3)
        n_label(6, "Multiplicative RL", "deblur.native")
        ttk.Checkbutton(
            self.native_deblur_frame, variable=self.deblur_multiplicative
        ).grid(row=6, column=1, sticky="w", pady=3)

        buttons = ttk.Frame(body)
        buttons.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8,0))
        ttk.Button(
            buttons, text="빠른 미리보기", command=self.deblur_preview_quick,
            style="Accent.TButton"
        ).pack(side="left", padx=(0,6))
        ttk.Button(
            buttons, text="전체 처리 + 결과 확인", command=self.deblur_preview_full
        ).pack(side="left", padx=6)
        ttk.Button(
            buttons, text="결과 승인", command=self.deblur_apply,
            style="Success.TButton"
        ).pack(side="left", padx=6)
        ttk.Button(
            buttons, text="이 단계 건너뛰기", command=self.deblur_skip
        ).pack(side="left", padx=6)

        body.columnconfigure(1, weight=1)
        self._refresh_deblur_ui()

    def _refresh_deblur_ui(self):
        if not hasattr(self, "parallax_frame"):
            return
        engine = self.deblur_engine.get().upper()
        if engine == "SYQON_PARALLAX":
            self.parallax_frame.grid()
            self.native_deblur_frame.grid_remove()
        else:
            self.native_deblur_frame.grid()
            self.parallax_frame.grid_remove()
            try:
                if self.deblur_regularization.get().upper() == "NONE":
                    self.deblur_alpha_entry.state(["disabled"])
                else:
                    self.deblur_alpha_entry.state(["!disabled"])
            except Exception:
                pass

    def _deblur_signature(self):
        return (
            self.deblur_engine.get().strip().upper(),
            self.parallax_edition.get().strip(),
            bool(self.parallax_correct.get()),
            self.parallax_star_level.get().strip(),
            self.parallax_sharpen.get().strip(),
            self.parallax_tile.get().strip(),
            self.parallax_overlap.get().strip(),
            self.parallax_pad.get().strip(),
            bool(self.parallax_use_mtf.get()),
            self.parallax_mtf_target.get().strip(),
            bool(self.parallax_linked.get()),
            bool(self.parallax_use_gpu.get()),
            bool(self.deblur_symmetric.get()),
            self.deblur_kernel.get().strip(),
            self.deblur_iterations.get().strip(),
            self.deblur_regularization.get().strip().upper(),
            self.deblur_alpha.get().strip(),
            bool(self.deblur_multiplicative.get()),
        )

    def _invalidate_deblur_preview(self, *args):
        self.deblur_preview_signature = None
        self.deblur_preview_mode = None
        self.deblur_full_candidate = None
        self.deblur_full_preview_meta = None

    def _deblur_params(self):
        engine = self.deblur_engine.get().strip().upper()
        if engine == "SYQON_PARALLAX":
            return {
                "engine": engine,
                "edition": self.parallax_edition.get().strip().lower(),
                "correct": bool(self.parallax_correct.get()),
                "star_level": float(self.parallax_star_level.get()),
                "sharpen": float(self.parallax_sharpen.get()),
                "tile": int(self.parallax_tile.get()),
                "overlap": int(self.parallax_overlap.get()),
                "pad": int(self.parallax_pad.get()),
                "use_mtf": bool(self.parallax_use_mtf.get()),
                "mtf_target": float(self.parallax_mtf_target.get()),
                "linked": bool(self.parallax_linked.get()),
                "use_gpu": bool(self.parallax_use_gpu.get()),
            }

        kernel_text = self.deblur_kernel.get().strip()
        kernel_size = None if not kernel_text else int(kernel_text)
        return {
            "engine": "SIRIL_RL",
            "symmetric_psf": bool(self.deblur_symmetric.get()),
            "kernel_size": kernel_size,
            "iterations": int(self.deblur_iterations.get()),
            "regularization": self.deblur_regularization.get().strip().upper(),
            "alpha": float(self.deblur_alpha.get()),
            "multiplicative": bool(self.deblur_multiplicative.get()),
        }

    def deblur_preview_quick(self):
        self._start_deblur_preview("QUICK")

    def deblur_preview_full(self):
        self._start_deblur_preview("FULL")

    def _start_deblur_preview(self, mode: str):
        if not self._require_project():
            return
        try:
            params = self._deblur_params()
        except ValueError:
            messagebox.showerror("오류", "Restoration 숫자 값을 확인하세요.")
            return

        signature = self._deblur_signature()
        mode = str(mode).upper()
        label = "빠른 미리보기" if mode == "QUICK" else "전체 처리 + 결과 확인"

        def work():
            return preview_deblur(
                self.project_dir, self.cfg, preview_mode=mode, **params
            )

        def done(result):
            jpg, linear_preview, meta = result
            self.deblur_preview_signature = signature
            self.deblur_preview_mode = mode
            if mode == "FULL":
                self.deblur_full_candidate = Path(linear_preview)
                self.deblur_full_preview_meta = meta
            crop = meta.get("crop") or {}
            geometry = meta.get("geometry_guard") or {}
            safe_banding = meta.get("safe_banding") or {}
            crop_text = ""
            if mode == "QUICK":
                crop_text = (
                    f"빠른 미리보기 영역: {crop.get('crop_width')}×{crop.get('crop_height')} "
                    f"/ 원본 {crop.get('source_width')}×{crop.get('source_height')}\n"
                )
            elif geometry.get("padded"):
                crop_text = (
                    "SyQon geometry guard: "
                    f"{geometry.get('source_width')}×{geometry.get('source_height')} → "
                    f"{geometry.get('prepared_width')}×{geometry.get('prepared_height')} 처리 후 "
                    "원본 크기로 복원\n"
                )
            if mode == "FULL" and safe_banding.get("chunked"):
                crop_text += (
                    "SyQon Safe-Band: "
                    f"{safe_banding.get('band_count')}개 band / "
                    f"overlap {safe_banding.get('overlap')}px / "
                    f"bridge 목표 ≤ {safe_banding.get('max_payload_mib'):.0f} MiB\n"
                )
            self.write(
                f"\nRestoration {label} 완료\n"
                f"Engine: {meta['engine']}\n"
                f"{crop_text}"
                f"표시용 JPEG: {jpg}\n"
                f"Linear Preview FITS: {linear_preview}\n"
                f"Script: {meta.get('script_path')}\n"
                f"명령: {meta.get('engine_command')}\n"
                f"PSF: {meta.get('psf_file')}\n"
            )
            if mode == "QUICK":
                self.status_var.set("빠른 미리보기 완료 · 값 확정 후 전체 처리를 실행하세요")
            else:
                if safe_banding.get("chunked"):
                    self.status_var.set(
                        f"전체 처리 완료 · Safe-Band {safe_banding.get('band_count')}개 결합 · 결과 승인 가능"
                    )
                else:
                    self.status_var.set(f"전체 처리 완료 · 결과 확인 후 [결과 승인]하세요 · {meta['engine']}")
            if mode == "QUICK" and meta.get("before_preview") and meta.get("after_preview"):
                self._open_before_after_preview(
                    Path(meta["before_preview"]),
                    Path(meta["after_preview"]),
                    crop_text=f"{crop.get('crop_width')}×{crop.get('crop_height')}",
                    fallback_after=Path(jpg),
                )
            else:
                self._open_preview(jpg)

        self.run_bg(
            work,
            operation=f"Restoration / Deblur {label}",
            on_success=done,
        )

    def deblur_apply(self):
        if not self._require_project():
            return
        try:
            params = self._deblur_params()
        except ValueError:
            messagebox.showerror("오류", "Restoration 숫자 값을 확인하세요.")
            return

        if (
            self.deblur_preview_signature != self._deblur_signature()
            or self.deblur_preview_mode != "FULL"
            or not self.deblur_full_candidate
            or not self.deblur_full_preview_meta
        ):
            messagebox.showwarning(
                "전체 처리 결과 필요",
                "빠른 미리보기는 값 비교용입니다.\n"
                "현재 설정과 동일한 값으로 [전체 처리 + 결과 확인]을 완료한 뒤 승인하세요."
            )
            return

        ok = messagebox.askyesno(
            "Restoration 결과 승인",
            "확인한 전체 처리 결과를 정식 Linear FITS로 승격합니다.\n"
            "Parallax AI를 다시 실행하지 않습니다.\n\n"
            f"Engine: {params['engine']}\n"
            f"Parameters: {params}\n\n"
            "이 결과를 승인할까요?"
        )
        if not ok:
            return

        candidate = Path(self.deblur_full_candidate)
        candidate_meta = dict(self.deblur_full_preview_meta)

        def work():
            return promote_deblur_preview(
                self.project_dir, self.cfg,
                preview_file=candidate, preview_meta=candidate_meta,
                confirmed=True, **params
            )

        def done(result):
            project, output, log = result
            self.deblur_preview_signature = None
            self.deblur_preview_mode = None
            self.deblur_full_candidate = None
            self.deblur_full_preview_meta = None
            self._show_project_task(
                project,
                f"Restoration 완료\nEngine: {log.get('engine')}\n출력: {output}"
            )
            self.status_var.set("Restoration 완료")
            next_task = project["project"].get("next_task", {})
            self._show_apply_success(
                f"Restoration · {log.get('engine')}",
                output,
                next_task.get("title"),
            )

        self.run_bg(
            work,
            operation="Restoration / Deblur 결과 승인",
            on_success=done,
        )

    def deblur_skip(self):
        if not self._require_project():
            return
        ok = messagebox.askyesno(
            "Restoration 건너뛰기",
            "Parallax/Siril Restoration을 적용하지 않고 다음 Linear 처리 단계로 이동할까요?"
        )
        if not ok:
            return
        try:
            project = skip_deblur(self.project_dir)
            self._show_project_task(project, "Restoration 건너뜀")
            self.status_var.set("Restoration 건너뜀")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _build_ghs_controls(self):
        self._clear_actions()

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))

        title = ttk.Label(head, text="GHS Stretch", font=("", 10, "bold"))
        title.pack(side="left")
        self.help.tooltip(title, "ghs.what")
        ttk.Label(
            head,
            text="적용 후 Non-linear",
        ).pack(side="left", padx=(8,0))

        self.help.section_help_button(
            head,
            "GHS Stretch 도움말",
            [
                "ghs.what", "ghs.method", "ghs.linked", "ghs.shadows_clip",
                "ghs.d", "ghs.b", "ghs.lp", "ghs.sp", "ghs.hp",
                "ghs.luminance", "ghs.clipmode", "ghs.preview", "ghs.apply",
            ],
        ).pack(side="right")

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        lbl = ttk.Label(body, text="Method", width=20)
        lbl.grid(row=0, column=0, sticky="w", pady=3, padx=(0,8))
        self.help.tooltip(lbl, "ghs.method")
        method = ttk.Combobox(
            body,
            textvariable=self.ghs_method,
            values=["AUTO_GHS", "MANUAL_GHT"],
            state="readonly",
            width=20,
        )
        method.grid(row=0, column=1, sticky="w", pady=3)
        method.bind("<<ComboboxSelected>>", lambda e: self._refresh_ghs_ui())

        self.ghs_auto_frame = ttk.LabelFrame(body, text="AutoGHS — 권장 시작")
        self.ghs_auto_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6,5))
        af = self.ghs_auto_frame

        def alabel(row, text, topic):
            w = ttk.Label(af, text=text, width=18)
            w.grid(row=row, column=0, sticky="w", padx=(8,6), pady=3)
            self.help.tooltip(w, topic)

        alabel(0, "Linked RGB", "ghs.linked")
        ttk.Checkbutton(af, variable=self.ghs_auto_linked).grid(row=0, column=1, sticky="w")

        alabel(1, "Shadows Clip", "ghs.shadows_clip")
        ttk.Entry(af, textvariable=self.ghs_auto_shadows, width=10).grid(row=1, column=1, sticky="w")

        alabel(2, "Stretch Amount D", "ghs.d")
        ttk.Entry(af, textvariable=self.ghs_auto_d, width=10).grid(row=2, column=1, sticky="w")

        alabel(3, "B", "ghs.b")
        ttk.Entry(af, textvariable=self.ghs_auto_b, width=10).grid(row=3, column=1, sticky="w")

        alabel(4, "LP", "ghs.lp")
        ttk.Entry(af, textvariable=self.ghs_auto_lp, width=10).grid(row=4, column=1, sticky="w")

        alabel(5, "HP", "ghs.hp")
        ttk.Entry(af, textvariable=self.ghs_auto_hp, width=10).grid(row=5, column=1, sticky="w")

        alabel(6, "Clip Mode", "ghs.clipmode")
        ttk.Combobox(
            af, textvariable=self.ghs_auto_clip,
            values=["rgbblend", "clip", "rescale", "globalrescale"],
            state="readonly", width=18,
        ).grid(row=6, column=1, sticky="w")
        af.columnconfigure(2, weight=1)

        self.ghs_manual_frame = ttk.LabelFrame(body, text="Manual GHT — 고급")
        self.ghs_manual_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(5,5))
        mf = self.ghs_manual_frame

        def mlabel(row, text, topic):
            w = ttk.Label(mf, text=text, width=18)
            w.grid(row=row, column=0, sticky="w", padx=(8,6), pady=3)
            self.help.tooltip(w, topic)

        mlabel(0, "D", "ghs.d")
        ttk.Entry(mf, textvariable=self.ghs_manual_d, width=10).grid(row=0, column=1, sticky="w")
        mlabel(1, "B", "ghs.b")
        ttk.Entry(mf, textvariable=self.ghs_manual_b, width=10).grid(row=1, column=1, sticky="w")
        mlabel(2, "LP", "ghs.lp")
        ttk.Entry(mf, textvariable=self.ghs_manual_lp, width=10).grid(row=2, column=1, sticky="w")
        mlabel(3, "SP", "ghs.sp")
        ttk.Entry(mf, textvariable=self.ghs_manual_sp, width=10).grid(row=3, column=1, sticky="w")
        mlabel(4, "HP", "ghs.hp")
        ttk.Entry(mf, textvariable=self.ghs_manual_hp, width=10).grid(row=4, column=1, sticky="w")
        mlabel(5, "Luminance", "ghs.luminance")
        ttk.Combobox(
            mf, textvariable=self.ghs_manual_lum,
            values=["HUMAN", "EVEN", "INDEPENDENT"],
            state="readonly", width=18,
        ).grid(row=5, column=1, sticky="w")
        mlabel(6, "Clip Mode", "ghs.clipmode")
        ttk.Combobox(
            mf, textvariable=self.ghs_manual_clip,
            values=["rgbblend", "clip", "rescale", "globalrescale"],
            state="readonly", width=18,
        ).grid(row=6, column=1, sticky="w")
        mf.columnconfigure(2, weight=1)

        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Button(
            buttons, text="미리보기", command=self.ghs_preview
        ).pack(side="left", padx=(0,6))
        ttk.Button(
            buttons, text="승인 후 적용", command=self.ghs_apply
        ).pack(side="left", padx=6)

        body.columnconfigure(1, weight=1)
        self._refresh_ghs_ui()

    def _refresh_ghs_ui(self):
        method = self.ghs_method.get().upper()
        if not hasattr(self, "ghs_auto_frame"):
            return

        def set_children_state(frame, enabled):
            for child in frame.winfo_children():
                try:
                    if isinstance(child, (ttk.Entry, ttk.Combobox, ttk.Checkbutton)):
                        child.state(["!disabled"] if enabled else ["disabled"])
                except Exception:
                    pass

        set_children_state(self.ghs_auto_frame, method == "AUTO_GHS")
        set_children_state(self.ghs_manual_frame, method == "MANUAL_GHT")

    def _ghs_signature(self):
        if self.ghs_method.get().upper() == "AUTO_GHS":
            return (
                "AUTO_GHS",
                bool(self.ghs_auto_linked.get()),
                self.ghs_auto_shadows.get().strip(),
                self.ghs_auto_d.get().strip(),
                self.ghs_auto_b.get().strip(),
                self.ghs_auto_lp.get().strip(),
                self.ghs_auto_hp.get().strip(),
                self.ghs_auto_clip.get().strip(),
            )
        return (
            "MANUAL_GHT",
            self.ghs_manual_d.get().strip(),
            self.ghs_manual_b.get().strip(),
            self.ghs_manual_lp.get().strip(),
            self.ghs_manual_sp.get().strip(),
            self.ghs_manual_hp.get().strip(),
            self.ghs_manual_lum.get().strip(),
            self.ghs_manual_clip.get().strip(),
        )

    def _invalidate_ghs_preview(self, *args):
        self.ghs_preview_signature = None

    def _ghs_params(self):
        method = self.ghs_method.get().upper()
        if method == "AUTO_GHS":
            return method, {
                "linked": bool(self.ghs_auto_linked.get()),
                "shadows_clip": float(self.ghs_auto_shadows.get()),
                "stretch_amount": float(self.ghs_auto_d.get()),
                "b": float(self.ghs_auto_b.get()),
                "lp": float(self.ghs_auto_lp.get()),
                "hp": float(self.ghs_auto_hp.get()),
                "clip_mode": self.ghs_auto_clip.get().strip(),
            }

        return method, {
            "d": float(self.ghs_manual_d.get()),
            "b": float(self.ghs_manual_b.get()),
            "lp": float(self.ghs_manual_lp.get()),
            "sp": float(self.ghs_manual_sp.get()),
            "hp": float(self.ghs_manual_hp.get()),
            "luminance_mode": self.ghs_manual_lum.get().strip().upper(),
            "clip_mode": self.ghs_manual_clip.get().strip(),
        }

    def ghs_preview(self):
        if not self._require_project():
            return
        try:
            method, params = self._ghs_params()
        except ValueError:
            messagebox.showerror("오류", "GHS 숫자 값을 확인하세요.")
            return

        signature = self._ghs_signature()

        def work():
            return preview_ghs(
                self.project_dir, self.cfg,
                method=method, **params
            )

        def done(result):
            jpg, preview_fits, meta = result
            self.ghs_preview_signature = signature
            self.write(
                "\nGHS 미리보기 완료\n"
                f"Pass: {meta['pass_number']}\n"
                f"표시용 JPEG: {jpg}\n"
                f"GHS preview FITS: {preview_fits}\n"
                f"명령: {meta['ghs_command']}\n"
                "※ GHS 자체가 실제 Stretch이므로 JPEG에 추가 AutoStretch를 하지 않았습니다.\n"
            )
            self.status_var.set("GHS 미리보기 완료")
            self._open_preview(jpg)

        self.run_bg(
            work,
            operation="GHS Stretch 미리보기",
            on_success=done,
        )

    def ghs_apply(self):
        if not self._require_project():
            return
        try:
            method, params = self._ghs_params()
        except ValueError:
            messagebox.showerror("오류", "GHS 숫자 값을 확인하세요.")
            return

        if self.ghs_preview_signature != self._ghs_signature():
            messagebox.showwarning(
                "미리보기 필요",
                "현재 GHS 설정과 동일한 값으로 미리보기를 먼저 확인하세요."
            )
            return

        ok = messagebox.askyesno(
            "GHS 실제 적용",
            "미리보기와 동일한 설정으로 실제 작업 FITS에 GHS를 적용합니다.\n\n"
            f"Method: {method}\n"
            f"설정: {params}\n\n"
            "첫 Pass인 경우 이미지가 Linear → Non-linear 상태로 전환됩니다.\n"
            "진행할까요?"
        )
        if not ok:
            return

        def work():
            return apply_ghs(
                self.project_dir, self.cfg,
                method=method, confirmed=True, **params
            )

        def done(result):
            project, output, log = result
            self.ghs_preview_signature = None
            self._show_project_task(
                project,
                f"GHS Pass {log['pass_number']} 완료\n출력: {output}"
            )
            self.status_var.set(f"GHS Pass {log['pass_number']} 완료")
            next_task = project["project"].get("next_task", {})
            self._show_apply_success(
                f"GHS Pass {log['pass_number']}",
                output,
                next_task.get("title"),
            )

        self.run_bg(
            work,
            operation="GHS Stretch 실제 적용",
            on_success=done,
        )

    def _build_ghs_review_controls(self):
        self._clear_actions()

        project = load_project(self.project_dir) if self.project_dir else None
        passes = []
        if project:
            passes = project["project"].get("stretch", {}).get("passes", [])
        pass_count = len(passes)

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))
        ttk.Label(
            head,
            text=f"GHS Stretch 결과 — 현재 {pass_count} Pass",
            font=("", 10, "bold"),
        ).pack(side="left")

        self.help.section_help_button(
            head,
            "GHS 반복 Stretch 도움말",
            ["ghs.additional", "ghs.finish"],
        ).pack(side="right")

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        ttk.Label(
            body,
            text="현재 결과가 충분하면 Stretch를 완료하고 StarNet으로 이동하세요. "
                 "조금 더 조정하려면 추가 GHS Pass를 선택할 수 있습니다.",
            wraplength=900,
        ).pack(anchor="w", pady=(0,8))

        btns = ttk.Frame(body)
        btns.pack(anchor="w")
        ttk.Button(
            btns,
            text="추가 GHS Pass",
            command=self.ghs_additional,
        ).pack(side="left", padx=(0,8))
        ttk.Button(
            btns,
            text="Stretch 완료 → StarNet",
            command=self.ghs_finish,
        ).pack(side="left", padx=8)

    def ghs_additional(self):
        if not self._require_project():
            return
        try:
            project = begin_additional_ghs(self.project_dir)
            self._show_project_task(project, "추가 GHS Pass 준비")
            self.status_var.set("추가 GHS Pass 준비")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def ghs_finish(self):
        if not self._require_project():
            return
        ok = messagebox.askyesno(
            "Stretch 완료",
            "현재 GHS 결과를 확정하고 다음 StarNet / 별 분리 단계로 이동할까요?"
        )
        if not ok:
            return
        try:
            project = finish_ghs(self.project_dir)
            self._show_project_task(project, "GHS Stretch 완료")
            self.status_var.set("GHS Stretch 완료")
            messagebox.showinfo(
                "Stretch 완료",
                "GHS Stretch를 완료했습니다.\n\n다음 단계: StarNet / 별 분리"
            )
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _build_starnet_controls(self):
        self._clear_actions()

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))

        title = ttk.Label(head, text="StarNet / 별 분리", font=("", 10, "bold"))
        title.pack(side="left")
        self.help.tooltip(title, "starnet.what")
        self.help.section_help_button(
            head,
            "StarNet / 별 분리 도움말",
            [
                "starnet.what", "starnet.engine", "starnet.linear",
                "starnet.stride", "starnet.upsample", "starnet.highlights",
                "starnet.starlayer", "starnet.native_mask",
                "starnet.preview", "starnet.apply", "starnet.skip",
            ],
        ).pack(side="right")

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        def row_label(row, text, topic):
            label = ttk.Label(body, text=text, width=21)
            label.grid(row=row, column=0, sticky="w", pady=3, padx=(0,8))
            self.help.tooltip(label, topic)
            return label

        row_label(0, "Stride", "starnet.stride")
        stride_frame = ttk.Frame(body)
        stride_frame.grid(row=0, column=1, sticky="w", pady=3)

        stride_combo = ttk.Combobox(
            stride_frame,
            textvariable=self.starnet_stride_preset,
            values=["STANDARD", "LARGE", "SMALL", "CUSTOM"],
            state="readonly",
            width=14,
        )
        stride_combo.pack(side="left")
        stride_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_starnet_ui())

        ttk.Label(stride_frame, text="  값").pack(side="left")
        self.starnet_stride_entry = ttk.Entry(
            stride_frame, textvariable=self.starnet_custom_stride, width=7
        )
        self.starnet_stride_entry.pack(side="left", padx=(4,0))
        self.starnet_stride_value_label = ttk.Label(stride_frame, text="")
        self.starnet_stride_value_label.pack(side="left", padx=(8,0))

        row_label(1, "2x Upsampling", "starnet.upsample")
        ttk.Checkbutton(body, variable=self.starnet_upsample).grid(
            row=1, column=1, sticky="w", pady=3
        )

        row_label(2, "Protect Highlights", "starnet.highlights")
        ttk.Checkbutton(body, variable=self.starnet_protect_highlights).grid(
            row=2, column=1, sticky="w", pady=3
        )

        row_label(3, "Native Starmask", "starnet.native_mask")
        ttk.Checkbutton(body, variable=self.starnet_native_mask).grid(
            row=3, column=1, sticky="w", pady=3
        )

        ttk.Label(
            body,
            text="권장 시작값: Standard 256 · 승인 시 미리보기 결과를 그대로 사용합니다.",
            wraplength=850, style="Muted.TLabel",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(6,8))

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=3, sticky="w")

        ttk.Button(
            buttons, text="미리보기", command=self.starnet_preview
        ).pack(side="left", padx=(0,6))

        self.starnet_starless_view_btn = ttk.Button(
            buttons, text="Starless 보기", command=self.starnet_open_starless_preview
        )
        self.starnet_starless_view_btn.pack(side="left", padx=6)
        self.starnet_starless_view_btn.state(["disabled"])

        self.starnet_stars_view_btn = ttk.Button(
            buttons, text="Stars 보기", command=self.starnet_open_stars_preview
        )
        self.starnet_stars_view_btn.pack(side="left", padx=6)
        self.starnet_stars_view_btn.state(["disabled"])

        ttk.Button(
            buttons, text="승인 후 적용", command=self.starnet_apply
        ).pack(side="left", padx=6)

        ttk.Button(
            buttons, text="이 단계 건너뛰기", command=self.starnet_skip
        ).pack(side="left", padx=6)

        body.columnconfigure(1, weight=1)
        self._refresh_starnet_ui()

    def _refresh_starnet_ui(self):
        if not hasattr(self, "starnet_stride_entry"):
            return
        preset = self.starnet_stride_preset.get().upper()
        values = {"STANDARD": 256, "LARGE": 384, "SMALL": 128}

        try:
            if preset == "CUSTOM":
                self.starnet_stride_entry.state(["!disabled"])
                self.starnet_stride_value_label.configure(text="Custom")
            else:
                self.starnet_stride_entry.state(["disabled"])
                value = values.get(preset, 256)
                self.starnet_custom_stride.set(str(value))
                labels = {
                    "STANDARD": "Standard / Telescope",
                    "LARGE": "Large / Wide landscape",
                    "SMALL": "Small / slower",
                }
                self.starnet_stride_value_label.configure(
                    text=f"{value} — {labels.get(preset, '')}"
                )
        except Exception:
            pass

    def _starnet_signature(self):
        return (
            self.starnet_stride_preset.get().strip().upper(),
            self.starnet_custom_stride.get().strip(),
            bool(self.starnet_upsample.get()),
            bool(self.starnet_protect_highlights.get()),
            bool(self.starnet_native_mask.get()),
        )

    def _invalidate_starnet_preview(self, *args):
        self.starnet_preview_signature = None
        self.starnet_preview_meta = None
        self.starnet_preview_starless_jpg = None
        self.starnet_preview_stars_jpg = None
        for btn in (
            getattr(self, "starnet_starless_view_btn", None),
            getattr(self, "starnet_stars_view_btn", None),
        ):
            if btn:
                try:
                    btn.state(["disabled"])
                except Exception:
                    pass

    def _starnet_params(self):
        preset = self.starnet_stride_preset.get().strip().upper()
        stride = int(self.starnet_custom_stride.get())
        return {
            "stride_preset": preset,
            "stride": stride,
            "upsample": bool(self.starnet_upsample.get()),
            "protect_highlights": bool(self.starnet_protect_highlights.get()),
            "save_native_starmask": bool(self.starnet_native_mask.get()),
        }

    def starnet_preview(self):
        if not self._require_project():
            return

        try:
            params = self._starnet_params()
        except ValueError:
            messagebox.showerror("오류", "Stride 값을 확인하세요.")
            return

        signature = self._starnet_signature()

        def work():
            return preview_star_separation(
                self.project_dir, self.cfg, **params
            )

        def done(meta):
            self.starnet_preview_signature = signature
            self.starnet_preview_meta = meta
            self.starnet_preview_starless_jpg = Path(meta["starless_jpg"])
            self.starnet_preview_stars_jpg = Path(meta["stars_jpg"])

            self.write(
                "\nStarNet 미리보기 완료\n"
                f"Starless FITS: {meta['starless_fits']}\n"
                f"Stars FITS: {meta['stars_fits']}\n"
                f"Starless JPEG: {meta['starless_jpg']}\n"
                f"Stars JPEG: {meta['stars_jpg']}\n"
                f"명령: {meta['command']}\n"
                "※ 승인 후 적용 시 설정이 같으면 StarNet을 다시 계산하지 않습니다.\n"
            )
            self.status_var.set("StarNet 미리보기 완료")

            try:
                self.starnet_starless_view_btn.state(["!disabled"])
                self.starnet_stars_view_btn.state(["!disabled"])
            except Exception:
                pass

            self._open_preview(self.starnet_preview_starless_jpg)

        self.run_bg(
            work,
            operation="StarNet 별 분리 미리보기",
            on_success=done,
        )

    def starnet_open_starless_preview(self):
        if self.starnet_preview_starless_jpg and self.starnet_preview_starless_jpg.exists():
            self._open_preview(self.starnet_preview_starless_jpg)

    def starnet_open_stars_preview(self):
        if self.starnet_preview_stars_jpg and self.starnet_preview_stars_jpg.exists():
            self._open_preview(self.starnet_preview_stars_jpg)

    def starnet_apply(self):
        if not self._require_project():
            return

        try:
            params = self._starnet_params()
        except ValueError:
            messagebox.showerror("오류", "Stride 값을 확인하세요.")
            return

        if (
            self.starnet_preview_signature != self._starnet_signature()
            or not self.starnet_preview_meta
        ):
            messagebox.showwarning(
                "미리보기 필요",
                "현재 StarNet 설정과 동일한 값으로 미리보기를 먼저 확인하세요."
            )
            return

        ok = messagebox.askyesno(
            "StarNet 실제 적용",
            "확인한 StarNet 미리보기 결과를 정식 작업파일로 확정합니다.\n\n"
            f"Stride: {params['stride_preset']} / {params['stride']}\n"
            f"2x Upsampling: {params['upsample']}\n"
            f"Protect Highlights: {params['protect_highlights']}\n"
            f"Native Starmask: {params['save_native_starmask']}\n"
            f"Stars Layer: SUBTRACT\n\n"
            "StarNet AI 계산은 다시 실행하지 않습니다.\n"
            "진행할까요?"
        )
        if not ok:
            return

        def work():
            return apply_star_separation(
                self.project_dir,
                self.cfg,
                confirmed=True,
                preview_meta=self.starnet_preview_meta,
                **params,
            )

        def done(result):
            project, starless, stars, payload = result
            self._show_project_task(
                project,
                f"StarNet 별 분리 완료\nStarless: {starless}\nStars: {stars}"
            )
            self.status_var.set("StarNet 별 분리 완료")
            next_task = project["project"].get("next_task", {})
            self._show_apply_success(
                "StarNet 별 분리",
                f"{starless}\nStars: {stars}",
                next_task.get("title"),
            )

        self.run_bg(
            work,
            operation="StarNet 결과 정식 적용",
            on_success=done,
        )

    def starnet_skip(self):
        if not self._require_project():
            return
        ok = messagebox.askyesno(
            "StarNet 건너뛰기",
            "별 분리를 하지 않고 현재 Non-linear 이미지를 그대로 유지할까요?"
        )
        if not ok:
            return
        try:
            project = skip_star_separation(self.project_dir)
            self._show_project_task(project, "StarNet 건너뜀")
            self.status_var.set("StarNet 건너뜀")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _build_starless_controls(self):
        self._clear_actions()

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))

        title = ttk.Label(head, text="Starless Processing", font=("", 10, "bold"))
        title.pack(side="left")
        self.help.tooltip(title, "starless.what")
        ttk.Label(
            head,
            text="천체 특징 기반 구조·색 보정",
        ).pack(side="left", padx=(8,0))

        self.help.section_help_button(
            head,
            "Starless Processing 도움말",
            [
                "recommendation.what", "recommendation.features",
                "starless.what", "starless.clahe", "starless.clahe_clip",
                "starless.tile", "starless.saturation",
                "starless.background_factor", "starless.preview", "starless.apply",
            ],
        ).pack(side="right")

        # Recommendation card
        rec_frame = ttk.LabelFrame(self.action_box, text="천체 특징 기반 추천")
        rec_frame.pack(fill="x", padx=10, pady=(0,8))

        ttk.Label(
            rec_frame,
            textvariable=self.starless_recommendation_var,
            justify="left",
            wraplength=900,
        ).pack(anchor="w", padx=10, pady=(7,5))

        rec_buttons = ttk.Frame(rec_frame)
        rec_buttons.pack(anchor="w", padx=8, pady=(0,7))
        ttk.Button(
            rec_buttons, text="추천 다시 계산", command=self.starless_calculate_recommendation
        ).pack(side="left", padx=(0,6))
        ttk.Button(
            rec_buttons, text="추천값 적용", command=self.starless_apply_recommendation
        ).pack(side="left", padx=6)
        ttk.Button(
            rec_buttons, text="천체 특징 수정", command=self.edit_target_characteristics
        ).pack(side="left", padx=6)

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        def row_label(row, text, topic):
            w = ttk.Label(body, text=text, width=23)
            w.grid(row=row, column=0, sticky="w", pady=3, padx=(0,8))
            self.help.tooltip(w, topic)
            return w

        row_label(0, "CLAHE Local Contrast", "starless.clahe")
        ttk.Checkbutton(body, variable=self.starless_clahe_enabled).grid(
            row=0, column=1, sticky="w", pady=3
        )

        row_label(1, "CLAHE Clip Limit", "starless.clahe_clip")
        ttk.Entry(body, textvariable=self.starless_clahe_clip, width=10).grid(
            row=1, column=1, sticky="w", pady=3
        )

        row_label(2, "CLAHE Tile Size", "starless.tile")
        ttk.Entry(body, textvariable=self.starless_tile, width=10).grid(
            row=2, column=1, sticky="w", pady=3
        )

        ttk.Separator(body, orient="horizontal").grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(6,6)
        )

        row_label(4, "Saturation", "starless.saturation")
        ttk.Checkbutton(body, variable=self.starless_sat_enabled).grid(
            row=4, column=1, sticky="w", pady=3
        )

        row_label(5, "Saturation Amount", "starless.saturation")
        ttk.Entry(body, textvariable=self.starless_sat_amount, width=10).grid(
            row=5, column=1, sticky="w", pady=3
        )

        row_label(6, "Background Factor", "starless.background_factor")
        ttk.Entry(body, textvariable=self.starless_sat_bg, width=10).grid(
            row=6, column=1, sticky="w", pady=3
        )

        row_label(7, "Hue Range", "starless.saturation")
        ttk.Combobox(
            body,
            textvariable=self.starless_sat_hue,
            values=["6", "0", "1", "2", "3", "4", "5"],
            state="readonly",
            width=10,
        ).grid(row=7, column=1, sticky="w", pady=3)
        ttk.Label(body, text="6 = All").grid(row=7, column=2, sticky="w", padx=(8,0))

        buttons = ttk.Frame(body)
        buttons.grid(row=9, column=0, columnspan=3, sticky="w")

        ttk.Button(
            buttons, text="미리보기", command=self.starless_preview
        ).pack(side="left", padx=(0,6))
        ttk.Button(
            buttons, text="승인 후 적용", command=self.starless_apply
        ).pack(side="left", padx=6)
        ttk.Button(
            buttons, text="이 단계 건너뛰기", command=self.starless_skip
        ).pack(side="left", padx=6)

        body.columnconfigure(1, weight=1)

        # Calculate on first display. The result is only displayed; it is not silently applied.
        try:
            self._calculate_starless_recommendation(show_status=False)
        except Exception as e:
            self.starless_recommendation_var.set(
                f"추천 계산을 완료하지 못했습니다: {e}\n현재 입력값으로 수동 진행할 수 있습니다."
            )

    def _starless_signature(self):
        return (
            bool(self.starless_clahe_enabled.get()),
            self.starless_clahe_clip.get().strip(),
            self.starless_tile.get().strip(),
            bool(self.starless_sat_enabled.get()),
            self.starless_sat_amount.get().strip(),
            self.starless_sat_bg.get().strip(),
            self.starless_sat_hue.get().strip(),
        )

    def _invalidate_starless_preview(self, *args):
        self.starless_preview_signature = None

    def _starless_params(self):
        return {
            "clahe_enabled": bool(self.starless_clahe_enabled.get()),
            "clahe_clip_limit": float(self.starless_clahe_clip.get()),
            "clahe_tile_size": int(self.starless_tile.get()),
            "saturation_enabled": bool(self.starless_sat_enabled.get()),
            "saturation_amount": float(self.starless_sat_amount.get()),
            "saturation_background_factor": float(self.starless_sat_bg.get()),
            "saturation_hue_range": int(self.starless_sat_hue.get()),
        }

    def _format_starless_recommendation(self, rec):
        ctx = rec["target_context"]
        vals = rec["recommended_values"]
        features = ", ".join(ctx.get("feature_labels") or []) or "추가 특징 없음"
        reasons = "\n".join(f"  • {x}" for x in rec.get("reasons", [])[:6])
        return (
            f"추천 기준: {ctx.get('target_name')} / {ctx.get('category_label')} "
            f"(source: {ctx.get('source')})\n"
            f"특징: {features}\n"
            f"추천 시작값: CLAHE={'ON' if vals['clahe_enabled'] else 'OFF'} "
            f"Clip={vals['clahe_clip_limit']} Tile={vals['clahe_tile_size']} / "
            f"Saturation={'ON' if vals['saturation_enabled'] else 'OFF'} "
            f"Amount={vals['saturation_amount']} BG={vals['saturation_background_factor']}\n"
            f"{rec.get('notice')}\n"
            f"추천 근거:\n{reasons}"
        )

    def _calculate_starless_recommendation(self, show_status=True):
        if not self._require_project():
            return None
        rec = recommend_starless(self.project_dir, self.cfg)
        self.starless_recommendation = rec
        self.starless_recommendation_var.set(
            self._format_starless_recommendation(rec)
        )
        if show_status:
            self.status_var.set("천체 특징 기반 추천 계산 완료")
        return rec

    def starless_calculate_recommendation(self):
        try:
            self._calculate_starless_recommendation(show_status=True)
        except Exception as e:
            messagebox.showerror("추천 계산 오류", str(e))

    def starless_apply_recommendation(self):
        try:
            rec = self.starless_recommendation or self._calculate_starless_recommendation(False)
            vals = rec["recommended_values"]

            self.starless_clahe_enabled.set(bool(vals["clahe_enabled"]))
            self.starless_clahe_clip.set(str(vals["clahe_clip_limit"]))
            self.starless_tile.set(str(vals["clahe_tile_size"]))
            self.starless_sat_enabled.set(bool(vals["saturation_enabled"]))
            self.starless_sat_amount.set(str(vals["saturation_amount"]))
            self.starless_sat_bg.set(str(vals["saturation_background_factor"]))
            self.starless_sat_hue.set(str(vals.get("saturation_hue_range", 6)))

            self.status_var.set("추천 시작값을 입력란에 적용했습니다. 미리보기로 확인하세요.")
        except Exception as e:
            messagebox.showerror("추천값 적용 오류", str(e))

    def edit_target_characteristics(self):
        if not self._require_project():
            return

        project = load_project(self.project_dir)
        p = project["project"]
        target = p.get("target", {})
        current_category = target.get("category", "UNKNOWN")
        current_features = set(target.get("features") or [])
        labels = feature_labels()

        win = tk.Toplevel(self)
        win.title("천체 특징 수정")
        win.geometry("560x620")
        win.transient(self)

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=f"대상: {p.get('target_name')}",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0,8))

        cat_frame = ttk.Frame(frame)
        cat_frame.pack(fill="x", pady=(0,8))
        ttk.Label(cat_frame, text="대상 종류", width=15).pack(side="left")
        category_var = tk.StringVar(
            value=ID_TO_LABEL.get(current_category, "모름/자동판단 대기")
        )
        ttk.Combobox(
            cat_frame,
            textvariable=category_var,
            values=[x[0] for x in CATEGORIES],
            state="readonly",
            width=25,
        ).pack(side="left")

        ttk.Label(
            frame,
            text="추천 계산에 사용할 천체 특징",
        ).pack(anchor="w", pady=(6,4))

        canvas = tk.Canvas(frame, highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0,0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        feature_vars = {}
        for feature_id, label in labels.items():
            var = tk.BooleanVar(value=feature_id in current_features)
            feature_vars[feature_id] = var
            ttk.Checkbutton(
                inner,
                text=label,
                variable=var,
            ).pack(anchor="w", pady=2)

        bottom = ttk.Frame(win, padding=(12,4,12,12))
        bottom.pack(fill="x")

        def save():
            selected = [k for k,v in feature_vars.items() if v.get()]
            category_id = LABEL_TO_ID.get(category_var.get(), "UNKNOWN")
            try:
                update_target_characteristics(
                    self.project_dir,
                    category=category_id,
                    features=selected,
                    user_confirmed=True,
                )
                self.category_var.set(ID_TO_LABEL.get(category_id, category_var.get()))
                win.destroy()
                self._calculate_starless_recommendation(show_status=True)
            except Exception as e:
                messagebox.showerror("오류", str(e), parent=win)

        ttk.Button(bottom, text="저장 + 추천 재계산", command=save).pack(side="right")
        ttk.Button(bottom, text="취소", command=win.destroy).pack(side="right", padx=(0,8))

    def starless_preview(self):
        if not self._require_project():
            return
        try:
            params = self._starless_params()
        except ValueError:
            messagebox.showerror("오류", "Starless Processing 숫자 값을 확인하세요.")
            return

        signature = self._starless_signature()

        def work():
            return preview_starless_processing(
                self.project_dir, self.cfg, **params
            )

        def done(result):
            jpg, preview_fits, meta = result
            self.starless_preview_signature = signature
            self.write(
                "\nStarless Processing 미리보기 완료\n"
                f"Preview FITS: {preview_fits}\n"
                f"JPEG: {jpg}\n"
                f"Commands: {meta['commands']}\n"
                "※ 이미 Non-linear이므로 AutoStretch를 추가하지 않았습니다.\n"
            )
            self.status_var.set("Starless Processing 미리보기 완료")
            self._open_preview(jpg)

        self.run_bg(
            work,
            operation="Starless Processing 미리보기",
            on_success=done,
        )

    def starless_apply(self):
        if not self._require_project():
            return
        try:
            params = self._starless_params()
        except ValueError:
            messagebox.showerror("오류", "Starless Processing 숫자 값을 확인하세요.")
            return

        if self.starless_preview_signature != self._starless_signature():
            messagebox.showwarning(
                "미리보기 필요",
                "현재 Starless 설정과 동일한 값으로 미리보기를 먼저 확인하세요."
            )
            return

        ok = messagebox.askyesno(
            "Starless Processing 실제 적용",
            "미리보기와 동일한 설정을 실제 Starless FITS에 적용합니다.\n\n"
            f"CLAHE: {params['clahe_enabled']} / "
            f"Clip={params['clahe_clip_limit']} / Tile={params['clahe_tile_size']}\n"
            f"Saturation: {params['saturation_enabled']} / "
            f"Amount={params['saturation_amount']} / BG={params['saturation_background_factor']}\n\n"
            "Stars 레이어는 변경하지 않습니다.\n진행할까요?"
        )
        if not ok:
            return

        def work():
            return apply_starless_processing(
                self.project_dir, self.cfg, confirmed=True, **params
            )

        def done(result):
            project, output, payload = result
            self.starless_preview_signature = None
            self._show_project_task(
                project,
                f"Starless Processing 완료\n출력: {output}"
            )
            self.status_var.set("Starless Processing 완료")
            next_task = project["project"].get("next_task", {})
            self._show_apply_success(
                "Starless Processing",
                output,
                next_task.get("title"),
            )

        self.run_bg(
            work,
            operation="Starless Processing 실제 적용",
            on_success=done,
        )

    def starless_skip(self):
        if not self._require_project():
            return
        ok = messagebox.askyesno(
            "Starless 보정 건너뛰기",
            "CLAHE / Saturation을 적용하지 않고 Stars Processing 단계로 이동할까요?"
        )
        if not ok:
            return
        try:
            project = skip_starless_processing(self.project_dir)
            self._show_project_task(project, "Starless Processing 건너뜀")
            self.status_var.set("Starless Processing 건너뜀")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _build_stars_controls(self):
        self._clear_actions()

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))

        title = ttk.Label(head, text="Stars Processing", font=("", 10, "bold"))
        title.pack(side="left")
        self.help.tooltip(title, "stars.what")
        ttk.Label(
            head,
            text="천체 특징 기반 별 밝기·색 보정",
        ).pack(side="left", padx=(8,0))

        self.help.section_help_button(
            head,
            "Stars Processing 도움말",
            [
                "stars.what", "stars.recommendation",
                "stars.brightness", "stars.saturation",
                "stars.preview", "stars.apply",
            ],
        ).pack(side="right")

        rec_frame = ttk.LabelFrame(self.action_box, text="천체 특징 기반 별 추천")
        rec_frame.pack(fill="x", padx=10, pady=(0,8))

        ttk.Label(
            rec_frame,
            textvariable=self.stars_recommendation_var,
            justify="left",
            wraplength=900,
        ).pack(anchor="w", padx=10, pady=(7,5))

        rec_buttons = ttk.Frame(rec_frame)
        rec_buttons.pack(anchor="w", padx=8, pady=(0,7))
        ttk.Button(
            rec_buttons,
            text="추천 다시 계산",
            command=self.stars_calculate_recommendation,
        ).pack(side="left", padx=(0,6))
        ttk.Button(
            rec_buttons,
            text="추천값 적용",
            command=self.stars_apply_recommendation,
        ).pack(side="left", padx=6)
        ttk.Button(
            rec_buttons,
            text="천체 특징 수정",
            command=self.edit_target_characteristics,
        ).pack(side="left", padx=6)

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        def row_label(row, text, topic):
            w = ttk.Label(body, text=text, width=24)
            w.grid(row=row, column=0, sticky="w", pady=3, padx=(0,8))
            self.help.tooltip(w, topic)
            return w

        row_label(0, "Brightness Scale", "stars.brightness")
        ttk.Entry(
            body, textvariable=self.stars_brightness, width=10
        ).grid(row=0, column=1, sticky="w", pady=3)
        ttk.Label(
            body,
            text="1.0=원본 / 0.6=별 신호 60%",
        ).grid(row=0, column=2, sticky="w", padx=(8,0))

        ttk.Separator(body, orient="horizontal").grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(6,6)
        )

        row_label(2, "Saturation", "stars.saturation")
        ttk.Checkbutton(
            body, variable=self.stars_sat_enabled
        ).grid(row=2, column=1, sticky="w", pady=3)

        row_label(3, "Saturation Amount", "stars.saturation")
        ttk.Entry(
            body, textvariable=self.stars_sat_amount, width=10
        ).grid(row=3, column=1, sticky="w", pady=3)

        row_label(4, "Background Factor", "stars.saturation")
        ttk.Entry(
            body, textvariable=self.stars_sat_bg, width=10
        ).grid(row=4, column=1, sticky="w", pady=3)
        ttk.Label(
            body,
            text="Stars-only layer 기본 시작값 0",
        ).grid(row=4, column=2, sticky="w", padx=(8,0))

        row_label(5, "Hue Range", "stars.saturation")
        ttk.Combobox(
            body,
            textvariable=self.stars_sat_hue,
            values=["6", "0", "1", "2", "3", "4", "5"],
            state="readonly",
            width=10,
        ).grid(row=5, column=1, sticky="w", pady=3)
        ttk.Label(body, text="6 = All").grid(
            row=5, column=2, sticky="w", padx=(8,0)
        )

        ttk.Label(
            body,
            text="※ Brightness Scale은 별 크기가 아니라 밝기와 존재감을 조절합니다.",
            wraplength=900,
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(6,8))

        buttons = ttk.Frame(body)
        buttons.grid(row=7, column=0, columnspan=3, sticky="w")

        ttk.Button(
            buttons,
            text="미리보기",
            command=self.stars_preview,
        ).pack(side="left", padx=(0,6))
        ttk.Button(
            buttons,
            text="승인 후 적용",
            command=self.stars_apply,
        ).pack(side="left", padx=6)
        ttk.Button(
            buttons,
            text="이 단계 건너뛰기",
            command=self.stars_skip,
        ).pack(side="left", padx=6)

        body.columnconfigure(1, weight=1)

        try:
            self._calculate_stars_recommendation(show_status=False)
        except Exception as e:
            self.stars_recommendation_var.set(
                f"추천 계산을 완료하지 못했습니다: {e}\n현재 입력값으로 수동 진행할 수 있습니다."
            )

    def _stars_signature(self):
        return (
            self.stars_brightness.get().strip(),
            bool(self.stars_sat_enabled.get()),
            self.stars_sat_amount.get().strip(),
            self.stars_sat_bg.get().strip(),
            self.stars_sat_hue.get().strip(),
        )

    def _invalidate_stars_preview(self, *args):
        self.stars_preview_signature = None

    def _stars_params(self):
        return {
            "brightness_scale": float(self.stars_brightness.get()),
            "saturation_enabled": bool(self.stars_sat_enabled.get()),
            "saturation_amount": float(self.stars_sat_amount.get()),
            "saturation_background_factor": float(self.stars_sat_bg.get()),
            "saturation_hue_range": int(self.stars_sat_hue.get()),
        }

    def _format_stars_recommendation(self, rec):
        ctx = rec["target_context"]
        vals = rec["recommended_values"]
        features = ", ".join(ctx.get("feature_labels") or []) or "추가 특징 없음"
        reasons = "\n".join(f"  • {x}" for x in rec.get("reasons", [])[:6])
        return (
            f"추천 기준: {ctx.get('target_name')} / {ctx.get('category_label')} "
            f"(source: {ctx.get('source')})\n"
            f"특징: {features}\n"
            f"추천 시작값: Brightness={vals['brightness_scale']} / "
            f"Saturation={'ON' if vals['saturation_enabled'] else 'OFF'} "
            f"Amount={vals['saturation_amount']} BG={vals['saturation_background_factor']}\n"
            f"{rec.get('notice')}\n"
            f"추천 근거:\n{reasons}"
        )

    def _calculate_stars_recommendation(self, show_status=True):
        if not self._require_project():
            return None
        rec = recommend_stars(self.project_dir, self.cfg)
        self.stars_recommendation = rec
        self.stars_recommendation_var.set(
            self._format_stars_recommendation(rec)
        )
        if show_status:
            self.status_var.set("천체 특징 기반 Stars 추천 계산 완료")
        return rec

    def stars_calculate_recommendation(self):
        try:
            self._calculate_stars_recommendation(show_status=True)
        except Exception as e:
            messagebox.showerror("추천 계산 오류", str(e))

    def stars_apply_recommendation(self):
        try:
            rec = self.stars_recommendation or self._calculate_stars_recommendation(False)
            vals = rec["recommended_values"]

            self.stars_brightness.set(str(vals["brightness_scale"]))
            self.stars_sat_enabled.set(bool(vals["saturation_enabled"]))
            self.stars_sat_amount.set(str(vals["saturation_amount"]))
            self.stars_sat_bg.set(str(vals["saturation_background_factor"]))
            self.stars_sat_hue.set(str(vals.get("saturation_hue_range", 6)))

            self.status_var.set("Stars 추천 시작값을 입력란에 적용했습니다. 미리보기로 확인하세요.")
        except Exception as e:
            messagebox.showerror("추천값 적용 오류", str(e))

    def stars_preview(self):
        if not self._require_project():
            return
        try:
            params = self._stars_params()
        except ValueError:
            messagebox.showerror("오류", "Stars Processing 숫자 값을 확인하세요.")
            return

        signature = self._stars_signature()

        def work():
            return preview_stars_processing(
                self.project_dir, self.cfg, **params
            )

        def done(result):
            jpg, preview_fits, meta = result
            self.stars_preview_signature = signature
            self.write(
                "\nStars Processing 미리보기 완료\n"
                f"Preview FITS: {preview_fits}\n"
                f"JPEG: {jpg}\n"
                f"Commands: {meta['commands']}\n"
                "※ Stars 레이어는 Non-linear이므로 AutoStretch를 추가하지 않았습니다.\n"
            )
            self.status_var.set("Stars Processing 미리보기 완료")
            self._open_preview(jpg)

        self.run_bg(
            work,
            operation="Stars Processing 미리보기",
            on_success=done,
        )

    def stars_apply(self):
        if not self._require_project():
            return
        try:
            params = self._stars_params()
        except ValueError:
            messagebox.showerror("오류", "Stars Processing 숫자 값을 확인하세요.")
            return

        if self.stars_preview_signature != self._stars_signature():
            messagebox.showwarning(
                "미리보기 필요",
                "현재 Stars 설정과 동일한 값으로 미리보기를 먼저 확인하세요."
            )
            return

        ok = messagebox.askyesno(
            "Stars Processing 실제 적용",
            "미리보기와 동일한 설정을 실제 Stars 레이어에 적용합니다.\n\n"
            f"Brightness Scale: {params['brightness_scale']}\n"
            f"Saturation: {params['saturation_enabled']}\n"
            f"Amount: {params['saturation_amount']}\n"
            f"Background Factor: {params['saturation_background_factor']}\n\n"
            "Main/Starless 레이어는 변경하지 않습니다.\n진행할까요?"
        )
        if not ok:
            return

        def work():
            return apply_stars_processing(
                self.project_dir, self.cfg, confirmed=True, **params
            )

        def done(result):
            project, output, payload = result
            self.stars_preview_signature = None
            self._show_project_task(
                project,
                f"Stars Processing 완료\nStars 출력: {output}"
            )
            self.status_var.set("Stars Processing 완료")
            next_task = project["project"].get("next_task", {})
            self._show_apply_success(
                "Stars Processing",
                output,
                next_task.get("title"),
            )

        self.run_bg(
            work,
            operation="Stars Processing 실제 적용",
            on_success=done,
        )

    def stars_skip(self):
        if not self._require_project():
            return
        ok = messagebox.askyesno(
            "Stars 보정 건너뛰기",
            "Stars 밝기/채도 보정을 하지 않고 Pixel Math 재합성 단계로 이동할까요?"
        )
        if not ok:
            return
        try:
            project = skip_stars_processing(self.project_dir)
            self._show_project_task(project, "Stars Processing 건너뜀")
            self.status_var.set("Stars Processing 건너뜀")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _build_recombine_controls(self):
        self._clear_actions()

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))

        title = ttk.Label(head, text="Pixel Math Recombine", font=("", 10, "bold"))
        title.pack(side="left")
        self.help.tooltip(title, "recombine.what")
        ttk.Label(
            head,
            text="Main + Stars × Weight",
        ).pack(side="left", padx=(8,0))

        self.help.section_help_button(
            head,
            "Pixel Math Recombine 도움말",
            [
                "recombine.what", "recombine.weight",
                "recombine.nosum", "recombine.rescale",
                "recombine.preview", "recombine.apply",
            ],
        ).pack(side="right")

        rec_frame = ttk.LabelFrame(self.action_box, text="재합성 추천")
        rec_frame.pack(fill="x", padx=10, pady=(0,8))

        ttk.Label(
            rec_frame,
            textvariable=self.recombine_recommendation_var,
            justify="left",
            wraplength=900,
        ).pack(anchor="w", padx=10, pady=(7,5))

        rb = ttk.Frame(rec_frame)
        rb.pack(anchor="w", padx=8, pady=(0,7))
        ttk.Button(
            rb, text="추천 다시 계산",
            command=self.recombine_calculate_recommendation
        ).pack(side="left", padx=(0,6))
        ttk.Button(
            rb, text="추천값 적용",
            command=self.recombine_apply_recommendation
        ).pack(side="left", padx=6)

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        def row_label(row, text, topic):
            w = ttk.Label(body, text=text, width=22)
            w.grid(row=row, column=0, sticky="w", pady=3, padx=(0,8))
            self.help.tooltip(w, topic)
            return w

        project = load_project(self.project_dir)
        sep = project["project"].get("separation", {})
        main = sep.get("recombine_main_file") or project["project"].get("current_file")
        stars = (
            sep.get("recombine_stars_file")
            or sep.get("stars_processed_file")
            or sep.get("stars_file")
        )

        row_label(0, "Main / Starless", "recombine.what")
        ttk.Label(body, text=str(main), wraplength=760).grid(
            row=0, column=1, columnspan=2, sticky="w", pady=3
        )

        row_label(1, "Stars", "recombine.what")
        ttk.Label(body, text=str(stars), wraplength=760).grid(
            row=1, column=1, columnspan=2, sticky="w", pady=3
        )

        row_label(2, "Star Weight", "recombine.weight")
        ttk.Entry(
            body, textvariable=self.recombine_star_weight, width=10
        ).grid(row=2, column=1, sticky="w", pady=3)
        ttk.Label(
            body, text="1.0 = 현재 Stars 레이어 그대로"
        ).grid(row=2, column=2, sticky="w", padx=(8,0))

        row_label(3, "출력 Rescale", "recombine.rescale")
        ttk.Checkbutton(
            body, variable=self.recombine_rescale
        ).grid(row=3, column=1, sticky="w", pady=3)
        ttk.Label(
            body, text="기본 OFF 권장"
        ).grid(row=3, column=2, sticky="w", padx=(8,0))

        self.recombine_expression_var = tk.StringVar(value="")
        ttk.Label(
            body, text="계산식", width=22
        ).grid(row=4, column=0, sticky="w", pady=3)
        ttk.Label(
            body,
            textvariable=self.recombine_expression_var,
            font=("Consolas", 10),
        ).grid(row=4, column=1, columnspan=2, sticky="w", pady=3)

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=3, sticky="w")
        ttk.Button(
            buttons, text="미리보기",
            command=self.recombine_preview
        ).pack(side="left", padx=(0,6))
        ttk.Button(
            buttons, text="승인 후 적용",
            command=self.recombine_apply
        ).pack(side="left", padx=6)

        body.columnconfigure(1, weight=1)
        self._refresh_recombine_expression()

        try:
            self._calculate_recombine_recommendation(show_status=False)
        except Exception as e:
            self.recombine_recommendation_var.set(
                f"추천 계산을 완료하지 못했습니다: {e}\n현재 입력값으로 수동 진행할 수 있습니다."
            )

    def _refresh_recombine_expression(self):
        try:
            weight = float(self.recombine_star_weight.get())
            expr = f"$Main$ + $Stars$ * {weight:g}"
        except Exception:
            expr = "$Main$ + $Stars$ * ?"
        if hasattr(self, "recombine_expression_var"):
            self.recombine_expression_var.set(expr)

    def _recombine_signature(self):
        return (
            self.recombine_star_weight.get().strip(),
            bool(self.recombine_rescale.get()),
        )

    def _invalidate_recombine_preview(self, *args):
        self.recombine_preview_signature = None
        self.recombine_preview_meta = None
        self._refresh_recombine_expression()

    def _recombine_params(self):
        return {
            "star_weight": float(self.recombine_star_weight.get()),
            "rescale_output": bool(self.recombine_rescale.get()),
        }

    def _format_recombine_recommendation(self, rec):
        vals = rec["recommended_values"]
        reasons = "\n".join(f"  • {x}" for x in rec.get("reasons", [])[:5])
        prior = rec.get("prior_stars_brightness_scale")
        effective = rec.get("effective_star_scale_vs_original_subtraction_layer")
        prior_text = (
            f"\nStars Processing Brightness={prior:g} → "
            f"추천 Recombine 적용 시 원본 Stars 대비 실질 약 {effective:g}"
            if prior is not None else
            f"\n예상 Recombine 별 가중치: {effective:g}"
        )
        return (
            f"추천 시작값: Star Weight={vals['star_weight']} / "
            f"Rescale={'ON' if vals['rescale_output'] else 'OFF'}"
            f"{prior_text}\n"
            f"{rec.get('notice')}\n"
            f"추천 근거:\n{reasons}"
        )

    def _calculate_recombine_recommendation(self, show_status=True):
        if not self._require_project():
            return None
        rec = recommend_recombine(self.project_dir)
        self.recombine_recommendation = rec
        self.recombine_recommendation_var.set(
            self._format_recombine_recommendation(rec)
        )
        if show_status:
            self.status_var.set("Recombine 추천 계산 완료")
        return rec

    def recombine_calculate_recommendation(self):
        try:
            self._calculate_recombine_recommendation(show_status=True)
        except Exception as e:
            messagebox.showerror("추천 계산 오류", str(e))

    def recombine_apply_recommendation(self):
        try:
            rec = self.recombine_recommendation or self._calculate_recombine_recommendation(False)
            vals = rec["recommended_values"]
            self.recombine_star_weight.set(str(vals["star_weight"]))
            self.recombine_rescale.set(bool(vals["rescale_output"]))
            self.status_var.set("Recombine 추천 시작값을 입력란에 적용했습니다. 미리보기로 확인하세요.")
        except Exception as e:
            messagebox.showerror("추천값 적용 오류", str(e))

    def recombine_preview(self):
        if not self._require_project():
            return
        try:
            params = self._recombine_params()
        except ValueError:
            messagebox.showerror("오류", "Star Weight 숫자 값을 확인하세요.")
            return

        signature = self._recombine_signature()

        def work():
            return preview_recombine(
                self.project_dir, self.cfg, **params
            )

        def done(result):
            jpg, preview_fits, meta = result
            self.recombine_preview_signature = signature
            self.recombine_preview_meta = meta

            clip = float(meta.get("max_highlight_clip_ratio", 0) or 0)
            clip_note = (
                f"주의: 최대 highlight clipping ratio={clip:.6f}"
                if clip > 0.001 else
                f"Highlight clipping ratio={clip:.6f}"
            )

            self.write(
                "\nPixel Math Recombine 미리보기 완료\n"
                f"Preview FITS: {preview_fits}\n"
                f"JPEG: {jpg}\n"
                f"Expression: {meta['expression']}\n"
                f"Command: {meta['pm_command']}\n"
                f"{clip_note}\n"
            )
            self.status_var.set("Recombine 미리보기 완료")
            self._open_preview(jpg)

            if clip > 0.001 and not params["rescale_output"]:
                messagebox.showwarning(
                    "하이라이트 확인",
                    "Recombine 미리보기에서 일부 highlight clipping이 감지되었습니다.\n\n"
                    "먼저 Star Weight를 낮춰 비교하는 것을 권장합니다.\n"
                    "Rescale Output은 전체 톤을 바꿀 수 있으므로 두 번째 선택지로 사용하세요."
                )

        self.run_bg(
            work,
            operation="Pixel Math Recombine 미리보기",
            on_success=done,
        )

    def recombine_apply(self):
        if not self._require_project():
            return
        try:
            params = self._recombine_params()
        except ValueError:
            messagebox.showerror("오류", "Star Weight 숫자 값을 확인하세요.")
            return

        if (
            self.recombine_preview_signature != self._recombine_signature()
            or not self.recombine_preview_meta
        ):
            messagebox.showwarning(
                "미리보기 필요",
                "현재 Recombine 설정과 동일한 값으로 미리보기를 먼저 확인하세요."
            )
            return

        ok = messagebox.askyesno(
            "Pixel Math Recombine 실제 적용",
            "확인한 미리보기 결과를 정식 Recombined FITS로 확정합니다.\n\n"
            f"Expression: {self.recombine_preview_meta['expression']}\n"
            f"Rescale: {params['rescale_output']}\n"
            f"Metadata: -nosum\n\n"
            "Main/Stars 원본 파일은 그대로 보존됩니다.\n진행할까요?"
        )
        if not ok:
            return

        def work():
            return apply_recombine(
                self.project_dir,
                self.cfg,
                confirmed=True,
                preview_meta=self.recombine_preview_meta,
                **params,
            )

        def done(result):
            project, output, payload = result
            self.recombine_preview_signature = None
            self.recombine_preview_meta = None
            self._show_project_task(
                project,
                f"Pixel Math Recombine 완료\n출력: {output}"
            )
            self.status_var.set("Pixel Math Recombine 완료")
            next_task = project["project"].get("next_task", {})
            self._show_apply_success(
                "Pixel Math Recombine",
                output,
                next_task.get("title"),
            )

        self.run_bg(
            work,
            operation="Pixel Math Recombine 실제 적용",
            on_success=done,
        )

    def _build_final_export_controls(self):
        self._clear_actions()

        project = load_project(self.project_dir)
        p = project["project"]
        current = p.get("current_file")
        target = p.get("target_name")
        base = final_basename(target)

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))

        title = ttk.Label(head, text="Final / Export", font=("", 10, "bold"))
        title.pack(side="left")
        self.help.tooltip(title, "final.what")
        ttk.Label(
            head,
            text="최종 결과 저장",
        ).pack(side="left", padx=(8,0))

        self.help.section_help_button(
            head,
            "Final / Export 도움말",
            [
                "final.what", "final.fits", "final.tiff",
                "final.png", "final.checksum", "final.deflate",
                "final.preview", "final.apply",
            ],
        ).pack(side="right")

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,8))

        def row_label(row, text, topic):
            w = ttk.Label(body, text=text, width=22)
            w.grid(row=row, column=0, sticky="w", pady=3, padx=(0,8))
            self.help.tooltip(w, topic)
            return w

        row_label(0, "현재 최종 이미지", "final.what")
        ttk.Label(
            body, text=str(current), wraplength=760
        ).grid(row=0, column=1, columnspan=3, sticky="w", pady=3)

        ttk.Label(body, text="최종 파일명", width=22).grid(
            row=1, column=0, sticky="w", pady=3, padx=(0,8)
        )
        ttk.Label(
            body, text=base, font=("Consolas", 10)
        ).grid(row=1, column=1, columnspan=3, sticky="w", pady=3)

        ttk.Separator(body, orient="horizontal").grid(
            row=2, column=0, columnspan=4, sticky="ew", pady=(6,6)
        )

        row_label(3, "32-bit FITS", "final.fits")
        ttk.Checkbutton(
            body, variable=self.final_export_fits
        ).grid(row=3, column=1, sticky="w", pady=3)
        ttk.Label(
            body, text=f"output\\fits\\{base}.fits"
        ).grid(row=3, column=2, columnspan=2, sticky="w", padx=(8,0))

        row_label(4, "FITS Checksum", "final.checksum")
        ttk.Checkbutton(
            body, variable=self.final_fits_checksum
        ).grid(row=4, column=1, sticky="w", pady=3)

        row_label(5, "16-bit TIFF", "final.tiff")
        ttk.Checkbutton(
            body, variable=self.final_export_tiff
        ).grid(row=5, column=1, sticky="w", pady=3)
        ttk.Label(
            body, text=f"output\\tiff\\{base}.tif"
        ).grid(row=5, column=2, columnspan=2, sticky="w", padx=(8,0))

        row_label(6, "TIFF Deflate", "final.deflate")
        ttk.Checkbutton(
            body, variable=self.final_tiff_deflate
        ).grid(row=6, column=1, sticky="w", pady=3)

        row_label(7, "16-bit PNG", "final.png")
        ttk.Checkbutton(
            body, variable=self.final_export_png
        ).grid(row=7, column=1, sticky="w", pady=3)
        ttk.Label(
            body, text=f"output\\png\\{base}.png"
        ).grid(row=7, column=2, columnspan=2, sticky="w", padx=(8,0))

        ttk.Label(body, text="미리보기 JPEG 품질", width=22).grid(
            row=8, column=0, sticky="w", pady=3, padx=(0,8)
        )
        ttk.Entry(
            body, textvariable=self.final_preview_quality, width=8
        ).grid(row=8, column=1, sticky="w", pady=3)

        ttk.Label(
            body,
            text="※ PNG/TIFF는 색상 프로파일 변환 없이 현재 픽셀 결과를 저장합니다.",
            wraplength=900,
        ).grid(row=9, column=0, columnspan=4, sticky="w", pady=(7,8))

        buttons = ttk.Frame(body)
        buttons.grid(row=10, column=0, columnspan=4, sticky="w")

        ttk.Button(
            buttons,
            text="미리보기",
            command=self.final_export_preview,
        ).pack(side="left", padx=(0,6))

        ttk.Button(
            buttons,
            text="승인 후 최종 저장",
            command=self.final_export_apply,
        ).pack(side="left", padx=6)

        ttk.Button(
            buttons,
            text="결과 폴더 열기",
            command=self.open_output_folder,
        ).pack(side="left", padx=6)

        body.columnconfigure(2, weight=1)

    def _final_export_options(self):
        return {
            "export_fits": bool(self.final_export_fits.get()),
            "export_tiff16": bool(self.final_export_tiff.get()),
            "export_png16": bool(self.final_export_png.get()),
            "tiff_deflate": bool(self.final_tiff_deflate.get()),
            "fits_checksum": bool(self.final_fits_checksum.get()),
            "preview_jpeg_quality": int(self.final_preview_quality.get()),
        }

    def final_export_preview(self):
        if not self._require_project():
            return

        try:
            quality = int(self.final_preview_quality.get())
        except ValueError:
            messagebox.showerror("오류", "미리보기 JPEG 품질 값을 확인하세요.")
            return

        def work():
            return preview_final_export(
                self.project_dir,
                self.cfg,
                preview_jpeg_quality=quality,
            )

        def done(result):
            jpg, meta = result
            self.final_preview_meta = meta
            self.final_preview_source = meta.get("input_file")

            clip = float(meta.get("max_highlight_clip_ratio", 0) or 0)
            clip_note = (
                f"주의: 최대 highlight clipping ratio={clip:.6f}"
                if clip > 0.001 else
                f"Highlight clipping ratio={clip:.6f}"
            )

            self.write(
                "\nFinal 미리보기 완료\n"
                f"JPEG: {jpg}\n"
                f"{clip_note}\n"
                "※ AutoStretch 없이 현재 Recombined 결과를 그대로 확인합니다.\n"
            )
            self.status_var.set("Final 미리보기 완료")
            self._open_preview(jpg)

            if clip > 0.001:
                messagebox.showwarning(
                    "Final 하이라이트 확인",
                    "최종 이미지에서 일부 highlight clipping이 감지되었습니다.\n\n"
                    "필요하면 이전 Recombine 단계의 Star Weight를 조정하거나 "
                    "외부 최종 편집에서 하이라이트를 다시 검토하세요."
                )

        self.run_bg(
            work,
            operation="Final 미리보기",
            on_success=done,
        )

    def final_export_apply(self):
        if not self._require_project():
            return

        try:
            options = self._final_export_options()
        except ValueError:
            messagebox.showerror("오류", "Final Export 숫자 값을 확인하세요.")
            return

        if not self.final_preview_meta:
            messagebox.showwarning(
                "미리보기 필요",
                "현재 Recombined 이미지의 Final 미리보기를 먼저 확인하세요."
            )
            return

        project = load_project(self.project_dir)
        current = project["project"].get("current_file")
        if str(current) != str(self.final_preview_meta.get("input_file")):
            messagebox.showwarning(
                "미리보기 다시 필요",
                "현재 프로젝트 파일이 Final 미리보기 이후 변경되었습니다.\n미리보기를 다시 실행하세요."
            )
            return

        selected = []
        if options["export_fits"]:
            selected.append("32-bit FITS")
        if options["export_tiff16"]:
            selected.append("16-bit TIFF")
        if options["export_png16"]:
            selected.append("16-bit PNG")

        if not selected:
            messagebox.showerror("오류", "FITS / TIFF / PNG 중 하나 이상을 선택하세요.")
            return

        ok = messagebox.askyesno(
            "Finalize + Export",
            "현재 Recombined 결과를 최종본으로 확정합니다.\n\n"
            f"생성 형식: {', '.join(selected)}\n"
            f"FITS Checksum: {options['fits_checksum']}\n"
            f"TIFF Deflate: {options['tiff_deflate']}\n"
            f"Base Name: {final_basename(project['project']['target_name'])}\n\n"
            "진행할까요?"
        )
        if not ok:
            return

        def work():
            return apply_final_export(
                self.project_dir,
                self.cfg,
                confirmed=True,
                preview_meta=self.final_preview_meta,
                **options,
            )

        def done(result):
            project, outputs, payload = result
            self.final_preview_meta = None
            self.final_preview_source = None

            lines = ["Final / Export 완료"]
            for key, value in outputs.items():
                if value:
                    lines.append(f"{key}: {value}")

            self._show_project_task(
                project,
                "\n".join(lines)
            )
            self.status_var.set("Final / Export 완료")

            out_text = "\n".join(
                str(v) for k, v in outputs.items()
                if k != "working_final_fits" and v
            )
            messagebox.showinfo(
                "기본 파이프라인 완료",
                "최종 저장이 완료되었습니다.\n\n"
                f"{out_text}"
            )

        self.run_bg(
            work,
            operation="Finalize + Export",
            on_success=done,
        )

    def open_output_folder(self):
        if not self._require_project():
            return
        path = Path(self.project_dir) / "output"
        try:
            path.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(path))
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            messagebox.showerror("폴더 열기 오류", str(e))

    def _validated_final_output_files(self):
        """Return verified exported user-facing files only when the project is truly EXPORTED."""
        if not self.project_dir:
            return []

        try:
            project = load_project(self.project_dir)
            p = project["project"]

            if p.get("current_state") != "EXPORTED":
                return []

            finalization = p.get("finalization") or {}
            if not finalization.get("exported", False):
                return []

            outputs = finalization.get("outputs") or {}

            # Only user-facing exports count toward button visibility.
            # The internal working FITS alone is not enough.
            verified = []
            for key in ("fits", "tiff16", "png16"):
                value = outputs.get(key)
                if value and Path(value).is_file():
                    verified.append(Path(value))

            return verified
        except Exception:
            return []

    def _final_result_folder_is_ready(self):
        return len(self._validated_final_output_files()) >= 1

    def _build_pipeline_complete_controls(self):
        self._clear_actions()

        head = ttk.Frame(self.action_box)
        head.pack(fill="x", padx=10, pady=(8,6))

        ttk.Label(
            head,
            text="보정 및 최종 저장 완료",
            font=("", 11, "bold"),
        ).pack(side="left")

        body = ttk.Frame(self.action_box)
        body.pack(fill="x", padx=10, pady=(2,10))

        files = self._validated_final_output_files()

        if files:
            ttk.Label(
                body,
                text=(
                    f"최종 출력 파일 {len(files)}개를 확인했습니다."
                ),
            ).pack(anchor="w", pady=(0,6))

            for path in files:
                ttk.Label(
                    body,
                    text=str(path),
                    wraplength=900,
                ).pack(anchor="w", pady=1)

            ttk.Button(
                body,
                text="최종 결과 폴더 열기",
                command=self.open_final_result_folder,
            ).pack(anchor="w", pady=(10,0))
        else:
            ttk.Label(
                body,
                text=(
                    "완료된 최종 출력 파일을 찾지 못했습니다. 상세 로그에서 Export 결과를 확인하세요."
                ),
                wraplength=900,
            ).pack(anchor="w")

    def open_final_result_folder(self):
        if not self._require_project():
            return

        files = self._validated_final_output_files()
        if not files:
            messagebox.showwarning(
                "최종 결과 없음",
                "완료된 최종 출력 파일을 확인할 수 없습니다."
            )
            return

        # All final exports live below the project's output folder.
        path = Path(self.project_dir) / "output"
        try:
            path.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(path))
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            messagebox.showerror("폴더 열기 오류", str(e))

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

    def _open_before_after_preview(
        self, before_path: Path, after_path: Path, *, crop_text: str = "",
        fallback_after: Path | None = None,
    ):
        """Show Parallax quick preview as a same-scale Before / After pair."""
        before_path = Path(before_path)
        after_path = Path(after_path)
        try:
            if not before_path.exists() or not after_path.exists():
                raise FileNotFoundError("Before/After 비교 파일을 찾지 못했습니다.")

            win = tk.Toplevel(self)
            win.title("Restoration 빠른 미리보기 · Before / After")
            win.transient(self)
            win.configure(bg=self.palette.get("bg", "#10141c"))

            outer = ttk.Frame(win, padding=14)
            outer.pack(fill="both", expand=True)
            images = ttk.Frame(outer)
            images.pack(fill="both", expand=True)

            before_img = tk.PhotoImage(file=str(before_path))
            after_img = tk.PhotoImage(file=str(after_path))
            max_each_w = max(320, int(self.winfo_screenwidth() * 0.43))
            max_h = max(320, int(self.winfo_screenheight() * 0.62))
            ratio = max(
                before_img.width() / max_each_w,
                before_img.height() / max_h,
                after_img.width() / max_each_w,
                after_img.height() / max_h,
                1.0,
            )
            factor = max(1, int(ratio))
            if factor < ratio:
                factor += 1
            if factor > 1:
                before_img = before_img.subsample(factor, factor)
                after_img = after_img.subsample(factor, factor)

            left = ttk.Frame(images)
            right = ttk.Frame(images)
            left.grid(row=0, column=0, sticky="nsew", padx=(0,6))
            right.grid(row=0, column=1, sticky="nsew", padx=(6,0))
            images.columnconfigure(0, weight=1)
            images.columnconfigure(1, weight=1)

            ttk.Label(left, text="Before · SPCC", font=("Segoe UI Semibold", 10)).pack(pady=(0,6))
            ttk.Label(left, image=before_img).pack()
            ttk.Label(right, text="After · Parallax", font=("Segoe UI Semibold", 10)).pack(pady=(0,6))
            ttk.Label(right, image=after_img).pack()

            note = "동일 영역 · 동일한 표시 Stretch · 실제 FITS는 Linear 상태 유지"
            if crop_text:
                note = f"{crop_text} · " + note
            ttk.Label(outer, text=note, style="Muted.TLabel").pack(anchor="center", pady=(10,4))
            ttk.Button(outer, text="닫기", command=win.destroy).pack(anchor="e", pady=(4,0))

            # Tk images must stay referenced for the lifetime of the window.
            win._preview_images = (before_img, after_img)
            win.update_idletasks()
            x = self.winfo_rootx() + max(20, (self.winfo_width() - win.winfo_width()) // 2)
            y = self.winfo_rooty() + max(20, (self.winfo_height() - win.winfo_height()) // 4)
            win.geometry(f"+{x}+{y}")
        except Exception as e:
            self.write(f"Before/After 비교창 표시 실패: {e}")
            if fallback_after and Path(fallback_after).exists():
                self._open_preview(Path(fallback_after))
            else:
                messagebox.showwarning("미리보기", f"Before/After 비교창을 열지 못했습니다.\n{e}")

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
