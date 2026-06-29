# Robot Art Studio — M0609 픽셀 점묘화 자동 출력 시스템

---

## 1. 🎨 시스템 설계 및 플로우 차트

### 1-1. 시스템 설계도 (System Architecture)

```mermaid
flowchart LR
    A[Customer UI<br/>React / Vite] -->|WebSocket| B[Backend Server<br/>FastAPI]
    B --> C[ROS2 Bridge Node<br/>rclpy]
    C --> D[robot_art_node<br/>DrawingEngine]
    D --> E[DSR Controller2]
    E --> F[Doosan M0609<br/>+ RG2 Gripper]
    B --> G[(SQLite DB)]
```

### 1-2. 플로우 차트 (Flow Chart)

<p align="center">
  <img src="./docs/images/flow_chart.png" alt="플로우 차트" width="320">
</p>

---

## 2. 🖥️ 운영체제 환경 (OS Environment)

<p>
  <img src="https://img.shields.io/badge/Ubuntu-22.04 LTS-E95420?style=for-the-badge&logo=ubuntu&logoColor=white"/>
  <img src="https://img.shields.io/badge/ROS2-Humble-22314E?style=for-the-badge&logo=ros&logoColor=white"/>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/TypeScript-5.x-3178C6?style=for-the-badge&logo=typescript&logoColor=white"/>
  <img src="https://img.shields.io/badge/VS Code-IDE-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white"/>
</p>

| 항목 | 내용 |
|:---|:---|
| **OS** | Ubuntu 22.04 LTS |
| **ROS Version** | ROS2 Humble Hawksbill |
| **Language** | Python 3.10, TypeScript |
| **IDE** | VS Code |

> ⚠️ VM/Docker 사용 시 네트워크를 **Host 모드**로 설정해야 로봇과 정상 통신됩니다.

---

## 3. 🛠️ 사용 장비 목록 (Hardware List)

| 장비명 (Model) | 수량 | 비고 |
|:---:|:---:|:---|
| Doosan M0609 | 1 | 6축 협동로봇 |
| OnRobot RG2 | 1 | 전동 그리퍼 (Modbus TCP) |
| 일반 용지 (A5) | - | 그리기 매체 |
| 연필 | - | 드로잉 도구 |

---

## 4. 📦 의존성 (Dependencies)

### Backend (Python)
```
Python >= 3.10
fastapi
uvicorn
websockets
pymodbus
rclpy (ROS2 Humble)
```

### Frontend (Node.js)
```
Node.js >= 18
React 19
TypeScript
Vite
```

### ROS2 패키지
```
dsr_msgs2
dsr_hardware2
controller_manager
```

---

## 5. ▶️ 실행 순서 (Usage Guide)

### Step 1. ROS2 Workspace 빌드

```bash
cd ~/ws_cobot_pjt/ws_edu
colcon build --symlink-install
source install/setup.bash
```

### Step 2. 로봇 bringup (실제 로봇)

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=real host:=192.168.1.100 model:=m0609
```

### Step 3. robot_art_node 실행

```bash
python3 ros2_node/robot_art_node.py
```

### Step 4. Backend 실행

```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Step 5. Frontend 실행

```bash
cd frontend
npm install
npm run dev
```

---

## 6. 📸 Preview

### 손님 화면 (Customer Screen)

| 이미지 등록 | 이미지 크롭 |
| :---: | :---: |
| <img src="./docs/video/hmi 이미지 등록.gif" width="360"/> | <img src="./docs/video/hmi 이미지 크롭.gif" width="360"/> |

| 이미지 편집 | 픽셀 편집 |
| :---: | :---: |
| <img src="./docs/video/hmi 이미지 편집.gif" width="360"/> | <img src="./docs/video/hmi 픽셀 편집.gif" width="360"/> |

### 관리자 HMI

| 전체 동작 흐름 | 개별 동작 제어 |
| :---: | :---: |
| <img src="./docs/video/모든동작.gif" width="360"/> | <img src="./docs/video/개별동작.gif" width="360"/> |

| 일시정지 / 재개 | 캘리브레이션 |
| :---: | :---: |
| <img src="./docs/video/일시정지.gif" width="360"/> | <img src="./docs/video/캘리브레이션.gif" width="360"/> |

| 통신 연결 상태 |
| :---: |
| <img src="./docs/video/통신연결상태.gif" width="360"/> |

---

## 7. 🖼 결과물

| Pikachu | Mario |
| :---: | :---: |
| <img src="./docs/images/20260628_173505.jpg" width="360"/> | <img src="./docs/images/20260628_173530.jpg" width="360"/> |

| Starry Night | Photo Style |
| :---: | :---: |
| <img src="./docs/images/20260628_173558.jpg" width="360"/> | <img src="./docs/images/20260628_173654.jpg" width="360"/> |

---

## 8. 🔌 ROS2 Communication

| Service | Description |
| --- | --- |
| `/robot_art/start` | 드로잉 시작 |
| `/robot_art/stop` | 작업 정지 |
| `/robot_art/estop` | 비상 정지 |
| `/robot_art/release_estop` | 비상 정지 해제 |
| `/robot_art/home` | 홈 위치 복귀 |
| `/robot_art/pencil_grip` | 펜 파지 |
| `/robot_art/pencil_release` | 펜 반납 |

| Topic | Type | Description |
| --- | --- | --- |
| `/robot_art/pixels` | `std_msgs/String` | 픽셀 데이터 전달 |
| `/robot_art/status` | `std_msgs/String` | 로봇 상태 전달 |
| `/dsr01/msg/joint_state` | `Float64MultiArray` | 로봇 조인트 상태 |
| `/dsr01/msg/current_posx` | `Float64MultiArray` | TCP 위치 |
