# v0.4.1 Hotfix

## Fixed
Siril 1.4.4 checks for a `requires` command at the top of script input.
The single-FITS analysis path (`run_gui.bat`) sent commands through
`siril-cli -s -` without that line.

Result:
- Siril started normally.
- Siril reported that `requires` was missing.
- The script ended without running `load` / `jsonmetadata`.
- AstroSirilAssistant then reported that the metadata JSON did not exist.

v0.4.1 automatically inserts:

`requires 1.4.0`

as the first command for all stdin Siril scripts.

The old GUI title (`v0.3.3`) was also corrected.
