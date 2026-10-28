# Local Link Lab 진행 관리

갱신: 2026-10-28 Asia/Seoul. 사용자 환경은 Windows, 삼성 구형폰 확보 예정. 기종·Android 버전·주당 투입 시간은 미확인이다.

## 진행 상태

| 단계 | 산출물 | 현재 상태 | 종료 기준 |
|---|---|---|---|
| M0 | 범위·프로토콜·시나리오·판단 기록·검토 요청 | OPUS 검토 반영, M1 진행 | 명세 자체 검사, OPUS의 범위·계약 검토 반영 |
| M1 | Android → POS 실제 왕복 | 정상 왕복 검증 완료, OPUS 독립 검토 대기 | 실제 앱과 Room, 실제 TCP와 POS DB, UI 결과 대조 |
| M2 | 장애 3종과 핵심 검증, 결함 사본 2종 | 예정 | 시나리오별 근거 확보, OPUS 검토 반영 |
| M3 | CI·APK·영상·공개 설명 | 예정 | 실행 증거와 한계가 일치하는 지원용 산출물 |

## 담당과 변경 관리

- Codex: 범위·일정·실행 근거 관리, 조사·구현·테스트·수정.
- OPUS: 고정 커밋의 설계와 구현을 독립 검토. 구현 담당이 작성한 M0 요청을 OPUS가 검토했으며, 구현 담당의 처리 내역은 `reviews/M0_RESPONSE.md`에 기록함.
- 사용자: 실제 폰 연결·설치·기기에서만 가능한 관측, 설계 설명 연습.
- 검토 의견에는 번호, 우선순위, 근거, 재현, 채택/보류/기각 이유를 남긴다. 중요한 계약 변경은 DECISIONS와 명세에 함께 반영한다.

## 다음 작업

1. [M1 검토 요청](reviews/M1_REQUEST.md)을 OPUS에게 전달한다. 구현 및 검사 기준은 아래의 고정 커밋이다.
2. 검토에서 발견된 수정 사항을 처리하고 M2 검증에 진입한다.
3. M2에서 단절·응답 유실·OS 프로세스 종료와 결함 사본 2종을 검증한다.
4. 기기 확보 후 Windows와 삼성 기기 모델/API를 기록하고 실제 LAN을 확인한다.

## 실행 근거

- M0 검토 수정: `0b572af` (main). [처리 내역](reviews/M0_RESPONSE.md).
- M1 작업 브랜치: `codex/m1-first-roundtrip`. [PR #1](https://github.com/chrysaor80/local-link-lab/pull/1).
- 검증 구현 SHA: `21e8ad5e3240287683aa1ef9abd0079f481fad76`. 후속 보고 문서 커밋은 이 구현의 검증 결과를 기록한다.
- Linux 로컬: Python 3.11, JDK 17.0.21, SDK 35.
- `python scripts/check_spec.py`: 14 구조 예제, 31 원문 예제, 본문 JSON 4개, 시나리오 12개, 결함 계획 2개. PASS.
- `python -m unittest pos.test_pos -v`: 7개 PASS. 실제 loopback TCP와 SQLite; Android 경로가 아님.
- `:core:test`: 9개 PASS. 공유 원문 31개, 정책 대역, 실제 소켓 취소/제한 시간.
- `:app:assembleDebug`, `:app:assembleDebugAndroidTest`, `:app:lintDebug`: PASS. APK 생성은 Android 실행 성공을 뜻하지 않음.
- GitHub Actions: [M1 실행 40620268630](https://github.com/chrysaor80/local-link-lab/actions/runs/40620268630) 전체 SUCCESS. Linux/Windows 각각 POS 7개, JVM 9개, API 29 에뮬레이터 Android 4개 PASS.
- UI 접수 전 기준값 ↔ Room ACK ↔ 새 POS DB 전체 행 1개/영수증 대조 PASS. network_path=`emulator-nat`, Android 10/API 29 x86_64.
- [검증 APK·로그·DB·테스트 보고서](https://github.com/chrysaor80/local-link-lab/actions/runs/40620268630/artifacts/12786603308). [영구 요약](evidence/M1.md).
- Android 프로세스 종료, 결함 사본 2종, 삼성 실기기/LAN: NOT_RUN.

Room DB 재열기 검사는 OS 프로세스 종료 검증으로 간주하지 않는다. 에뮬레이터 정상 왕복의 판정은 UI에서 접수 전에 기록한 기준값, Room의 ACK 결과, 새 POS DB의 전체 행 집합과 영수증을 비교한다. 실행 누락은 성공으로 처리하지 않는다.

## 협업과 환경

원격 저장소 업로드는 Git push로 가능하다. GitHub API와 CI 조회는 연결 도구를 사용한다. 로컬에는 KVM이 없어 Android 실행은 CI 에뮬레이터로 확인한다. OPUS 직접 연결은 없으므로 고정 커밋의 검토 요청을 사용자가 전달한다. 공개 출처·비공개 링크 점검은 구현 담당의 수동 점검이다.

## M2에서 보강할 경계

POS_MISMATCH에서 PENDING 보존과 현재 worker 중지는 구현됐지만, 전경 복귀/수동 재개 때 목적지 hello 재확인을 반드시 거치는 상태 전이는 남아 있다. POS 트랜잭션의 DB ID 검사는 항상 수행된다. API 23 호환성, 기기 이전 차단의 실제 OS 동작과 메모리/저장 공간 장애는 확인 전이다. Lint는 오류 없이 통과했으며 백업 속성 안내 경고 1개가 남아 있다.
