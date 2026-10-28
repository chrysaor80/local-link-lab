# OPUS M2 검토 처리

검토 대상 `127ea3232bd6a6dc9b8c1b54eca78b3e092127d7`. [원본 보고](OPUS_M2_REVIEW_REPORT.md)와 [원본 패치](m2-redteam-tests.patch)를 보존했다. OPUS 판정은 조건부 승인이다. 아래 수정본에 대한 별도 OPUS 승인을 뜻하지 않는다.

## 판단과 변경

| 지적 | 처리 | 근거·변경 |
|---|---|---|
| M2-01 / P2 | 채택 | E1에서 최초 ACK 보류 중 재시도가 ACK를 받고, E2에서 이미 ACK인 복원 상태도 일반 판정이 허용함을 직접 재현했다. 일반 데이터 정합성과 장애 전제를 분리해 검사한다. |
| M2-02 / P3 | 채택 | 기존 영구 JSON의 결함 사본에 artifact의 접수 전 baseline, DB ID, final=False, original_receipts를 보완했다. interim 재판정과 실행 전체의 final=True 위반 수가 다른 이유도 기록했다. |
| M2-03 / P3 | 채택 | 수정·미추적 입력이 있으면 실행을 거부한다. 시작·종료 시 pm path에서 실제 설치 APK를 읽어 빌드 파일과 SHA-256을 비교하고 정상·결함 사본 모두 기록한다. |
| M2-04 / P3 | 채택 | Controller JVM 초기 준비 대기를 10초에서 30초로 조정했다. 제품의 네트워크 제한 시간은 바꾸지 않았다. OPUS의 취소 회귀 테스트를 추가했다. |
| M2-05 / P3 | 목적 채택·방식 조정 | S01의 차단 관측 뒤 연결 복구와 명시적 재개를 함께 실행해 새 재시도 예산을 보장한다. 먼저 차단을 풀면 MUT02의 거짓 완료를 관측하기 전에 POS 저장이 진행될 수 있어 관측 순서는 유지한다. |
| M2-06 / P3 | 채택 | debug/release DEX와 aapt2로 해석한 binary manifest를 모두 검사한다. manifest에만 남은 receiver도 차단하며 Python -O에서도 확인한다. |

S03 유휴 변형은 접수 후와 재실행 후 PENDING·영수증 없음·POS 0건·submit 0회를 요구한다. 전경 worker의 사용자 중지 상태까지 관측한다. 사용자 중지를 무시하는 MUT03은 SENT_WHILE_PAUSED로 실패해야 한다. 이 결함은 종료 전에 발견해도 검출이며, 종료까지 실행했다고 주장하지 않는다.

commit 후 종료 변형은 신규 저장과 중복 재시도 ACK를 모두 before_ack 장벽에서 붙잡는다. 종료 전과 새 PID 재실행 후에 PENDING·POS 1건·원래 영수증·방출 ACK 0회를 확인한 뒤 장벽을 해제한다. 재시도 횟수 0을 요구하는 대신 재시도 응답도 막아 느린 실행기에서도 장애 창을 유지한다. 전제를 놓친 실행은 BLOCKED다.

## 실행과 한계

- 로컬 Python 26개 PASS: 실제 TCP의 재시도 ACK 보류, 단계별 판정, dirty checkout·설치 APK 불일치 거부 포함.
- 코어 JVM 19개, Controller JVM 7개 PASS. debug/release/계측 APK 빌드 PASS. DEX·manifest 검사 일반/`-O` PASS.
- 명세 검사: 시나리오 12개, 결함 계획 3개 PASS.
- 구현 `6c7187d`의 [수정본 CI·원본 재대조](../evidence/M2_REDTEAM_FIX.md) 완료: Android 외부 시나리오 6 PASS, MUT01~03 모두 KILLED. 실제 설치 APK 해시도 빌드 파일과 일치했다.
- 기존 M2·M3의 시나리오 PASS는 당시 하네스의 결과다. 그 결과가 S03의 강화된 전제를 검증했다고 소급해서 해석하지 않는다. 실기기·Windows LAN·촬영은 여전히 NOT_RUN이다.

`lab/m2_redteam_evidence.py`는 검토 당시의 after_commit 훅을 의도적으로 재현하는 역사적 스크립트다. 수정 후에도 E1·E2 결과가 유지되는 것이 정상이다. 새 장벽은 `lab.test_m2_redteam`과 Android 실행기·MUT03으로 확인한다. 공개 원본 패치와 보고서는 수정하지 않았다.
