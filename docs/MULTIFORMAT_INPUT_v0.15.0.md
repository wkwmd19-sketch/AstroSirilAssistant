# Multi-format Input v0.15.0

## Contract

The intake layer accepts supported single-image formats and normalizes them to a deterministic FITS processing contract while preserving the original source unchanged.

### Source families

- FITS: direct analysis; copied to immutable original + normalized project FITS
- Camera RAW: Siril `convertraw ... -debayer` in an isolated directory, then deterministic 32-bit FITS save
- TIFF/PNG: Siril supported-format load/save to FITS; linearity remains conservative/unknown unless stronger evidence exists
- JPEG: load/save to FITS but classified non-linear and lossy

## Safety invariants

1. Never modify the selected source file.
2. Always preserve a project copy in `input/original`.
3. Never register an incomplete normalization result as `current_file`.
4. RAW normalization must produce an explicit debayered FITS result. There is no ambiguous generic-loader fallback.
5. Keep source and normalization metadata in `input/metadata/source_metadata.json` and `project.yaml`.
6. Existing legacy FITS projects remain readable.

## RAW note

This single-image intake path debayers a RAW for post-processing convenience. A multi-frame deep-sky RAW sequence that needs calibration should use the sequence workflow so calibration can occur on CFA data before debayering.

## Runtime status

The existing FITS/SyQon pipeline has been user runtime-validated through Final Export. The new multi-format intake, especially CR3-to-FITS normalization, requires first Windows/Siril runtime validation in v0.15.0.
