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
from config import (GRIPPER_OPEN_WIDTH, GRIPPER_CLOSE_WIDTH, DOT_HOLD_SEC,
                    MOVE_SPEED, DRAW_SPEED, PIXEL_SIZE_MM, PIXEL_PITCH_MM)

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
DSR_IMP_PATH = "/home/jihoon/ros2_ws/src/DoosanBootcamp/dsr_common2/imp"


def _read_dsr_robot_params() -> tuple[str, int]:
    """dsr_hardware2 config YAML 파일에서 robot host/port를 읽어 반환. 실패 시 config.py 값 사용."""
    try:
        import glob
        pattern = f"/home/jihoon/ros2_ws/install/dsr_hardware2/share/dsr_hardware2/config/{ROBOT_ID}_parameters.yaml"
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

        # MoveStop 서비스 직접 클라이언트 (E-STOP용)
        from dsr_msgs2.srv import MoveStop
        _stop_client = node.create_client(MoveStop, f'/{ROBOT_ID}/motion/move_stop')
        _dsr_funcs['stop_client'] = _stop_client
        _dsr_funcs['MoveStop']    = MoveStop

        _dsr_available = True
        log.info("DSR_ROBOT2 초기화 성공 — 실제 M0609 제어 모드")
        return True

    except Exception as e:
        log.warning(f"DSR_ROBOT2 초기화 실패 → 시뮬레이션 모드: {e}")
        return False


_init_dsr()


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


class RobotController:

    _HOME_JOINTS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    _HOME_TCP    = (423.0, 12.0, 315.0)

    def __init__(self):
        self.state = RobotState()
        self._lock = threading.Lock()
        self.robot_ip, self.robot_port = _read_dsr_robot_params()

    # ── 연결 ────────────────────────────────────────────────────
    def connect(self) -> bool:
        if _dsr_available:
            self._sync_state_from_robot()   # 초기 TCP 위치
            self._start_joint_subscriber()  # joint_states 토픽 구독
            log.info("M0609 연결됨 (DSR_ROBOT2)")
        else:
            log.info("시뮬레이션 모드로 연결")
        self._start_gripper_poll()          # 그리퍼 너비 폴링 (항상)
        with self._lock:
            self.state.connected = True
            self.state.powered   = True
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
        /dsr01/msg/joint_state  → 조인트 각도 (degrees, Float64MultiArray)
        /dsr01/msg/current_posx → TCP 위치 mm (Float64MultiArray)
        서비스 콜을 쓰는 g_node와 충돌하지 않도록 별도 노드 사용.
        """
        rclpy = _dsr_funcs['rclpy']
        from std_msgs.msg import Float64MultiArray

        sub_node = rclpy.create_node('robot_art_sub')

        def _joint_cb(msg: Float64MultiArray):
            joints = [round(v, 2) for v in msg.data]
            if len(joints) == 6:
                with self._lock:
                    self.state.joints = joints

        def _posx_cb(msg: Float64MultiArray):
            if len(msg.data) >= 3:
                with self._lock:
                    self.state.tcp_x = round(msg.data[0], 2)
                    self.state.tcp_y = round(msg.data[1], 2)
                    self.state.tcp_z = round(msg.data[2], 2)

        sub_node.create_subscription(Float64MultiArray, '/dsr01/msg/joint_state',   _joint_cb, 10)
        sub_node.create_subscription(Float64MultiArray, '/dsr01/msg/current_posx',  _posx_cb, 10)

        from rclpy.executors import SingleThreadedExecutor
        sub_executor = SingleThreadedExecutor()
        sub_executor.add_node(sub_node)
        t = threading.Thread(target=sub_executor.spin, daemon=True)
        t.start()
        self._sub_node = sub_node
        self._sub_executor = sub_executor
        log.info("joint_state / current_posx 토픽 구독 시작")

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
                MoveStop = _dsr_funcs['MoveStop']
                client   = _dsr_funcs['stop_client']
                rclpy    = _dsr_funcs['rclpy']
                node     = _dsr_funcs['node']
                req = MoveStop.Request()
                req.stop_mode = 0  # STOP_TYPE_QUICK_STO (STO → 안전회로 트리거 + 빨간 램프)
                future = client.call_async(req)
                rclpy.spin_until_future_complete(node, future, timeout_sec=2.0)
                log.info("E-STOP: move_stop 완료")
            except Exception as e:
                log.error(f"E-STOP 처리 실패: {e}")

    def release_estop(self):
        log.info("E-STOP 해제")
        if _dsr_available:
            try:
                from DSR_ROBOT2 import set_robot_mode
                from DRFC import ROBOT_MODE_AUTONOMOUS
                set_robot_mode(ROBOT_MODE_AUTONOMOUS)
                log.info("E-STOP 해제: AUTONOMOUS 모드 복귀")
            except Exception as e:
                log.error(f"AUTONOMOUS 모드 복귀 실패: {e}")
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
                _dsr_funcs['move_home'](target=0)  # DR_HOME_TARGET_MECHANIC
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
                time.sleep(DOT_HOLD_SEC)
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
            time.sleep(DOT_HOLD_SEC)

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

            start_offset = pixel_size / 2.0
            hover_pos = posx(x - start_offset, y + start_offset, z_up,    0, 180, 0)
            ready_pos = posx(x - start_offset, y + start_offset, z_ready, 0, 180, 0)

            try:
                # 상공 → 종이 근처로 이동
                ret = movel(hover_pos, vel=MOVE_SPEED, acc=MOVE_SPEED * 2)
                log.info(f"movel hover ret={ret}")
                time.sleep(0.1)
                ret = movel(ready_pos, vel=DRAW_SPEED, acc=DRAW_SPEED * 2)
                log.info(f"movel ready ret={ret}")

                # 컴플라이언스 + 목표 힘 인가
                time.sleep(0.1)
                _dsr_funcs['task_compliance_ctrl']([3000, 3000, 500, 100, 100, 100])
                time.sleep(0.1)
                _dsr_funcs['set_desired_force'](
                    [0, 0, -force, 0, 0, 0],
                    dir=[0, 0, 1, 0, 0, 0],
                    mod=DR_FC_MOD_REL,
                )
                time.sleep(2)

                with self._lock:
                    self.state.pen_force = force

                # 래스터 스캔 시작점(좌상단)으로 미세 이동
                amovel(posx(-start_offset, start_offset, 0, 0, 0, 0),
                       vel=10, acc=20, ref=DR_BASE, mod=DR_MV_MOD_REL)
                time.sleep(0.1)

                # ㄹ자 패턴
                lines     = int(pixel_size / pitch)
                direction = 1
                for i in range(lines + 1):
                    amovel(posx(direction * pixel_size, 0, 0, 0, 0, 0),
                           vel=10, acc=20, ref=DR_BASE, mod=DR_MV_MOD_REL)
                    time.sleep(0.2)
                    if i < lines:
                        amovel(posx(0, -pitch, 0, 0, 0, 0),
                               vel=10, acc=20, ref=DR_BASE, mod=DR_MV_MOD_REL)
                        time.sleep(0.1)
                        direction *= -1

            finally:
                # 힘 해제 후 상공 복귀
                time.sleep(0.1)
                _dsr_funcs['release_force']()
                time.sleep(0.1)
                _dsr_funcs['release_compliance_ctrl']()
                with self._lock:
                    self.state.pen_force = 0.0
                time.sleep(0.1)
                movel(hover_pos, vel=MOVE_SPEED, acc=MOVE_SPEED * 2)

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

    # ── 그리퍼 (RG2, Modbus TCP) ────────────────────────────────
    def gripper_open(self, force: float = 20.0):
        log.info(f"그리퍼 열기 (force={force}N)")
        _gripper_move(force, GRIPPER_OPEN_WIDTH)
        time.sleep(1.5)  # 동작 완료 대기
        w = _gripper_read_width()
        with self._lock:
            self.state.gripper_width = w if w is not None else GRIPPER_OPEN_WIDTH

    def gripper_close(self, force: float = 20.0):
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
            tcp    = _dsr_funcs['get_current_posx']()   # [x,y,z,rx,ry,rz]
            with self._lock:
                if joints:
                    self.state.joints = [float(j) for j in joints]
                if tcp:
                    self.state.tcp_x = float(tcp[0])
                    self.state.tcp_y = float(tcp[1])
                    self.state.tcp_z = float(tcp[2])
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
                "ros2"         : _dsr_available,
            }

    def set_status(self, status: str):
        with self._lock:
            if self.state.estop:  # E-STOP 중에는 외부에서 status 변경 불가
                return
            self.state.status = status
