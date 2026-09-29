# v0.14.1 Windows BAT Launcher Hotfix

## Symptom

`run_gui.bat` 실행 시 Windows CMD가 정상 명령을 잘못 분리해서
`'on' is not recognized`, `'hon.exe' is not recognized` 같은 오류를 표시할 수 있었습니다.

## Cause addressed

v0.14.0의 공통 launcher는 Linux 스타일 LF line endings와 UTF-8 한국어 echo 문장을 포함했습니다.
Windows CMD의 codepage / batch parser 조합에 따라 안전하지 않을 수 있습니다.

## Fix

- Batch launchers are now ASCII-only.
- Every line uses Windows CRLF.
- `run_gui.bat` and `run_sequence_gui.bat` are standalone and use the same template.
- `.venv\Scripts\python.exe` is preferred.
- `py.exe -3` is the fallback.
- Error exits pause so the console message remains visible.
- Other distributed BAT files are normalized to CRLF too.
