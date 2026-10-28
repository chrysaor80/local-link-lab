# M1 독립 검토 반영 후 M2 재검증

2026-10-28 UTC. 고정 구현은 `127ea3232bd6a6dc9b8c1b54eca78b3e092127d7`이다. [CI 40629074288](https://github.com/chrysaor80/local-link-lab/actions/runs/40629074288) 전체 SUCCESS. M1의 필수 수정과 회귀 검사를 통합한 같은 코드에서 기존 M2 장애·결함 검출을 다시 실행했다. OPUS의 수정본 또는 M2 재승인을 뜻하지 않는다.

CI는 PR merge `85d9da1d899852932582c3dee5129e33733e7db4`를 checkout했다. 구현 HEAD와 두 Git tree가 모두 `c8840faa918c0532f1a2974b3ec9974789e0e33a`로 같음을 확인했다. 외부 실행기의 source_commit에는 이 실제 checkout SHA가 남아 있다. 후속 문서 커밋은 구현을 변경하지 않는다.

| 검사 | 환경 | 결과 |
|---|---|---|
| POS·검사기 회귀 | Python 3.12, Ubuntu 24.04 / Windows 2022 | 각각 21개 PASS |
| 핵심 정책·TCP | JDK 17 JVM | 19개 PASS |
| Controller 회귀 | Robolectric 4.14.1/SDK 34, 실제 Room·loopback TCP | 6개 PASS |
| Android 정상 왕복·저장 | Android 10/API 29 x86_64 에뮬레이터 | 4개 PASS |
| Android 연결 복구 | 같은 에뮬레이터, 별도 POS/Room DB | 2개 PASS |
| M2 외부 장애 실행 | 실제 Android·Room·TCP·POS SQLite | 6개 PASS |
| 의도적 결함 사본 | 동일 정상 코드 기준 별도 빌드·설치·실행 | 2개 KILLED |
| APK | debug/release/계측 빌드, release DEX 제어 코드 제외 | PASS |

JUnit 미실행·실패·오류는 모두 0이었다. Android의 두 연결 복구 회귀는 연결 거부 및 5초 침묵 응답 뒤에, 사용자 재개 없이 기존 POS로 주문이 ACK되는지 검사한다. 정상 왕복의 접수 전 기준·Room 결과·POS 전체 행 1개/영수증 대조도 통과했다.

## 장애와 검출 결과

- S01: POS 저장 전 소켓 종료 후 동일 주문 1건과 ACK로 복구.
- S02: POS commit 뒤 최초 ACK 유실 후 최초 영수증 유지.
- S03_am_kill / S03_force_stop: 실제 PID 종료·새 PID를 관측하고 보관 주문과 사용자 중지를 복원, 명시적 재개 후 완료.
- S03_after_pos_commit: commit 후 ACK를 보류한 동안 force-stop, 재실행 뒤 같은 영수증·POS 1건.
- C07_resume: 다른 DB의 hello 응답으로 전송 중지, 그 DB에 submit 0회·저장 0건, 원래 DB 복원 후 완료.
- MUT01: 재시도 ID 재발급 사본이 `POS_EXTRA_ID`로 검출됨.
- MUT02: ACK 전 완료 사본이 `ACK_WITHOUT_POS`로 검출됨.

두 결함 사본 모두 빌드/설치 종료값 0, 시나리오 종료값 1이었다. 환경 실패를 결함 검출로 계산하지 않았다. 원본 artifact를 내려받아 정상 6개의 기준값·실제 SQLite 전체 행·최종 로컬 행·최초 영수증을 판정기로 다시 대조했다. 결함 사본의 diff 해시와 실제 관측 행으로 위 두 위반도 다시 계산했다.

## 근거와 한계

- [원본 APK·DB·사건/PID/명령·JUnit·결함 diff](https://github.com/chrysaor80/local-link-lab/actions/runs/40629074288/artifacts/12790658682)
- [영구 관측 JSON](m2-review-observation.json): source/HEAD/tree, 검사 개수, 정상 행, 결함 위반과 해시.
- [M1 지적별 처리와 원본 보존](../reviews/M1_RESPONSE.md), [수정 전 M2 기록](M2.md).

경로는 emulator-nat이며 삼성 실기기/LAN 검증은 아니다. S01은 소켓 종료이며 Wi-Fi 간섭 시험이 아니다. am kill은 백그라운드 PID 종료이며 실제 저메모리 재현이 아니다. API 23, 실제 저장 공간 고갈·전원 차단, 모든 UI 동시 조작, 업데이트·마이그레이션, Windows QuickEdit 실제 현상은 미검증이다. M3 배포 후보 조건·영상은 아직 별도 작업이다.
