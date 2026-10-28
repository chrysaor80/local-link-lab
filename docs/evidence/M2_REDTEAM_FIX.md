# M2 독립 검토 수정본 실행 증거

2026-10-28 Asia/Seoul. 구현 `6c7187d021ab5390ab5c3388dfd99b24327a15f3`의 [CI 40639032749](https://github.com/chrysaor80/local-link-lab/actions/runs/40639032749)가 전체 성공했다. [OPUS 보고](../reviews/OPUS_M2_REVIEW_REPORT.md)의 M2-01~06 처리 후 실행이다. 독립 검토 판정은 기존 코드에 대한 조건부 승인이며, 이 수정본의 OPUS 재승인은 아직 없다.

## 실행 대상과 원본

- CI 실제 checkout: `7efeb5746b99780f3fc52a26c2aac28e60a9f611` (PR 합성 merge).
- 구현과 checkout의 동일 tree: `c12de6f48fe86707b293f221448e390e5d4c5737`.
- [원본 APK·로그·DB·JUnit artifact](https://github.com/chrysaor80/local-link-lab/actions/runs/40639032749/artifacts/12794997080), ZIP SHA-256 `6d4b481f1e4d6da6a4437020c162dce0668fdd7d4891aecf61b9db6764747f5d`.
- 정상 debug APK SHA-256: `77422c02ebd7e267826088ee28df666b0f23e32cc0deb535849e47628a35593b`. 실행 전후의 설치 APK와 빌드 파일에서 일치했다.
- [영구 관측 JSON](m2-redteam-fix-observation.json): 접수 전 baseline, DB ID, 단계별 final 인자·실제 행·시도 수·ACK 방출 수·원래 영수증, PID 사건, 정상·결함 사본의 설치 해시, 변이 diff 보존.

## 실행 결과

| 검사 | 결과 |
|---|---|
| 명세 | 시나리오 12개·결함 계획 3개 PASS |
| Python (Windows/Linux 각각) | 26개 PASS |
| 코어 JVM / Controller JVM | 19개 / 7개 PASS |
| Android API 29 정상 / 복구 계측 | 4개 / 2개 PASS, skip 0 |
| 외부 Android 장애 시나리오 | 6개 PASS |
| 결함 사본 | MUT01·MUT02·MUT03 모두 빌드·설치 성공 후 지정 위반으로 KILLED |
| release 제외 | DEX·binary manifest에서 시험 receiver 부재 PASS |

S03_am_kill은 PID 4152 종료 후 4300, S03_force_stop은 4391 종료 후 4475를 관측했다. 두 사례 모두 접수 후와 재실행 후 PENDING·영수증 없음·POS 0건·submit 0회·사용자 중지 worker 상태를 확인한 다음 재개했다.

S03_after_pos_commit은 PID 4565 종료 후 4669를 관측했다. 종료 직전 submit 1회, 재실행 후 submit 2회였고 두 관측 모두 PENDING·영수증 없음·POS 1건·ACK 방출 0회였다. 이후 장벽 해제와 최초 영수증으로 로컬 ACK commit을 확인했다.

MUT01은 POS_EXTRA_ID, MUT02는 ACK_WITHOUT_POS, MUT03은 SENT_WHILE_PAUSED로 검출됐다. MUT03은 중지 상태에서 전송한 사실을 접수 직후 잡아 실패했으며, 이 결함 사본에서 프로세스 종료까지 실행했다고 세지 않는다.

## 구현 담당의 원본 재대조

ZIP 해시 확인 후 내려받은 정상 6개와 결함 3개의 모든 관측을 데이터 판정기·단계 검사로 다시 계산했다. 기록된 위반 집합과 일치했고, S03 두 ACK 장벽 관측도 true였다. 결함 diff 해시 3개, JUnit 네 그룹의 시험 수·실패·누락, 설치 APK와 artifact APK 해시도 대조했다.

이전 [M2 기록](M2_REVIEW.md)은 당시 하네스의 PASS이며 강화된 전제 검사로 소급하지 않는다. 이번 실행은 API 29 에뮬레이터의 emulator-nat 경로다. 삼성 실기기·Windows LAN·전원 차단·전체 OS 조합·영상 촬영은 NOT_RUN이다.
