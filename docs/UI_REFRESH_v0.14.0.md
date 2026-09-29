# Astro Graphite UI v0.14.0

## Goal

Tk/ttk stability is retained while removing the default-classic Windows look.

No external GUI framework is required.

## Shared design

Both `gui.py` and `sequence_gui.py` use `astroauto/ui_theme.py`.

Palette:
- deep navy/graphite background
- raised project/task cards
- cyan accent
- green success action
- muted secondary text
- dark input fields

Typography:
- Segoe UI
- Cascadia Mono for logs when available

## Shared interaction requirements

Both GUIs now use:
- resolution-aware startup size
- responsive width
- overflow-only scrolling
- collapsible/resizable log pane
- log copy
- progress indicator
- elapsed time
- action lock while processing
- automatic log expansion on errors

## Launchers

`run_gui.bat` and `run_sequence_gui.bat` now call the same `run_common.bat`.

This keeps:
- `.venv` preference
- `py -3` fallback
- missing-Python error handling
- non-zero exit pause behavior

identical between both launchers.
