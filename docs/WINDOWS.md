# Windows와 Android 실행 준비

M0 준비 문서다. APK·POS 프로그램은 M1에서 구현한다. 여기서는 기기·네트워크와 종료 재현의 확인 절차를 정한다.

## 기기 확인

USB 디버깅을 활성화하고 폰에서 해당 PC의 디버깅 연결을 허용한다. Android SDK Platform Tools가 설치된 PowerShell에서 실행한다.

```powershell
adb devices -l
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
```

기기가 여러 대면 이후 모든 adb 명령에 `-s <선택한 serial>`을 넣는다. 공개 결과에는 serial 같은 개인 식별값을 넣지 않는다. 위 버전과 실제 빌드 의존성의 최소 지원 버전을 확인한 뒤 minSdk를 확정한다.

## LAN 연결 확인

1. PC와 폰을 같은 테스트용 공유기에 연결한다. 게스트 Wi-Fi의 기기 간 격리 여부를 확인한다.
2. `ipconfig`로 PC의 해당 NIC IPv4를 확인한다. 폰에서 127.0.0.1은 PC를 뜻하지 않는다.
3. POS 서버가 구현된 뒤 선택한 NIC 주소와 포트 8765에 listen하는지 확인한다. 충돌하면 설정 포트를 함께 바꾼다.
4. Windows 방화벽에서 막히면 아래처럼 **해당 TCP 포트·Private 프로필·LocalSubnet**에 한정한 테스트 규칙을 사용한다. 방화벽 전체를 끄지 않는다.

관리자 PowerShell에서, 신뢰하는 테스트 네트워크가 Private임을 확인한 뒤 사용한다. 이 문서 작성 시 규칙을 실행하거나 방화벽을 변경하지 않았다.

```powershell
New-NetFirewallRule -DisplayName "Local Link Lab TCP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private -RemoteAddress LocalSubnet
```

테스트 규칙이 필요 없어지면 제거한다.

```powershell
Remove-NetFirewallRule -DisplayName "Local Link Lab TCP"
```

Android INTERNET 권한 및 대상 OS/SDK의 LAN 접근 정책은 M1에서 확인한다. v1 raw TCP에 HTTP용 평문 허용 설정을 무조건 추가하지 않는다. HTTP로 바꾸면 그에 맞는 정책과 위협 범위를 다시 검토한다.

## 프로세스 종료 기록

예정 applicationId는 `dev.locallinklab.demo`다. M1의 실제 manifest와 확인한 뒤 다음 명령을 사용한다. 테스트 시작 전 미확인 주문의 ID·본문과 `LOCAL_COMMITTED` 이벤트를 기록한다.

`am kill` 실행:

```powershell
adb shell pidof dev.locallinklab.demo
adb shell input keyevent KEYCODE_HOME
adb shell am kill dev.locallinklab.demo
adb shell pidof dev.locallinklab.demo
```

기존 PID가 실제 종료됐는지 확인한다. 종료되지 않으면 해당 실행은 BLOCKED이며 성공으로 세지 않는다. 폰에서 앱을 다시 열어 새 PID, 같은 요청 ID·본문, POS 1건, 로컬 확인 상태를 기록한다.

`force-stop`은 별도의 새 실행으로 기록한다.

```powershell
adb shell am force-stop dev.locallinklab.demo
adb shell pidof dev.locallinklab.demo
```

사용자가 앱을 다시 열어 복원을 확인한다. force-stop 이후 자동 백그라운드 재개를 기대하지 않는다. 예약 작업을 포함한 구체적인 영향은 OS/API에 따라 달라질 수 있으므로 모든 Android 버전에서 동일하다고 주장하지 않는다.

두 방식 모두 실제 저메모리 상황이나 물리 전원 차단을 재현한 증거로 사용하지 않는다. [공식 adb 명령 설명](https://developer.android.com/tools/adb)을 기준으로 어떤 명령을 사용했는지 보고서에 남긴다.
