# 통신 및 저장 규칙 v1

M0 검토 반영본. 구조는 [wire.schema.json](../spec/wire.schema.json), 원문 바이트 계약은 [wire.raw-examples.json](../spec/wire.raw-examples.json)을 따른다. JSON Schema만으로 숫자 표기·중복 키·UTF-8·프레임 경계를 검증했다고 주장하지 않는다.

## I01 로컬 접수와 ID

- 주문 초안마다 UUID v4 하나를 배정해 재사용하고 저장 중 중복 접수를 막는다. ID 생성은 트랜잭션 밖이어도 되지만 ID·불변 본문·대상 pos_db_id·로컬 증가 순번은 함께 commit한다. 로컬 request_id는 UNIQUE다.
- commit 전에는 전송하거나 `기기에 접수됨`을 표시하지 않는다. 저장 실패는 `접수되지 않음`과 이유를 표시한다. commit 결과가 불분명하면 같은 ID로 조회/재시도하고 본문 일치를 확인한다. 다른 내용이면 성공이 아니다.
- commit 후 UI 갱신 전에 죽어도 기존 접수를 DB에서 복원한다. 새 접수 동작 없이 자동으로 새 주문을 생성하지 않는다.
- PENDING + NEEDS_ATTENTION 합계 최대 1,000건. 기존 초안 행 확인 → 한도 확인 → 삽입을 같은 트랜잭션에서 직렬화한다. 초과·저장 오류는 새 접수만 거부하고 기존 행을 삭제하지 않는다.
- 첫 접수 전에는 주문을 생성하지 않는 hello로 POS를 확인하고 DB ID를 저장한다. 이후 해당 DB에 묶인 주문은 오프라인 접수가 가능하다.

## I02 POS 원자성과 중복 방지

- POS 초기화 시 UUID v4인 pos_db_id를 metadata에 commit한다. 재시작해도 동일하다. 주문 request_id는 PRIMARY KEY, receipt_id는 UNIQUE다.
- SQLite WAL, synchronous=FULL, busy_timeout=1,000ms를 기본으로 기록한다. BEGIN IMMEDIATE로 시작해 같은 트랜잭션에서 대상 DB ID 확인·기존 행 확인·주문과 receipt 저장을 수행한다.
- 같은 ID·같은 파싱된 본문이면 최초 receipt의 ACK. 같은 ID·다른 본문이면 ID_CONFLICT이며 기존 행을 보존한다. 본문 동일성은 item_code·quantity·unit_price_krw로 판단하고 JSON 키 순서에는 의존하지 않는다.
- 동시 연결도 고유 제약과 트랜잭션으로 처리한다. 모든 IntegrityError를 중복 성공으로 취급하지 않는다. 실제 기존 request_id 행·본문·receipt를 확인한다.
- ACK는 commit 성공 뒤에만 가능하다. 주문·ID·receipt는 DB 존속 동안 보존한다. DB 삭제·손상·과거 백업 복원·복제 DB의 분기는 보장 밖이다. pos_db_id는 인증 수단이 아니다.
- 동일 ID의 주문 저장 효과를 한 건으로 제한한다. 외부 결제·인쇄 등의 exactly-once를 주장하지 않는다.

## I03 원문 프레임과 연결

- 송신은 바이너리 I/O로 정확히 UTF-8 JSON 객체 + 0x0A. LF 포함 최대 8,192바이트. CRLF·BOM, 중복 JSON 키, 잘못된 UTF-8, NaN/Infinity, 추가 필드, 잘못된 타입/범위, LF 이전 EOF, 초과 길이는 거부한다.
- 정수는 소수점·지수 없는 JSON 정수 리터럴만 허용한다. 1.0·1e0·boolean을 거부한다. UUID와 item_code는 전체 문자열이 패턴과 일치해야 하며 이스케이프된 후행 LF도 거부한다.
- 한 시도마다 TCP 연결 하나를 열고 요청 한 프레임·응답 한 프레임 후 닫는다. 단말 worker와 진행 주문은 각각 하나다. 주기적 heartbeat는 없다. 한 read를 한 메시지로 가정하지 않는다.
- 기본 포트 8765(변경 가능). loopback·에뮬레이터·adb reverse는 127.0.0.1 bind, LAN Wi-Fi는 실제 NIC IPv4 bind. network_path를 따로 기록한다.
- 클라이언트 접속 제한 2초, 연결·쓰기·읽기 전체 5초. 단조 시계를 쓰고 부분 수신으로 시간을 연장하지 않는다.
- POS는 동시 연결을 처리하되 최대 활성 연결 32개. 수락부터 첫 LF까지 전체 5초, 응답 쓰기 1초 제한. 초과 시 닫고 자원을 해제한다. 침묵 연결 하나가 다른 요청을 막으면 안 된다.
- SQLite busy/locked는 클라이언트 제한보다 짧게 종료하고 TEMPORARY_UNAVAILABLE 또는 연결 종료로 처리한다.
- 취소·제한 시간에는 실제 소켓을 닫는다. SocketException이어도 job 취소가 원인이면 재시도하지 않는다. withTimeout만으로 blocking I/O가 끝난다고 가정하지 않는다.

## I06 목적지 확인과 주소 변경

hello는 주문을 만들지 않는 첫 설정·주소 변경 진단이다.

```json
{"version":1,"type":"hello"}
```

```json
{"version":1,"type":"hello_ack","pos_db_id":"323e4567-e89b-42d3-a456-426614174000"}
```

같은 pos_db_id가 확인되면 미확인 주문이 있어도 IP/포트 변경을 허용한다. 다른 DB면 미확인(PENDING+NEEDS_ATTENTION) 주문이 있을 때 변경을 거부한다. worker를 중지·종료한 뒤 목적지와 DB ID를 원자적으로 저장하고 재개한다.

hello 뒤 DB가 교체되는 경쟁도 막도록 모든 주문에 대상 pos_db_id를 포함한다. POS는 주문 트랜잭션에서 이를 확인하고 불일치 시 POS_MISMATCH, 쓰기 없음. 앱은 PENDING을 유지하고 목적지 재확인까지 자동 시도를 중지한다.

```json
{"version":1,"type":"submit_order","pos_db_id":"323e4567-e89b-42d3-a456-426614174000","request_id":"123e4567-e89b-42d3-a456-426614174000","order":{"item_code":"COFFEE","quantity":1,"unit_price_krw":4500}}
```

```json
{"version":1,"type":"ack","pos_db_id":"323e4567-e89b-42d3-a456-426614174000","request_id":"123e4567-e89b-42d3-a456-426614174000","receipt_id":"223e4567-e89b-42d3-a456-426614174000"}
```

## I04 응답 의미·재시도·순서

ERROR는 version=1, type=error, 서버 pos_db_id, request_id(해석 불가 시 null), code를 가진다.

| code | 서버의 이번 시도 | 클라이언트 |
|---|---|---|
| INVALID_REQUEST / UNSUPPORTED_VERSION | 입력 검증 중 쓰기 전 거부. 같은 ID의 과거 저장까지 없다는 뜻은 아님 | 일치하는 ID/DB 응답이면 NEEDS_ATTENTION |
| ID_CONFLICT | 다른 본문의 기존 행이 있음, 기존 행 보존 | NEEDS_ATTENTION, 저장 없음으로 단정하지 않음 |
| TEMPORARY_UNAVAILABLE | 저장 여부 불확실 가능, busy 포함 | 같은 ID로 제한된 재시도 |
| POS_MISMATCH | 대상 DB 불일치, 이번 시도 쓰기 없음 | PENDING 유지, 목적지 재확인까지 중지 |

commit 이후 예외나 commit 불확실성을 INVALID/UNSUPPORTED/CONFLICT로 바꾸지 않는다. TEMPORARY_UNAVAILABLE 또는 응답 없이 종료한다. null·다른 요청 ID·다른 DB 응답을 업무 결과에 적용하지 않는다(POS_MISMATCH의 목적지 중지 처리는 예외).

- 영속 상태는 PENDING / ACKNOWLEDGED / NEEDS_ATTENTION. ACK의 요청 ID·대상 DB·receipt를 검증한 뒤 상태와 receipt를 함께 commit해야 `POS 저장 확인`을 표시한다. 기록 실패면 PENDING이다.
- NEEDS_ATTENTION은 진단 목록에 보존하고 자동 전송 대상에서 제외한다. 다음 PENDING을 처리한다. 사용자의 `다시 확인`은 같은 ID·본문으로 PENDING 복귀다. 취소·삭제·미저장 확정이 아니다.
- 선택 시 가장 오래된 PENDING부터 처리한다. 그 요청의 통신 오류 동안 뒤 요청은 기다리며, NEEDS_ATTENTION은 건너뛴다. 전체 주문의 POS 저장 순서는 보장하지 않는다.
- 1회 실행 최대 5시도, 지연 1·2·4·8초 + 0~20% jitter. 시간·난수 주입. 상한 중지는 실행 중 상태이며 새 전경 실행/수동 재개로 같은 ID를 재시도한다.
- 연결 실패·응답 불완전·제한 시간은 주문 실패 확정이 아니다. 요청을 보존한다.

## I05 사용자 중지·수명·UI

- 접수 후 주문 취소·수정·삭제는 제외한다. 전송 중지는 이미 처리된 주문을 되돌리지 않는다.
- 사용자 중지는 영속 설정 user_paused로 저장하고 명시적 재개로만 해제한다. 재실행·전경 복귀가 해제하지 않는다. 시도 상한 중지와 구분한다.
- 전경은 ProcessLifecycleOwner ON_START/ON_STOP 기준. STOP 시 worker 취소·소켓 닫기. START 시 이전 worker 종료 후 단일 worker 시작(user_paused면 시작 안 함). 회전은 중복 worker를 만들지 않는다.
- 업무 UI는 Room의 commit된 상태에서 만든다. PENDING=`기기에 접수됨 · POS 확인 대기`, ACKNOWLEDGED=`POS 저장 확인`, NEEDS_ATTENTION=`확인 필요`. 전송 중·재시도 대기·사용자 중지는 별도 실행 상태다.
- 프로세스 종료 후 명시적 재실행 때 DB로 복원한다. 자동 앱 재실행·백그라운드 지속 전송은 보장하지 않는다.

프로세스 종료는 전원 차단·장치 고장 시험이 아니다. [SQLite 원자성](https://www.sqlite.org/atomiccommit.html)과 실제 journal/synchronous 설정을 구분해 기록한다.
