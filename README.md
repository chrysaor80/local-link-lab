# Local Link Lab

Android 단말과 PC의 POS 시뮬레이터 사이에서 주문 요청을 보존하고, 통신 장애 후 같은 요청을 다시 처리하는 과정을 검증하는 포트폴리오 프로젝트입니다. 실제 결제 승인 기능은 포함하지 않습니다.

현재 단계는 **M1 구현 검증 중**입니다. Android 앱, Kotlin 연결 코어, Python POS를 구현했습니다. 로컬에서 APK 빌드·JVM 테스트·POS 실제 TCP 테스트를 통과했으며, Android 실행 결과는 [진행 기록](docs/CONTROL.md)에 따로 표시합니다. `scripts/check_spec.py`는 명세의 일관성만 검사합니다.

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

Linux에서는 `py` 대신 `python3`를 사용합니다.

## 실행

JDK 17, Android SDK 35, Python 3.10 이상이 필요합니다. `local.properties`에 로컬 SDK 경로를 설정하거나 `ANDROID_HOME`을 지정합니다. Gradle Wrapper가 고정 버전을 다운로드합니다. Windows PowerShell에서:

```powershell
py -m unittest pos.test_pos -v
.\gradlew.bat :core:test :app:assembleDebug
py -m pos.server --db artifacts/pos.db --host 192.168.0.10 --port 8765
```

`app/build/outputs/apk/debug/app-debug.apk`를 설치하고, 앱에서 PC의 LAN IPv4와 포트 `8765`를 입력해 **연결 확인 → 기기에 주문 접수**를 실행합니다. 두 번째 주문은 **새 주문 준비**로 별도 ID를 만듭니다. `POS 저장 확인`은 서버 영수증을 Android DB에도 저장한 뒤 표시됩니다. 주소·방화벽·USB 확인 절차는 [Windows 안내](docs/WINDOWS.md)를 참고하세요.

에뮬레이터에서는 호스트 주소 `10.0.2.2`, USB 포워딩에서는 `adb reverse tcp:8765 tcp:8765` 후 `127.0.0.1`을 사용합니다. 이 경로들은 Wi-Fi LAN 검증과 구분합니다. 서버는 기본적으로 `127.0.0.1`에만 바인딩합니다. 위 `192.168.0.10`은 예시이므로 `ipconfig`로 확인한 PC의 실제 LAN IPv4로 바꾸세요.

합성 주문만 사용하세요. 실결제 승인, TLS/인증, 자동 검색, 백그라운드 지속 전송은 포함하지 않습니다. 현재 최소 버전은 Android 6/API 23으로 잠정 설정했으며 사용자 기기 호환성은 확인 전입니다.

## 구성과 검사

- `core`: 엄격한 메시지 파서, 취소 가능한 TCP, 재시도와 주문 확인 정책. JVM 테스트 9개.
- `app`: Compose 화면, Room 주문 보관, 프로세스 전경 수명에 맞춘 단일 전송 작업.
- `pos`: SQLite 트랜잭션과 중복 방지, 바이너리 TCP 서버. Python 테스트 7개.
- `spec`: 두 언어가 공유하는 원문 메시지 31개와 장애 시나리오 정의.
- `.github/workflows/m1.yml`: Linux/Windows POS 검사, APK/JVM 검사, Android 에뮬레이터에서 UI·Room·POS 전체 DB 대조. 실행 결과는 Actions에서 확인합니다.


## 협업

구현 담당은 코드·실행 결과를 제출하고, 검토 담당은 같은 커밋의 명세와 코드를 독립적으로 검토합니다. 문서 확정, 실제 왕복 완료, 장애 검증 완료의 세 시점에 검토를 요청합니다. [M0 검토 처리 결과](docs/reviews/M0_RESPONSE.md)를 반영해 M1을 구현 중입니다.

## 공개 참고 자료

- [edge-device-kit](https://github.com/chrysaor80/edge-device-kit): 저장 후 전송과 결함 검출 확인 방식. 주문 보존 정책은 새로 정의합니다.
- [Android Architecture Samples](https://github.com/android/architecture-samples): Compose, ViewModel, Flow, Room과 테스트 구성 참고.
- [kotlinx-coroutines-test](https://github.com/Kotlin/kotlinx.coroutines/tree/master/kotlinx-coroutines-test): 재시도·취소를 가상 시간으로 검증하는 도구.

외부 코드를 복사하는 경우 출처와 라이선스를 별도로 기록합니다. 현재 명세와 검사 스크립트는 이 프로젝트에서 새로 작성했습니다.

MIT License · Wonse Cho
