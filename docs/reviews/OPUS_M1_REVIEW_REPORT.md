# OPUS M1 독립 검토·레드팀 보고서

| 항목 | 내용 |
|---|---|
| 저장소 | `chrysaor80/local-link-lab` |
| 검토 기준 스냅샷 | `ee67e2c62d844c538fd7cca26543ab3a103628fe` (요청서 지시대로 검토 중 변경하지 않음) |
| 실행 검증 구현 | `21e8ad5e3240287683aa1ef9abd0079f481fad76` |
| 요청서 | `docs/reviews/OPUS_M1_REDTEAM.md`, `docs/reviews/M1_REQUEST.md` |
| 작성 | OPUS (검토 담당). 구현 담당: Codex(아스트라) |
| 작성일 | 2026-10-28 |
| 첨부 | `m1-redteam-tests.patch` — 5개 파일, +385줄. `ee67e2c`에 `git apply --check` 통과 |

이 문서는 검토 의견과 재현 결과다. 저장소에 커밋·푸시하지 않았다. 제품 코드 수정은 구현 담당이 판단한다. 검토자 작업 환경의 경로와 이름은 공개 저장소 규칙에 맞춰 생략했다.

## 문서 구성

- **0. 최종 요약** — 2차 실행 결과를 반영한 최종 판정과 지적별 상태. **먼저 읽을 부분.**
- **1. 1차 보고** — 정적 검토와 독립 코드 실행 결과. 저장소 코드는 실행하기 전이다. 2차에서 바뀐 부분은 `[2차 갱신]`으로 표시했다.
- **2. 2차 보고** — 사용자가 실행 권한을 허용한 뒤 저장소 코드와 재현 테스트를 직접 실행한 결과.
- **3. 작업 경과** — 실패한 시도와 검토자 자신의 실수까지 포함한 시간순 기록.
- **부록 A** 재현 명령, **부록 B** 면접 질문.

---

## 0. 최종 요약

### 판정: 조건부 승인

- 정상 왕복(UI → Room commit → TCP → POS commit → ACK → Room 확인)과 판정기는 계약대로다. 주문 유실, 중복 저장, 잘못된 완료 표시를 만드는 반례는 찾지 못했다.
- **반드시 먼저 고칠 것: M1-01.** M1-03은 수정이 작아서 함께 고치기를 권한다.
- 조건: M2 장애 시연 전에 M1-01을 고치고 회귀 테스트를 넣는다.
- CI 실행 [40620268630](https://github.com/chrysaor80/local-link-lab/actions/runs/40620268630)은 검토자가 직접 열람하지 못했다. 결과는 저장소 문서의 기록에 의존했다.
- 이미 알려진 M2 항목(POS_MISMATCH 후 재개할 때 hello 재확인)은 중복 보고하지 않았다. M1-01은 이와 다른 경로지만 같은 상태 전이 코드이므로 함께 설계하기를 권한다.

### 지적별 최종 상태

| 번호 | 우선순위 | 분류 | 실행 여부 | 최종 상태 | 재현 테스트 |
|---|---|---|---|---|---|
| M1-01 | P2 | 확인된 결함 | Robolectric·JVM 실행. Android 기기는 NOT_RUN | **재현됨.** ① 연결 확인 실패 뒤 전경에서 전송 정지 ② 시간 초과 시 문구 고착(원인을 실시간 30/30으로 재현) | `ControllerRobolectricTest.failedProbeKeepsDeliveringToConfiguredPos`, `RedTeamTest.attemptDeadlineIsNotReportedAsCancellation`, `ControllerRecoveryTest`(NOT_RUN) |
| M1-02 | P3 | 확인된 위험 | 실행 | **재현됨.** hello는 DB A라고 답하는데 주문은 DB B가 처리. 다른 DB에 쓰이지는 않음 | `test_hello_reports_the_database_that_handles_orders` |
| M1-03 | P3 | 확인된 결함(언어 의미) | 실행 | **재현됨.** `python -O`일 때 고아 행이 있어도 "M1 PASS" | `test_verify_m1_rejects_orphan_row_even_with_python_optimize` |
| M1-04 | P3 | 검사 공백 | 정적 | M1-01이 기존 테스트에 걸리지 않은 원인 | 패치의 회귀 테스트 |
| M1-05 | P3 | 가설(일부 확인) | JVM 실행. Android NOT_RUN | **JVM에서 재현.** 앞자리 0 IPv4가 검증을 통과해 실제로 연결됨. Android 해석 방식은 미확인 | `RedTeamTest.ambiguousIpv4TextIsRejectedBeforeResolution` |
| M1-06 | P3 | 가설 | NOT_RUN (Windows 필요) | Windows 콘솔 QuickEdit 선택 시 POS 정지 가능성 | 없음 |
| M1-07 | P3 | 정적 위험 | 정적 | Android 테스트가 운영 DB와 컨트롤러를 공유해 격리되지 않음 | 없음 |
| 회귀 4종 | — | 결함 아님 | 실행 | **PASS.** POS 잠금 시 약 1초 안에 일시 오류 응답, 서버·클라이언트 모두 느린 송신이 제한 시간을 연장하지 않음, 다른 ID·다른 DB의 응답 무시 | `pos.test_m1_redteam` 2개, `RedTeamTest` 2개 |

### 1차 보고에서 2차로 바뀐 점

1. 1차의 "저장소 코드 전부 NOT_RUN"은 2차에서 사용자 허용 후 실행했다. 단 Android 에뮬레이터·기기와 Windows 실측은 여전히 NOT_RUN이다.
2. 1차의 "시간 초과 시 문구가 고착된다"는 표현이 너무 강했다. 실제로는 두 제한 시간 중 어느 쪽이 먼저 걸리느냐의 경합이다. 실시간 측정에서는 30/30 고착 쪽이었다. Robolectric의 PASS는 시뮬레이션 시계 때문에 생긴 착시다.
3. 패치가 바뀌었다. 1차는 3개 파일 256줄이었고, 최종은 5개 파일 +385줄이다. 추가된 것은 Robolectric 하네스, 원인 테스트, Android 테스트의 판정 결함 수정, `app/build.gradle.kts`의 테스트 의존성이다.
4. 1차의 "재현 테스트 사용법(모두 NOT_RUN)" 표는 2차 결과표로 대체한다.
5. 검토자의 테스트 실수(연결 확인 시간 초과 테스트가 너무 일찍 판정)를 2.4절에 공개했다.

### M1-01 최종 권고

1. `TcpTransport`가 자기 시도 제한 시간을 "취소"가 아닌 일반 시간 초과 오류로 바꿔 던지게 한다. 예: 내부에서 `withTimeoutOrNull`을 쓰고 `SocketTimeoutException("Attempt deadline")`을 던진다. 그러면 호출하는 쪽(연결 확인 분기, `DeliveryEngine`)이 모두 같은 방식으로 처리한다.
2. 연결 확인이 실패하면 블록을 끝내지 말고 기존 설정으로 전송 경로를 이어 간다. 실패 문구는 그대로 표시한다.
3. 참고: M2 브랜치 `70a4eca`는 전송 경로에 `DestinationVerifier`를 추가했지만 연결 확인 분기는 바꾸지 않았다. 그래서 M1-01은 그 브랜치에도 남아 있다. 이 판단은 diff만 읽은 정적 판단이며 실행하지 않았다.

---

## 1. 1차 보고 — 정적 검토와 독립 코드 실행 (저장소 코드 실행 전)

### 판정: 조건부 승인

정적 검토 기준으로 정상 왕복(UI → Room commit → TCP → POS commit → ACK → Room 확인)과 판정기는 계약대로입니다. 주문 유실, 중복 저장, 잘못된 완료 표시를 만드는 반례는 찾지 못했습니다.

- **반드시 먼저 고칠 것: M1-01.** "연결 확인"이 실패하면, 앱이 전경에 있어도 전송이 멈춘 채 다시 시작되지 않습니다.
- M1-03은 수정이 한 줄 수준이라 함께 고치기를 권합니다.
- 조건: M2 장애 시연 전에 M1-01 수정과 회귀 테스트(`ControllerRecoveryTest`)를 넣는 것.
- CI 실행 40620268630은 직접 열람하지 못했습니다. 결과는 저장소 문서의 기록에 의존했습니다.
- 알려진 M2 항목(POS_MISMATCH 후 재개 시 hello 재확인)은 중복 보고하지 않았습니다. M1-01은 그와 다른 경로입니다. 다만 같은 상태 전이 코드라 함께 설계하기를 권합니다.

### 실행한 것 / 못한 것 `[2차 갱신: 2절에서 저장소 코드를 실행함]`

- **실행 안 함 (NOT_RUN): 저장소 코드 전부.** POS 테스트, Kotlin core 테스트, Android 테스트, 검토자가 쓴 재현 테스트까지 포함입니다. 세션의 자동 권한 검사가 외부 저장소 코드 실행을 두 번 막았고, 우회하지 않았습니다.
- **실행한 것(검토자가 작성한 독립 코드만)**
  1. Kotlin 2.1.20 / coroutines 1.10.2 / JDK 21: M1-01과 같은 구조로 만든 테스트 1개 **PASS**. 시간 초과 후 상태가 "checking"으로 고착되고, 일반 `catch`에 걸리지 않으며, 새 주문의 깨우기 신호는 다음 실행 요청 전까지 아무도 받지 않음을 확인했습니다.
  2. JDK 21.0.12: `"127.000.000.001"` → 127.0.0.1, `"192.168.0.010"` → 192.168.0.10(10진수로 해석). `Character.isDigit('١')` = true.
  3. 재현 패치를 `ee67e2c`에 `git apply --check`로 적용 확인 — 정상.
- 저장소 commit·push는 없습니다. 재현 테스트는 `m1-redteam-tests.patch`에 있습니다. `[2차 갱신: 3개 파일 256줄 → 최종 5개 파일 +385줄]`

### 확인된 결함

#### M1-01 / P2 / 확인(정적 분석 + 같은 구조 실행) — 연결 확인 실패 후 전경 전송이 멈추고, 시간 초과 시 상태 문구가 고착됨 `[2차 갱신: 실제 코드로 재현. 문구 고착은 경합 의존]`
- **파일·줄**: `LinkApplication.kt:44-53`(연결 확인 분기), `:66`(CancellationException 재던짐), `:67`(일반 예외 처리), `:84`(새 주문 깨우기 신호). 같은 상황을 올바르게 처리하는 비교 대상은 `DeliveryEngine.kt:49-52`.
- **트리거 순서**
  1. POS가 확인된 상태에서 PENDING 주문이 있거나 새 주문을 받습니다.
  2. 사용자가 다른 주소로 "연결 확인"을 누릅니다.
  3. `collectLatest`가 기존 전송 작업을 취소합니다.
  4. 연결 확인이 실패합니다(연결 거부 / 5초 시간 초과 / 다른 DB라서 변경 거부).
  5. 블록이 그대로 끝나고, 전송 작업은 다시 시작되지 않습니다.
- **기대와 실제**
  - 기대: 확인된 기존 POS로 전송이 계속되거나, 전송이 멈췄다는 사실이 표시됩니다.
  - 실제: 앱이 전경에 있는 동안 PENDING과 새로 접수한 주문이 전송되지 않습니다. `wake.trySend`를 받을 작업이 없습니다.
  - 5초 시간 초과(`TimeoutCancellationException`)는 `:66`에서 재던져집니다. 그래서 실패 문구가 나오지 않고 **"POS 연결 확인 중"으로 고착**됩니다. `[2차 갱신: 내부 소켓 제한과의 경합. 실시간 30/30 고착]`
  - 복구 방법은 "전송 재개"를 누르거나 앱을 백그라운드로 보냈다가 돌아오는 것뿐입니다.
- **깨지는 규칙**: I05 "START 시 단일 worker 시작(user_paused면 시작 안 함)". 사용자 중지가 아닌데 worker가 없습니다.
- **최소 재현**: 패치의 `ControllerRecoveryTest`. 두 테스트 모두 현재 FAIL 예상. `[2차 갱신: Robolectric·JVM 테스트 추가]`
- **권고** `[2차 갱신: 0절의 최종 권고가 우선]`
  - 연결 확인 실패 경로에서 `TimeoutCancellationException`을 따로 잡습니다. `ensureActive()`로 부모 취소 여부를 확인한 뒤 실패 문구를 설정합니다.
  - 그다음 `return` 대신 기존 설정으로 전송 경로를 이어 갑니다.

#### M1-03 / P3 / 확인(언어 의미) — `verify_m1.py`가 `assert`에 의존
- **파일·줄**: `scripts/verify_m1.py:13-19`.
- **트리거**: `python -O`로 실행하거나 `PYTHONOPTIMIZE`가 설정되어 있으면 assert가 모두 제거됩니다. 그러면 고아 행이 있어도 "M1 PASS"를 출력하고 종료 코드 0을 냅니다.
- **영향 범위**: CI는 이 설정을 쓰지 않으므로 기록된 M1 증거는 영향을 받지 않습니다.
- **최소 재현**: `VerifierFailClosedTest`(`-O` 경우에 현재 FAIL 예상).
- **권고**: 명시적인 조건 검사와 `sys.exit(1)`로 바꿉니다.

### 정적으로 발견한 위험

#### M1-02 / P3 — hello가 시작 시점에 캐시한 DB ID를 보고함
- **파일·줄**: `server.py:58-59`(`self.store.db_id`) 대 `store.py:37`(요청마다 metadata를 다시 읽음). `store.py:27`의 `sqlite3.connect`는 파일이 없으면 새로 만듭니다.
- **트리거**: POS 실행 중 DB 파일이 교체되거나 삭제되는 경우.
- **기대와 실제**
  - 안전성은 유지됩니다. 주문은 POS_MISMATCH로 거부되고 다른 DB에 쓰이지 않습니다.
  - 하지만 hello는 이미 서비스되지 않는 DB를 "확인됨"으로 보고합니다.
  - 파일이 삭제된 경우에는 빈 DB 파일이 생기고, 모든 주문이 영구히 TEMPORARY_UNAVAILABLE이 됩니다. 앱은 이를 일시적 장애로만 봅니다.
  - DB 교체·삭제는 계약상 보장 밖이므로 P3입니다. 진단 일관성의 문제입니다.
- **최소 재현**: `test_hello_reports_the_database_that_handles_orders`(현재 FAIL 예상).
- **권고**: hello도 트랜잭션 안에서 metadata를 읽게 합니다. DB는 `file:...?mode=rw` URI로 열어 파일이 없으면 오류가 나게 합니다.

#### M1-04 / P3 — 검사 공백 (M1-01이 걸리지 않은 원인)
- 컨트롤러 수준의 테스트가 없습니다. 연결 확인 실패, 새 주문, 일시 중지·재개가 겹치는 경우를 검사하지 않습니다.
- `TcpTransportTest.kt:27-40`은 실패 여부만 봅니다. 즉시 실패하는 잘못된 구현도 통과합니다.
- 원문 예제는 유효/무효만 판정합니다. POS가 각 오류에 어떤 코드로 응답하는지, request_id를 되돌려주는지 null로 주는지는 검사하지 않습니다. 클라이언트는 이 값에 따라 NEEDS_ATTENTION으로 갈지 재시도할지가 갈립니다.
- **권고**: 패치의 회귀 테스트를 추가하고, 원문 예제에 `expected_code`와 `expected_request_id` 항목을 넣습니다.

#### M1-07 / P3 — Android 테스트가 격리되지 않음
- **파일·줄**: `RoundTripTest.kt:18-21`이 운영용 DB(`local-link.db`, `LinkApplication.kt:18`)와 Application의 컨트롤러를 그대로 씁니다.
- **문제**
  - 깨끗한 CI 에뮬레이터에서는 괜찮습니다.
  - 다시 쓰는 기기(사용자의 삼성 폰)에서는 기존 PENDING 주문 때문에 POS_MISMATCH로 멈추거나, 이전 설정 때문에 대기 조건이 바로 통과할 수 있습니다.
  - 새 Android 테스트를 추가하면 `verify_m1`의 "POS 행 정확히 1건" 검사가 깨집니다.
- **권고**: 실행 전에 `pm clear`를 하고, 테스트 클래스마다 별도의 POS DB를 씁니다.

### 추가 검증이 필요한 가설

#### M1-05 / P3 — IPv4 검증을 통과한 문자열이 플랫폼 리졸버로 넘어감 `[2차 갱신: JVM에서 재현]`
- **파일·줄**: `TcpTransport.kt:19`(`Char::isDigit`, 앞자리 0 허용), `:27`(`InetSocketAddress(String)`).
- **확인된 것**: 데스크톱 JDK 21은 앞자리 0을 10진수로 읽습니다.
- **확인 안 된 것**: Android에서 8진수로 읽거나 DNS 조회로 넘어가는지는 모릅니다. 직접 확인한 근거가 없습니다(확신도 중).
- 잘못된 입력에 대한 오류 문구가 "Failed requirement."로만 나옵니다.
- **권고**: ASCII 숫자만 허용하고 앞자리 0을 금지합니다. 주소는 `InetAddress.getByAddress(byte[4])`로 만들고, 검증은 `connect()`에서 합니다.

#### M1-06 / P3 — Windows 콘솔 QuickEdit 선택 상태에서 POS 전체가 멈출 수 있음
- **파일·줄**: `server.py:67`(이벤트 루프 위에서 동기 `print`).
- **가설**: Windows 콘솔에서 로그 줄을 선택하면 콘솔 출력이 막힙니다. 그러면 이벤트 루프 전체가 정지하고, 클라이언트는 시간 초과 후 재시도 한도에 걸립니다. 안전성은 유지됩니다. Windows 실측은 하지 않았습니다(확신도 중상).
- **권고**: 로그를 파일이나 백그라운드 스레드로 쓰거나, 시연 절차에 출력 리디렉션을 명시합니다.

### 다섯 경계 요약

| 경계 | 결론 |
|---|---|
| 1. 접수와 완료 | 반례 없음. ACK는 요청 ID·DB가 맞고 상태가 PENDING일 때만 적용되며, UI는 Room 상태에서 만듭니다 |
| 2. 수명과 사용자 조작 | 단일 worker, 사용자 중지 유지, 취소와 재시도 구분은 정상. **M1-01** |
| 3. 목적지와 중복 방지 | 다른 DB에 쓰지 않음, 동시 중복과 ID 충돌은 정상. M1-02 |
| 4. 통신과 자원 종료 | 클라이언트 5초, 서버 수신 5초 / 쓰기 1초, 무관한 응답 미적용 모두 정상(회귀 테스트 제공). M1-05 |
| 5. 검사의 신뢰성 | POS 전체 행과 고아 행 비교, 미실행 표기 모두 정직함. M1-03 / 04 / 07 |

### 재현 테스트 사용법 `[2차 갱신: 아래 "모두 NOT_RUN" 표는 2절 결과로 대체. 최종 명령은 부록 A]`

| 테스트 | ee67e2c에서 예상 결과 |
|---|---|
| `pos.test_m1_redteam`: busy → TEMPORARY 응답, 느린 송신 데드라인 | 회귀 테스트, PASS |
| `pos.test_m1_redteam`: hello 캐시(M1-02), `-O` 검증기(M1-03) | FAIL |
| `RedTeamTest`: 느린 송신 데드라인, 무관한 응답 | 회귀 테스트, PASS |
| `RedTeamTest`: 앞자리 0 IPv4(M1-05) | 권고 동작 테스트, FAIL |
| `ControllerRecoveryTest` 2개(M1-01) | FAIL. 별도의 새 POS DB 필요 |

---

## 2. 2차 보고 — 직접 실행 결과

사용자가 실행 권한을 허용한 뒤 저장소 코드와 재현 테스트를 직접 실행했다. M1-01·02·03·05의 4건은 예상대로 재현됐고 판정은 **조건부 승인** 그대로다. Android 에뮬레이터·실기기 테스트는 실행 환경 제약으로 돌리지 못했다(2.5절).

### 2.1 실행 환경

| 구성 | 버전 |
|---|---|
| Python | 3.13.17 (CI는 3.12) |
| Gradle | 저장소 wrapper 8.11.1 |
| JDK | Temurin 17.0.21 (CI와 같은 17). 1차 독립 하네스는 JDK 21.0.12 + Gradle 8.14.3 |
| Android SDK | platform 35, build-tools 35.0.0 |
| Robolectric | 4.14.1, `@Config(sdk = [34])` |
| 에뮬레이터 | 사용 불가 (`/dev/kvm` 없음, CPU 가상화 플래그 없음) |

### 2.2 기존 테스트 (기준선)

| 대상 | 환경 | 결과 |
|---|---|---|
| POS 테스트 (`pos.test_pos`) | Python 3.13 | 7/7 PASS |
| JVM 코어 테스트 (`:core:test`) | 저장소 Gradle 8.11.1 + JDK 17.0.21 | 9/9 PASS |
| APK 빌드 (`:app:assembleDebug`) | 같은 환경 + Android SDK 35 | 성공 (`app-debug.apk` 생성) |

### 2.3 재현 테스트 결과

| 지적 | 테스트 | 결과 |
|---|---|---|
| **M1-01 (전송 멈춤)** | 실제 `LinkController`·`Repository`·Room·`TcpTransport` + 실제 POS 프로세스 (Robolectric으로 JVM에서 실행) | **FAIL (재현).** 연결 거부로 "연결 확인"이 실패한 뒤(`확인 필요: Connection refused`), 새 주문이 앱 전경 상태에서 15초간 전송되지 않음. "전송 재개"(`pause(false)`)를 누르자 바로 전송됨(`deliveredAfterResume=true`) |
| 위 테스트의 대조군 | 같은 하네스에서 정상 주문 | PASS (하네스가 제대로 동작함을 확인. POS 로그에 commit 기록) |
| **M1-01 (문구 고착)** | 실제 `TcpTransport`, 실시간 단일 스레드 디스패처, 침묵 서버 | **FAIL (재현).** 30번 중 30번 시간 초과가 `TimeoutCancellationException`으로 올라옴. 연결 확인 분기는 이 예외를 다시 던지므로 "POS 연결 확인 중"이 그대로 남음 (`attemptDeadlineIsNotReportedAsCancellation`) |
| **M1-02** | 실행 중 POS의 DB 파일 교체 후 hello와 submit | **FAIL (재현).** hello는 DB A라고 답하는데 주문은 DB B가 처리함(POS_MISMATCH). 다른 DB에 주문이 쓰이지는 않음 |
| **M1-03** | 고아 행이 있는 증거로 `verify_m1.py` 실행 | **FAIL (재현).** `-O`일 때 "M1 PASS"를 출력하고 종료 코드 0. `-O` 없이는 정상적으로 실패함 |
| **M1-05** | 앞자리 0이 붙은 IPv4 (`127.000.000.001`) | **FAIL (재현).** 검증을 통과해 실제로 연결된 뒤 300ms 시간 초과. Android에서 어떻게 해석되는지는 아직 모름 |
| 회귀 테스트 4개 | POS 잠금 시 약 1초 안에 일시 오류 응답 / 서버 쪽 느린 송신 / 클라이언트 쪽 느린 송신(500ms 제한에 0.649초 종료) / 다른 ID·다른 DB의 응답 무시 | 4개 모두 PASS (결함 아님) |

### 2.4 바로잡을 점

- **"문구 고착" 표현을 고친다.** 1차 보고에서 "항상 고착된다"고 쓴 것은 너무 강했다.
  - `TcpTransport`에는 제한 시간이 두 개 있다. 외부 `withTimeout`(5초)과, 각 읽기마다 남은 시간으로 다시 설정하는 내부 소켓 `soTimeout`(약 5초)이다.
  - 외부 것이 먼저 걸리면 `TimeoutCancellationException`이 되어 문구가 고착된다. 내부 것이 먼저 걸리면 일반 예외가 되어 "확인 필요"로 정상 표시된다.
  - 실시간 단일 스레드에서는 30번 모두 외부 것이 먼저 걸렸다.
  - Robolectric은 메인 스레드 시계를 시뮬레이션하므로 실시간인 내부 것이 항상 이긴다. 그래서 Robolectric에서는 PASS가 나왔고(6.07초에 종료), 이건 테스트 환경의 착시다.
  - Android 기기에서는 시간 초과 신호가 메인 스레드 Handler로 전달되므로, 메인 스레드 지연에 따라 드물게 반대로 나올 수 있다. 기기 실측은 NOT_RUN이다.
  - 그래서 전송 계층에서 원인을 직접 확인하는 테스트(`attemptDeadlineIsNotReportedAsCancellation`)를 추가했다.
- **검토자 테스트의 실수.**
  - 처음 돌린 Robolectric 연결 확인 시간 초과 테스트는 확인이 시작되기도 전(1.46초)에 판정했다. "busy가 아님" 조건이 연결 확인 시작 전에 이미 참이었기 때문이다.
  - 그 FAIL은 무의미하므로 결과에서 뺐고, 확인 시작(busy=true)을 먼저 기다리도록 고쳤다.
  - 같은 실수가 Android `ControllerRecoveryTest`에도 있었다(아무것도 확인하지 않고 통과할 수 있었음). 함께 고쳤다.

### 2.5 실행하지 못한 것

- **Android 에뮬레이터와 실기기 테스트(`ControllerRecoveryTest`).** 환경에 KVM이 없고 CPU 가상화 기능도 꺼져 있어 에뮬레이터를 띄울 수 없다. 같은 컨트롤러 동작을 Robolectric으로 대신 확인했다.
- **M1-06 (Windows 콘솔 정지).** 실행 환경이 Linux라 확인할 수 없다.
- **CI 실행 기록 열람.** 검토자 세션에서는 이 저장소를 GitHub API로 조회할 수 없어 보지 못했다.

### 2.6 참고 사항

- `codex/m2-fault-verification` 브랜치의 새 커밋 2개(`1ac3507`, `70a4eca`)와 PR #2는 검토자가 아니라 구현 담당 쪽 작업이다. 검토자는 이 저장소에 읽기 권한만 있어 커밋·푸시·PR 생성을 하지 않았다.
- 검토 기준은 요청서 지시대로 `ee67e2c`로 유지했다. M2 브랜치는 diff만 읽었다(0절 권고 3).
- 실행에 쓴 POS 프로세스는 모두 종료했다. 모든 실행은 검토자 쪽 임시 작업 사본에서만 했다.
- Robolectric 하네스 때문에 패치가 `app/build.gradle.kts`에 테스트 의존성을 추가한다. `testImplementation`으로 `junit 4.13.2`, `robolectric 4.14.1`, `androidx.test:core 1.6.1`을 넣고 `testOptions.unitTests.isIncludeAndroidResources = true`를 설정한다. 제품 코드가 아니므로 채택 여부는 구현 담당이 판단한다.

---

## 3. 작업 경과 (시간순)

1. 문서·Kotlin 코어·Android 앱·POS 코드를 요청서 순서대로 읽었다.
2. 기존 POS 테스트로 기준선을 확인하려 했으나, 세션의 자동 권한 검사가 외부 저장소 코드 실행을 막았다. 우회하지 않고, 재현 테스트를 파일로만 작성했다. Kotlin/Java 언어 동작은 검토자가 직접 쓴 독립 코드로만 확인했다.
3. 독립 하네스 빌드 중 Maven Central이 429(요청 과다)를 반환했다. 대부분의 의존성이 캐시돼 있어 한 번 재시도로 해결했다.
4. 독립 코드로 "collectLatest 안의 연결 확인" 구조에서 전송 시간 초과가 상태 문구를 고착시키고, 새 주문의 깨우기 신호를 받을 작업이 없어진다는 점을 확인했다.
5. 재현 테스트를 임시 작업 사본에 작성하고 패치로 묶은 뒤 `ee67e2c`에 적용되는지 확인했다(1차 보고).
6. 사용자가 실행 권한을 허용했다. POS 기준선 7/7 PASS. POS 재현 테스트 4개 중 회귀 2개 PASS, M1-02·M1-03은 예상대로 FAIL.
7. JVM 코어: 기존 9/9 PASS. 재현 테스트는 회귀 2개 PASS, M1-05는 예상대로 FAIL.
8. KVM이 없어 Android 에뮬레이터를 쓸 수 없었다. JDK 17과 Android SDK 35를 설치하고 Robolectric 하네스를 구성했다.
9. Robolectric 첫 실행에서 대조군을 포함한 3개가 모두 실패했다. 원인은 Robolectric이 Android 런타임 jar를 내려받다 Maven 429를 맞은 것이다. 제품 결함이 아니라 하네스 문제였다. jar 캐시를 확인한 뒤 재실행했다.
10. 재실행 결과 대조군 PASS, 전송 정지 테스트 FAIL(재현). 연결 확인 시간 초과 테스트는 1.46초에 FAIL했지만 판정 시점 결함으로 무효 처리하고 고쳤다. Android 테스트도 같이 고쳤다.
11. 수정 후 Robolectric 시간 초과 테스트는 PASS(6.07초)였다. 시뮬레이션 시계 착시로 판단하고, 실제 `TcpTransport`를 실시간으로 30회 측정했다. 30/30 `TimeoutCancellationException`.
12. 저장소 빌드 기준선을 확인했다(`:core:test` 9/9, `:app:assembleDebug` 성공).
13. 원인 테스트 `attemptDeadlineIsNotReportedAsCancellation`을 추가했다. 예상대로 FAIL.
14. 최종 패치(5개 파일, +385줄)를 다시 만들고 `ee67e2c` 적용을 확인했다. 실행 프로세스를 정리했다(2차 보고).

---

## 부록 A. 재현 명령

```bash
git apply m1-redteam-tests.patch
```

```bash
python -m unittest pos.test_m1_redteam -v
```

Robolectric 테스트(`ControllerRobolectricTest`)를 돌리기 전에, 별도 터미널에서 18765 포트로 새 POS를 띄워 둔다.

```bash
python -m pos.server --db artifacts/rt-pos.db --port 18765
```

```bash
./gradlew :core:test :app:testDebugUnitTest --tests '*RedTeamTest' --tests '*ControllerRobolectricTest'
```

Android 계측 테스트는 에뮬레이터나 기기가 필요하다. `verify_m1.py`의 1행 검사와 섞이지 않도록 별도의 새 POS DB(127.0.0.1:8765)를 쓴다.

```bash
./gradlew :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=dev.locallinklab.app.ControllerRecoveryTest
```

| 테스트 | ee67e2c에서 기대 결과 | 검토자 실행 |
|---|---|---|
| `pos.test_m1_redteam` 회귀 2개 | PASS | PASS |
| `pos.test_m1_redteam` M1-02, M1-03 | FAIL | FAIL (재현) |
| `RedTeamTest` 회귀 2개 | PASS | PASS |
| `RedTeamTest.attemptDeadlineIsNotReportedAsCancellation` (M1-01 원인) | FAIL | FAIL (재현) |
| `RedTeamTest.ambiguousIpv4TextIsRejectedBeforeResolution` (M1-05 권고 동작) | FAIL | FAIL (재현) |
| `ControllerRobolectricTest.normalOrderIsAcknowledged` (대조군) | PASS | PASS |
| `ControllerRobolectricTest.failedProbeKeepsDeliveringToConfiguredPos` (M1-01) | FAIL | FAIL (재현) |
| `ControllerRobolectricTest.probeDeadlineIsReportedNotLeftAsChecking` | 시뮬레이션 시계 때문에 PASS. M1-01 판정용으로 쓰지 말 것 | PASS (착시) |
| `ControllerRecoveryTest` 2개 (M1-01, Android) | FAIL | NOT_RUN |

M1-01을 고친 뒤에는 FAIL로 표시된 M1-01 테스트들이 PASS로 바뀌어야 한다. 대조군과 회귀 테스트는 계속 PASS여야 한다.

## 부록 B. 면접 질문 (핵심 설계 판단 3개)

1. 별도의 처리 ID 테이블 대신 "주문 행 PK + 같은 트랜잭션"으로 중복을 막은 이유는? ACK가 유실됐을 때 같은 영수증이 돌아오는 원리는?
2. 시간 초과를 "실패"가 아니라 "미확인"으로 두는 이유는? 그래서 UI에 `기기에 접수됨`과 `POS 저장 확인`이 왜 따로 필요한가?
3. IP와 `pos_db_id`를 분리하고, hello뿐 아니라 주문마다 DB ID를 넣은 이유는? DHCP 주소 변경과 DB 교체를 각각 어떻게 막는가?
