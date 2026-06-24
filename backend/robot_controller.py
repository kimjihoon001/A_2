# ================================================================
# robot_controller.py — 로봇 제어 (DSR_ROBOT2 / 시뮬 폴백)
#
# ROS2 워크스페이스 빌드 + source install/setup.bash 후에는
# DSR_ROBOT2를 실제로 import해 M0609에 명령을 보냄.
# 빌드 전 / source 안 된 상태에서는 시뮬레이션으로 동작.
# ================================================================

import sys
import os
import math
import random
import socket
import struct
import threading
import time
import logging

from dataclasses import dataclass, field
from config import (GRIPPER_OPEN_WIDTH, GRIPPER_CLOSE_WIDTH, GRIPPER_DEFAULT_FORCE,
                    DOT_HOLD_SEC, MOVE_SPEED, DRAW_SPEED, PIXEL_SIZE_MM, PIXEL_PITCH_MM)
from database import Database as _Database
_db = _Database()

# ── OnRobot RG2 Modbus TCP ────────────────────────────────────────
_GRIPPER_IP   = '192.168.1.1'
_GRIPPER_PORT = 502
_GRIPPER_UNIT = 65   # RG2 Modbus unit ID


def _gripper_read_width() -> float | None:
    """그리퍼 실제 너비 읽기 (mm). 실패 시 None 반환."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect((_GRIPPER_IP, _GRIPPER_PORT))
            # Read holding register 275 (width with fingertip offset in 1/10 mm), unit=65
            req = struct.pack('>HHHBBHH', 1, 0, 6, _GRIPPER_UNIT, 0x03, 275, 1)
            s.sendall(req)
            resp = s.recv(256)
            if len(resp) >= 11:
                return struct.unpack('>H', resp[9:11])[0] / 10.0
    except Exception as e:
        log.debug(f"그리퍼 너비 읽기 실패: {e}")
    return None


def _gripper_move(force_n: float, width_mm: float):
    """그리퍼 이동 명령. force: N, width: mm."""
    try:
        values = [int(force_n * 10), int(width_mm * 10), 16]  # 16 = grip command
        n      = len(values)
        data   = struct.pack(f'>{n}H', *values)
        length = 1 + 1 + 2 + 2 + 1 + len(data)
        req    = struct.pack('>HHHBBHHB', 1, 0, length, _GRIPPER_UNIT, 0x10, 0, n, len(data)) + data
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect((_GRIPPER_IP, _GRIPPER_PORT))
            s.sendall(req)
            s.recv(256)
    except Exception as e:
        log.error(f"그리퍼 이동 명령 실패: {e}")

log = logging.getLogger(__name__)

ROBOT_ID    = "dsr01"
ROBOT_MODEL = "m0609"
DSR_IMP_PATH = str(os.path.join(os.path.expanduser("~"), "ws_cobot_pjt/ws_edu/src/cobot_rg2/doosan-robot2/dsr_common2/imp"))


def _read_dsr_robot_params() -> tuple[str, int]:
    """dsr_hardware2 config YAML 파일에서 robot host/port를 읽어 반환. 실패 시 config.py 값 사용."""
    try:
        import glob
        pattern = f"/home/jihoon/ws_cobot_pjt/ws_edu/install/dsr_hardware2/share/dsr_hardware2/config/{ROBOT_ID}_parameters.yaml"
        matches = glob.glob(pattern)
        if not matches:
            raise FileNotFoundError(f"파라미터 파일 없음: {pattern}")
        with open(matches[0]) as f:
            import yaml
            params = yaml.safe_load(f)
        host = params.get('host', '')
        port = int(params.get('port', 12345))
        if host:
            log.info(f"DSR 파라미터 파일에서 로봇 연결 정보 로드: {host}:{port}")
            return host, port
    except Exception as e:
        log.warning(f"DSR 파라미터 파일 읽기 실패, config.py 값 사용: {e}")
    from config import ROBOT_IP, ROBOT_PORT
    return ROBOT_IP, ROBOT_PORT

# ── DSR_ROBOT2 초기화 시도 ───────────────────────────────────────
_dsr_available = False
_dsr_funcs: dict = {}   # movel, movej, move_home, get_current_posj, get_current_posx, get_robot_state
_controller: 'RobotController | None' = None

def _init_dsr() -> bool:
    global _dsr_available, _dsr_funcs
    try:
        import rclpy
        if not rclpy.ok():
            rclpy.init()

        # imp 폴더를 경로에 추가 (빌드 전 소스 참조)
        if DSR_IMP_PATH not in sys.path:
            sys.path.insert(0, DSR_IMP_PATH)

        import DR_init
        DR_init.__dsr__id    = ROBOT_ID
        DR_init.__dsr__model = ROBOT_MODEL

        node = rclpy.create_node('robot_art_controller', namespace=ROBOT_ID)
        DR_init.__dsr__node = node

        # DSR 노드 전용 executor — 별도 스레드에서 spin (서비스 응답 수신용)
        dsr_executor = rclpy.executors.SingleThreadedExecutor()
        dsr_executor.add_node(node)
        dsr_spin_thread = threading.Thread(target=dsr_executor.spin, daemon=True, name='dsr_executor')
        dsr_spin_thread.start()

        from DSR_ROBOT2 import (
            set_robot_mode,
            movel, movej, amovel, move_home,
            get_current_posj, get_current_posx, get_robot_state,
            posx, posj,
            DR_BASE, DR_MV_MOD_ABS, DR_MV_MOD_REL,
            task_compliance_ctrl, set_desired_force,
            release_force, release_compliance_ctrl,
            check_force_condition, DR_AXIS_Z, DR_FC_MOD_REL,
        )
        from DRFC import ROBOT_MODE_AUTONOMOUS

        ret = set_robot_mode(ROBOT_MODE_AUTONOMOUS)
        if ret != 0:
            log.warning(f"set_robot_mode 실패 (ret={ret}) — 티칭펜던트가 수동 모드일 수 있음")
        else:
            log.info("AUTONOMOUS 모드 설정 완료")

        _dsr_funcs = {
            'movel':                    movel,
            'movej':                    movej,
            'amovel':                   amovel,
            'move_home':                move_home,
            'get_current_posj':         get_current_posj,
            'get_current_posx':         get_current_posx,
            'get_robot_state':          get_robot_state,
            'posx':                     posx,
            'posj':                     posj,
            'DR_BASE':                  DR_BASE,
            'DR_MV_MOD_REL':            DR_MV_MOD_REL,
            'node':                     node,
            'rclpy':                    rclpy,
            'task_compliance_ctrl':     task_compliance_ctrl,
            'set_desired_force':        set_desired_force,
            'release_force':            release_force,
            'release_compliance_ctrl':  release_compliance_ctrl,
            'check_force_condition':    check_force_condition,
            'DR_AXIS_Z':                DR_AXIS_Z,
            'DR_FC_MOD_REL':            DR_FC_MOD_REL,
        }

        # MoveStop 서비스 클라이언트 (E-STOP용)
        from dsr_msgs2.srv import MoveStop, SetRobotControl, GetRobotState
        _stop_client     = node.create_client(MoveStop,         f'/{ROBOT_ID}/motion/move_stop')
        _servo_on_client = node.create_client(SetRobotControl,  f'/{ROBOT_ID}/system/set_robot_control')
        _state_client    = node.create_client(GetRobotState,    f'/{ROBOT_ID}/system/get_robot_state')
        _dsr_funcs['stop_client']      = _stop_client
        _dsr_funcs['servo_on_client']  = _servo_on_client
        _dsr_funcs['state_client']     = _state_client
        _dsr_funcs['MoveStop']         = MoveStop
        _dsr_funcs['SetRobotControl']  = SetRobotControl
        _dsr_funcs['GetRobotState']    = GetRobotState
        _dsr_funcs['dsr_executor']     = dsr_executor

        _dsr_available = True
        log.info("DSR_ROBOT2 초기화 성공 — 실제 M0609 제어 모드")

        # 로봇 상태 폴링 타이머 (0.5초마다 estop 감지)
        node.create_timer(0.5, _poll_robot_state)
        return True

    except Exception as e:
        log.warning(f"DSR_ROBOT2 초기화 실패 → 시뮬레이션 모드: {e}")
        return False


_ESTOP_STATES = {5, 6}  # STATE_SAFE_STOP, STATE_EMERGENCY_STOP


def _poll_robot_state():
    try:
        client = _dsr_funcs.get('state_client')
        GetRobotState = _dsr_funcs.get('GetRobotState')
        if client is None or not client.service_is_ready():
            return
        future = client.call_async(GetRobotState.Request())
        future.add_done_callback(_on_robot_state)
    except Exception as e:
        log.warning(f"robot state 폴링 오류: {e}")


def _on_robot_state(future):
    try:
        result = future.result()
        if result is None or _controller is None:
            return
        state = result.robot_state
        with _controller._lock:
            if state in _ESTOP_STATES and not _controller.state.estop:
                log.warning(f"외부 E-STOP 감지 (robot_state={state})")
                _controller.state.estop  = True
                _controller.state.status = "estop"
            elif state not in _ESTOP_STATES and _controller.state.estop:
                log.info(f"E-STOP 해제 감지 (robot_state={state})")
                _controller.state.estop  = False
                _controller.state.status = "idle"
    except Exception as e:
        log.warning(f"robot state 콜백 오류: {e}")


# ── 상태 ────────────────────────────────────────────────────────
@dataclass
class RobotState:
    connected    : bool  = False
    powered      : bool  = False
    estop        : bool  = False
    status       : str   = "idle"
    joints       : list  = field(default_factory=lambda: [0.0, -30.0, 60.0, 0.0, 45.0, 0.0])
    tcp_x        : float = 423.0
    tcp_y        : float = 12.0
    tcp_z        : float = 315.0
    speed        : float = 0.0
    gripper_width: float = 85.0
    pen_force    : float = 0.0
    tool_force   : list  = field(default_factory=lambda: [0.0] * 6)  # [Fx,Fy,Fz,Tx,Ty,Tz] N/Nm


class RobotController:

    _HOME_JOINTS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    _HOME_TCP    = (423.0, 12.0, 315.0)

    def __init__(self):
        global _controller
        self.state = RobotState()
        self._lock = threading.Lock()
        self._move_speed   = float(MOVE_SPEED)
        self._dot_hold_sec = float(DOT_HOLD_SEC)

    def load_config(self):
        """드로잉 시작 전 DB에서 속도 설정 로드."""
        self._move_speed   = float(_db.get_setting('move_speed',  MOVE_SPEED))
        self._dot_hold_sec = float(_db.get_setting('dot_hold_ms', DOT_HOLD_SEC * 1000)) / 1000.0
        log.info(f"속도 설정: 이동={self._move_speed}mm/s, 유지={self._dot_hold_sec*1000:.0f}ms")
        self.robot_ip, self.robot_port = _read_dsr_robot_params()
        _controller = self

    # ── 연결 ────────────────────────────────────────────────────
    def connect(self) -> bool:
        if not _dsr_available:
            _init_dsr()
        if _dsr_available:
            self._sync_state_from_robot()   # 초기 TCP 위치
            self._start_joint_subscriber()  # joint_states 토픽 구독
            log.info("M0609 연결됨 (DSR_ROBOT2)")
            with self._lock:
                self.state.connected = True
                self.state.powered   = True
        else:
            log.info("시뮬레이션 모드 (로봇 미연결)")
            with self._lock:
                self.state.connected = False
                self.state.powered   = False
        self._start_gripper_poll()          # 그리퍼 너비 폴링 (항상)
        return True

    def ensure_real_connection(self) -> bool:
        """초기화 순서 문제로 시뮬레이션에 빠졌다면 DSR 연결을 다시 시도한다."""
        if _dsr_available:
            return True
        log.info("DSR_ROBOT2 실제 로봇 연결 재시도")
        if not _init_dsr():
            return False
        self._sync_state_from_robot()
        self._start_joint_subscriber()
        return True

    def _start_gripper_poll(self):
        """그리퍼 너비를 1초마다 Modbus TCP로 읽어 state 갱신"""
        self._gripper_poll_active = True

        def _loop():
            while self._gripper_poll_active:
                w = _gripper_read_width()
                if w is not None:
                    with self._lock:
                        self.state.gripper_width = w
                time.sleep(1.0)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        log.info("그리퍼 너비 폴링 시작 (1 Hz)")

    def _start_joint_subscriber(self):
        """
        /dsr01/joint_states     → 조인트 각도 (sensor_msgs/JointState, 라디안) → 도(degree) 변환
        TCP 위치               → get_current_posx 서비스 폴링 (0.1 Hz)
        """
        import math
        rclpy = _dsr_funcs['rclpy']
        from sensor_msgs.msg import JointState

        sub_node = rclpy.create_node('robot_art_sub')

        def _joint_cb(msg: JointState):
            if len(msg.name) < 6:
                return
            name_to_rad = dict(zip(msg.name, msg.position))
            try:
                joints_deg = [round(math.degrees(name_to_rad[f'joint_{i}']), 2) for i in range(1, 7)]
            except KeyError:
                return
            with self._lock:
                self.state.joints = joints_deg

        sub_node.create_subscription(JointState, '/dsr01/joint_states', _joint_cb, 10)

        from rclpy.executors import SingleThreadedExecutor
        sub_executor = SingleThreadedExecutor()
        sub_executor.add_node(sub_node)
        t = threading.Thread(target=sub_executor.spin, daemon=True)
        t.start()
        self._sub_node = sub_node
        self._sub_executor = sub_executor

        def _poll_tcp():
            import time
            get_current_posx = _dsr_funcs['get_current_posx']
            while True:
                try:
                    tcp_pos, _ = get_current_posx()  # returns (posx[6], sol)
                    if tcp_pos:
                        with self._lock:
                            self.state.tcp_x = round(float(tcp_pos[0]), 2)
                            self.state.tcp_y = round(float(tcp_pos[1]), 2)
                            self.state.tcp_z = round(float(tcp_pos[2]), 2)
                except Exception:
                    pass
                time.sleep(0.5)

        threading.Thread(target=_poll_tcp, daemon=True, name='tcp_poller').start()
        log.info("joint_states 토픽 구독 및 TCP 폴링 시작")

    def disconnect(self):
        with self._lock:
            self.state.connected = False
            self.state.powered   = False
        log.info("로봇 컨트롤러 종료")

    # ── E-STOP ──────────────────────────────────────────────────
    def emergency_stop(self):
        log.warning("E-STOP 활성화")
        with self._lock:
            self.state.estop  = True
            self.state.status = "estop"
            self.state.speed  = 0.0

        if _dsr_available:
            try:
                import threading as _threading
                client = _dsr_funcs['stop_client']
                MoveStop = _dsr_funcs['MoveStop']
                req = MoveStop.Request()
                req.stop_mode = 1  # DR_QSTOP: 소프트웨어 즉시 정지 (STO 없이 복구 가능)
                done = _threading.Event()
                future = client.call_async(req)
                future.add_done_callback(lambda _: done.set())
                if not done.wait(timeout=2.0):
                    log.warning("E-STOP: move_stop 응답 타임아웃")
                else:
                    log.info("E-STOP: move_stop 완료")
            except Exception as e:
                log.error(f"E-STOP 처리 실패: {e}")

    def release_estop(self):
        log.info("E-STOP 해제")
        if _dsr_available:
            try:
                import threading as _threading
                client = _dsr_funcs['servo_on_client']
                SetRobotControl = _dsr_funcs['SetRobotControl']
                req = SetRobotControl.Request()
                req.robot_control = 3  # CONTROL_RESET_SAFET_OFF → STATE_STANDBY
                done = _threading.Event()
                future = client.call_async(req)
                future.add_done_callback(lambda _: done.set())
                if not done.wait(timeout=2.0):
                    log.warning("E-STOP 해제: set_robot_control 응답 타임아웃")
                else:
                    log.info("E-STOP 해제: 서보 온 완료")
            except Exception as e:
                log.error(f"서보 온 실패: {e}")
        with self._lock:
            self.state.estop  = False
            self.state.status = "idle"

    # ── 이동 ────────────────────────────────────────────────────
    def home(self):
        log.info("원점 복귀 중...")
        with self._lock:
            self.state.status = "homing"

        if _dsr_available:
            try:
                posj  = _dsr_funcs['posj']
                movej = _dsr_funcs['movej']
                home_pos = posj(8.5, 5.45, 82.85, 179.96, -91.70, -171.71)
                movej(home_pos, vel=30, acc=50)
                with self._lock:
                    self.state.status = "idle"
                log.info("원점 복귀 완료")
            except Exception as e:
                log.error(f"원점 복귀 실패: {e}")
                with self._lock:
                    self.state.status = "error"
        else:
            time.sleep(2.0)
            with self._lock:
                self.state.joints = list(self._HOME_JOINTS)
                self.state.tcp_x  = self._HOME_TCP[0]
                self.state.tcp_y  = self._HOME_TCP[1]
                self.state.tcp_z  = self._HOME_TCP[2]
                self.state.status = "idle"
            log.info("원점 복귀 완료 (시뮬)")

    def movej(self, joints: list, vel: float = 30.0, acc: float = 50.0):
        """관절 이동"""
        if self.state.estop:
            raise RuntimeError("E-STOP 상태에서 이동 불가")

        mode = "실제" if _dsr_available else "시뮬"
        log.info(f"movej [{mode}] joints={joints} vel={vel} acc={acc}")

        if _dsr_available:
            try:
                pos = _dsr_funcs['posj'](*joints)
                _dsr_funcs['movej'](pos, vel=vel, acc=acc)
                self._sync_state_from_robot()
            except Exception as e:
                log.error(f"movej 실패: {e}")
                raise
        else:
            time.sleep(1.0)
            with self._lock:
                self.state.joints = list(joints)
            log.info(f"movej 시뮬: {joints}")

    def movel_relative(self, dx: float, dy: float, dz: float,
                       velocity: float = 100.0):
        """상대 이동 (DR_MV_MOD_REL)"""
        if self.state.estop:
            raise RuntimeError("E-STOP 상태에서 이동 불가")

        if _dsr_available:
            try:
                from DSR_ROBOT2 import DR_MV_MOD_REL
                pos = _dsr_funcs['posx'](dx, dy, dz, 0.0, 0.0, 0.0)
                _dsr_funcs['movel'](pos, vel=[velocity, velocity],
                                    acc=[velocity * 2, velocity * 2],
                                    ref=_dsr_funcs['DR_BASE'],
                                    mod=DR_MV_MOD_REL)
                self._sync_state_from_robot()
            except Exception as e:
                log.error(f"movel_relative 실패: {e}")
                raise
        else:
            time.sleep(0.3)
            with self._lock:
                self.state.tcp_x += dx
                self.state.tcp_y += dy
                self.state.tcp_z += dz
            log.info(f"movel_relative 시뮬: dx={dx} dy={dy} dz={dz}")

    def movel(self, x: float, y: float, z: float,
              velocity: float = 100.0, force_z: float = 0.0):
        """
        직선 이동 (Cartesian, mm). tool 방향은 수직 하향(0, 180, 0) 고정.
        force_z > 0 이면 Z 방향 힘 제어로 펜 찍기:
          1) 접근 위치(x, y, z)로 이동
          2) 컴플라이언스 + 목표 힘 설정
          3) 접촉 감지 후 DOT_HOLD_SEC 유지
          4) 힘 해제
        """
        if self.state.estop:
            raise RuntimeError("E-STOP 상태에서 이동 불가")

        if _dsr_available:
            try:
                with self._lock:
                    self.state.speed = velocity
                pos = _dsr_funcs['posx'](x, y, z, 0.0, 180.0, 0.0)
                vel = [velocity, velocity]
                acc = [velocity * 2, velocity * 2]
                _dsr_funcs['movel'](pos, vel=vel, acc=acc, ref=_dsr_funcs['DR_BASE'])

                if force_z > 0:
                    self._pen_force_draw(force_z)

                with self._lock:
                    self.state.speed     = 0.0
                    self.state.pen_force = 0.0
            except Exception as e:
                log.error(f"movel 실패: {e}")
                raise
        else:
            dist = math.sqrt(
                (x - self.state.tcp_x) ** 2 +
                (y - self.state.tcp_y) ** 2 +
                (z - self.state.tcp_z) ** 2
            )
            time.sleep(max(0.005, dist / max(velocity, 1)) * 0.008)
            with self._lock:
                self.state.tcp_x     = x
                self.state.tcp_y     = y
                self.state.tcp_z     = z
                self.state.speed     = velocity
                self.state.pen_force = force_z
                self.state.joints    = [j + random.uniform(-0.15, 0.15) for j in self.state.joints]
            if force_z > 0:
                time.sleep(self._dot_hold_sec)
            with self._lock:
                self.state.pen_force = 0.0

    def _pen_force_draw(self, force_n: float):
        """
        현재 위치에서 Z 방향 힘 제어로 펜을 누름.
        X/Y는 단단히 고정(3000 N/m), Z는 유연(200 N/m)으로
        종이 표면 굴곡에 자동 적응.
        """
        try:
            # Z 방향만 유연하게, X/Y는 위치 유지
            _dsr_funcs['task_compliance_ctrl'](
                [3000, 3000, 200, 3100, 3100, 100]
            )
        
            time.sleep(0.05)

            # 아래 방향으로 force_n 만큼 힘 인가
            _dsr_funcs['set_desired_force'](
                [0, 0, -force_n, 0, 0, 0],
                dir=[0, 0, 1, 0, 0, 0],
                mod=_dsr_funcs['DR_FC_MOD_REL'],
            )

            # 접촉 감지 대기 (최대 1.5초)
            deadline = time.time() + 1.5
            while time.time() < deadline:
                if _dsr_funcs['check_force_condition'](
                    _dsr_funcs['DR_AXIS_Z'], max=force_n * 0.7
                ):
                    break
                time.sleep(0.02)

            # 접촉 유지
            time.sleep(self._dot_hold_sec)

            with self._lock:
                self.state.pen_force = force_n

        finally:
            _dsr_funcs['release_force']()
            time.sleep(0.03)
            _dsr_funcs['release_compliance_ctrl']()
            with self._lock:
                self.state.pen_force = 0.0

    def draw_pixel(self, x: float, y: float, force: float,
                   z_up: float, z_ready: float,
                   pixel_size: float = PIXEL_SIZE_MM,
                   pitch: float = PIXEL_PITCH_MM):
        """
        픽셀 한 칸을 사각형 래스터 스캔(ㄹ자)으로 그림.
        pixel_test.py의 draw_pixel 로직을 서버에 통합한 버전.
        """
        if self.state.estop:
            raise RuntimeError("E-STOP 상태에서 이동 불가")

        mode = "실제" if _dsr_available else "시뮬"
        log.info(f"draw_pixel [{mode}] x={x:.1f} y={y:.1f} force={force:.1f}N z_up={z_up:.1f} z_dn={z_ready:.1f}")

        if _dsr_available:
            posx   = _dsr_funcs['posx']
            movel  = _dsr_funcs['movel']
            amovel = _dsr_funcs['amovel']
            DR_BASE       = _dsr_funcs['DR_BASE']
            DR_MV_MOD_REL = _dsr_funcs['DR_MV_MOD_REL']
            DR_FC_MOD_REL = _dsr_funcs['DR_FC_MOD_REL']

            # 픽셀 좌상단을 hover 목표로 설정 (접촉 후 긁힘 방지)
            hover_pos = posx(x - pixel_size, y + pixel_size, z_up, 0, 180, 0)

            try:
                # 상공 → 좌상단으로 이동
                ret = movel(hover_pos, vel=self._move_speed, acc=self._move_speed * 2)
                log.info(f"movel hover ret={ret}")

                if self.state.estop:
                    return

                # 컴플라이언스 + 목표 힘 인가
                time.sleep(0.03)
                _dsr_funcs['task_compliance_ctrl']([3000, 3000, 500, 100, 100, 100])
                time.sleep(0.03)
                _dsr_funcs['set_desired_force'](
                    [0, 0, -force, 0, 0, 0],
                    dir=[0, 0, 1, 0, 0, 0],
                    mod=DR_FC_MOD_REL,
                )
                # 실제 힘이 목표의 70%에 도달할 때까지 대기 (최대 1.5초)
                t0 = time.time()
                deadline = t0 + 1.5
                while time.time() < deadline:
                    if self.state.estop:
                        return
                    with self._lock:
                        fz = abs(self.state.tool_force[2]) if len(self.state.tool_force) > 2 else 0
                    if fz >= force * 0.7:
                        log.info(f"힘 도달: {fz:.2f}N / 목표 {force}N ({(time.time()-t0)*1000:.0f}ms)")
                        break
                    time.sleep(0.02)
                else:
                    with self._lock:
                        fz = abs(self.state.tool_force[2]) if len(self.state.tool_force) > 2 else 0
                    log.warning(f"힘 도달 타임아웃 (현재 {fz:.2f}N / 목표 {force}N)")

                with self._lock:
                    self.state.pen_force = force

                # ㄹ자 패턴
                lines     = int(pixel_size / pitch)
                direction = 1
                for i in range(lines + 1):
                    if self.state.estop:
                        return
                    amovel(posx(direction * pixel_size, 0, 0, 0, 0, 0),
                           vel=10, acc=20, ref=DR_BASE, mod=DR_MV_MOD_REL)
                    time.sleep(0.05)
                    if i < lines:
                        amovel(posx(0, -pitch, 0, 0, 0, 0),
                               vel=10, acc=20, ref=DR_BASE, mod=DR_MV_MOD_REL)
                        time.sleep(0.03)
                        direction *= -1

            finally:
                # 힘 해제 후 상공 복귀
                _dsr_funcs['release_force']()
                time.sleep(0.03)
                _dsr_funcs['release_compliance_ctrl']()
                with self._lock:
                    self.state.pen_force = 0.0
                movel(hover_pos, vel=self._move_speed, acc=self._move_speed * 2)

        else:
            # 시뮬레이션
            lines = int(pixel_size / pitch)
            sim_time = max(0.05, lines * 0.05)
            with self._lock:
                self.state.tcp_x     = x
                self.state.tcp_y     = y
                self.state.pen_force = force
            time.sleep(sim_time)
            with self._lock:
                self.state.pen_force = 0.0

    def draw_contour_segment(self, points: list[tuple], force: float,
                             z_up: float, z_dn: float):
        """
        등고선 선분: 펜을 내린 채로 points 목록을 movel로 연속 이동.
        draw_pixel 대비 컴플라이언스 setup/teardown이 선분당 1회라 빠름.
        """
        if not points or self.state.estop:
            return

        if _dsr_available:
            posx    = _dsr_funcs['posx']
            movel   = _dsr_funcs['movel']
            DR_BASE = _dsr_funcs['DR_BASE']

            hover = posx(points[0][0], points[0][1], z_up, 0, 180, 0)

            movel(hover, vel=[self._move_speed, self._move_speed], acc=[self._move_speed*2, self._move_speed*2], ref=DR_BASE)

            try:
                _dsr_funcs['task_compliance_ctrl']([3000, 3000, 500, 100, 100, 100])
                time.sleep(0.03)
                _dsr_funcs['set_desired_force'](
                    [0, 0, -force, 0, 0, 0],
                    dir=[0, 0, 1, 0, 0, 0],
                    mod=_dsr_funcs['DR_FC_MOD_REL'],
                )
                t0 = time.time()
                while time.time() - t0 < 1.5:
                    with self._lock:
                        fz = abs(self.state.tool_force[2]) if len(self.state.tool_force) > 2 else 0
                    if fz >= force * 0.7:
                        break
                    time.sleep(0.02)
                with self._lock:
                    self.state.pen_force = force

                for rx, ry in points[1:]:
                    pos = posx(rx, ry, z_dn, 0, 180, 0)
                    movel(pos, vel=[DRAW_SPEED, DRAW_SPEED], acc=[DRAW_SPEED*2, DRAW_SPEED*2], ref=DR_BASE)

            finally:
                _dsr_funcs['release_force']()
                time.sleep(0.03)
                _dsr_funcs['release_compliance_ctrl']()
                with self._lock:
                    self.state.pen_force = 0.0
                movel(hover, vel=[self._move_speed, self._move_speed], acc=[self._move_speed*2, self._move_speed*2], ref=DR_BASE)

        else:
            with self._lock:
                self.state.pen_force = force
            time.sleep(len(points) * 0.01)
            if points:
                with self._lock:
                    self.state.tcp_x = points[-1][0]
                    self.state.tcp_y = points[-1][1]
            with self._lock:
                self.state.pen_force = 0.0

    # ── 자동 Z 캘리브레이션 ──────────────────────────────────────
    def auto_calibrate_z(self, origin_x: float, origin_y: float) -> dict:
        """
        종이 원점 XY에서 Z를 천천히 내려 접촉점 자동 측정.
        반환: {'contact_z': float, 'pen_up_z': float, 'pen_down_z': float}
        """
        Z_START         = 280.0   # 탐색 시작 높이 (mm)
        FORCE_THRESHOLD = 0.8     # 접촉 감지 임계 힘 (N)

        if self.state.estop:
            raise RuntimeError("E-STOP 상태에서 Z 측정 불가")
        if not _dsr_available:
            raise RuntimeError("실제 로봇 연결 필요 (시뮬 모드에서는 불가)")

        posx   = _dsr_funcs['posx']
        movel  = _dsr_funcs['movel']
        DR_BASE = _dsr_funcs['DR_BASE']

        log.info(f"자동 Z 측정 시작: ({origin_x:.1f}, {origin_y:.1f}), 시작 Z={Z_START}")

        start_pos = posx(origin_x, origin_y, Z_START, 0.0, 180.0, 0.0)
        movel(start_pos, vel=[self._move_speed, self._move_speed], acc=[self._move_speed * 2, self._move_speed * 2], ref=DR_BASE)

        _dsr_funcs['task_compliance_ctrl']([3000, 3000, 500, 3100, 3100, 100])
        time.sleep(0.05)
        _dsr_funcs['set_desired_force'](
            [0, 0, -1.0, 0, 0, 0],
            dir=[0, 0, 1, 0, 0, 0],
            mod=_dsr_funcs['DR_FC_MOD_REL'],
        )

        contact_z = None
        deadline  = time.time() + 6.0
        while time.time() < deadline:
            with self._lock:
                fz = abs(self.state.tool_force[2]) if len(self.state.tool_force) > 2 else 0
            if fz >= FORCE_THRESHOLD:
                tcp_pos, _ = _dsr_funcs['get_current_posx']()
                if tcp_pos:
                    contact_z = float(tcp_pos[2])
                break
            time.sleep(0.05)

        _dsr_funcs['release_force']()
        time.sleep(0.03)
        _dsr_funcs['release_compliance_ctrl']()
        movel(start_pos, vel=[self._move_speed, self._move_speed], acc=[self._move_speed * 2, self._move_speed * 2], ref=DR_BASE)

        if contact_z is None:
            raise RuntimeError("접촉 감지 실패 — 종이 없음 또는 Z_START가 너무 낮음")

        pen_up_z   = round(contact_z + 3.0, 2)
        pen_down_z = round(contact_z + 2.0, 2)
        log.info(f"Z 측정 완료: 접촉={contact_z:.2f}mm, pen_up={pen_up_z}, pen_down={pen_down_z}")
        return {'contact_z': round(contact_z, 2), 'pen_up_z': pen_up_z, 'pen_down_z': pen_down_z}

    # ── 그리퍼 (RG2, Modbus TCP) ────────────────────────────────
    def gripper_open(self, force: float = GRIPPER_DEFAULT_FORCE):
        log.info(f"그리퍼 열기 (force={force}N)")
        _gripper_move(force, GRIPPER_OPEN_WIDTH)
        time.sleep(1.5)  # 동작 완료 대기
        w = _gripper_read_width()
        with self._lock:
            self.state.gripper_width = w if w is not None else GRIPPER_OPEN_WIDTH

    def gripper_close(self, force: float = GRIPPER_DEFAULT_FORCE):
        log.info(f"그리퍼 닫기 (force={force}N)")
        _gripper_move(force, GRIPPER_CLOSE_WIDTH)
        time.sleep(1.5)
        w = _gripper_read_width()
        with self._lock:
            self.state.gripper_width = w if w is not None else GRIPPER_CLOSE_WIDTH

    # ── 상태 조회 ────────────────────────────────────────────────
    def _sync_state_from_robot(self):
        """실제 로봇 위치를 state에 반영 (movel 이후 호출)"""
        if not _dsr_available:
            return
        try:
            joints = _dsr_funcs['get_current_posj']()  # [j1..j6]
            tcp_pos, _ = _dsr_funcs['get_current_posx']()  # returns (posx[6], sol)
            with self._lock:
                if joints:
                    self.state.joints = [float(j) for j in joints]
                if tcp_pos:
                    self.state.tcp_x = float(tcp_pos[0])
                    self.state.tcp_y = float(tcp_pos[1])
                    self.state.tcp_z = float(tcp_pos[2])
        except Exception as e:
            log.debug(f"상태 동기화 실패: {e}")

    def get_state(self) -> dict:
        # _sync_state_from_robot은 movel/movej 직후에만 호출 — 여기서 블로킹하면 async 루프 막힘
        with self._lock:
            s = self.state
            return {
                "connected"    : s.connected,
                "powered"      : s.powered,
                "estop"        : s.estop,
                "status"       : s.status,
                "joints"       : list(s.joints),
                "tcpX"         : round(s.tcp_x, 2),
                "tcpY"         : round(s.tcp_y, 2),
                "tcpZ"         : round(s.tcp_z, 2),
                "speed"        : round(s.speed, 1),
                "gripperWidth" : round(s.gripper_width, 1),
                "penForce"     : round(s.pen_force, 2),
                "toolForce"    : [round(v, 2) for v in s.tool_force],
                "ros2"         : _dsr_available,
                "robotIp"      : self.robot_ip,
                "robotPort"    : self.robot_port,
            }

    def set_status(self, status: str):
        with self._lock:
            if self.state.estop:  # E-STOP 중에는 외부에서 status 변경 불가
                return
            self.state.status = status

    # ── 액자 작업 시퀀스 (T4_robottask 기반) ───────────────────
    def run_frame_task(self):
        """액자 하판/상판 조립 + 종이 픽업 + 캘리브레이션 + 꺼내기 시퀀스."""
        if self.state.estop:
            raise RuntimeError("E-STOP 상태에서 실행 불가")
        if not _dsr_available:
            raise RuntimeError("실제 로봇 연결 필요")

        movej  = _dsr_funcs['movej']
        movel  = _dsr_funcs['movel']
        amovel = _dsr_funcs['amovel']
        posx   = _dsr_funcs['posx']
        posj   = _dsr_funcs['posj']
        task_compliance_ctrl    = _dsr_funcs['task_compliance_ctrl']
        set_desired_force       = _dsr_funcs['set_desired_force']
        release_force           = _dsr_funcs['release_force']
        release_compliance_ctrl = _dsr_funcs['release_compliance_ctrl']
        DR_FC_MOD_REL = _dsr_funcs['DR_FC_MOD_REL']
        DR_MV_MOD_REL = _dsr_funcs['DR_MV_MOD_REL']

        home_pos = posj(8.5, 5.45, 82.85, 179.96, -91.70, -171.71)

        with self._lock:
            self.state.status = "running"

        def frame_lower_setup():
            pos_lowframe_start_hover  = posj(-17.09, -4.66, 71.34, 179.97, -113.32, 72.06)
            pos_lowframe_start_hoverx = posx(291.95, -83.31, 569.94, 170.08, -180, 79.19)
            pos_lowframe_start        = posx(291.95, -83.31, 352.89, 170.08, -180, 79.19)
            pos_frame_lower1          = posj(60.82, 29.56, 80.77, 120.95, -144.29, 126.52)
            pos_frame_lower2          = posx(269.77, 295.96, 74.64, 90.91, -89.97, -0.03)
            pos_frame_lower3          = posx(269.77, 345.96, 74.64, 90.91, -89.97, -0.03)
            pos_frame_lower4          = posx(269.77, 345.96, 174.64, 90.91, -89.97, -0.03)

            self.gripper_open()
            time.sleep(0.1)
            movej(home_pos, vel=30, acc=50)
            log.info("--- [1] 액자 하판 파지 시작 ---")
            time.sleep(0.1)
            movej(pos_lowframe_start_hover, vel=20, acc=50)
            time.sleep(0.1)
            movel(pos_lowframe_start, vel=20, acc=50)
            time.sleep(0.1)
            self.gripper_close()
            time.sleep(0.1)
            movel(pos_lowframe_start_hoverx, vel=20, acc=50)
            time.sleep(0.1)
            movej(pos_frame_lower1, vel=20, acc=50)
            time.sleep(0.1)
            movel(pos_frame_lower2, vel=20, acc=50, mod=0)
            time.sleep(0.1)
            self.gripper_open()
            time.sleep(0.5)
            movel(pos_frame_lower3, vel=20, acc=50, mod=0)
            time.sleep(0.1)
            movel(pos_frame_lower4, vel=20, acc=50, mod=0)
            time.sleep(0.1)
            movej(home_pos, vel=30, acc=50)

        def frame_high_setup():
            pos_frame_highstart_hover  = posj(-24.40, -1.33, 65.83, 180.02, -115.51, 65.63)
            pos_frame_highstart_hoverx = posx(295.35, -127.08, 583.96, 70.24, 179.95, -19.80)
            pos_frame_highstart        = posx(295.36, -127.08, 347.73, 67.75, 179.95, -22.29)
            pos_frame_high1            = posj(60.55, 31.09, 84.84, 127.70, -141.56, 134.69)
            pos_frame_high2            = posx(274.49, 328.02, 81.75, 90.06, -90.00, 0.00)
            pos_frame_high3            = posx(274.49, 378.02, 81.75, 90.06, -90.00, 0.00)
            pos_frame_high4            = posx(274.49, 378.02, 181.75, 90.06, -90.00, 0.00)

            self.gripper_open()
            time.sleep(0.1)
            movej(home_pos, vel=30, acc=50)
            log.info("--- [2] 액자 상판 파지 시작 ---")
            time.sleep(0.1)
            movej(pos_frame_highstart_hover, vel=20, acc=50)
            time.sleep(0.1)
            movel(pos_frame_highstart, vel=20, acc=50)
            time.sleep(0.1)
            self.gripper_close()
            time.sleep(0.1)
            movel(pos_frame_highstart_hoverx, vel=20, acc=50)
            time.sleep(0.1)
            movej(pos_frame_high1, vel=20, acc=50)
            time.sleep(0.1)
            movel(pos_frame_high2, vel=20, acc=50, mod=0)
            time.sleep(0.1)
            self.gripper_open()
            time.sleep(0.5)
            movel(pos_frame_high3, vel=20, acc=50, mod=0)
            time.sleep(0.1)
            movel(pos_frame_high4, vel=20, acc=50, mod=0)
            time.sleep(0.1)
            movej(home_pos, vel=30, acc=50)

        def calibration_frame():
            pos_paper_calx0 = posj(-1.28, -31.68, 111.03, 180.06, -100.58, 88.75)
            pos_paper_calx1 = posj(-1.25, -31.81, 131.84, 180.07, -79.95, 88.74)
            pos_paper_caly0 = posx(277.05, 158.74, 390.10, 68.97, 179.95, -21.07)
            pos_paper_caly1 = posx(277.05, 158.74, 290.10, 68.97, 179.95, -21.07)

            log.info("--- [Cal] Y축 캘리브레이션 ---")
            self.gripper_close()
            time.sleep(0.1)
            movel(pos_paper_caly0, vel=50, acc=50)
            time.sleep(0.1)
            movel(pos_paper_caly1, vel=50, acc=50)
            time.sleep(0.5)
            task_compliance_ctrl(stx=[100, 3000, 3000, 100, 100, 100])
            time.sleep(0.5)
            set_desired_force(fd=[0, -15, 0, 0, 0, 0], dir=[0, 1, 0, 0, 0, 0], mod=DR_FC_MOD_REL)
            time.sleep(13)
            release_force()
            time.sleep(0.5)
            release_compliance_ctrl()
            time.sleep(0.1)
            movel(pos_paper_caly1, vel=50, acc=50)
            time.sleep(0.1)
            movel(pos_paper_caly0, vel=50, acc=50)

            log.info("--- [Cal] X축 캘리브레이션 ---")
            self.gripper_close()
            time.sleep(0.1)
            movej(pos_paper_calx0, vel=50, acc=50)
            time.sleep(0.1)
            movej(pos_paper_calx1, vel=50, acc=50)
            time.sleep(0.5)
            task_compliance_ctrl(stx=[100, 3000, 3000, 100, 100, 100])
            time.sleep(0.5)
            set_desired_force(fd=[15, 0, 0, 0, 0, 0], dir=[1, 0, 0, 0, 0, 0], mod=DR_FC_MOD_REL)
            time.sleep(7.5)
            release_force()
            time.sleep(0.5)
            release_compliance_ctrl()
            time.sleep(0.1)
            movej(pos_paper_calx1, vel=50, acc=50)
            time.sleep(0.1)
            movej(pos_paper_calx0, vel=50, acc=50)

        def slide_and_pinch_paper():
            pos_paper_center        = posx(547.03, 75.97, 334.62, 9.86, 180.00, 98.32)
            pos_cliff_edge          = posx(547.03, 120.97, 334.63, 179.99, 180.00, -91.36)
            pos_frame_paper_prepare = posx(288.95, 239.42, 444.60, 91, -135.9, 179)
            pos_frame_paper0        = posx(288.96, 179.73, 334.59, 91.03, -135.31, 178.80)
            pos_frame_paper1        = posx(288.96, 179.73, 444.59, 91.03, -135.31, 178.80)
            pinch_ready_pos0        = posx(554.45, 403.09, 193.32, 91.36, -90.00, 180.00)
            pinch_ready_pos1        = posx(554.45, 403.11, 103.32, 91.36, -90.00, 180.00)
            pinch_ready_pos2        = posx(554.45, 373.14, 103.32, 91.36, -90.00, -180.00)
            hover_pos               = posx(547.03, 75.97, 364.62, 9.86, 180.00, 98.32)  # Z+30
            cliff_up                = posx(547.03, 120.97, 434.63, 179.99, 180.00, -91.36)

            log.info("--- [3] 종이 슬라이딩 시작 ---")
            self.gripper_open()
            time.sleep(0.1)
            movej(home_pos, vel=30, acc=50)
            time.sleep(0.1)
            movel(hover_pos, vel=100, acc=100, mod=0)
            time.sleep(0.1)
            self.gripper_close()
            time.sleep(0.1)
            movel(pos_paper_center, vel=30, acc=50, mod=0)

            task_compliance_ctrl(stx=[500, 500, 500, 100, 100, 100])
            time.sleep(0.5)
            set_desired_force(fd=[0, 0, -3, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0], mod=DR_FC_MOD_REL)
            time.sleep(2)
            amovel(pos_cliff_edge, vel=30, acc=50, mod=0, ref=0)
            time.sleep(3)
            release_force()
            time.sleep(0.5)
            release_compliance_ctrl()
            time.sleep(0.1)
            movel(cliff_up, vel=100, acc=100)

            log.info("--- [3] 꼬집기(Pinch) 픽업 ---")
            self.gripper_open()
            movel(pinch_ready_pos0, vel=50, acc=50)
            time.sleep(0.1)
            movel(pinch_ready_pos1, vel=50, acc=50)
            time.sleep(0.1)
            movel(pinch_ready_pos2, vel=50, acc=50)
            time.sleep(0.1)
            self.gripper_close()
            time.sleep(0.1)
            movel(pinch_ready_pos0, vel=50, acc=50)
            time.sleep(0.5)

            movel(pos_frame_paper_prepare, vel=30, acc=50)
            log.info("--- [3] 액자로 이동 ---")
            movel(pos_frame_paper0, vel=50, acc=50)
            time.sleep(0.1)
            self.gripper_open()
            time.sleep(2)
            pos_paper_release = posx(0, 0, 0, 90, -40, -90)
            amovel(pos_frame_paper1, vel=[30.0, 30.0], acc=[20.0, 20.0], mod=0, ref=0)
            amovel(pos_paper_release, vel=[20.0, 20.0], acc=[10.0, 10.0], mod=DR_MV_MOD_REL, ref=0)
            time.sleep(3)
            movej(home_pos, vel=30, acc=50)
            log.info("--- 액자 안착 완료 ---")

        def frameout():
            pos_frameout0        = posx(281.78, 288.83, 80.12, 90, -90, 0)
            pos_frameout1        = posx(281.78, 340.83, 80.12, 90, -90, 0)
            pos_frameout1_hover  = posx(281.78, 340.83, 300.12, 90, -90, 0)
            pos_framefinal       = posx(420, 51.77, 349.94, 7.48, 179.48, -173.96)
            pos_framefinal_hover = posx(420, 51.77, 549.94, 7.48, 179.48, -173.96)

            log.info("--- [5] 액자 꺼내기 ---")
            movej(home_pos, vel=30, acc=50)
            time.sleep(0.1)
            self.gripper_open()
            time.sleep(0.1)
            movel(pos_frameout1_hover, vel=30, acc=50)
            time.sleep(0.1)
            movel(pos_frameout1, vel=30, acc=50)
            time.sleep(0.1)
            movel(pos_frameout0, vel=30, acc=50)
            time.sleep(0.1)
            self.gripper_close()
            time.sleep(0.1)
            movel(pos_frameout1_hover, vel=30, acc=50)
            time.sleep(0.1)
            movel(pos_framefinal_hover, vel=30, acc=50)
            time.sleep(0.1)
            movel(pos_framefinal, vel=30, acc=50)
            time.sleep(0.1)
            self.gripper_open()
            time.sleep(0.1)
            movel(pos_frameout1_hover, vel=30, acc=50)

        try:
            frame_lower_setup()
            slide_and_pinch_paper()
            calibration_frame()
            frame_high_setup()
            calibration_frame()
            frameout()
            log.info("액자 작업 시퀀스 완료")
        except Exception as e:
            log.error(f"액자 작업 실패: {e}")
            raise
        finally:
            with self._lock:
                self.state.status = "idle"
