# v0.15.1 FITS 분석 핫픽스 반영 기록

`main` 및 `v0.15.1-fits-hotfix`에는 기존에 제공된
`AstroSirilAssistant_v0.15.1_FITS_Hotfix.zip`의 수정이 적용되어 있습니다.
핫픽스를 다시 설치할 필요가 없습니다. 원래 전체 배포본은 `v0.15.1` 태그에 보존했습니다.

## 적용 내용

`astroauto/fits_analysis.py`의 `analyze_pixels`, `read_header_summary`에서
`fits.open(..., memmap=True)`를 `memmap=False`로 변경했습니다.
BZERO/BSCALE로 스케일링되는 FITS의 데이터에 접근할 때 발생한 오류를 대상으로 한 기존 수정입니다.
프로젝트 데이터나 다른 처리 로직은 변경하지 않았습니다.

## 확인한 범위

- 실제 전체 v0.15.1 원본 파일에 기존 핫픽스 스크립트를 적용했습니다.
- 변경은 위 두 인자에 한정되며 나머지 파일은 원본과 동일합니다.
- 제공된 핫픽스 테스트 2개(적용·백업·재실행, 다른 버전 거부)가 통과했습니다.
- 수정된 소스의 Python 구문 검사를 통과했습니다.
- 이 환경에는 Astropy가 없어 실제 스케일링 FITS 분석 테스트를 실행하지 않았습니다.
- Windows의 Siril/실제 CR3 디코딩과 GUI 파이프라인 실행은 확인하지 않았습니다.

```shell
git diff v0.15.1 v0.15.1-fits-hotfix -- astroauto/fits_analysis.py
```
