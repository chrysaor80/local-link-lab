# Local Link Lab

Android 단말과 PC의 POS 시뮬레이터 사이에서 주문 요청을 보존하고, 통신 장애 후 같은 요청을 다시 처리하는 과정을 검증하는 포트폴리오 프로젝트입니다. 실제 결제 승인 기능은 포함하지 않습니다.

현재 단계는 **M0 설계 검토본**입니다. Android 앱·연결 SDK·POS 실행 프로그램은 아직 구현되지 않았습니다. `scripts/check_spec.py`는 명세의 예제와 시나리오 참조를 검사하며 제품 동작을 검증하지는 않습니다.

## 읽는 순서

1. [범위와 완료 기준](docs/SCOPE.md)
2. [통신 및 저장 규칙](docs/PROTOCOL.md)
3. [장애 시나리오와 증거 기준](docs/SCENARIOS.md)
4. [설계 판단 기록](docs/DECISIONS.md)
5. [현재 진행 상태](docs/CONTROL.md)

Windows PC 한 대와 Android 기기 한 대를 같은 LAN에 연결합니다. 첫 버전은 IP 직접 입력과 TCP 통신을 사용합니다. 기기 검색은 후속 단계에서 NSD로 추가합니다.

## 명세 검사

Python 3.10 이상에서 저장소 루트 기준으로 실행합니다.

```powershell
py -m pip install -r requirements-spec.txt
py scripts/check_spec.py
```

Linux에서는 `py` 대신 `python3`를 사용합니다. 앱의 실행·빌드 명령은 M1에서 검증한 뒤 추가합니다.

## 협업

구현 담당은 코드·실행 결과를 제출하고, 검토 담당은 같은 커밋의 명세와 코드를 독립적으로 검토합니다. 문서 확정, 실제 왕복 완료, 장애 검증 완료의 세 시점에 검토를 요청합니다. 현재 요청은 [M0 검토 요청](docs/reviews/M0_REQUEST.md)입니다.

## 공개 참고 자료

- [edge-device-kit](https://github.com/chrysaor80/edge-device-kit): 저장 후 전송과 결함 검출 확인 방식. 주문 보존 정책은 새로 정의합니다.
- [Android Architecture Samples](https://github.com/android/architecture-samples): Compose, ViewModel, Flow, Room과 테스트 구성 참고.
- [kotlinx-coroutines-test](https://github.com/Kotlin/kotlinx.coroutines/tree/master/kotlinx-coroutines-test): 재시도·취소를 가상 시간으로 검증하는 도구.

외부 코드를 복사하는 경우 출처와 라이선스를 별도로 기록합니다. 현재 명세와 검사 스크립트는 이 프로젝트에서 새로 작성했습니다.

MIT License · Wonse Cho
