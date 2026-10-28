# Windows와 Android 실행 준비

M1 실행 안내다. APK·POS의 빌드와 실행은 README를 따르고, 여기서는 실기기·네트워크와 종료 재현의 확인 절차를 정한다. CI Windows POS 성공과 사용자 PC/폰 검증은 별개다.

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
2. `ipconfig`로 폰의 Wi-Fi와 같은 서브넷인 실제 Wi-Fi/Ethernet NIC IPv4를 고른다. vEthernet·VPN·가상머신 어댑터는 제외한다. 폰에서 127.0.0.1은 PC를 뜻하지 않는다.
3. POS 서버를 선택한 NIC 주소와 포트 8765에 실행하고 listen하는지 확인한다. 충돌하면 설정 포트를 함께 바꾼다.
4. Windows 방화벽에서 막히면 아래처럼 **해당 TCP 포트·Private 프로필·LocalSubnet**에 한정한 테스트 규칙을 사용한다. 방화벽 전체를 끄지 않는다.

관리자 PowerShell에서, 신뢰하는 테스트 네트워크가 Private임을 확인한 뒤 사용한다. 이 문서 작성 시 규칙을 실행하거나 방화벽을 변경하지 않았다.

```powershell
New-NetFirewallRule -DisplayName "Local Link Lab TCP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private -RemoteAddress LocalSubnet
```

테스트 규칙이 필요 없어지면 제거한다.

```powershell
Remove-NetFirewallRule -DisplayName "Local Link Lab TCP"
```

프로필 확인은 `Get-NetConnectionProfile`로 한다. 신뢰하는 테스트 NIC에 한해서 관리자 권한으로 `Set-NetConnectionProfile -InterfaceIndex <확인한 번호> -NetworkCategory Private`를 사용할 수 있다. 모든 네트워크를 일괄 변경하지 않는다.

명시적 차단 규칙은 허용 규칙보다 우선한다. Python 경고를 취소하면 차단 규칙이 생길 수 있다. 아래로 해당 프로그램 규칙을 확인하고 관련된 규칙만 원인을 검토한다. [Microsoft 공식 규칙](https://learn.microsoft.com/windows/security/operating-system-security/network-security/windows-firewall/rules).

```powershell
Get-NetFirewallRule -Direction Inbound -Action Block -Enabled True | Get-NetFirewallApplicationFilter | Where-Object Program -like '*python*'
```

에뮬레이터의 10.0.2.2는 호스트 loopback을 가리키므로 서버를 127.0.0.1에 bind한다. USB의 `adb reverse tcp:8765 tcp:8765`도 서버 loopback을 사용하고 앱에서는 127.0.0.1로 접근한다. 둘 다 실제 LAN 방화벽 통과 증거가 아니다. 결과에 network_path를 기록한다.

Android INTERNET 권한이 필요하다. Android 17 이상 기기에서 targetSdk 37 이상이면 ACCESS_LOCAL_NETWORK 런타임 권한이 적용된다. Android 16은 opt-in 여부도 확인한다. 기기·target 조합을 함께 기록한다. [Android 공식 LAN 권한](https://developer.android.com/privacy-and-security/local-network-permission). raw TCP에 HTTP용 평문 허용 설정을 무조건 추가하지 않는다.

adb 목록이 비어 있으면 케이블·USB 모드·삼성 OEM 드라이버를 확인하고, unauthorized이면 폰의 디버깅 승인 창을 확인한다. One UI 6 이상 기기는 Auto Blocker 정책도 확인한다. 해당 설정의 기본값이나 적용 여부를 모든 삼성 기기에 일반화하지 않는다. Android 11 이상이면 무선 디버깅을 대안으로 쓸 수 있다.

## 프로세스 종료 기록

M1 applicationId는 `dev.locallinklab.app`이다. 아래 종료 시험은 M2 검증 절차이며 현재 실행 완료를 의미하지 않는다. 테스트 시작 전 미확인 주문의 ID·본문과 `LOCAL_COMMITTED` 이벤트를 기록한다.

`am kill` 실행:

```powershell
adb shell pidof dev.locallinklab.app
adb shell input keyevent KEYCODE_HOME
adb shell am kill dev.locallinklab.app
adb shell pidof dev.locallinklab.app
```

기존 PID가 실제 종료됐는지 확인한다. 종료되지 않으면 BLOCKED다. 이 순서는 worker가 이미 중지된 유휴 PENDING 복원 시험이다. 전송 중 사망 증거로 사용하지 않는다. 앱을 다시 열어 새 PID, 같은 ID·본문, POS 1건, 로컬 확인을 기록한다.

`force-stop`은 별도의 새 실행으로 기록한다.

```powershell
adb shell am force-stop dev.locallinklab.app
adb shell pidof dev.locallinklab.app
```

사용자가 앱을 다시 열어 복원을 확인한다. force-stop 이후 자동 백그라운드 재개를 기대하지 않는다. 예약 작업을 포함한 구체적인 영향은 OS/API에 따라 달라질 수 있으므로 모든 Android 버전에서 동일하다고 주장하지 않는다.

두 방식 모두 실제 저메모리 상황이나 물리 전원 차단을 재현한 증거로 사용하지 않는다. [공식 adb 명령 설명](https://developer.android.com/tools/adb)을 기준으로 어떤 명령을 사용했는지 보고서에 남긴다.

전송 중 종료는 별도로 POS_COMMITTED hook에서 ACK를 보류한 상태를 확인한 뒤 외부 실행기로 force-stop한다. 재실행 후 최초 receipt가 돌아오고 POS 전체 행이 하나인지 검사한다. hook과 실행기 구현은 M2에서 제공한다.
