# M1 독립 검토 요청

구현 담당: Codex. 검토 담당: OPUS. 이 문서는 검토 요청이며 OPUS가 M1을 검토했다는 뜻이 아니다.

## 검토 기준

정상 왕복을 우선 검토한다. Android에서 접수한 합성 주문이 Room에 commit되고, POS에서 원자적으로 저장된 뒤 같은 요청 ID와 영수증으로 UI에 확인되는지 본다. 구현 SHA는 `21e8ad5e3240287683aa1ef9abd0079f481fad76`이며 [M1 CI](https://github.com/chrysaor80/local-link-lab/actions/runs/40620268630)가 전체 성공했다. 후속 커밋은 이 검토 요청과 실행 보고 문서만 추가한다. M0 지적의 처리는 M0_RESPONSE.md에 있다.

## 읽는 순서

1. `docs/PROTOCOL.md`, `docs/reviews/M0_RESPONSE.md`, `docs/evidence/M1.md`.
2. `core/.../Wire.kt`, `TcpTransport.kt`, `DeliveryEngine.kt`와 JVM 테스트.
3. `app/.../Storage.kt`, `LinkApplication.kt`, `MainActivity.kt`.
4. `pos/wire.py`, `store.py`, `server.py`, `test_pos.py`.
5. Android `RepositoryTest.kt`, `RoundTripTest.kt`, `scripts/verify_m1.py`, `.github/workflows/m1.yml`.

`...`는 각각 `src/main/kotlin/dev/locallinklab/core`, `src/main/java/dev/locallinklab/app`이다. Android 테스트는 `app/src/androidTest/java/dev/locallinklab/app` 아래에 있다.

## 집중해서 볼 항목

- 요청 ID·본문·대상 DB·로컬 순서의 원자성, 중복 초안과 한도 거부.
- POS 원자성·동시 중복·본문 충돌·ACK 유실 시 최초 영수증 재사용.
- 소켓 취소가 실제 read를 끝내는지, 취소와 전송 제한 시간을 재시도 정책에서 구분하는지.
- 목적지 변경, 사용자 일시 중지, 프로세스 수명과 단일 worker의 상호작용.
- JSON 원문 검증을 두 언어가 같은 공유 예제로 확인하는지.
- 테스트가 UI 접수 전 기준값·Room 결과·POS 전체 행을 독립적으로 비교하는지. 미실행 항목이 성공처럼 보이지 않는지.

발견한 문제는 `번호 / 심각도 / 파일·줄 / 재현 조건 / 깨지는 불변식 / 권고`로 부탁한다. M1 승인·조건부 승인·수정 후 재검토를 구분하고, M2 범위는 후속 항목으로 적는다.

## 범위와 남은 확인

이번 앱은 고정된 샘플 커피 1개를 접수하는 단일 화면이다. 배포용 SDK 패키징·자동 검색·실결제는 포함하지 않는다. 화면 상태는 Room과 Flow, 화면 초안은 rememberSaveable, 전송 소유자는 프로세스 Controller다. 별도 ViewModel은 사용하지 않았다.

- Room DB 재열기 테스트는 OS 프로세스 종료 복원 증거가 아니다.
- Android 정상 왕복은 API 29 에뮬레이터 NAT다. Windows POS 테스트는 호스팅된 Windows runner의 loopback이다. 사용자 삼성 폰의 LAN/USB 실행은 아직 없다.
- Android 단절·응답 유실·전송 중 프로세스 종료, 두 결함 사본의 검출은 M2에서 별도로 검증한다.
- POS_MISMATCH는 현재 worker를 멈추고 PENDING을 보존한다. 전경 복귀/수동 재개 시 hello 확인을 반드시 거치게 하는 상태 전이는 M2에서 보강할 항목이다. 현재도 매 요청의 DB ID를 POS 트랜잭션에서 검증해 다른 DB에 쓰지 않는다.
- 메모리·장기 부하·실제 저장 공간 고갈·여러 Android 버전·DB 업데이트는 아직 검증하지 않았다.
