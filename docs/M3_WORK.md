# M3 시연·지원 준비

OPUS의 고정 검토 대상은 `127ea3232bd6a6dc9b8c1b54eca78b3e092127d7`이다. M3는 그 구현을 바꾸지 않고 CI 산출물과 실행·설명 자료를 준비한다. 검토 결과의 새 결함은 시연 확장보다 우선한다.

## 이번 작업과 종료 기준

| 항목 | 범위 | 완료 판단 |
|---|---|---|
| 시연 후보 | 통과한 동일 debug APK + POS 코드 + 실행 안내 + manifest | 필수 CI 성공, SHA/결과 대조 후 별도 artifact 생성 |
| Windows·폰 안내 | 설치·LAN·같은 DB 재시작·수동 복원·결과 기록 | 절차 문서 준비. 실기기 실행 완료와 구분 |
| 영상 | 정상/단절/ACK 유실/프로세스 종료의 2~3분 구성 | 촬영 계획 준비. 실제 촬영·편집은 별도 상태 |
| 지원 설명 | 문제·설계 선택·검증·한계·면접 설명 | 실행한 사실과 본인 판단을 구분한 초안 |

## 후보 생성 규칙

`.github/workflows/m1.yml`의 candidate job은 spec, pos(Windows/Linux matrix), android가 모두 성공해야 실행된다. 진단용 `android-fault-evidence`는 실패 때도 보존하지만 시연 후보 업로드는 성공 경로에만 있다. 후보는 GitHub Actions artifact이며 GitHub Release 게시나 실매장 배포가 아니다.

1. 앱 빌드 직후, 에뮬레이터 실행 전에 실제 checkout SHA와 debug APK SHA-256을 `verification-input.json`에 기록한다.
2. 정상·회귀·장애 6개와 결함 사본 2개를 실행한다. 정상 APK는 재빌드하지 않고 해당 실행의 증거 artifact에서 가져온다.
3. candidate job은 동일 소스인지, APK 해시가 유지됐는지, JUnit 네 그룹이 존재하고 실패/오류/누락 없이 최소 19/6/4/2개 및 필수 사례를 실행했는지 확인한다. 테스트 수·필수 이름은 현재 필수 회귀 하한이며 테스트 계약이 달라지면 함께 검토한다.
4. 정상 결과 6개가 중복/누락 없이 PASS인지, 결함 2개가 같은 소스에서 빌드/설치 성공 후 지정된 데이터 위반으로 KILLED인지 확인한다. 검사에는 Python assert를 사용하지 않는다.
5. 모두 만족한 뒤 `local-link-lab-demo-<CI checkout SHA>` artifact를 생성한다. manifest에는 source, CI run/attempt, APK와 동봉 파일 해시, debug 제어 포함 여부, 에뮬레이터 검증 범위와 실기기 NOT_RUN을 남긴다.

이 절차는 CI 내부의 실행 결과·파일 일치 검증이다. 악의적인 저장소 관리자에 대한 공급망 인증이나 APK 운영 서명 체계는 제공하지 않는다. OPUS의 검토 판정도 자동 승인으로 바꾸지 않는다.

## 검증 방법

`python -m unittest lab.test_candidate -v`와 `python -O -m unittest lab.test_candidate -v`는 실패한 job, 빠진 stamp/시나리오, 빈/건너뛴 JUnit, 다른 소스, 바뀐 APK, 빌드 실패를 KILLED로 잘못 표기한 결과 등을 거부하고 후보 폴더가 생기지 않는지 검사한다. 합성 파일 fixture이며 Android 실행의 대체 증거가 아니다. 실제 후보 생성은 새 CI에서 끝까지 실행해 확인한다.

## 사용자와 진행할 부분

[설치·LAN 안내](DEMO_QUICKSTART.md), [영상 촬영 계획](DEMO_VIDEO.md), [지원·면접 설명 초안](PORTFOLIO.md)을 사용한다. 삼성 폰의 기종/API, USB 승인, 사용자 PC의 LAN·방화벽은 사용자가 실제 기기에서 관측해야 한다. CI Windows 테스트가 그 환경의 성공을 대신하지 않는다.

시연 후보의 debug 서명 키는 CI 실행마다 달라질 수 있다. 설치 충돌을 자동 삭제로 해결하지 않으며, 테스트 폰의 기존 주문 데이터 보존 여부를 먼저 확인한다. 배포용 signing key/Play Store/자동 업데이트는 후속 범위다.
