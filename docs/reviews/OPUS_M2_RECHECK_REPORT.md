# OPUS M2 수정본 집중 재확인 보고서

| 항목 | 내용 |
|---|---|
| 저장소 | `chrysaor80/local-link-lab` |
| M2 수정 구현 | `6c7187d021ab5390ab5c3388dfd99b24327a15f3` (비교 기준 `127ea3232bd6a6dc9b8c1b54eca78b3e092127d7`) |
| CI checkout | `7efeb5746b99780f3fc52a26c2aac28e60a9f611`. git으로 받아 tree `c12de6f48fe86707b293f221448e390e5d4c5737`가 구현과 같음을 직접 확인함 |
| M3 통합·후보 조건 | `70a634720333d12cce0642f357a338850e919fb4`. `6c7187d` 대비 변경은 CI·문서·`lab/package_candidate.py`·`lab/test_candidate.py`뿐이며 제품 코드는 같음 |
| 근거 문서 커밋 | `3c18ce5` (`docs/reviews/M2_RECHECK_REQUEST.md`, `M2_RESPONSE.md`, `docs/evidence/M2_REDTEAM_FIX.md`, `m2-redteam-fix-observation.json`) |
| 작성 | OPUS (검토 담당). 구현 담당: Codex |
| 작성일 | 2026-10-28 |
| 첨부 | `m2-recheck-tests.patch` — 1개 파일(`lab/test_m3_recheck.py`), +34줄. `70a6347`에 `git apply --check` 통과 |

검토 의견과 재현 결과다. 구현 브랜치에 커밋·푸시하지 않았고 제품 코드도 바꾸지 않았다.

---

## 0. 판정

### M2 수정본(`6c7187d`): 승인 — 기존 조건(M2-01) 해소

- **M2-01은 해소됐다.**
  - ACK 장벽이 최초 응답과 재시도 응답을 모두 붙잡는다.
  - S03 세 변형이 종료 전과 재실행 후의 전제(보관 상태, POS 행 수, submit 수, ACK 방출 수, worker 상태)를 기록하고 강제한다.
  - MUT03은 실제 동작 위반으로 KILLED됐다.
  - 코드, 원본 관측의 재판정, 테스트 실행으로 각각 확인했다.
- **M2-02·04·06은 해소됐다.** M2-05는 판단이 타당하다. 다만 S01 증거의 의미가 바뀌었으므로 문구를 정확히 해야 한다(R-03).
- **M2-03은 대부분 해소됐다.** 단, 무시된(git-ignored) 빌드 산출물과 소스의 결속은 CI의 stamp에만 의존한다(R-02).
- 새로 찾은 문제는 모두 P3이며 **지원용 시연을 막지 않는다.**

### M3 후보 생성 조건(`70a6347`): 요구 충족, P3 1건

- 후보 게이트는 CI job 결과, APK stamp, JUnit, 정상·결함 실행의 설치 해시, 하네스 v2, S03 단계 관측을 모두 다시 검사한다.
- **빠진 것**: S03의 프로세스 종료·재실행(PID) 사건과, S01·S02·C07의 장애 사건은 다시 검사하지 않는다(R-01). 확정했고 재현 테스트를 첨부했다.

---

## 1. 실행 환경과 결과

### 1.1 환경

| 구성 | 값 |
|---|---|
| OS | Linux 컨테이너, KVM 없음(에뮬레이터 불가) |
| Python | 3.13.17 (CI는 3.12) |
| JDK / Gradle | Temurin 17.0.21 / 저장소 wrapper 8.11.1 |
| Android SDK | platform 35, build-tools 35.0.0 (aapt2) |
| Robolectric | 4.14.1, SDK 34 |

### 1.2 실행 결과 (모두 검토자 실행)

| 대상 SHA | 검사 | 결과 |
|---|---|---|
| `6c7187d` | `python -m unittest pos.test_pos pos.test_m1_redteam lab.test_verdict lab.test_variants lab.test_m2_redteam` | **26/26 PASS** |
| `70a6347` | 위 묶음 + `lab.test_candidate` | **38/38 PASS** |
| `70a6347` | `python -O -m unittest lab.test_candidate` | **12/12 PASS** |
| `6c7187d`·`70a6347` | `scripts/check_spec.py` | 둘 다 OK (시나리오 12, 결함 계획 3) |
| `6c7187d` | `:core:test` | **19/19 PASS** |
| `6c7187d` | `:app:testDebugUnitTest` (POS 127.0.0.1:18765) | **7/7 PASS** (Controller 6 + 취소 회귀 1). 이번에는 콜드 스타트에서도 통과 |
| `6c7187d` | `:app:assembleDebug :app:assembleRelease` | 성공 |
| `6c7187d` | `python -m lab.check_variants`, `-O` | 둘 다 PASS (DEX와 aapt2 manifest) |
| `6c7187d` | `python -m lab.m2_redteam_evidence` | E1·E2 출력이 이전과 같음 — 요청서 설명대로 이전 훅의 역사적 재현이므로 정상 |
| `70a6347` | 신규 `lab.test_m3_recheck` (일반/`-O`) | 대조군 PASS, **R-01 재현 FAIL**(예상대로) |

### 1.3 원본 관측 재검증 (`m2-redteam-fix-observation.json`)

| 대상 | 방법 | 결과 |
|---|---|---|
| 결함 diff 3개 | `6c7187d`의 `lab.mutations.mutate`로 다시 만들어 해시 비교 | MUT01·02·03 **모두 일치**, 저장된 diff 본문도 같음 |
| 모든 단계 관측 | 정상 6 + 결함 3의 기준·DB ID·`final` 인자로 `evaluate` + `paused_violations` + `commit_window`를 다시 계산 | 기록된 위반 집합·창 판정과 **모두 일치** |
| 정상·결함 설치 해시 | summary의 시작·종료 identity | 정상: 설치 = 빌드 `77422c02…` (시작·종료 같음). 결함 3개도 각각 설치 = 빌드 |
| CI artifact ZIP | — | **NOT_CHECKED** (검토자 세션에서 Actions artifact를 받을 수 없음) |

### 1.4 실행하지 못한 것

- Android 에뮬레이터(외부 장애 6개, 결함 3개, 계측 테스트): **NOT_RUN** — KVM 없음. 위 1.3의 원본 관측 재판정으로 대신했다.
- 삼성 실기기, Windows LAN: 요청서대로 범위 밖.

---

## 2. 우선 확인 항목별 답

### 2.1 M2-01 — 해소 (확정: 정적 확인 + 실행 + 원본 재판정)

| 질문 | 답 | 근거 |
|---|---|---|
| `before_ack`가 최초·재시도 응답을 모두 보류하는가 | **예** | `pos/server.py:82`(`6c7187d`)에서 `before_ack`는 `created`와 상관없이 ACK 응답 직전에 호출된다. `lab.test_m2_redteam.AckBarrierTest` PASS. 원본: S03_after_pos_commit의 submit 1·2 모두 `ACK_HELD`, 장벽 해제 뒤 `ACK_RELEASED` 2회 |
| 종료 전·재실행 후 PENDING·POS 1건·ACK 방출 0이 기록됐는가 | **예** | `committed_ack_held`: PENDING, POS 1, submit 1, 방출 0, 창 true. `restored_ack_held`: PENDING, POS 1, submit 2, 방출 0, 창 true. PID 4565 → 4669. 창을 놓치면 `Blocked`(`android_run.py:178-179`) |
| 유휴 S03이 플래그 외에 PENDING·POS 0·submit 0·worker 상태를 확인하는가 | **예** | `phases.paused_violations` + `observe_paused`가 runtime `사용자가 전송을 일시 중지함`까지 기다린다(`android_run.py:182-190`). 원본: am_kill·force_stop 모두 `accepted_paused`·`restored_pending`에서 PENDING, POS 0, submit 0, 해당 runtime |
| MUT03이 실제 데이터/동작 위반으로 KILLED인가 | **예** | 원본: `accepted_paused`에서 submit 1, POS 1, 로컬 ACKNOWLEDGED, runtime `대기 중` → `SENT_WHILE_PAUSED`. 이 위반 하나뿐이고 최종 데이터 위반은 없다. 빌드·설치 종료값 0, 시나리오 종료값 1, summary FAIL, 설치 해시 = 빌드. 문서의 "종료까지 실행했다고 세지 않는다"는 표현과도 맞다 |

### 2.2 M2-03·배포 조건

| 구멍 후보 | 결과 |
|---|---|
| dirty checkout | **차단.** `identity.clean_source`(추적 중인 파일 수정, 미추적 파일) → BLOCKED. `IdentityTest` PASS |
| 잘못 설치된 APK | **차단.** 시작·종료 시 `pm path`의 실제 바이트 해시 = 빌드 파일 해시. 정상·결함 모두 기록됨. 게이트도 `verify_identity`로 다시 확인 |
| 하네스 v1 | **차단.** 게이트가 summary와 각 결과에 `harness_version == 2`를 요구한다(`test_legacy_harness…` PASS) |
| 누락된 단계 관측 | **일부만 차단.** S03 단계 관측(`accepted_paused`, `restored_pending`, `*_ack_held`)은 차단된다. **PID 종료·재실행 사건과 S01·S02·C07 장애 사건은 게이트가 보지 않는다 → R-01** |
| 무시된 빌드 산출물(stale APK) | **CI 후보는 차단, 그 밖의 로컬 증거는 미차단 → R-02** |

### 2.3 나머지 처리

- **M2-02 해소**: 결함 사본에 기준·DB ID·단계별 `final`·원래 영수증이 보존돼 검토자가 다시 판정할 수 있었고 결과가 일치했다.
- **M2-04 해소**: 준비 대기 30초(`ControllerRobolectricTest.kt:48`). 검토자 실행 7/7.
- **M2-06 해소**: DEX + aapt2 manifest. 일반/`-O` PASS. manifest에만 receiver가 남는 경우도 주입 테스트로 막는다.
- **M2-05 — 판단은 타당, 증거 문구는 보정 필요 → R-03.**
  - 관측 전에 차단을 풀지 않는 이유(MUT02의 `ACK_WITHOUT_POS`를 관측해야 함)는 맞다. 원본에서도 MUT02가 `request_blocked`에서 검출됐다.
  - 다만 원본 S01에서는 차단된 submit 1(43.502) 뒤 **122ms 만에** submit 2(43.624)가 왔다. 앱의 자동 재시도 대기는 최소 1초이므로, 이 submit은 명시적 재개(43.571 차단 해제 직후)가 띄운 새 실행이 보낸 것이다.
  - 즉 S01 증거는 "차단 → 수동 재개 → 같은 ID 1건"을 보여 준다. "자동 재시도로 복구"를 보여 주지는 않는다.
  - 자동 재시도는 S02(ACK 유실 뒤 1.12초 후 submit 2, 재개 없음)와 S03_after_pos_commit(새 프로세스)에서 Android 수준으로 확인된다. 그래서 검출력의 실질 손실은 작다.

---

## 3. 발견

### R-01 / P3 / 확정(실행) — 후보 게이트가 S03의 PID 종료·재실행 사건을 다시 검사하지 않음

- **대상**: `70a6347` `lab/package_candidate.py:87-105` (`verify_phases`).
- **기대**: 요청서 기준 "누락된 단계 관측은 후보 생성으로 이어지지 않는다". S03 기록에는 이전 PID 소멸(`OLD_PROCESS_TERMINATED`)과 다른 새 PID(`EXPLICIT_RELAUNCH`)가 있어야 한다.
- **실제**: `verify_phases`는 단계 관측만 다시 계산하고 `events`는 보지 않는다. PID 사건이 하나도 없는 S03 기록도 후보로 승격된다. 같은 이유로 S01 `REQUEST_BLOCKED_BEFORE_POS_WRITE`, S02 `ACK_DROPPED`, C07 `DESTINATION_MISMATCH_STOPPED`(`other_submits=0`)도 게이트에서 검사하지 않는다.
- **영향**: 하네스 v2는 실행 중에 이 사건이 없으면 BLOCKED로 끝내므로, 현재 CI 증거의 결론은 바뀌지 않는다. 게이트가 단계 관측에 대해 하는 이중 검사가 이 사건들에는 없다는 비대칭이다.
- **재현**: `python -m unittest lab.test_m3_recheck -v` (첨부 패치)
  - 대조군 `test_fixture_is_otherwise_promotable`: PASS
  - `test_s03_without_observed_pid_death_and_relaunch_is_blocked`: **FAIL** (`… not raised`), 일반/`-O` 모두
- **환경**: Python 3.13.17, `70a6347`. Android 불필요.
- **권고**: `verify_phases`에 다음을 추가한다.
  - S03 세 변형: `OLD_PROCESS_TERMINATED`의 pid ≠ `EXPLICIT_RELAUNCH`의 pid. 두 사건이 각각 해당 관측(`restored_pending`/`restored_ack_held`)보다 먼저 일어나야 함.
  - S01·S02·C07: 각 장애 사건이 있어야 하고, C07은 `other_submits == 0`·`other_rows == []`.

### R-02 / P3 / 확정(실행) — 신원 검사가 무시된 빌드 산출물의 출처를 보지 않음

- **대상**: `6c7187d` `lab/identity.py:10-13`(`clean_source`), `:16-25`(`installed_apk`). `lab/mutations.py`가 결함 실행 뒤 정상 APK를 다시 설치하는 부분(`finally`).
- **기대**: summary의 `source_commit`과 `apk_identity`가 "이 APK는 이 소스로 빌드됐다"를 뜻해야 한다.
- **실제**: `git status`는 `.gitignore`의 `**/build/`를 보지 않는다. 그래서 수정본으로 빌드한 뒤 소스만 되돌린 APK도 "깨끗한 HEAD + 설치 = 빌드 파일"로 통과한다.
  - 검토자가 임시 git 저장소에서 `clean_source`와 `installed_apk`를 그대로 호출해 재현했다(두 검사 모두 통과).
  - **CI 후보는 영향이 없다.** 컴파일 직후 같은 job에서 `package_candidate stamp`가 소스와 APK 해시를 묶고, 게이트가 이를 대조하기 때문이다.
  - 또 결함 실행 뒤 정상 APK 재설치는 해시를 확인하지 않는다. 후보는 파일을 쓰므로 영향은 없다.
- **권고**: `lab.android_run`도 `artifacts/verification-input.json` stamp(소스 = HEAD, APK 해시 일치)를 요구한다. 또는 빌드에 소스 SHA를 넣고 receiver snapshot이 이를 보고하게 한다. 결함 실행 뒤 재설치에도 `installed_apk`를 호출해 기록한다.

### R-03 / P3 / 확정(원본 관측) — S01 증거는 "수동 재개 후 복구"를 보여 줌

- **대상**: `6c7187d` `lab/android_run.py:256-264`. 원본 S01 사건 시각.
- **실제**: 2.3절 참고. S01의 복구 submit은 명시적 재개가 띄운 새 실행에서 왔다.
- **영향**: 데이터 보존이나 중복 방지 결론에는 영향이 없다. "연결 단절 후 자동 재시도 복구"라고 쓰면 과장이다. `DECISIONS.md:71`의 "수동 재개 경로도 사용한다"는 실제("수동 재개 경로로 복구된다")보다 약하게 적혀 있다.
- **권고(둘 중 하나)**:
  1. 문서에서 S01을 "차단 후 수동 재개 → 같은 ID 1건"으로 적고, 자동 재시도의 Android 근거는 S02로 가리킨다.
  2. 차단을 풀고 나서 재개 없이 자동 재시도를 먼저 기다린다. 앱이 재시도 한도에 이르렀을 때만 재개하고, 이를 `recovered_by_resume`로 별도 기록한다. 관측 순서는 지금처럼 유지해 MUT02 검출을 보존한다.

### 통과한 회귀 (결함 아님)

- M2-01 장벽·전제·MUT03, M2-02 보존, M2-04 대기, M2-06 manifest(2절).
- 이전 회귀 전부: Controller 7, core 19, Python 26/38, 결함 diff 3, 원본 재판정 9건.

### 미검증 가설

- 없음. 위 세 건은 모두 실행 또는 원본 관측으로 확인했다. Android 실기기에서 동작이 같은지는 범위 밖이다.

---

## 부록 A. 재현 명령

```bash
git apply m2-recheck-tests.patch
```

```bash
python -m unittest lab.test_m3_recheck -v
```

```bash
python -O -m unittest lab.test_m3_recheck -v
```

| 테스트 | 기대(`70a6347`) | 검토자 실행 |
|---|---|---|
| `ProcessDeathEvidenceGateTest.test_fixture_is_otherwise_promotable` | PASS (대조군) | PASS |
| `ProcessDeathEvidenceGateTest.test_s03_without_observed_pid_death_and_relaunch_is_blocked` | FAIL (R-01) | FAIL, 일반/`-O` |

R-01을 고치면 둘째 테스트는 PASS로 바뀌어야 한다. 이때 기존 `lab.test_candidate`의 fixture도 PID 사건을 포함하도록 갱신해야 정상 경로가 계속 통과한다. R-02의 재현은 임시 git 저장소에서 `lab.identity`를 직접 호출한 일회성 실행이며, 설계 선택이 필요해 패치에는 넣지 않았다.
