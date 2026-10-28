# 검토 수정 반영 후 시연 후보

2026-10-28 Asia/Seoul. 고정 통합 구현 `70a634720333d12cce0642f357a338850e919fb4`의 [CI 40639250044](https://github.com/chrysaor80/local-link-lab/actions/runs/40639250044)가 모든 필수 검사와 후보 생성을 완료했다. [M2 수정](M2_REDTEAM_FIX.md)을 통합하고 하네스 v2·설치 APK 일치·S03 단계 관측·결함 3종을 후보 조건으로 요구한다.

- **[새 시연 묶음 다운로드](https://github.com/chrysaor80/local-link-lab/actions/runs/40639250044/artifacts/12794744175)**: debug APK, POS 코드, 실행 안내, 파일 해시 manifest.
- [원본 검증 artifact](https://github.com/chrysaor80/local-link-lab/actions/runs/40639250044/artifacts/12794593112): 시험 XML·단계별 관측·접수 전 기준·DB·로그·변이 diff·빌드 APK.
- [영구 관측 JSON](m3-redteam-fix-observation.json): 정상과 결함 사본의 모든 단계 재판정 입력, 실제 설치 해시, 후보 manifest.
- [Windows·폰 안내](../DEMO_QUICKSTART.md), [영상 계획](../DEMO_VIDEO.md), [지원·면접 초안](../PORTFOLIO.md).

## 검사 대상과 결과

CI checkout은 PR 합성 merge `9a8496e6168077cf769d1c9232742c6409a686c1`이다. 통합 구현과 tree `7094c1723c70c983c55fa041d7523cdc20bdfe12`가 같다. 후속 보고 문서 커밋은 이 검증된 구현을 바꾸지 않는다.

Python 38개(Windows/Linux 각각), 별도 후보 조건 12개(-O), 코어 JVM 19개, Controller JVM 7개, Android API 29 정상 4개·복구 2개가 통과했다. 외부 장애 6개 PASS, 결함 3개 KILLED다. 필수 검사를 생략하거나 skip한 사례는 없다.

후보 APK SHA-256은 `5306bfa311c9175455c6818f99407489150aec970bd6ac82d77d2f43eea5a95e`다. 빌드 직후 stamp, Android 실행 전후 실제 설치 파일, 가져온 검증 APK, 후보에 담긴 APK가 모두 같다. CI 실행마다 debug 서명 키가 달라질 수 있으므로 이전 M2 실행의 APK와 동일 바이트라고 주장하지 않는다.

원본 재대조에서 유휴 S03 두 변형의 접수 후/복원 후 submit 0회와 PENDING을 확인했다. commit 후 종료는 종료 전 1회·복원 후 2회 제출됐으나 두 관측 모두 ACK 방출 0회·PENDING이었다. MUT03은 중지 중 전송을 SENT_WHILE_PAUSED로 검출했다. 모든 관측의 데이터·단계 위반 집합과 변이 diff 해시를 재계산해 기록과 일치함을 확인했다.

후보 ZIP SHA-256: `074c216e4565c29a539288977bed351ed2b76ab30ceaef697f4c06aedc6c4071`.
검증 ZIP SHA-256: `63fd800ece60f110279705d93ca7286d1bf7fb7ac863498eafceef125d2f01ba`.

두 ZIP을 내려받아 해시를 대조하고 후보 manifest의 모든 동봉 파일을 확인했다. 가져온 원본으로 후보 판정을 다시 실행해 같은 결과를 얻었다. 묶음의 POS만 별도 임시 DB와 loopback TCP에서 실행해 hello와 동일 주문 2회 제출 → 전체 1행·같은 영수증을 확인했다. 이것은 삼성 폰/LAN 검증의 대체가 아니다.

## 남은 범위

후속 [OPUS 재확인 보고](../reviews/OPUS_M2_RECHECK_REPORT.md)는 M2 수정본 6c7187d를 승인했다. 이 M3 후보의 추가 P3는 [처리 기록](../reviews/M2_RECHECK_RESPONSE.md)으로 추적하며, 아래 실행 이력과 후속 보강의 검증을 구분한다. 이 후보는 통제된 합성 주문 시연용 debug APK이며 시험 제어를 포함한다. 실결제·운영 릴리즈·삼성 실기기·Windows LAN·영상 촬영은 완료하지 않았다. [이전 후보 기록](M3.md)은 S03 전제 검사 누락이 있던 당시 실행 이력으로 보존한다.
