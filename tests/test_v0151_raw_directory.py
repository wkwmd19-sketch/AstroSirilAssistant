from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile

from astroauto.input_formats import _normalize_raw
from astroauto.siril import SirilError


def test_convertraw_scans_staged_raw_in_explicit_siril_directory():
    with tempfile.TemporaryDirectory(prefix="siril dir space ") as td:
        root = Path(td)
        source = root / "camera original.CR3"
        source.write_bytes(b"intact source raw")
        destination = root / "normalized" / "input.fits"
        calls = []

        def fake_run(config, commands, cwd=None):
            assert cwd is not None
            staged = Path(cwd) / source.name
            assert staged.is_file()
            assert staged.read_bytes() == source.read_bytes()
            assert commands[0] == f'cd "{Path(cwd).resolve().as_posix()}"'
            assert commands.index("set32bits") < commands.index("setext fits")
            assert commands[-1].startswith("convertraw astroauto_raw -debayer ")
            assert '"-out=' in commands[-1]
            assert Path(cwd) != source.parent
            converted = Path(cwd).parent / "converted" / "astroauto_raw_00001.fits"
            converted.write_bytes(b"mocked RGB FITS")
            calls.append(tuple(commands))
            return SimpleNamespace(returncode=0, stdout="Conversion completed")

        def fake_save(config, converted, target):
            assert converted.name == "astroauto_raw_00001.fits"
            target.write_bytes(converted.read_bytes())
            return SimpleNamespace(returncode=0, stdout="saved")

        with patch("astroauto.input_formats.run_script", side_effect=fake_run), \
             patch("astroauto.input_formats._run_load_save", side_effect=fake_save):
            _normalize_raw({}, source, destination)
        assert len(calls) == 1
        assert source.read_bytes() == b"intact source raw"
        assert destination.read_bytes() == b"mocked RGB FITS"


def test_failed_raw_conversion_never_falls_back_or_modifies_source():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "IMG_4321.CR3"
        source.write_bytes(b"original raw")
        output = root / "normalized" / "test.fits"
        def fake_run(config, commands, cwd=None):
            assert commands[0].startswith('cd "')
            # Failed conversion generates no result, even if cli exits zero.
            return SimpleNamespace(returncode=0, stdout="No RAW files were found")
        with patch("astroauto.input_formats.run_script", side_effect=fake_run), \
             patch("astroauto.input_formats._run_load_save") as saver:
            try:
                _normalize_raw({}, source, output)
            except SirilError as error:
                assert "원본 RAW는 변경되지 않았습니다" in str(error)
            else:
                raise AssertionError("Missing converted RAW must fail")
            saver.assert_not_called()
        assert source.read_bytes() == b"original raw"
        assert not output.exists()
