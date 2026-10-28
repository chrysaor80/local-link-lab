# OPUS 요청: M1 수정 확인과 M2 독립 검토

검토할 제품 코드는 **`127ea3232bd6a6dc9b8c1b54eca78b3e092127d7`**로 고정한다. [해당 코드](https://github.com/chrysaor80/local-link-lab/tree/127ea3232bd6a6dc9b8c1b54eca78b3e092127d7), [PR #2](https://github.com/chrysaor80/local-link-lab/pull/2). 이 요청과 후속 증거 문서 커밋은 제품 코드를 바꾸지 않는다.

[OPUS 원본 M1 보고서](OPUS_M1_REVIEW_REPORT.md)와 패치를 보존했고, [구현 담당 처리 기록](M1_RESPONSE.md)에 재현·수정·테스트 조정 이유를 남겼다. M1 수정본과 M2 통합본 모두 CI를 통과했다. [최신 M2 실행 근거](../evidence/M2_REVIEW.md)와 [관측 JSON](../evidence/m2-review-observation.json)을 확인해 달라. CI 실제 merge checkout SHA는 `85d9da1d899852932582c3dee5129e33733e7db4`이며 검토 코드와 tree가 같다. 독립 검토 완료를 미리 주장하지 않는다.

## 맡길 역할

구현 담당은 Codex다. OPUS는 같은 고정 코드의 **독립 검토·레드팀·최소 재현 테스트**를 맡는다. 검토 중 제품 코드 변경이나 다른 브랜치 통합은 하지 않고, 필요한 최소 재현 테스트는 별도 patch로 제출한다. 테스트 결과가 정적 판단을 바꾸면 둘을 구분해 갱신한다.

1. **M1-01 수정 확인:** 실패/침묵 probe 이후 기존 목적지 전송이 실제로 재개되는가? 오류 사유가 전송 상태에 덮이지 않는가? 사용자 중지·상위 취소·미확인 주문이 있는 다른 DB 변경 거부는 유지되는가? 자체 timeout의 통신 오류 변환이 상위 취소를 삼키지 않는가?
2. **M1 보조 수정 확인:** 현재 DB ID 응답과 파일 미생성, 일반/`-O` 검사 거부, ASCII IPv4 입력, 테스트 DB 분리가 계약에 맞는가? 원본 hello 테스트의 기대를 조정한 이유가 타당한가? Windows QuickEdit는 미재현으로 남긴 판단을 구분한다.
3. `lab/android_run.py`: commit 사건 이후에 장애가 주입되는가? PID 종료·재실행을 실제로 관측하는가? 실행 누락·환경 실패가 PASS가 될 경로가 있는가?
4. `lab/verdict.py`: 앱과 POS가 동시에 틀린 ID로 바뀌어도 접수 전 기준으로 검출하는가? 추가 행·본문·최초 영수증을 비교하는가?
5. `lab/mutations.py`: 정상과 동일한 판정기인가? 빌드/설치 실패를 KILLED로 오인하는가? 결함 diff와 관측 데이터가 일치하는가?
6. `app/src/debug` / `DestinationVerifier.kt`: 실제 화면과 같은 Controller를 사용하는가? debug 제어 권한·응답·release 제외가 맞는가? 재개 전 hello와 주문 트랜잭션의 DB ID 검사가 함께 유지되는가?

## 제출 형식과 범위

`OPUS_M2_REVIEW_REPORT.md` 한 파일과 필요할 때 재현 patch를 제출한다. 발견은 ID·중요도·고정 파일/줄·기대/실제·재현 명령·환경·실행 여부·권고를 포함한다. 확정 버그, 통과한 회귀, 미검증 가설을 구분한다. 승인/조건부 승인/변경 필요 판단과 지원용 시연을 막는 항목을 앞에 둔다. 비공개 저장소명·내부 작업 경로·인증 정보를 넣지 않는다.

이번에는 데이터 보존, 취소/복구 경계, 검증 근거의 신뢰성을 우선한다. BLE·USB·자동 검색·새 플랫폼·성능 대시보드는 추가하지 않는다. 기기/LAN, 실제 전원 차단·저메모리·디스크 고갈, 모든 UI 동시 조작은 현재 보장의 범위 밖이다. 실행하지 못한 항목은 NOT_RUN/BLOCKED로 기록한다.
