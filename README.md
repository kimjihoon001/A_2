# Robot Art Studio — M0609 협동로봇 픽셀 점묘화 시스템

두산 M0609 협동로봇과 RG2 그리퍼를 이용해 이미지를 픽셀 점묘화로 자동 출력하는 시스템입니다.  
사용자가 이미지를 업로드하면 그레이스케일 픽셀로 변환하여 로봇이 펜으로 종이에 한 점씩 찍어 그림을 완성합니다.

<!-- 사진 1: 로봇 전체 셋업 사진 (로봇 + 그리퍼 + 그림판 전경) -->
<!-- ![로봇 셋업](docs/images/setup.jpg) -->

---

## 시스템 구성

```
Frontend (React/Vite)
      ↕ WebSocket
Backend (FastAPI + ROS2 Node)
      ↕ ROS2 Topic/Service
DSR Controller2 (두산 ROS2 패키지)
      ↕ DSR C++ API (Drfl)
M0609 로봇 + RG2 그리퍼
```

| 구성 요소 | 기술 스택 | 역할 |
|-----------|-----------|------|
| Frontend | React 19, TypeScript, Vite | 고객용 화면 / 관리자 HMI |
| Backend | FastAPI, WebSocket, Python | 상태 관리, DB, ROS2 브릿지 |
| ROS2 Node | rclpy (Python) | 로봇 동작 서비스 제공 |
| DSR Controller | dsr_controller2 (C++) | 두산 DSR API 래퍼 |
| Robot | Doosan M0609 + OnRobot RG2 | 실제 구동부 |

---

## 주요 기능

- **픽셀 변환**: 업로드 이미지 → 그레이스케일 → 64×64 등 설정 해상도로 다운샘플링
- **자동 그리기**: 경로 최적화 후 픽셀 밝기에 따라 압력 조절하며 점 찍기
- **액자 작업**: 종이 픽업 → 정렬 → 그리기 → 액자 상/하판 조립 → 배출 자동화
- **E-STOP / 비상 해제**: 서보 즉시 OFF + 안전 상태 복구
- **캘리브레이션**: Z축 자동 측정, 원점 보정
- **고객 화면 / 관리자 HMI**: 모드 분리 운영

<!-- 사진 2: 고객 화면 스크린샷 (이미지 업로드 → 픽셀 미리보기) -->
<!-- ![고객 화면](docs/images/customer_screen.png) -->

<!-- 사진 3: 관리자 HMI 스크린샷 (드로잉 단계 제어 화면) -->
<!-- ![관리자 HMI](docs/images/admin_hmi.png) -->

---

## 디렉토리 구조

```
ws_cobot_pjt/
├── backend/
│   ├── main.py              # FastAPI WebSocket 서버 + ROS2 브릿지 노드
│   ├── robot_controller.py  # 로봇 동작 제어 (movej/movel/그리퍼 등)
│   ├── drawing_engine.py    # 드로잉 경로 생성 및 실행 스레드
│   ├── database.py          # SQLite DB (캘리브레이션, 설정, 작업 이력)
│   ├── config.py            # 로봇 IP, 속도, 그리퍼 등 전역 설정
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.tsx           # 메인 앱 (WebSocket 연결, 상태 관리)
│       ├── pages/
│       │   ├── CustomerScreen.tsx  # 고객용 이미지 업로드/미리보기 화면
│       │   ├── DrawingControl.tsx  # 관리자 드로잉 단계 제어
│       │   ├── Safety.tsx          # E-STOP / 비상 해제
│       │   ├── Calibration.tsx     # 캘리브레이션
│       │   ├── Dashboard.tsx       # 상태 대시보드
│       │   ├── Gripper.tsx         # 그리퍼 수동 제어
│       │   └── Settings.tsx        # 속도/힘 설정
│       └── hooks/            # WebSocket 훅 등
├── ros2_node/
│   └── robot_art_node.py    # ROS2 서비스 서버 (start/stop/estop 등)
├── ws_edu/                  # 두산 ROS2 패키지 (dsr_controller2 등)
└── tools/
    └── pixelart.py          # 이미지 픽셀 변환 유틸리티
```

---

## 환경 요구사항

- Ubuntu 22.04
- ROS2 Humble
- Python 3.10+
- Node.js 18+
- 두산 ROS2 패키지 (`doosan-robot2`, `dsr_msgs2`)

---

## 실행 방법

### 1. 두산 ROS2 패키지 빌드 및 실행

```bash
cd ws_edu
colcon build --symlink-install
source install/setup.bash
ros2 launch dsr_bringup2 m0609_rg2_bringup.launch.py
```

### 2. 백엔드 실행

```bash
cd backend
pip install -r requirements.txt
python main.py
```

### 3. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev        # 개발 서버
# 또는
npm run build      # 빌드 후 dist/ 배포
```

---

## 주요 설정 (`backend/config.py`)

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `ROBOT_IP` | 192.168.1.100 | 로봇 IP |
| `WS_PORT` | 8765 | WebSocket 서버 포트 |
| `MOVE_SPEED` | 200 mm/s | 이동 속도 |
| `DOT_HOLD_SEC` | 0.15 s | 점 찍기 유지 시간 |
| `PIXEL_SIZE_MM` | 2.0 mm | 픽셀 하나의 크기 |
| `GRIPPER_OPEN_WIDTH` | 60 mm | 그리퍼 열림 너비 |

---

## ROS2 통신 구조

자세한 토픽/서비스 목록은 [`ros2_communication.txt`](ros2_communication.txt) 참고.

### 주요 서비스 (모두 `std_srvs/Trigger`)

| 서비스명 | 설명 |
|----------|------|
| `/robot_art/start` | 그리기 시작 |
| `/robot_art/stop` | 강제 정지 |
| `/robot_art/estop` | E-STOP 활성화 |
| `/robot_art/release_estop` | E-STOP 해제 |
| `/robot_art/home` | 홈 복귀 |
| `/robot_art/pencil_grip` | 연필 파지 |
| `/robot_art/pencil_release` | 연필 반납 |

### 주요 토픽

| 토픽명 | 타입 | 방향 |
|--------|------|------|
| `/robot_art/pixels` | `std_msgs/String` | Backend → Node |
| `/robot_art/status` | `std_msgs/String` | Node → Backend |
| `/dsr01/msg/joint_state` | `Float64MultiArray` | DSR → Backend |

---

## 결과물

<!-- 사진 4: 로봇이 실제로 그림 그리는 중간 과정 사진 -->
<!-- ![그리기 중](docs/images/drawing_in_progress.jpg) -->

<!-- 사진 5: 완성된 점묘화 결과물 (액자 포함) -->
<!-- ![완성 결과물](docs/images/result.jpg) -->

---

## 팀

- 개발: M0609 RG2 그리퍼 픽셀 아트 프린터 팀
- 로봇: Doosan Robotics M0609 + OnRobot RG2
