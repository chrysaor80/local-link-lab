# Windows·Android 시연용 묶음

이 묶음은 모든 필수 CI 검사를 통과한 **debug APK와 동일 커밋의 POS 시뮬레이터**다. 소스·CI 실행·파일 SHA-256은 `manifest.json`에 있다. 합성 주문을 쓰는 통제된 테스트 LAN용이며, APK에 DUMP 권한으로 보호된 debug 시험 제어가 포함돼 있다. 현재 실행 증거는 Android API 29 에뮬레이터다. 삼성 실기기 실행 결과는 별도로 기록한다.

## 1. 준비와 파일 확인

Windows에 Python 3.10 이상과 Android SDK Platform Tools(adb)를 준비한다. APK를 설치해 시연할 때는 JDK나 Android Studio 빌드가 필요하지 않다. ZIP을 새 폴더에 풀고 PowerShell에서 그 폴더로 이동한다.

```powershell
$demoManifest = Get-Content .\manifest.json -Raw | ConvertFrom-Json
$demoHash = (Get-FileHash .\local-link-lab-demo.apk -Algorithm SHA256).Hash.ToLowerInvariant()
if ($demoHash -ne $demoManifest.files.'local-link-lab-demo.apk') { throw 'APK 해시 불일치' }
$demoManifest.source_commit
$demoManifest.evidence_level
py --version
adb version
adb devices -l
```

폰에서 개발자 옵션·USB 디버깅을 켜고 PC 연결을 승인한다. 기기가 여러 대면 아래 adb 명령마다 `-s <선택한 serial>`을 추가한다. 공개 자료에는 serial을 남기지 않는다.

```powershell
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb install -r .\local-link-lab-demo.apk
```

`INSTALL_FAILED_UPDATE_INCOMPATIBLE`이면 중단하고 기존 설치의 출처를 확인한다. CI마다 debug 서명 키가 달라질 수 있다. 주문 보존을 위해 앱 삭제·데이터 초기화를 자동 해결책으로 쓰지 않는다. 현재 최소 설치 API는 23이지만 API 23에서 실행 검증했다는 뜻은 아니다.

## 2. PC와 폰 연결

PC와 폰을 같은 신뢰하는 테스트 LAN에 연결한다. `ipconfig`로 실제 Wi-Fi/Ethernet IPv4를 확인한다. 예시 `192.168.0.10`을 그 주소로 바꾼다.

```powershell
New-Item -ItemType Directory -Force data | Out-Null
py -u -m pos.server --db data/pos.db --host 192.168.0.10 --port 8765 > data/pos.log 2>&1
```

이 창은 서버 실행 중에 사용한다. 별도 PowerShell에서 `Get-Content data/pos.log -Wait`로 관측한다. 재시작할 때 **같은 `data/pos.db`**를 사용한다. POS DB 삭제·과거 파일 복원은 복구 시험에 포함하지 않는다.

앱에서 PC 주소와 `8765`를 입력하고 **연결 확인 → 기기에 주문 접수**를 누른다. 화면의 요청 ID를 기록하고 `POS 저장 확인`과 영수증을 확인한다. 다음 주문은 **새 주문 준비**를 누른다.

연결이 안 되면 [Windows·네트워크 안내](WINDOWS.md)의 NIC·게스트 Wi-Fi 격리·Private 방화벽 절차를 따른다. USB의 `adb reverse`로 성공한 결과는 LAN 성공으로 기록하지 않는다.

## 3. 보존·복구 관측

1. POS 창에서 Ctrl+C로 서버를 멈춘다. 앱에서 새 주문을 한 번 접수한다.
2. 요청 ID와 `기기에 접수됨 · POS 확인 대기`를 기록한다. 저장 완료로 표시되면 실패다.
3. 같은 명령·같은 DB로 POS를 다시 실행한다. 자동 시도 한도 안이면 같은 주문이 자동 복구된다. 한도가 끝났으면 **전송 재개**로 같은 주문을 확인한다.
4. 기존 요청 ID가 유지되고 영수증이 표시되는지 확인한다. 재전송 중 새 주문 접수 버튼을 눌러 같은 주문을 다시 만드는 방식으로 대체하지 않는다.

프로세스 종료는 별도 주문으로 전송을 일시 중지한 뒤, 접수 ID를 기록하고 `adb shell am force-stop dev.locallinklab.app`을 실행한다. 앱을 직접 다시 열어 같은 주문과 일시 중지가 유지되는지 확인하고 **전송 재개**를 누른다. 이 과정은 물리 전원 차단 시험이 아니다.

서버 전체 행을 읽기 전용으로 확인하려면 서버를 멈춘 뒤 다음을 실행한다.

```powershell
py -c "import json,sqlite3; c=sqlite3.connect('file:data/pos.db?mode=ro',uri=True); c.row_factory=sqlite3.Row; print(json.dumps([dict(r) for r in c.execute('SELECT * FROM orders')],indent=2)); c.close()"
```

매 실행의 접수 ID와 POS의 전체 ID/본문/영수증을 비교한다. 앱의 완료 문구만으로 전체 DB에 추가 주문이 없다고 판단하지 않는다. 최초 ACK 유실·commit 직후 종료 시험은 별도 사건 기반 자동 실행기로 수행하며, 이 수동 절차를 그 증거로 사용하지 않는다.

## 4. 결과 전달

기종, Android/API, Windows 버전, manifest 소스 SHA/APK 해시, 경로(LAN/USB/에뮬레이터), 시나리오별 접수 ID·POS 행·결과·관측 파일을 기록한다. 실행하지 못한 항목은 NOT_RUN, 환경 때문에 막히면 BLOCKED로 남긴다. 휴대폰 serial·개인 데이터·실결제 정보는 제외한다.
