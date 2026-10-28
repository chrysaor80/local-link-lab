# M1 독립 검토 처리 기록

2026-10-28 · 구현 담당 Codex. OPUS의 판정은 **조건부 승인**이며, 아래는 구현 담당의 재현·수정 기록이다. 수정본에 대한 OPUS 재승인을 뜻하지 않는다.

원본 [보고서](OPUS_M1_REVIEW_REPORT.md)와 [재현 패치](m1-redteam-tests.patch)는 첨부 내용 그대로 보존했다. 검토 문서의 제안은 저장소 계약과 실행 결과를 대조해 채택했다.

## 수정 전 재현

고정 커밋 `ee67e2c62d844c538fd7cca26543ab3a103628fe`에 원본 패치를 적용했다. Linux, Python 3.12, JDK 17.0.21, Gradle 8.11.1, SDK 35, Robolectric 4.14.1/SDK 34, 실제 loopback TCP 환경이다. Android OS 실행과 구분한다.

| 실행 | 결과 | 해석 |
|---|---|---|
| `python -m unittest pos.test_m1_redteam -v` | 4개 중 2개 실패 | 시작 시점 DB ID 캐시와 `python -O` 검사 누락 재현. SQLite 잠금·부분 수신 제한은 통과 |
| `:core:test` (원본 패치 포함) | 13개 중 2개 실패 | 자체 timeout이 취소로 전달됨, 앞자리 0 IPv4 허용. 나머지 11개 통과 |
| `:app:testDebugUnitTest --tests '*ControllerRobolectricTest'` | 3개 중 1개 실패 | 정상 전송 통과. 실패한 probe 뒤 15초 동안 미전송, 명시적 재개 뒤 ACK. timeout UI 검사는 Robolectric 시간 특성상 통과하므로 반례 기각의 근거로 쓰지 않음 |

## 지적별 결정

| 항목 | 처리 | 구현과 검증 |
|---|---|---|
| M1-01 P2 | 채택·수정 | probe 오류를 별도 결과로 표시하고 영속 목적지의 worker로 이어감. 자체 deadline은 SocketTimeoutException, 상위 취소는 전파. 실패 후 자동 전송, 사용자 중지 유지, 다른 DB 변경 거부 후 기존 목적지 보존을 검사 |
| M1-02 P3 | 채택·수정 | hello/오류 ID는 현재 metadata를 읽음. 초기화 외 DB 연결은 mode=rw. 파일 교체 시 현재 ID/기존 ID 거부/새 ID ACK, 삭제 시 미생성·연결 종료 검사. DB 삭제 복구 보장은 추가하지 않음 |
| M1-03 P3 | 채택·수정 | verify_m1의 assert를 명시적 실패로 변경하고 증거 DB는 read-only로 열기. 일반 실행과 `-O` 모두 정상 증거 통과·orphan 행 거부 |
| M1-04 P3 | 채택·보강 | Controller 실제 Room/TCP 회귀, 시간 하한·상한·소켓 EOF, 상위 timeout 전파. 원문 오류 25개에 code/request_id 기대값을 추가하고 실제 TCP 오류 응답 22개도 대조 |
| M1-05 P3 | 채택·입력 계약 명확화 | ASCII IPv4 네 옥텟, 앞자리 0 금지, DNS 없이 바이트 주소 사용. 잘못된 입력은 worker 취소 전 거부. Android가 모호한 주소를 어떻게 해석했는지는 주장하지 않음 |
| M1-06 P3 | 운영 지침 채택·현상 미재현 | Windows 실행 예시에서 stdout/stderr를 파일로 돌림. 실제 QuickEdit 재현·비동기 로깅·디스크 정지 방지는 NOT_RUN/범위 밖 |
| M1-07 P3 | 채택·격리 | 계측 전용 Application은 매 실행 새 Room DB를 사용하며 일반 앱 DB를 열지 않음. 정상 왕복 POS, JVM 회귀 POS, Android 회귀 POS를 각각 별도 DB/포트로 실행 |

## 원본 패치에서 조정한 점

- 원본 hello 검사는 교체 후 hello ID로 주문을 보내면서 POS_MISMATCH도 기대했다. hello가 올바른 새 ID를 반환하면 주문은 성공해야 한다. 회귀판은 **교체 전 ID로 보내면 거부**, **hello가 반환한 현재 ID로 보내면 ACK**를 각각 확인한다.
- Controller 검사는 순간적인 runtime 문자열 대신 probe 순번/성공 여부를 기다린다. Room 관측 Flow 전달까지 기다리고, teardown에서 Controller scope를 닫는다. 최초 통합 실행에서 probe 완료 직후 settings Flow가 아직 전달되지 않은 테스트 대기 조건을 발견해 고쳤다.
- timeout 검사에 구체적 예외 종류와 경과 시간 범위를 추가했다. 상위 coroutine deadline은 여전히 취소이며 실제 소켓이 닫히는지 별도로 검사한다. 테스트 peer는 EOF에서 무한 반복하지 않는다.
- Android 두 회귀는 전용 POS 포트 18766을 사용한다. 정상 왕복 전체 행 1개 판정은 기존 포트 8765에서 별도 수행한다. JVM Controller 테스트 포트는 18765다.
- 주문 미확인 중 다른 DB로 전환하려는 경우, 실패한 연결 확인 중 사용자 중지 보존, 잘못된 주소 입력 뒤 정상 전송을 추가했다.

## 실행 및 남은 확인

로컬 Python 회귀 13개, 핵심 JVM 14개, Controller JVM 6개 통과. debug APK·계측 APK 빌드와 lintDebug 통과(기존 백업 설정 안내 경고는 유지). API 29 Android CI 결과는 커밋을 고정한 뒤 후속 기록에 연결한다. 실행하지 않은 계측 검사를 빌드 성공으로 대체하지 않는다.

M1 수정은 PR #1에 반영하고 M2 브랜치에도 통합한다. M2의 정상 시나리오 6개와 결함 사본 2개를 같은 수정본에서 다시 실행한다. 삼성 실기기/LAN, Windows QuickEdit 실제 재현, API 23, 실제 저메모리/전원 차단은 미검증이다.
