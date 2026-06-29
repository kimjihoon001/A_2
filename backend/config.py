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

# 데이터베이스 (config.py 위치 기준 절대경로)
import os as _os
DB_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "robot_art.db")

# 그리기 시작 전 준비 자세 (관절각도, deg)
READY_JOINTS = [0.0, 0.0, 90.0, 180.0, -90.0, 0.0]
READY_VEL    = 30   # deg/s
READY_ACC    = 50   # deg/s²

# 드로잉 속도 기본값 — 실제 값은 DB settings 테이블에서 관리 (move_speed, draw_speed)
MOVE_SPEED  = 200   # mm/s (폴백용, DB 미연결 시)
DRAW_SPEED  =  50   # mm/s (폴백용, DB 미연결 시)
LIFT_SPEED  = 100   # mm/s — 펜 올릴 때

# 흰색에 가까운 픽셀은 스킵 (시간 단축)
# 255(완전 흰색)에 가까울수록 스킵. 0이면 모두 찍음
SKIP_THRESHOLD = 245

# 그리퍼 RG2 기본 설정
GRIPPER_OPEN_WIDTH  = 60    # mm
GRIPPER_CLOSE_WIDTH =  10   # mm
GRIPPER_DEFAULT_FORCE = 40  # N

# 펜 찍기 유지 시간 기본값 — 실제 값은 DB settings 테이블 dot_hold_ms 에서 관리
DOT_HOLD_SEC = 0.15   # 초 (폴백용)

# 픽셀 사각형 래스터 스캔 설정
PIXEL_SIZE_MM  = 1.67  # 픽셀 하나의 가로세로 크기 (mm)
PIXEL_PITCH_MM = 1.0  # 래스터 선 간격 (mm)

# 상태 업데이트 주기
STATUS_INTERVAL_SEC = 0.2   # 200ms마다 HMI로 상태 전송

# 캘리브레이션 기본값 (DB에 활성 레코드 없을 때 폴백)
DEFAULT_CALIBRATION = {
    'origin_x': 356.0,
    'origin_y': -41.0,
}
