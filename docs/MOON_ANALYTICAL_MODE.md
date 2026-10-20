# ASA Moon · 분석형 달 사진 파이프라인 (실험적)

> 초기 구현: 2026-10 · Siril 1.4.4 + OpenCV + Astropy.
> 딥스카이 파이프라인과 독립적입니다. 목성/토성 영상 lucky-imaging 용도가 아닙니다.
> **최종 천체사진 품질은 자동 점수만으로 보장되지 않습니다.**

## 접근 경로

ASA GUI 실행 후 시작 화면의 **🌕 Moon 분석형** 버튼으로 전용 창을 엽니다.
또는 CLI에서 \`moon-analyze\` → 분석 계획 검토 → \`moon-run --yes\` 순서로 실행합니다.

기존 사용자의 원본 폴더나 원본 FITS/RAW는 **수정하거나 이동하지 않습니다.**
캘리브레이션이 없는 Light-only 촬영도 지원하며 없는 Dark/Bias/Flat을 가정하거나 생성하지 않습니다.

### Mode

| Mode | 입력 | 엔진 |
|---|---|---|
| \`single\` | 1장 | 달 표면 검출, 밝기·노이즈·색 편차 분석, 보수적 국부 대비 |
| \`stack\` | 동일 FOV 2장 이상 | 프레임 선명도 품질 선별 → 달 영상 기준 ECC 회전/이동 정렬 → 유효 픽셀 평균 |
| \`mosaic\` | 겹치는 달 패널 2장 이상 | ORB 특징점 → RANSAC 부분 아핀 → 패널 연결성 확인 → 경계 feather 합성 |

**모자이크에서 모든 패널의 연결을 확인하지 못하면 처리 중단합니다.**
서로 다른 배율·회전·노출이 심한 촬영에서는 수동 패널 그룹핑/정렬이 필요할 수 있습니다.
같은 구도 반복 컷이 있다면 먼저 해당 패널을 선별·스태킹하고, 대표 이미지를 모자이크 입력으로 사용하는 것이 안전합니다.

### CLI: 사용 예

Windows 터미널에서 ASA 저장소 폴더로 이동 후:

\`\`\`powershell
python app.py moon-analyze --mode stack --source "D:\AstroProjects\Astrophoto\BCTO90\20231228\Full" --pattern "*.CR3" --output "D:\AstroProjects\Moon\Full_Output"
python app.py moon-run --plan "D:\AstroProjects\Moon\Full_Output\Moon_analysis_plan.json" --output "D:\AstroProjects\Moon\Full_Output" --yes
\`\`\`

단일 파일은 \`--mode single --source "D:\...\_MG_0975.CR3"\` 형태.
모자이크 패널은 \`--mode mosaic\`과 패널만 들어 있는 별도 폴더 사용.

**모자이크 25장을 한꺼번에 처리하기 전에 입력 패널의 겹침 관계를 확인하세요.**
대량 RAW는 변환 시간과 메모리 사용량이 큽니다.
프레임이 4장 미만이면 노이즈 감소 효과가 제한됩니다.

## 출력

- \`Moon_analysis_plan.json\`: 입력별 품질 점수, 달 영역, 선택 제안 및 위험 알림
- \`Moon_combined_linear.fits\`: 합성/정렬 후 보정 전 선형 작업본
- \`Moon_final.fits\`: 보정 후 32-bit RGB 결과
- \`Moon_final_16bit.tif\`: 16-bit RGB 편집용 결과 (Photoshop/Lightroom)
- \`Moon_preview.png\`: 빠른 화면 검토용 8-bit 미리보기
- \`Moon_processing_report.json\`: 정렬 성공/실패, 파라미터, 육안 검사 목록

이미 결과물이 존재하면 **덮어쓰지 않고 중단**합니다. 다음 보정 시 별도 출력 폴더를 사용하세요.

## 분석 지표와 자동 조정

1. 달 표면의 가장 큰 밝은 영역을 찾습니다. 프레임 가득 찬 패널에서 마스크 감지는 어려울 수 있습니다.
2. 라플라시안 기반 상대 선명도와 배경 MAD 노이즈로 품질을 평가합니다.
3. 같은 구도 Stack에서는 최고 점수를 기준으로 지나치게 흐린 프레임을 보류합니다. 점수는 경험적 기준으로, 모든 촬영에 맞는 정답이 아닙니다.
4. 채널별 색 균형은 최대 ±15%로 제한하고, Moon CLAHE는 16%만 혼합합니다.
5. 정확한 PSF 추정이 불가능할 때 블라인드 디컨볼루션을 **자동으로 사용하지 않습니다.** 과한 크레이터 테두리·링잉 방지가 우선입니다.

Siril의 \`AutoStretch\`는 표시용이며 실제 FITS/TIFF 결과에 반영되지 않습니다. 출력된 TIFF를 실제 데이터 기준으로 확인하세요.

## 현재 범위 및 검증 한계

- 자동화는 **화질 측정 기반의 보수적 첫 결과**이며 인간의 미적 판단을 대체하지 않습니다.
- 원본 센서 포화 여부는 단순 화면 밝기/히스토그램으로 확정할 수 없습니다.
- 모자이크는 겹치는 특징점에 기반합니다. 넓은 빈 하늘, 반복 무늬, 적은 겹침, 광학 왜곡은 정렬을 실패시킬 수 있습니다.
- 완전 자동 중복 패널 클러스터링, 비선형 광학 왜곡, 타일 기반 대형 메모리 모자이크, 행성 동영상 lucky-imaging, 실시간 Siril GUI 컨트롤은 이 첫 버전 범위 밖입니다.
- 촬영 원본(예: BCTO90 2023-12-28 CR3 4장/25장)으로 정확한 정렬과 색상, 크레이터 구조에 대한 **실측 테스트가 필요합니다.**

## 검증

\`\`\`powershell
python -m pip install -r requirements.txt pytest
python -m pytest -q tests/test_moon_pipeline.py
\`\`\`

테스트는 인공 디스크/크레이터를 이용해 사진 분석, Stack 변환, 모자이크 실패 방지, 출력 안전성을 검증합니다. 실제 천체사진 검증은 별도로 진행해야 합니다.
