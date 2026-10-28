# 설계 판단 기록

2026-10-28 · OPUS의 M0 검토를 반영했다. 처리 내역은 [M0 검토 반영](reviews/M0_RESPONSE.md)에 있다. 이번 수정의 수용 여부는 구현 담당이 판단했으며 OPUS의 재검토 완료를 뜻하지 않는다.

## D01 저장 후 전송과 접수의 의미

주문 본문과 요청 ID가 함께 commit된 시점을 접수로 정의한다. UUID 생성 자체가 반드시 트랜잭션 안에 있어야 하는 것은 아니다. commit 전에 생성한 UUID를 잃어도 아직 전송·접수하지 않았다면 주문 중복은 발생하지 않는다. 위험한 순서는 저장 확정 이전의 전송 또는 접수 완료 표시다.

로컬 저장 완료와 POS 저장 확인을 UI에서 구분한다. [Android 상태 보존 문서](https://developer.android.com/topic/libraries/architecture/saving-states)가 설명하듯 ViewModel과 영속 저장은 프로세스 종료에서 수명이 다르다. 업무 데이터는 Room에 둔다.

## D02 미전송 주문을 버리지 않음

[edge-device-kit의 outbox](https://github.com/chrysaor80/edge-device-kit/blob/main/python/edgekit/outbox.py)는 최신 센서 관측을 남기기 위해 오래된 미전송 데이터를 제거하는 정책을 포함한다. 주문에서는 이미 접수한 작업을 잃지 않는 것이 우선이다. 용량 한도는 새 접수 거부로 처리한다. 저장 실패 이유를 접수 완료 전에 보여준다.

## D03 POS 주문 행이 중복 방지 기록

별도의 메모리 집합이나 먼저 쓰는 처리 ID 테이블을 두지 않는다. request_id 고유 제약을 가진 주문 행과 최초 receipt_id를 한 트랜잭션에서 저장한다. 동시 중복도 이 제약으로 처리한다. 최초 결과는 DB 존속 동안 보존한다. 같은 ID의 다른 내용은 오류다.

## D04 요청별 TCP와 제한 시간

v1은 처리 성능보다 실패 시점의 명확성과 구현 범위를 우선해 시도마다 연결을 연다. 장기 연결의 유휴 상태와 heartbeat 정책은 후속으로 미룬다. 그 대신 연결·쓰기·읽기에 전체 제한 시간을 둬 응답 없는 상대도 멈추지 않게 한다. 요청당 연결 비용은 수용한다. 성능 요구나 다중 단말 도입 시 재검토한다.

평문 TCP는 합성 데이터의 통제된 LAN 데모에만 사용한다. Android의 HTTP 평문 설정을 무조건 켜지 않는다. [NetworkSecurityPolicy](https://developer.android.com/reference/android/security/NetworkSecurityPolicy)는 Socket API가 그 정책을 자동 준수한다고 기대하지 않는다고 설명한다. 이는 앱의 통신 보안이 갖춰졌다는 뜻이 아니다.

## D05 취소·순서·보장 경계

접수 후 취소는 별도 업무 프로토콜이 필요하므로 제외한다. 전송 중지는 주문 취소가 아니다. 가장 오래된 PENDING부터 처리하되 NEEDS_ATTENTION은 보존하고 건너뛴다. 같은 ID의 과거 저장이 없다는 보장이 없는 오류를 CLOSED_UNSENT로 종결하지 않는다. 이 변경으로 전체 POS 저장 순서 보장은 포기한다. 미확인 한도에는 두 상태 모두 포함한다.

## D08 주소와 DB 정체성 분리

잘못된 첫 IP와 DHCP 변경을 복구하려면 주소 잠금만으로 부족하다. maybe_delivered 플래그는 한 번이라도 전송 가능성이 생긴 주문의 주소 변경을 해결하지 못한다. hello/hello_ack와 영속 pos_db_id를 v1에 포함한다. 같은 DB의 새 주소는 허용하고 다른 DB로 미확인 주문을 보내지 않는다. hello 이후 교체도 막도록 제출 본문에 대상 DB ID를 넣고 POS 트랜잭션에서 확인한다. DB 복제·이력 롤백과 악의적 서버 인증은 이 ID가 해결하지 않는다.

## D09 입력 계약과 검증 범위

JSON Schema의 integer는 1.0도 허용한다. 전송 계약에서는 소수·지수 리터럴을 거부하고, 양쪽 파서가 같은 원문 바이트 예제를 읽는다. 정규식의 문자열 끝은 후행 LF 앞을 매칭하는 $ 대신 실제 끝을 확인한다. POS는 바이너리 I/O로 LF를 송신한다. 문서 JSON 예제도 명세 검사에 포함한다.

## D10 사용자 의도 보존

사용자 일시 중지는 영속 설정으로 두고 명시적 재개만 허용한다. 제한 횟수 초과는 실행별 상태다. 앱 수명은 ProcessLifecycleOwner, 업무 UI는 Room에서 복원한다. 취소에 의해 발생한 SocketException을 재시도 사유로 오판하지 않는다.

## D06 자동 테스트와 Android 증거

핵심 정책을 JVM에서 빠르게 검증하고 POS와 실제 TCP를 별도로 확인한다. Android 프로세스 종료는 실제 OS 명령과 PID로 검증한다. [adb 문서](https://developer.android.com/tools/adb)의 kill과 force-stop은 서로 다른 조건이므로 동일한 검증으로 취급하지 않는다.

## D07 협업과 공개

구현은 Codex, 독립 검토는 OPUS, 기기 실행과 설계 이해 확인은 사용자와 함께 진행한다. M0/M1/M2에서만 검토 요청을 묶는다. 의견의 합치 대신 재현 가능한 결과로 결론을 낸다. 공개 저장소에는 공개 출처만 링크하고, 외부 코드의 라이선스는 실제 재사용 시 보존한다.


## D11 M1 실행 구조와 도구 버전

전송 작업은 Application의 Controller 하나가 소유하며 ProcessLifecycleOwner로 전경 여부를 받는다. 화면 회전으로 전송 소유자를 새로 만들지 않는다. 명령 변경은 collectLatest가 이전 작업을 취소하고 기다린 뒤 처리하고, 새 주문은 conflated 채널로 알린다. 한도 초과 이후 새 주문 접수만으로 재시도 예산을 초기화하지 않는다. 화면 초안 ID는 rememberSaveable, 업무 상태와 사용자 중지는 Room에 둔다. 현재 단일 화면에는 별도 ViewModel을 추가하지 않았다.

JDK 17 / Gradle 8.11.1 / AGP 8.9.2 / Kotlin 2.1.20 / Room 2.7.1 / SDK 35 조합을 빌드로 확인했다. minSdk 23은 잠정 하한이다. CI의 API 29 에뮬레이터 결과도 삼성 실기기 검증과 구분한다. M1 APK는 디버그 검증 산출물이며 M3 배포 후보가 아니다.

## D13 독립 검토 후 연결 진단과 전송 수명 분리

OPUS M1-01 재현에서 연결 확인 실패가 기존 worker를 없앴다. 확인 실패는 저장된 목적지를 변경하지 않으므로 같은 설정으로 worker를 다시 실행하며, 실패 결과는 별도 StateFlow로 유지한다. 사용자 중지는 유지한다. 전송 자체 timeout은 SocketTimeoutException으로 변환하고 상위 취소는 전파한다. 잘못된 IPv4는 worker 취소 전에 거부한다.

M1-02는 hello의 시작 시점 캐시를 없애고 현재 metadata를 읽는다. DB를 여는 일반 경로는 mode=rw로 한정한다. M1-03 판정은 Python assert가 아닌 명시적 실패 조건을 사용한다. M1-07은 테스트용 Application/새 DB와 별도 POS를 사용해 사용자의 접수 내역을 테스트에서 읽지 않는다. 원본 보고와 변경 이유는 M1_RESPONSE에 기록한다.
