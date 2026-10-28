# OPUS M2 독립 검토 보고서 — M1 수정 확인과 M2 레드팀

| 항목 | 내용 |
|---|---|
| 저장소 | `chrysaor80/local-link-lab` |
| 검토 고정 코드 | `127ea3232bd6a6dc9b8c1b54eca78b3e092127d7` (검토 중 변경하지 않음) |
| CI merge checkout | `85d9da1d899852932582c3dee5129e33733e7db4`. git으로 받아 tree `c8840faa918c0532f1a2974b3ec9974789e0e33a`가 고정 코드와 같음을 직접 확인함 |
| 이후 문서 커밋 | `a0adf50`. 고정 코드 대비 `docs/`와 `README.md`만 바뀌었음을 확인함 |
| 요청서 | `docs/reviews/M2_REQUEST.md` |
| 작성 | OPUS (검토 담당). 구현 담당: Codex |
| 작성일 | 2026-10-28 |
| 첨부 | `m2-redteam-tests.patch` — 2개 파일, +163줄. `127ea32`에 `git apply --check` 통과 |

이 문서는 검토 의견과 재현 결과다. 저장소에 커밋·푸시하지 않았다. 제품 코드는 바꾸지 않았다. 재현에 쓴 결함 사본은 임시 사본에서만 만들었다.

---

## 0. 판정과 시연 차단 항목

### 판정: 조건부 승인

- **지원용 시연을 막는 제품 결함: 없음.** 주문 유실, 중복 저장, 잘못된 완료 표시, 복구 정지를 만드는 반례를 제품 코드에서 찾지 못했다.
- **M1 지적 7건(M1-01~07)의 수정을 모두 확인했다.** 특히 M1-01은 같은 측정 방법으로 수정 전후가 갈렸다. 실시간 30회 측정에서 수정 전 30/30 `TimeoutCancellationException` → 수정 후 30/30 `SocketTimeoutException`.
- **조건 — M2-01 (P2, 검증 근거 신뢰성).** S03 변형 3개는 "주문이 아직 보관 중일 때 죽었다", "ACK를 받기 전에 죽었다"는 전제를 검사하지 않는다. 그래서 의도한 장애 창을 지나지 않고도 PASS할 수 있다. S03 결과를 "보관 주문 복원", "commit 직후 사망 복구"의 근거로 내세우기 전에 보강해야 한다.
  - 제품 동작 자체의 결함은 아니다.
  - 이번 CI 실행에서는 commit에서 종료까지 240ms라 창을 실제로 지났을 가능성이 높다. 다만 판정기가 이를 보장하지 않는다.
- 나머지(M2-02~06)는 P3이며 시연을 막지 않는다.

### 반드시 먼저 고칠 것

1. **M2-01**: S03의 전제 조건 검사를 추가하고, 사용자 중지를 무시하는 결함 사본(MUT03)을 추가한다.

---

## 1. 실행 환경과 실행 결과

### 1.1 환경

| 구성 | 값 |
|---|---|
| OS | Linux 컨테이너 (KVM 없음, CPU 가상화 플래그 없음 → Android 에뮬레이터 불가) |
| Python | 3.13.17 (CI는 3.12) |
| JDK / Gradle | Temurin 17.0.21 / 저장소 wrapper 8.11.1 |
| Android SDK | platform 35, build-tools 35.0.0 (aapt2 포함) |
| Robolectric | 4.14.1, SDK 34 (저장소 설정 그대로) |
| 실시간 경합 측정 | 검토자 하네스(고정 코드의 core 소스를 그대로 컴파일), JDK 21.0.12, Gradle 8.14.3 |

### 1.2 기존 검사 (고정 코드 그대로)

| 검사 | 명령 | 결과 |
|---|---|---|
| CI Python 묶음 | `python -m unittest pos.test_pos pos.test_m1_redteam lab.test_verdict lab.test_variants -v` | **21/21 PASS** |
| 핵심 JVM | `./gradlew :core:test` | **19/19 PASS** (DeliveryEngine 6, DestinationVerifier 5, RedTeam 4, TcpTransport 3, Wire 1) |
| Controller JVM | `./gradlew :app:testDebugUnitTest` (POS 127.0.0.1:18765) | 첫 실행(콜드 스타트) **5/6** — M2-04. 이후 3회 연속 **6/6 PASS** |
| APK 빌드 | `:app:assembleDebug :app:assembleRelease` | 성공 |
| release 제어 코드 제외 | `python -m lab.check_variants`, `python -O -m lab.check_variants` | 둘 다 PASS |
| manifest 직접 확인 | `aapt2 dump xmltree` | debug: `LabControlReceiver` exported=true, permission=`android.permission.DUMP`, debuggable=true. release: receiver 없음 |
| 명세 검사 | `python scripts/check_spec.py` | OK (예제 14, 원문 31, 문서 예제 4, 시나리오 12, 결함 계획 2) |

### 1.3 증거 재검증

| 대상 | 결과 |
|---|---|
| 결함 사본 diff 해시 | `lab.mutations.mutate`를 고정 코드의 `DeliveryEngine.kt`에 적용해 다시 계산. MUT01 `01c370fd…`, MUT02 `87d4d939…` — 관측 JSON과 **일치** |
| 정상 6개의 최종 행 | `m2-review-observation.json`의 기준·로컬·POS 행·최초 영수증을 `lab.verdict.evaluate(final=True)`로 다시 판정. **6개 모두 위반 0** |
| 결함 사본 재판정 | 영구 JSON에 기준(baseline)이 없어 다시 판정할 수 없음 → M2-02 |
| CI 실행 페이지 | 직접 열람하지 못함(NOT_CHECKED). merge SHA와 tree 동일성은 git으로 확인함 |

### 1.4 레드팀 실행

| 검사 | 결과 | 의미 |
|---|---|---|
| 실시간 단일 스레드에서 `TcpTransport` 자체 제한 시간 30회 | **30/30 `SocketTimeoutException`** (같은 방법으로 `ee67e2c`에서는 30/30 `TimeoutCancellationException`) | M1-01 원인 수정 확인 |
| 신규 회귀 `ProbeCancellationRedTeamTest` | **PASS** | 연결 확인 중 백그라운드 전환 시 실패 결과를 게시하지 않고, 설정을 유지하며, 중지 중에는 전송하지 않고, ON_START 후 전송함 |
| MUT03(사용자 중지 검사 1줄 삭제) + Controller JVM | `failedProbePreservesUserPause` **FAIL** (기대 PENDING, 실제 ACKNOWLEDGED), 나머지 5개 PASS | JVM 묶음은 중지 무시 결함을 잡음 → M2-01 대조 |
| E1: S03_after_pos_commit 훅 모델 | 첫 ACK가 보류된 동안 재시도가 **원래 영수증의 ACK를 즉시 받음** | M2-01 |
| E2: S03 복원 단계 판정 | 보관 중(PENDING)·이미 전송됨(ACK) 모두 **위반 0** | M2-01 |

### 1.5 실행하지 못한 것

| 항목 | 상태 | 이유 |
|---|---|---|
| Android 계측(`RoundTripTest`, `ControllerRecoveryTest`), `lab.android_run`, `lab.mutations` | NOT_RUN | 에뮬레이터 불가(KVM 없음). M2-01의 Android 쪽 판단은 정적 추적 |
| Windows(QuickEdit 포함), 삼성 실기기/LAN | NOT_RUN | 환경 없음 |
| CI 40629074288 원본 artifact | NOT_CHECKED | 검토자 세션에서 Actions API를 쓸 수 없음 |

---

## 2. 요청 항목별 답

### 2.1 M1-01 수정 확인 — 확인됨

| 질문 | 답 | 근거 |
|---|---|---|
| 실패/침묵 probe 뒤 기존 목적지 전송 재개 | **예** | `LinkApplication.kt:52-66`에서 실패해도 블록을 끝내지 않고 `:67-90`(설정 재조회 → 중지 확인 → hello 확인 → 전송)으로 이어짐. Robolectric `failedProbeKeepsDeliveringToConfiguredPos`, `probeDeadlineIsReportedNotLeftAsChecking` PASS |
| 오류 사유가 전송 상태에 덮이지 않음 | **예** | `probeResult`는 별도 StateFlow(`:39-40`, `:56-61`)이고, 화면은 `probe-error`로 따로 표시함. 다음 연결 확인 전까지 남아 있음 — 설계대로이며 결함은 아님 |
| 사용자 중지 유지 | **예** | `:71`. `failedProbePreservesUserPause` PASS. MUT03을 이 테스트가 잡음(1.4절) |
| 상위 취소 전파 | **예** | probe 분기는 `CancellationException`을 다시 던짐(`:57`), 일반 예외 처리에서 `ensureActive`(`:59`). `TcpTransportTest.callerDeadlineStillCancelsAndClosesSocket` PASS. 신규 `ProbeCancellationRedTeamTest` PASS |
| 미확인 주문이 있을 때 다른 DB 변경 거부 | **예** | `Repository.configure` 변경 없음. `rejectedDatabaseSwitchKeepsPendingOrderAndOriginalDestination` PASS |
| 자체 timeout의 통신 오류 변환이 상위 취소를 삼키지 않음 | **예** | `TcpTransport.kt:28` `withTimeoutOrNull`은 자기 제한 시간만 null로 바꾸고 상위 취소는 그대로 전파함. `:58`에서 `SocketTimeoutException`. 실시간 30/30 |

### 2.2 M1 보조 수정 확인 — 확인됨

- **현재 DB ID와 파일 미생성**: `store.py:27-40`(`mode=rw`, `db_id`를 매번 읽음), `server.py`의 `identity()`. `test_deleted_database_is_not_recreated_by_hello` PASS.
- **일반/`-O` 검사 거부**: `verify_m1.py`가 명시적 `require`를 쓰고 증거 DB를 `mode=ro`로 연다. 일반/`-O` 모두 정상 증거는 통과, 고아 행은 거부함을 확인.
- **ASCII IPv4**: `TcpTransport.kt:18-25` — 네 옥텟, 앞자리 0 금지, DNS 없이 바이트 주소 사용. `connect()`는 worker를 취소하기 전에 검증(`LinkApplication.kt:102-111`). 관련 테스트 PASS.
- **테스트 DB 분리**: `LabTestRunner`가 실행마다 새 Room DB를 쓰고, POS 포트도 8765/18766/18765로 나뉨. 계약에 맞는다. 참고로 재사용하는 실기기에는 `instrumented-<uuid>.db`가 실행마다 쌓인다(정리 단계 권장, 사소함).
- **원본 hello 테스트의 기대 조정: 타당하다. 원본은 검토자의 테스트 설계 오류였다.**
  - 원본은 "교체 후 hello가 돌려준 ID로 주문을 보내면 POS_MISMATCH"를 기대했다. 올바른 구현은 현재 ID를 돌려주므로 그 주문은 ACK여야 한다.
  - 즉 원본 테스트는 결함 코드에서는 둘째 단언에서, 수정 코드에서는 첫째 단언에서 실패하는 모순된 테스트였다.
  - Codex가 "교체 전 ID → 거부, hello가 돌려준 현재 ID → ACK"로 나눈 것이 맞다.
- **Windows QuickEdit**: 실행 지침(출력 리디렉션)만 채택하고 "미재현"으로 남긴 판단은 적절하다. 계속 NOT_RUN으로 유지할 것.

### 2.3 `lab/android_run.py`

| 질문 | 답 |
|---|---|
| commit 사건 이후에 장애가 주입되는가 | **예.** S01: 접수 전에 일시 중지(`:174-178`)하므로 `LOCAL_COMMITTED` 전에는 전송이 없고, `before_submit`이 POS 쓰기 전에 연결을 닫음. S02·S03_after_pos_commit: `after_commit`(POS commit 후)에서 주입 |
| PID 종료·재실행을 실제로 관측하는가 | **예.** `pidof` 폴링, 이전 PID 소멸, 자동 재시작 감지(`:84-96`), 명시적 실행 뒤 새 PID 비교(`:192-203`, `:239-250`). 관측 JSON에서도 PID가 바뀜(4187→4316 등) |
| 실행 누락·환경 실패가 PASS가 될 경로 | 예외·BLOCKED는 요약에서 FAIL/INCOMPLETE가 된다(`:263-268`, `verdict.summarize`). **다만 "의도한 장애 창을 지나지 않은 실행"이 PASS가 되는 경로가 있다 → M2-01** |

### 2.4 `lab/verdict.py` — 요구를 충족함

- **기준 독립성**: 접수 전에 외부 실행기가 기준을 만들어 저장한다(`android_run.py:111-114`). 앱 DB에서 가져오지 않는다.
- **앱과 POS가 함께 틀린 ID로 바뀐 경우**: `LOCAL_ID_SET`·`POS_EXTRA_ID`(최종 시 `POS_ID_SET`)로 검출한다. `test_orphan_is_detected_even_when_local_and_pos_agree_on_new_id` PASS.
- **추가 행·본문·최초 영수증**: `POS_EXTRA_ID`, `POS_PAYLOAD`/`LOCAL_PAYLOAD`, `RECEIPT_MISMATCH`, `ORIGINAL_RECEIPT_CHANGED`로 모두 비교한다.
- "단계별 전제 조건"(예: 복원 시점에 PENDING이어야 함)은 판정 함수가 아니라 실행기가 맡을 일이다 → M2-01.

### 2.5 `lab/mutations.py`

- **정상과 같은 판정기인가**: 예. 결함 사본 APK만 바꾸고, 저장소 루트의 원본 `lab.android_run`·`verdict`를 실행한다(`:89-92`).
- **빌드/설치 실패를 KILLED로 오인하는가**: 아니다. KILLED는 "시나리오 종료값 1 + 판정 FAIL + 기대 위반 코드 포함"일 때만이다(`:83-101`). 빌드·설치 실패, 시간 초과(124), BLOCKED는 모두 KILLED가 아니다.
- **diff와 관측 데이터 일치**: diff 해시는 다시 계산해 일치함. 관측된 위반 코드도 결함 내용과 맞는다(MUT01: 추가 ID 행, MUT02: POS 행 없는 ACK).
- **빈틈**: 기준 미보존(M2-02), 작업 사본·APK 결속(M2-03). 사용자 중지 무시 결함이 결함 사본 목록에 없음(M2-01).

### 2.6 `app/src/debug`·`DestinationVerifier.kt` — 요구를 충족함

- **화면과 같은 Controller**: `LabControlReceiver.kt:22-23`이 Application의 같은 `controller`를 쓴다. 단 화면의 초안 ID·버튼 경로를 건너뛰고 request_id를 직접 주입한다. 이 점은 문서에 이미 구분되어 있다.
- **권한·응답**: DUMP 권한과 exported는 debug manifest에만 있다(aapt2로 확인). 토큰 형식을 검사하고, 결과를 AtomicFile로 쓴다. Controller가 busy이면 실패로 응답한다(`:25`). 명령이 적용되지 않으면 8초 뒤 `ok:false`로 응답한다(fail-closed).
- **release 제외**: DEX(`check_variants`)와 manifest(aapt2) 둘 다 없음을 확인했다.
- **재개 전 hello + 주문 트랜잭션의 DB ID 검사**: 둘 다 유지된다. `LinkApplication.kt:73-83`이 전송 전에 hello로 확인하고, 각 주문은 `pos_db_id`를 담아 보낸다. `store.submit`은 `BEGIN IMMEDIATE` 안에서 DB ID를 비교한다(변경 없음). `test_changed_database_is_rejected_before_write` PASS.

---

## 3. 발견

### 3.1 M2-01 / P2 / 확정(실행 E1·E2·MUT03-JVM) + 정적(Android NOT_RUN) — S03 변형의 전제 조건을 검사하지 않아 의도한 장애 창 없이도 PASS 가능

**고정 파일·줄**
- `lab/android_run.py:146-148` — `after_commit`에서 ACK를 보류함.
- `pos/server.py:76-78` — `after_commit`은 `created`일 때만 호출됨. 같은 요청의 재시도는 기존 행 경로를 타서 훅을 거치지 않음.
- `lab/android_run.py:204-207` — `restored_pending` 단계는 사용자 중지 *플래그*만 확인하고 `evaluate(final=False)`를 씀.
- `lab/android_run.py:236-245` — `committed_ack_held` 단계는 `evaluate(final=False)` 뒤 바로 force-stop.

**기대**
- S03_am_kill / S03_force_stop의 PASS는 "주문이 보관 중(PENDING)인 채로 프로세스가 죽었고, 재실행 후 복원·전송됐다"를 뜻해야 한다.
- S03_after_pos_commit의 PASS는 "POS commit 후 앱이 영수증을 받기 전에 죽었다"를 뜻해야 한다.

**실제**
- **E1 (실행)**: 같은 형태의 훅에서 첫 연결의 ACK가 보류된 동안, 같은 요청의 재시도가 원래 영수증의 ACK를 즉시 받았다(`ack_still_held=true`, `retry_reply_type=ack`).
  - 실행기가 commit부터 force-stop까지 앱의 시도 제한 시간(약 5초)보다 오래 걸리면, 앱은 재시도로 ACK를 영구 기록한 뒤에 죽는다.
  - 그 경우에도 판정은 PASS다. 느린 에뮬레이터·실기기에서 생길 수 있다.
- **E2 (실행)**: 복원 단계 판정은 "보관 중"과 "이미 전송됨"을 구별하지 못한다. `evaluate(final=False)`가 둘 다 `[]`, 최종 판정도 `[]`.
- **MUT03 (JVM 실행 + Android 정적 추적)**: `LinkApplication.kt:71`의 사용자 중지 검사를 지운 사본.
  - JVM Controller 묶음은 잡는다(`failedProbePreservesUserPause` FAIL).
  - Android 실행기에서는 이 사본이 접수 직후 바로 전송한다. 그 결과 S01·S02·S03_after_pos_commit은 PASS, S03_am_kill·S03_force_stop·C07은 PASS 또는 BLOCKED(접수 확인 단계에서 이미 ACK를 보면 BLOCKED)가 된다. **어느 경우에도 KILLED가 되지 않는다.**
  - 실행기의 중지 확인은 영속 플래그만 보고 "중지 중 미전송" 동작은 보지 않기 때문이다. NOT_RUN(에뮬레이터 없음).
- **참고**: 이번 CI 관측에서 S03_after_pos_commit의 `POS_COMMITTED`(03:59:25.285)부터 `OLD_PROCESS_TERMINATED`(25.525)까지 240ms였다. 이번 실행은 창을 지났을 가능성이 높다. 판정기가 이를 보장하지 않는다는 것이 문제다.

**깨지는 것**: `docs/evidence/M2_REVIEW.md`의 "보관 주문과 사용자 중지를 복원", "commit 후 ACK를 보류한 동안 force-stop" 주장의 근거.

**권고(최소)**
1. S03_am_kill / S03_force_stop: `restored_pending`에서 다음을 모두 요구한다. 아니면 FAIL(`SENT_WHILE_PAUSED`)로 판정한다.
   - 로컬 상태 PENDING
   - POS 전체 행 0
   - `before_submit` 호출 0회(재개 전)
2. S03_after_pos_commit: `before_submit`에서 POS_COMMITTED 이후 같은 요청의 재제출을 세고 `allow_ack`까지 붙잡는다. force-stop 직전에 로컬 PENDING과 재제출 0을 요구하고, 아니면 BLOCKED("fault window missed")로 둔다.
3. 결함 사본 MUT03(사용자 중지 검사 삭제)을 추가하고, 기대 위반을 `SENT_WHILE_PAUSED`(S03_am_kill)로 정한다.

**재현**: 부록 A의 `python -m lab.m2_redteam_evidence`(E1·E2). MUT03은 부록 A의 diff를 적용한 뒤 Controller JVM 묶음을 실행.

### 3.2 P3 발견

#### M2-02 / P3 / 정적 — 결함 사본 영구 관측에 기준이 없어 다시 판정할 수 없음
- **파일**: `docs/evidence/m2-review-observation.json`의 `mutations[*].observation` — `local_rows`, `pos_rows`, `rechecked_violations`만 있다.
- **기대**: artifact가 만료돼도 판정기로 다시 계산할 수 있어야 한다.
- **실제**: 기준(baseline)과 `pos_db_id`, `final` 인자가 없어 검토자가 다시 계산할 수 없다. 또 `rechecked_violations`(MUT01은 1개)와 기록된 `violations`(3개)가 다른 이유가 적혀 있지 않다.
- **권고**: 결함 사본에도 기준·DB ID·판정 인자(final 여부)를 함께 보존한다.

#### M2-03 / P3 / 정적 — 소스 SHA와 실행 대상의 결속이 약함
- **파일**: `lab/mutations.py:72-73`(작업 트리를 그대로 복사, 깨끗한지 검사 안 함), `lab/android_run.py:107`·`:286`(`git rev-parse HEAD`만 기록).
- **실제**: 수정 중인 작업 트리나 예전에 설치한 APK로 실행해도 기록상 SHA는 HEAD로 남는다. CI는 깨끗한 checkout이라 이번 증거는 영향을 받지 않는다.
- **권고**: `git status --porcelain`이 비어 있지 않으면 BLOCKED로 둔다. 설치된 APK의 `pm path`와 sha256을 기록해 빌드 산출물과 비교한다.

#### M2-04 / P3 / 실행 관측 — Controller JVM 테스트의 콜드 스타트 시간 의존
- **파일**: `ControllerRobolectricTest.kt:47` `waitFor(10_000)`(실제 시간).
- **실제**: 검토자 환경의 첫 실행(Robolectric 콜드 스타트, 테스트 시간 103.8초)에서 첫 테스트가 setUp의 "initial probe completed"로 실패했다. 이후 3회는 6/6 PASS. 제품 결함은 아니다.
- **권고**: 첫 연결 확인 대기는 30초로 늘리거나 워밍업을 둔다. 신규 회귀 테스트는 30초를 쓴다.

#### M2-05 / P3 / 정적 — S01의 관측 지연이 앱의 재시도 예산을 소모함
- **파일**: `lab/android_run.py:229-233`.
- **실제**: 차단을 푸는 시점이 관측(adb 왕복) 뒤다. 그 사이 앱의 재시도가 계속 차단되며 5회 예산을 쓴다. 느린 기기에서는 RETRY_LIMIT로 잘못된 FAIL이 날 수 있다. 잘못된 PASS는 아니다. 이번 관측에서는 0.13초였다.
- **권고**: 첫 차단 사건 직후 차단을 풀고, 관측은 그 뒤에 한다.

#### M2-06 / P3 / 정적 — release 제외 검사가 DEX만 봄
- **파일**: `lab/check_variants.py:6-9`.
- **실제**: 검토자가 aapt2로 확인한 결과 release manifest에도 receiver가 없다. 다만 manifest 유출은 자동 검사하지 않는다.
- **권고**: aapt2 등으로 release manifest의 `LabControlReceiver` 부재도 검사한다.

### 3.3 통과한 회귀 (결함 아님)

- M1-01: probe 실패/침묵/잘못된 주소/다른 DB 거부 뒤 전송 계속, 사용자 중지 유지, 상위 취소 전파, 실시간 30/30 `SocketTimeoutException`.
- M1-02·03·05·07: 2.2절 항목 전부.
- 신규: `ProbeCancellationRedTeamTest.backgroundDuringProbePublishesNothingAndDoesNotDeliver` PASS.
- 판정기·결함 사본: 정상 6개 재판정 위반 0, diff 해시 일치, release 제외(DEX·manifest).

### 3.4 미검증 가설·범위 밖

- Android에서 MUT03이 실제로 SURVIVED/BLOCKED가 되는지(M2-01의 정적 결론): NOT_RUN.
- Windows QuickEdit 정지(M1-06): NOT_RUN.
- 실기기·LAN, API 23, 전원 차단·저메모리·디스크 고갈, 모든 UI 동시 조작: 요청서대로 범위 밖.

---

## 4. 검토자 정정

- M1 보고의 `test_hello_reports_the_database_that_handles_orders`는 설계가 틀렸다(2.2절). Codex의 조정이 맞다.
- 이번 검토에서 첫 Controller JVM 실패(M2-04)는 콜드 스타트 때문이었다. 재실행 결과와 함께 그대로 기록했다. 제품 결함으로 세지 않는다.

---

## 부록 A. 재현 명령

```bash
git apply m2-redteam-tests.patch
```

E1·E2 증거 스크립트 (POS·판정기만 사용, Android 불필요):

```bash
python -m lab.m2_redteam_evidence
```

신규 회귀 테스트는 별도 터미널에서 새 POS를 띄운 뒤 실행한다.

```bash
python -u -m pos.server --db artifacts/robo-pos.db --port 18765
```

```bash
./gradlew :app:testDebugUnitTest --tests '*ProbeCancellationRedTeamTest' --tests '*ControllerRobolectricTest'
```

MUT03(사용자 중지 무시) 재현 — **임시 사본에서만** 적용한다. 위 POS를 띄운 상태에서 Controller JVM 묶음을 실행하면 `failedProbePreservesUserPause`가 FAIL해야 한다.

```diff
--- a/app/src/main/java/dev/locallinklab/app/LinkApplication.kt
+++ b/app/src/main/java/dev/locallinklab/app/LinkApplication.kt
@@ -71 +70,0 @@
-                    if (config.userPaused) { _runtime.value = "사용자가 전송을 일시 중지함"; return@collectLatest }
```

| 패치 파일 | 기대 결과(127ea32) | 검토자 실행 |
|---|---|---|
| `lab/m2_redteam_evidence.py` | E1: 보류 중 재시도가 ACK를 받음, E2: 두 경우 모두 위반 0 → M2-01 근거 | 실행, 위와 같음 |
| `app/src/test/.../ProbeCancellationRedTeamTest.kt` | PASS (회귀) | PASS |

M2-01을 보강한 뒤에는 E1 스크립트의 결과가 바뀌지 않는다. E1은 POS의 정상적인 멱등 동작을 보여 줄 뿐이고, 보강 대상은 실행기다. 보강 확인은 MUT03이 Android 실행기에서 KILLED가 되는지로 한다.
