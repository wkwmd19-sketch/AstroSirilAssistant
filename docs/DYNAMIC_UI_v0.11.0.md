# Dynamic / Responsive UI v0.11.0

The previous fixed-height layout could hide lower controls or logs on displays
with limited vertical resolution.

v0.11.0 changes the desktop UI structure.

## Screen-aware startup size

The initial geometry is calculated from the active display dimensions and keeps
margins for window chrome / taskbar.

## Scrollable workflow area

All project/input/task controls live inside a vertically scrollable Canvas.
If a processing stage becomes taller than the available window, the user can
scroll instead of losing the bottom controls.

## Resizable log pane

Logs remain collapsed by default.

When opened, they are inserted as the lower child of a vertical PanedWindow.
The separator between workflow and logs can be dragged to give either side more
space.

## Responsive width

The inner workflow frame automatically follows the Canvas width when the user
resizes the main window.

## Error behavior

Existing behavior is retained:
- error -> log pane automatically opens
- operation progress remains visible
- logs can still be copied during processing
