# ================================================================
# config.py — 전체 설정값
# 실제 환경에 맞게 수정하세요
# ================================================================

# WebSocket 서버
WS_HOST = "0.0.0.0"
WS_PORT = 8765

# 로봇 연결 정보
ROBOT_IP   = "192.168.1.100"
ROBOT_PORT = 12345

# 데이터베이스
DB_PATH = "data/robot_art.db"

# 종이 Z 좌표 (mm, 로봇 베이스 기준) — pixel_test.py 기준
# table_high = 242 → hover = 292, ready = 241
PEN_UP_Z    = 274.30  # 픽셀 간 이동 높이 (접촉 267.30 + 7mm)
PEN_DOWN_Z  = 269.30  # 종이 근처 하강 높이 (접촉 267.30 + 2mm, 힘 제어로 실제 접촉)

# 그리기 시작 전 준비 자세 (관절각도, deg)
READY_JOINTS = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]
READY_VEL    = 30   # deg/s
READY_ACC    = 50   # deg/s²

# 캔버스 기본 캘리브레이션 — pixel_test.py 좌표 기준 (실제 측정값으로 교체)
DEFAULT_CALIBRATION = {
    "origin_x"         : 463.94,     # 종이 좌상단 X (mm) — 실측
    "origin_y"         : 171.03,     # 종이 좌상단 Y (mm) — 실측
    "origin_z"         : PEN_UP_Z,   # 펜 이동 높이
    "pen_down_z"       : PEN_DOWN_Z, # 힘 제어 시작 높이 (접촉 267.30보다 ~2mm 위)
    "pixel_spacing_mm" :   2.0,      # 픽셀 간격 (mm)
}

# 드로잉 속도
MOVE_SPEED  = 200   # mm/s — 픽셀 간 이동
DRAW_SPEED  =  50   # mm/s — 펜 내릴 때
LIFT_SPEED  = 100   # mm/s — 펜 올릴 때

# 흰색에 가까운 픽셀은 스킵 (시간 단축)
# 255(완전 흰색)에 가까울수록 스킵. 0이면 모두 찍음
SKIP_THRESHOLD = 245

# 그리퍼 RG2 기본 설정
GRIPPER_OPEN_WIDTH  = 100   # mm
GRIPPER_CLOSE_WIDTH =  10   # mm
GRIPPER_DEFAULT_FORCE = 20  # N

# 펜 찍기 유지 시간
DOT_HOLD_SEC = 0.15   # 접촉 후 누르는 시간 (초)

# 픽셀 사각형 래스터 스캔 설정
PIXEL_SIZE_MM  = 2.0  # 픽셀 하나의 가로세로 크기 (mm)
PIXEL_PITCH_MM = 1.0  # 래스터 선 간격 (mm)

# 상태 업데이트 주기
STATUS_INTERVAL_SEC = 0.2   # 200ms마다 HMI로 상태 전송
