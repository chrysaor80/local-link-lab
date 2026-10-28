# 폰 준비 전 에뮬레이터 검증

2026-10-28 Asia/Seoul. 사용자의 삼성 폰은 충전 중이고 기종/API는 미확인이다. [CI 40649335083](https://github.com/chrysaor80/local-link-lab/actions/runs/40649335083)에서 **Android 10/API 29 x86_64 에뮬레이터의 실제 APK·Room·TCP와 호스트 POS/SQLite**를 실행했다. 필수 검사와 시연 후보 생성이 모두 성공했다.

- [실제 앱 화면 캡처](m3-emulator.png): 정상 장애 시나리오 마지막 C07 복구 후의 상단 화면. 앱에 저장된 주문 1건이 보이며, 상세 주문·영수증은 아래로 스크롤하는 영역에 있다. 데이터 판정은 아래 원본 관측으로 별도 확인한다.
- [시연 APK·POS 묶음](https://github.com/chrysaor80/local-link-lab/actions/runs/40649335083/artifacts/12798568788).
- [원본 APK·로그·DB·계측 결과·화면](https://github.com/chrysaor80/local-link-lab/actions/runs/40649335083/artifacts/12799630898).
- [영구 관측 JSON](m3-emulator-observation.json), [Windows·폰 실행 안내](../DEMO_QUICKSTART.md).

## 실행 결과

| 실제 에뮬레이터 시나리오 | 결과·확인점 |
|---|---|
| S01 연결 차단 | PASS. 차단 후 **수동 재개**, 같은 ID·본문으로 POS 1건. recovered_by_resume=true |
| S02 첫 ACK 유실 | PASS. 추가 재개 없이 **자동 재시도**, POS 1건·최초 영수증. recovered_by_resume=false |
| S03 am kill | PASS. 이전 PID 소멸·다른 새 PID·PENDING/중지 복원 뒤 재개 |
| S03 force-stop | PASS. 명시적 재실행과 보관 상태 복원 |
| S03 POS commit 뒤 종료 | PASS. 종료 전과 재실행 후 PENDING·POS 1·ACK 방출 0, 이후 최초 영수증으로 확인 |
| C07 다른 POS DB | PASS. 다른 DB 제출·저장 0건을 확인하고 원래 DB로 복구 |

MUT01(ID 재발급), MUT02(ACK 전 완료), MUT03(사용자 중지 무시)는 모두 빌드·설치 후 지정된 실제 위반으로 KILLED됐다. 이후 정상 APK 재설치도 실제 설치 파일 해시로 확인했다. Python 51개(Windows/Linux 각각), 관련 후보·사건·빌드 검사 23개(-O), 코어 JVM 19개, Controller JVM 7개, Android 정상 4개·복구 2개가 통과했다.

## 소스·APK 대조

- 구현: `c44ae9d7604109370444841d912a3e7d5335a9fa`.
- CI 실제 checkout: `567457cd8baca7bee1b4f4ef6d9927f8e91b4e97` (PR 합성 merge).
- 양쪽 동일 tree: `e24545b377c2b7e734c3c45d8110f7e83df31e7c`.
- APK SHA-256: `fd9350152f9c00446c9e4c1aca7aa398846da8d50eb63dee002009a6edfb1928`. 빌드 stamp, 정상 실행 전후 설치, 결함 시험 뒤 정상 재설치, 후보 APK에서 일치했다.
- 원본 ZIP SHA-256: `aa5cfb0b11e7dee286b573acb0f35e206f4b0bb74d291947e7de9bb03d862201`.
- 후보 ZIP SHA-256: `987be0560f2f66072c448526c1c34ed953d31834979e5cd605cd0030a2e3494e`.

두 ZIP을 내려받아 해시를 확인하고, 후보 manifest의 모든 동봉 파일과 APK를 대조했다. 정상 6개·결함 3개의 각 관측을 접수 전 기준·DB ID·final 인자·단계 검사로 다시 판정해 기록과 일치함을 확인했다. 새 후보 조건도 내려받은 원본에서 다시 실행해 PID/사건 순서·stamp·정상 APK 복원 검사를 통과했다. 후속 커밋은 이 실행 근거와 설명만 추가한다.

## 앞선 중단과 남은 범위

첫 P3 수정 실행 [40648061750](https://github.com/chrysaor80/local-link-lab/actions/runs/40648061750)은 5 PASS·1 BLOCKED였으며 후보를 생성하지 않았다. [원본 실패 기록](m3-recheck-blocked.json)을 보존했다. 새 PID의 단발 조회를 제한 시간 내 관측으로 바꾸고 시작 응답·실패 logcat을 보존하도록 보강한 뒤 이번 실행을 별도로 확인했다. 과거 중단의 OS 내부 원인이 확정됐거나 재발하지 않는다고 주장하지 않는다.

OPUS가 승인한 것은 M2 수정본 6c7187d다. 후속 P3와 재실행 관측 보강은 구현 담당의 회귀·CI 검증이며 [처리 기록](../reviews/M2_RECHECK_RESPONSE.md)에 구분했다. 이 결과는 에뮬레이터의 emulator-nat 경로다. 삼성 기기의 제조사 동작·실제 Windows LAN/Wi-Fi·전원 차단·영상 촬영은 아직 확인하지 않았다. 화면 PNG는 영상 촬영 완료를 뜻하지 않는다.
