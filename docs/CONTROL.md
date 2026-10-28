# Local Link Lab 진행 관리

갱신: 2026-10-28 Asia/Seoul. 사용자 환경은 Windows, 삼성 구형폰 확보 예정. 기종·Android 버전·주당 투입 시간은 미확인이다.

## 진행 상태

| 단계 | 산출물 | 현재 상태 | 종료 기준 |
|---|---|---|---|
| M0 | 범위·프로토콜·시나리오·판단 기록·검토 요청 | OPUS 검토 반영, M1 진행 | 명세 자체 검사, OPUS의 범위·계약 검토 반영 |
| M1 | Android → POS 실제 왕복 | 정상 왕복 검증 완료, OPUS 독립 검토 대기 | 실제 앱과 Room, 실제 TCP와 POS DB, UI 결과 대조 |
| M2 | 장애 3종과 핵심 검증, 결함 사본 2종 | 핵심 자동 검증 완료, 독립 검토 준비 | 시나리오별 근거 확보, OPUS 검토 반영 |
| M3 | CI·APK·영상·공개 설명 | 예정 | 실행 증거와 한계가 일치하는 지원용 산출물 |

## 담당과 변경 관리

- Codex: 범위·일정·실행 근거 관리, 조사·구현·테스트·수정.
- OPUS: 고정 커밋의 설계와 구현을 독립 검토. 구현 담당이 작성한 M0 요청을 OPUS가 검토했으며, 구현 담당의 처리 내역은 `reviews/M0_RESPONSE.md`에 기록함.
- 사용자: 실제 폰 연결·설치·기기에서만 가능한 관측, 설계 설명 연습.
- 검토 의견에는 번호, 우선순위, 근거, 재현, 채택/보류/기각 이유를 남긴다. 중요한 계약 변경은 DECISIONS와 명세에 함께 반영한다.

## 다음 작업

1. 사용자가 [OPUS 업무 요청](reviews/OPUS_M1_REDTEAM.md)을 전달했다. 결과를 기다린다. 고정된 M1에 대해 독립 검토·장애 레드팀·최소 재현 테스트를 맡긴다. 제품 구현·통합은 Codex가 담당한다.
2. OPUS의 M1 검토 결과를 받아 재현·회귀 수정에 반영한다. M2 핵심 자동 검증은 아래 근거로 완료했다.
3. M1 검토 결과를 반영한 고정 커밋으로 [M2 검토](reviews/M2_REQUEST.md)를 묶고 M3의 배포 후보 조건·시연 영상·최종 설명을 준비한다.
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
- M2 작업 브랜치: `codex/m2-fault-verification`. M1의 고정 검토 스냅샷은 유지한다.
- M2 검증 구현 SHA: `70a4ecaa31fb8fa0f0b1026da390ccf15726c98c`. [PR #2](https://github.com/chrysaor80/local-link-lab/pull/2). 후속 문서 커밋은 검증된 구현을 바꾸지 않는다.
- [M2 CI 40624098387](https://github.com/chrysaor80/local-link-lab/actions/runs/40624098387) 전체 SUCCESS. JVM 14개, Python 판정기 7개 + POS 7개(Windows/Linux 각각), Android 계측 4개, debug/release 빌드·release 제어 코드 부재 검사 PASS.
- Android 외부 실행기: S01, S02, S03 am kill/force-stop/commit 직후 force-stop, C07 재개 전 DB 확인의 6개 실행 PASS. PID 종료와 새 PID를 관측했고 최종 주문은 각각 1건.
- MUT01 ID 재발급과 MUT02 ACK 전 완료: 각각 추가 주문과 POS에 없는 완료 상태를 검출해 KILLED. 두 사본의 빌드·설치는 성공했으며 환경 실패를 검출로 세지 않았다.
- [M2 영구 증거](evidence/M2.md), [원본 artifact](https://github.com/chrysaor80/local-link-lab/actions/runs/40624098387/artifacts/12789036204).
- 삼성 실기기/LAN, 실제 디스크 고갈·전원 차단, 전체 UI 동시 조작·업데이트 등은 NOT_RUN.

Room DB 재열기 검사는 OS 프로세스 종료 검증으로 간주하지 않는다. 에뮬레이터 정상 왕복의 판정은 UI에서 접수 전에 기록한 기준값, Room의 ACK 결과, 새 POS DB의 전체 행 집합과 영수증을 비교한다. 실행 누락은 성공으로 처리하지 않는다.

## 협업과 환경

원격 저장소 업로드는 Git push로 가능하다. GitHub API와 CI 조회는 연결 도구를 사용한다. 로컬에는 KVM이 없어 Android 실행은 CI 에뮬레이터로 확인한다. OPUS 직접 연결은 없으므로 고정 커밋의 검토 요청을 사용자가 전달한다. 공개 출처·비공개 링크 점검은 구현 담당의 수동 점검이다.

## 보강한 경계와 검증 한계

M2는 전경 복귀/수동 재개마다 저장된 대상 DB를 hello로 먼저 확인하도록 보강했다. 다른 DB면 주문을 보내지 않고 중지하며, 확인 실패 시 주문을 보존한다. POS 트랜잭션의 DB ID 검사도 유지한다. JVM 검사와 실제 에뮬레이터 C07 재개 시험으로 확인한다. API 23 호환성, 기기 이전 차단의 실제 OS 동작과 메모리/저장 공간 장애는 확인 전이다. Lint는 오류 없이 통과했으며 백업 속성 안내 경고 1개가 남아 있다.
