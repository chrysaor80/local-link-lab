# M0 검토 반영

검토 기준: 9b6bf9d2ad709830e89a6684706760c3fe83805f. 사용자가 전달한 OPUS 보고를 Codex(이 채팅의 구현 에이전트, 사용자 호칭 아스트라)가 읽고 판단했다. OPUS는 자체 데이터 검사로 예제 12개를 확인했으며 저장소 스크립트·GitHub Actions·기기는 실행하지 않았다고 밝혔다. 아래는 구현 담당의 반영 결정이며 재검토 완료 기록이 아니다.

| 지적 | 결정과 근거 |
|---|---|
| R-01 P1 | 수용, 제안 수정. maybe_delivered는 이미 전송 가능성이 있는 주문의 DHCP 변경을 해결하지 못하므로 F-01을 앞당겨 hello + pos_db_id를 채택. 제출에도 DB ID를 포함해 확인 후 교체 경쟁을 차단 |
| R-02 P1 | 수용, 제시한 대안 중 NEEDS_ATTENTION 보존·자동 큐 제외 선택. 다음 PENDING을 처리하고 전체 POS 저장 순서 주장은 철회. 과거 저장 여부를 모르는 주문을 CLOSED_UNSENT로 종결하지 않음 |
| R-03 P2 | 서버 전체 수신 5초·응답 쓰기 1초, 동시 연결과 활성 연결 상한 32, C06 추가 |
| R-04 P2 | 코드별 이번 시도와 commit의 관계 명시. commit 이후/불확실성은 TEMPORARY_UNAVAILABLE 또는 종료. 입력 거부만으로 과거 동일 ID 저장까지 부정하지 않음 |
| R-05 P2 | 반례 직접 재현. 원문 바이트 corpus, 엄격한 숫자 리터럴·중복 키·UTF-8, 전체 문자열 패턴 명시 |
| R-06 P2 | 바이너리 UTF-8+LF, CRLF 거부. M1 POS 테스트를 Windows CI에도 배치할 계획. 아직 Windows 실행 증거 없음 |
| R-07 P2 | 공식 Microsoft·Android 문서 확인 후 방화벽 우선순위, 프로필, NIC, network_path, Android 17 target 조건 반영. 삼성 기기 정책은 조건부 점검 |
| R-08 P2 | S03의 유휴 복원과 POS commit 후 force-stop을 별도 변형으로 정의. 외부 실행기가 adb 수행 |
| R-09 P2 | 앱 DB와 독립적인 불변 접수 기준 + 새 POS DB 전체 집합·행 수 양방향 대조 |
| R-10 P2 | user_paused 영속, 사용자 재개만 해제. 시도 상한은 실행별 중지 |
| R-11 P3 | 로컬 ID UNIQUE, 초안 ID 재사용, 저장 중 중복 입력 방지. 같은 ID라도 본문 충돌은 성공으로 보지 않음 |
| R-12 P3 | UI 업무 상태를 Room commit에 연결하고 문구 통일 |
| R-13 P3 | ProcessLifecycleOwner와 worker 종료 순서, 취소 상태를 우선한 예외 분류 명시 |
| R-14 P3 | BEGIN IMMEDIATE, busy_timeout, receipt UNIQUE. 모든 IntegrityError를 중복으로 삼지 않음 |
| R-15 P3 | debug 전용 한도 축소/저장 오류 주입을 C01 재현 수단으로 정의, release 제외 |
| R-16 P3 | 제품명 규칙을 지원 대상 회사의 명칭 오용으로 한정. Codex는 실행 도구/에이전트 명칭으로 기록하며 특정 기반 모델을 추정하지 않음. 작성/검토 역할과 수동 점검을 구분 |

F-01은 R-01 해결에 필요한 최소 DB 정체성으로 채택했다. F-02 adb reverse는 선택 가능한 초기 연결 경로이며 LAN 증거와 구분한다. F-03 공개 금지 문자열 자동화는 보류하고 공개 전 수동 점검을 유지한다. F-04 본문의 JSON 예제 검사는 이번에 구현한다.

다음 검토 요청은 M1 실제 왕복 구현 결과에 묶는다. 문서 수정만으로 Android 동작을 입증하지 않는다.
