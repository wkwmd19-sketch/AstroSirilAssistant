"""Headless state/command integration without real Siril or Astropy pixel I/O."""
from __future__ import annotations
import re
import subprocess
from pathlib import Path

import pytest

from astroauto.project import save_project, load_project
from astroauto.workflow import next_task_after_analysis
from astroauto.gradient import skip_gradient
from astroauto.spcc import skip_spcc
from astroauto.deblur import skip_deblur
from astroauto.denoise import skip_denoise, migrate_post_spcc_task
from astroauto.ghs import preview_ghs, apply_ghs, finish_ghs
from astroauto.star_separation import skip_star_separation
from astroauto.final_export import (
    preview_final_export, apply_final_export, migrate_ready_for_final_export,
)


def _make_project(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    f = root / 'input' / 'normalized' / 'single.fits'
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b'original-raw-normalized-fits-test-sentinel')
    p = {
        'target_name': 'MilkyWay',
        'target': {'category': 'MILKYWAY'},
        'current_file': str(f),
        'current_state': 'CALIBRATION_SKIPPED',
        'image_state': {
            'linearity': 'LINEAR', 'stretched': False,
            'gradient_corrected': False, 'color_calibrated': False,
        },
        'input_stage': {'source_stage': 'SINGLE_LIGHT'},
        'calibration': {'input_status': 'RAW_UNCALIBRATED', 'resolution': 'SKIPPED',
                        'checked': False},
        'capture': {'date': '2026-06-16'},
        'metadata': {},
    }
    project = {'project': p}
    p['next_task'] = next_task_after_analysis(project)
    (root / 'logs').mkdir(exist_ok=True)
    save_project(root, project)
    return root, f


def _fake_siril(config, commands, cwd=None, **kwargs):
    """Simulate Siril's output paths, not the image operation itself."""
    for cmd in commands:
        match = re.match(r'(save|savejpg|savetif|savepng)\s+"([^"]+)"', cmd)
        if not match:
            continue
        name, stem = match.groups()
        suffix = {'save': '.fits', 'savejpg': '.jpg',
                  'savetif': '.tif', 'savepng': '.png'}[name]
        dest = Path(stem)
        if not dest.suffix:
            dest = dest.with_suffix(suffix)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b'FAKE_SIRIL_OUTPUT')
    return subprocess.CompletedProcess(commands, 0, 'mocked Siril success', '')


def _stats(*args, **kwargs):
    return {'shape': [3, 16, 16], 'channels': {
        'R': {'highlight_clip_ratio': 0},
        'G': {'highlight_clip_ratio': 0},
        'B': {'highlight_clip_ratio': 0},
    }}


def test_all_optional_skips_then_ghs_and_direct_export(tmp_path, monkeypatch):
    from astroauto import ghs, final_export
    pdir, source = _make_project(tmp_path / 'project')
    original = source.read_bytes()
    assert load_project(pdir)['project']['next_task']['task_id'] == 'GRADIENT_CORRECTION'
    assert load_project(pdir)['project']['calibration']['checked'] is False
    project = skip_gradient(pdir)
    assert project['project']['next_task']['task_id'] == 'COLOR_CALIBRATION_SPCC'
    assert project['project']['image_state']['gradient_corrected'] is False
    with pytest.raises(ValueError):
        skip_gradient(pdir)

    project = skip_spcc(pdir)
    assert project['project']['next_task']['task_id'] == 'DEBLUR'
    assert project['project']['image_state']['color_calibrated'] is False
    assert project['project']['color_calibration']['skipped'] is True
    with pytest.raises(ValueError):
        skip_spcc(pdir)

    project = skip_deblur(pdir)
    assert project['project']['next_task']['task_id'] == 'DENOISE'
    assert project['project']['restoration']['skipped'] is True
    # Reopening a project must NOT mistake the explicit skip for the legacy order.
    project = migrate_post_spcc_task(pdir)
    assert project['project']['next_task']['task_id'] == 'DENOISE'

    project = skip_denoise(pdir)
    assert project['project']['next_task']['task_id'] == 'GHS_STRETCH'
    assert project['project']['denoise']['skipped'] is True
    with pytest.raises(ValueError):
        skip_denoise(pdir)

    monkeypatch.setattr(ghs, 'run_script', _fake_siril)
    monkeypatch.setattr(ghs, 'analyze_pixels', _stats)
    jpg, preview, preview_meta = preview_ghs(pdir, {}, 'AUTO_GHS')
    assert jpg.exists() and preview.exists()
    project, output, report = apply_ghs(pdir, {}, 'AUTO_GHS', confirmed=True)
    assert output.exists()
    assert project['project']['current_state'] == 'STRETCHED'
    assert project['project']['next_task']['task_id'] == 'GHS_REVIEW'
    project = finish_ghs(pdir)
    assert project['project']['next_task']['task_id'] == 'STAR_SEPARATION'

    project = skip_star_separation(pdir)
    assert project['project']['current_state'] == 'EXPORT_READY'
    assert project['project']['next_task']['task_id'] == 'FINALIZE_EXPORT'
    assert project['project']['separation']['skipped'] is True
    with pytest.raises(ValueError):
        skip_star_separation(pdir)

    monkeypatch.setattr(final_export, 'run_script', _fake_siril)
    monkeypatch.setattr(final_export, 'analyze_pixels', _stats)
    jpg, meta = preview_final_export(pdir, {})
    assert jpg.exists()
    project, outputs, report = apply_final_export(
        pdir, {}, export_fits=True, export_tiff16=True,
        export_png16=True, tiff_deflate=False, fits_checksum=False,
        confirmed=True, preview_meta=meta,
    )
    assert project['project']['current_state'] == 'EXPORTED'
    assert project['project']['next_task']['task_id'] == 'PIPELINE_COMPLETE'
    assert all(Path(outputs[k]).exists() for k in ('fits', 'tiff16', 'png16'))
    assert Path(outputs['fits']).stem == 'MilkyWay_final_Auto'
    assert source.read_bytes() == original


def test_old_starnet_skip_project_migrates_without_changing_pixels(tmp_path):
    pdir, source = _make_project(tmp_path / 'legacy')
    project = load_project(pdir)
    project['project']['current_state'] = 'STRETCHED'
    project['project']['image_state'].update({'linearity': 'NONLINEAR', 'stretched': True})
    project['project']['next_task'] = {
        'task_id': 'POST_STARNET_SKIPPED', 'title': 'legacy placeholder'}
    save_project(pdir, project)
    before = source.read_bytes()
    project = migrate_ready_for_final_export(pdir)
    assert project['project']['current_state'] == 'EXPORT_READY'
    assert project['project']['next_task']['task_id'] == 'FINALIZE_EXPORT'
    assert project['project']['separation']['skipped'] is True
    assert source.read_bytes() == before
    project = migrate_ready_for_final_export(pdir)
    assert project['project']['current_state'] == 'EXPORT_READY'
    assert source.read_bytes() == before


def test_final_export_refuses_linear_and_unconfirmed_state(tmp_path):
    pdir, source = _make_project(tmp_path / 'unsafe')
    project = load_project(pdir)
    project['project']['current_state'] = 'EXPORT_READY'
    project['project']['next_task'] = {'task_id':'FINALIZE_EXPORT'}
    save_project(pdir, project)
    with pytest.raises(ValueError):
        preview_final_export(pdir, {})


def test_ui_has_skips_and_final_export_handler():
    from ast import parse, walk, FunctionDef, ClassDef
    root = Path(__file__).resolve().parents[1]
    tree = parse((root/'gui.py').read_text(encoding='utf-8'))
    app = next(n for n in tree.body if isinstance(n, ClassDef) and n.name == 'App')
    methods = {n.name for n in app.body if isinstance(n, FunctionDef)}
    assert {'gradient_skip', 'spcc_skip', 'starnet_skip', 'final_export_preview',
            'final_export_apply', 'open_final_result_folder'} <= methods


def test_starnet_starless_stars_recombine_to_export(tmp_path, monkeypatch):
    """Second end-to-end route: separated stars; fake model/Siril output only."""
    from astroauto import star_separation, recombine, final_export
    from astroauto.starless_processing import skip_starless_processing
    from astroauto.stars_processing import skip_stars_processing
    pdir, original = _make_project(tmp_path / 'split-branch')
    p = load_project(pdir)
    p['project']['current_state'] = 'STRETCHED'
    p['project']['image_state'].update({'linearity':'NONLINEAR','stretched':True})
    p['project']['next_task'] = star_separation.make_star_separation_task()
    save_project(pdir,p)
    source_original = original.read_bytes()
    native_stars = pdir / 'temp' / 'stars_fake.fits'
    native_stars.parent.mkdir(parents=True,exist_ok=True)
    native_stars.write_bytes(b'FAKE_STARS_FITS')

    def fake_starnet(*args,**kwargs):
        return {'starless_fits':str(original),'stars_fits':str(native_stars),
                'native_starmask':None,'command':'stub starnet'}
    monkeypatch.setattr(star_separation,'_run_starnet_once',fake_starnet)
    monkeypatch.setattr(star_separation,'analyze_pixels',_stats)
    project, main, stars, _ = star_separation.apply_star_separation(pdir,{},confirmed=True)
    assert project['project']['next_task']['task_id'] == 'STARLESS_PROCESS'
    assert Path(main).is_file() and Path(stars).is_file()

    project = skip_starless_processing(pdir)
    assert project['project']['next_task']['task_id'] == 'STARS_PROCESS'
    project = skip_stars_processing(pdir)
    assert project['project']['next_task']['task_id'] == 'PIXEL_MATH_RECOMBINE'

    monkeypatch.setattr(recombine,'run_script',_fake_siril)
    monkeypatch.setattr(recombine,'analyze_pixels',_stats)
    jpg, preview, meta = recombine.preview_recombine(pdir,{},star_weight=1.0)
    assert jpg.is_file() and preview.is_file()
    project, output, _ = recombine.apply_recombine(pdir,{},star_weight=1.0,
                                                   confirmed=True,preview_meta=meta)
    assert output.is_file()
    assert project['project']['current_state'] == 'RECOMBINED'
    assert project['project']['next_task']['task_id'] == 'FINALIZE_EXPORT'

    monkeypatch.setattr(final_export,'run_script',_fake_siril)
    monkeypatch.setattr(final_export,'analyze_pixels',_stats)
    _, meta = final_export.preview_final_export(pdir,{})
    project, outputs, _ = final_export.apply_final_export(
        pdir,{},export_fits=True,export_tiff16=False,export_png16=True,
        tiff_deflate=False,fits_checksum=False,confirmed=True,preview_meta=meta)
    assert project['project']['current_state']=='EXPORTED'
    assert Path(outputs['fits']).exists() and Path(outputs['png16']).exists()
    assert original.read_bytes() == source_original


def test_skip_restore_then_apply_native_denoise_advances_to_ghs(tmp_path,monkeypatch):
    from astroauto import denoise
    pdir, source = _make_project(tmp_path/'native-denoise')
    skip_gradient(pdir)
    skip_spcc(pdir)
    skip_deblur(pdir)
    monkeypatch.setattr(denoise,'run_script',_fake_siril)
    monkeypatch.setattr(denoise,'analyze_pixels',_stats)
    project, output, _ = denoise.apply_denoise(pdir,{},engine='SIRIL_NATIVE',confirmed=True)
    assert project['project']['current_state'] == 'DENOISED'
    assert project['project']['next_task']['task_id'] == 'GHS_STRETCH'
    assert output.parent.name == '06_denoise'
    assert source.is_file()


def test_actual_no_frame_skip_goes_to_gradient_without_claiming_scan(tmp_path):
    from astroauto.calibration import skip_project_calibration
    pdir, source = _make_project(tmp_path / 'no-frames')
    project = load_project(pdir)
    p = project['project']
    p['current_state'] = 'INPUT_STAGE_CONFIRMED'
    p['calibration'] = {'input_status':'RAW_UNCALIBRATED', 'checked':False}
    p['next_task'] = next_task_after_analysis(project)
    assert p['next_task']['task_id'] == 'CHECK_CALIBRATION_FRAMES'
    save_project(pdir, project)
    original = source.read_bytes()
    project = skip_project_calibration(pdir)
    assert project['project']['next_task']['task_id'] == 'GRADIENT_CORRECTION'
    assert project['project']['calibration']['checked'] is False
    assert project['project']['calibration']['resolution'] == 'SKIPPED'
    assert source.read_bytes() == original
