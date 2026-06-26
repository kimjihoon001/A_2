# ================================================================
# main.py — FastAPI WebSocket 브리지 (HMI ↔ ROS2 robot_art_node)
#
# 실행 순서:
#   1. ros2 launch dsr_bringup2 dsr_bringup2_rviz.launch.py ...
#   2. python3 ros2_node/robot_art_node.py  (robot_art_node)
#   3. uvicorn main:app --host 0.0.0.0 --port 8765
# ================================================================

import asyncio
import json
import logging
import threading
import time
from contextlib import asynccontextmanager

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger
from std_msgs.msg import Float64MultiArray
from dsr_msgs2.srv import ServoOff, SetRobotControl, GetRobotState, Jog, JogMulti, SetRobotMode
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from config import WS_HOST, WS_PORT, STATUS_INTERVAL_SEC
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

# ── 공유 상태 ────────────────────────────────────────────────────
db      = Database()
_clients: set[WebSocket] = set()
_loop  : asyncio.AbstractEventLoop = None   # type: ignore
_last_status: dict = {}                     # ROS2 → HMI 캐시
_last_status_time: float = 0.0             # robot_art_node 마지막 수신 시각


# ── ROS2 브리지 노드 ──────────────────────────────────────────────
class BridgeNode(Node):
    """robot_art_node와 통신하는 브리지"""

    def __init__(self):
        super().__init__('robot_art_bridge')

        # 픽셀 발행 (→ robot_art_node)
        self._pixels_pub = self.create_publisher(String, '/robot_art/pixels', 10)

        # 서비스 클라이언트 (robot_art_node 경유)
        self._svc = {
            name: self.create_client(Trigger, f'/robot_art/{name}')
            for name in ('start', 'stop', 'pause', 'resume', 'home',
                         'gripper_open', 'gripper_close', 'pencil_grip', 'pencil_release', 'calibrate_z', 'frame_task',
                         'confirm_retry', 'release_estop')
        }

        # DSR 직접 서비스 클라이언트 (estop/release/연결확인)
        self._servo_off_client = self.create_client(ServoOff,        '/dsr01/system/servo_off')
        self._servo_on_client  = self.create_client(SetRobotControl, '/dsr01/system/set_robot_control')
        self._state_client     = self.create_client(GetRobotState,   '/dsr01/system/get_robot_state')
        self._jog_client       = self.create_client(Jog,             '/dsr01/motion/jog')
        self._jog_multi_client = self.create_client(JogMulti,        '/dsr01/motion/jog_multi')
        self._set_mode_client  = self.create_client(SetRobotMode,    '/dsr01/system/set_robot_mode')

        # 연결 상태 폴링 (0.5초)
        self._dsr_connected = False
        self.create_timer(0.5, self._poll_connection)

        # DSR 직접 토픽 구독 (joint/TCP 실시간)
        self._joints = [0.0] * 6
        self._tcp    = [0.0, 0.0, 0.0]
        self.create_subscription(Float64MultiArray, '/dsr01/msg/joint_state',   self._on_joint, 10)
        self.create_subscription(Float64MultiArray, '/dsr01/msg/current_posx',  self._on_posx,  10)

        # 상태/로그 구독 (robot_art_node →)
        self.create_subscription(String, '/robot_art/status', self._on_status, 10)
        self.create_subscription(String, '/robot_art/log',    self._on_log,    10)

    # ── 픽셀 전송 ───────────────────────────────────────────────
    def call_jog(self, axis: int, speed: float, ref: int = 0, timeout: float = 2.0) -> dict:
        if not self._jog_client.wait_for_service(timeout_sec=timeout):
            return {'success': False, 'message': 'jog 서비스 응답 없음'}
        req = Jog.Request()
        req.jog_axis       = axis
        req.move_reference = ref
        req.speed          = speed
        done = threading.Event()
        result_box: list = [None]
        future = self._jog_client.call_async(req)
        future.add_done_callback(lambda f: (result_box.__setitem__(0, f.result()), done.set()))
        if not done.wait(timeout=timeout):
            return {'success': False, 'message': 'jog 응답 타임아웃'}
        return {'success': result_box[0].success}

    def call_jog_multi(self, vector: list, speed: float, ref: int = 0, timeout: float = 2.0) -> dict:
        if not self._jog_multi_client.wait_for_service(timeout_sec=timeout):
            return {'success': False, 'message': 'jog_multi 서비스 응답 없음'}
        req = JogMulti.Request()
        req.jog_axis       = vector          # float64[6] 단위벡터
        req.move_reference = ref
        req.speed          = speed
        done = threading.Event()
        result_box: list = [None]
        future = self._jog_multi_client.call_async(req)
        future.add_done_callback(lambda f: (result_box.__setitem__(0, f.result()), done.set()))
        if not done.wait(timeout=timeout):
            return {'success': False, 'message': 'jog_multi 응답 타임아웃'}
        return {'success': result_box[0].success}

    def call_set_robot_mode(self, mode: int, timeout: float = 3.0) -> dict:
        if not self._set_mode_client.wait_for_service(timeout_sec=timeout):
            return {'success': False, 'message': 'set_robot_mode 서비스 응답 없음'}
        req = SetRobotMode.Request()
        req.robot_mode = mode
        done = threading.Event()
        result_box: list = [None]
        future = self._set_mode_client.call_async(req)
        future.add_done_callback(lambda f: (result_box.__setitem__(0, f.result()), done.set()))
        if not done.wait(timeout=timeout):
            return {'success': False, 'message': 'set_robot_mode 응답 타임아웃'}
        return {'success': result_box[0].success}

    def publish_pixels(self, pixels: list, settings: dict, image_name: str):
        msg = String()
        msg.data = json.dumps(
            {'pixels': pixels, 'settings': settings, 'imageName': image_name},
            ensure_ascii=False,
        )
        self._pixels_pub.publish(msg)

    # ── 서비스 호출 (동기, 타임아웃 5s) ────────────────────────
    def call_service(self, name: str, timeout: float = 5.0) -> dict:
        client = self._svc[name]
        if not client.wait_for_service(timeout_sec=timeout):
            return {'success': False, 'message': f'{name} 서비스 응답 없음 (타임아웃 {timeout}s)'}
        done = threading.Event()
        result_box: list = [None]
        def _cb(f):
            result_box[0] = f.result()
            done.set()
        future = client.call_async(Trigger.Request())
        future.add_done_callback(_cb)
        if not done.wait(timeout=timeout):
            return {'success': False, 'message': f'{name} 서비스 응답 없음 (타임아웃 {timeout}s)'}
        r = result_box[0]
        return {'success': r.success, 'message': r.message}

    def _poll_connection(self):
        self._dsr_connected = self._state_client.service_is_ready()

    def _on_joint(self, msg: Float64MultiArray):
        if len(msg.data) == 6:
            self._joints = [round(v, 2) for v in msg.data]

    def _on_posx(self, msg: Float64MultiArray):
        if len(msg.data) >= 3:
            self._tcp = [round(msg.data[0], 2), round(msg.data[1], 2), round(msg.data[2], 2)]

    def call_estop(self, timeout: float = 5.0) -> dict:
        if not self._servo_off_client.wait_for_service(timeout_sec=timeout):
            return {'success': False, 'message': 'servo_off 서비스 응답 없음'}
        done = threading.Event()
        result_box: list = [None]
        req = ServoOff.Request()
        req.stop_type = ServoOff.Request.STOP_TYPE_QUICK
        future = self._servo_off_client.call_async(req)
        future.add_done_callback(lambda f: (result_box.__setitem__(0, f.result()), done.set()))
        if not done.wait(timeout=timeout):
            return {'success': False, 'message': 'servo_off 응답 타임아웃'}
        return {'success': result_box[0].success, 'message': 'E-STOP 활성화'}

    def call_release_estop(self, timeout: float = 5.0) -> dict:
        if not self._servo_on_client.wait_for_service(timeout_sec=timeout):
            return {'success': False, 'message': 'set_robot_control 서비스 응답 없음'}

        def _send(control_val: int) -> bool:
            done = threading.Event()
            result_box: list = [None]
            req = SetRobotControl.Request()
            req.robot_control = control_val
            future = self._servo_on_client.call_async(req)
            future.add_done_callback(lambda f: (result_box.__setitem__(0, f.result()), done.set()))
            if not done.wait(timeout=timeout):
                return False
            r = result_box[0]
            return r is not None and r.success

        # 1단계: 안전 상태 리셋
        _send(3)
        time.sleep(0.3)
        # 2단계: 서보 ON — 최대 3회 재시도
        for attempt in range(1, 4):
            if _send(1):
                log.info(f"서보 ON 성공 (시도 {attempt}회)")
                return {'success': True, 'message': 'E-STOP 해제 완료'}
            log.warning(f"서보 ON 실패 (시도 {attempt}/3)")
            time.sleep(0.5)

        return {'success': False, 'message': '서보 ON 3회 모두 실패'}

    # ── 구독 콜백 ──────────────────────────────────────────────
    def _on_status(self, msg: String):
        global _last_status, _last_status_time
        try:
            data = json.loads(msg.data)
            _last_status = data
            _last_status_time = time.time()
            # status 타입은 _status_broadcast_loop이 주기적으로 전송
            # 그 외(draw_progress, confirm_request 등)는 즉시 브로드캐스트
            if data.get('type') != 'status' and _loop:
                asyncio.run_coroutine_threadsafe(broadcast(data), _loop)
        except Exception:
            pass

    def _on_log(self, msg: String):
        try:
            data = json.loads(msg.data)
            if _loop:
                asyncio.run_coroutine_threadsafe(broadcast(data), _loop)
        except Exception:
            pass


_bridge: BridgeNode = None   # type: ignore

# STATUS_INTERVAL_SEC의 5배 이내에 수신이 없으면 node 오프라인 판정
_NODE_TIMEOUT = STATUS_INTERVAL_SEC * 5

def _node_online() -> bool:
    return _last_status_time > 0 and (time.time() - _last_status_time) < _NODE_TIMEOUT

def _current_robot_state() -> dict:
    """최신 robot 상태 반환. DSR 서비스 응답 여부로 연결 상태 직접 판단."""
    robot = _last_status.get("robot", {}) if _last_status else {}
    dsr_connected = _bridge is not None and _bridge._dsr_connected
    if not dsr_connected:
        robot = {**robot, "ros2": False, "connected": False, "powered": False}
    return robot


# ── 브리지 스레드 (SingleThreadedExecutor) ───────────────────────
def _ros_spin():
    from rclpy.executors import SingleThreadedExecutor
    while True:
        try:
            executor = SingleThreadedExecutor()
            executor.add_node(_bridge)
            executor.spin()
        except BaseException as e:
            # SystemExit / KeyboardInterrupt 포함 — 스레드가 죽으면 프로세스 전체가 죽으므로
            # 예외를 삼키고 1초 후 재시작해서 ROS2 spin을 유지
            log.error(f"ROS2 spin 예외 (1초 후 재시작): {e}")
            time.sleep(1)


# ── 상태 주기 브로드캐스트 ──────────────────────────────────────
async def _status_broadcast_loop():
    while True:
        try:
            await asyncio.sleep(STATUS_INTERVAL_SEC)
            if not _clients:
                continue

            dsr_connected = _bridge._dsr_connected if _bridge else False

            robot = _last_status.get("robot", {}) if _last_status else {}
            if _bridge:
                robot = {
                    **robot,
                    "connected"    : dsr_connected,
                    "powered"      : dsr_connected,
                    "ros2"         : dsr_connected,
                }

            status_data = {
                **(_last_status or {}),
                "type"      : "status",
                "nodeOnline": dsr_connected,
                "robot"     : robot,
            }
            await broadcast(status_data)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"상태 브로드캐스트 오류: {e}")


# ── WebSocket 브로드캐스트 ───────────────────────────────────────
async def broadcast(data: dict):
    if not _clients:
        return
    msg = json.dumps(data, ensure_ascii=False)
    dead = set()
    for ws in _clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


# ── 앱 생명주기 ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bridge, _loop

    _loop = asyncio.get_event_loop()

    db.init()
    log.info("DB 초기화 완료")

    rclpy.init()
    _bridge = BridgeNode()
    threading.Thread(target=_ros_spin, daemon=True, name="RosBridge").start()
    log.info("ROS2 브리지 노드 시작")
    log.info(f"서버 시작 — ws://{WS_HOST}:{WS_PORT}/ws")

    asyncio.get_event_loop().create_task(_status_broadcast_loop())

    yield

    try:
        rclpy.shutdown()
    except Exception:
        pass
    log.info("서버 종료")


app = FastAPI(title="Robot Art Bridge", lifespan=lifespan)


# ── 명령 처리기 ─────────────────────────────────────────────────
async def handle_command(ws: WebSocket, msg: dict):
    cmd  = msg.get("cmd", "")
    data = msg.get("data", {})

    # ── 그리기 시작: 픽셀 발행 후 start 서비스 호출
    if cmd == "start_drawing":
        pixels     = msg.get("pixels", [])
        settings   = msg.get("settings", {})
        image_name = msg.get("imageName", "unknown")
        if not pixels:
            await ws.send_text(json.dumps({"type": "error", "message": "픽셀 데이터가 없습니다."}))
            return
        await asyncio.to_thread(_bridge.publish_pixels, pixels, settings, image_name)
        await asyncio.sleep(0.1)    # 토픽이 node에 도달할 시간
        result = await asyncio.to_thread(_bridge.call_service, 'start')
        level = "INFO" if result['success'] else "ERROR"
        await ws.send_text(json.dumps({"type": "log", "level": level, "message": result['message']}))

    elif cmd == "pause":
        result = await asyncio.to_thread(_bridge.call_service, 'pause')
        await broadcast({"type": "log", "level": "INFO", "message": result['message']})

    elif cmd == "resume":
        result = await asyncio.to_thread(_bridge.call_service, 'resume')
        await broadcast({"type": "log", "level": "INFO", "message": result['message']})

    elif cmd == "stop":
        # 강제정지 = E-STOP: engine 중단 후 서보 OFF
        await asyncio.to_thread(_bridge.call_service, 'stop')
        await asyncio.to_thread(_bridge.call_estop)
        db.add_log("강제정지 (서보 OFF)", "WARNING")
        await broadcast({"type": "log", "level": "WARNING", "message": "강제정지 — 서보 OFF"})

    elif cmd == "estop":
        result = await asyncio.to_thread(_bridge.call_estop)
        db.add_log("E-STOP 활성화", "ERROR")
        await broadcast({"type": "log", "level": "ERROR", "message": result['message']})

    elif cmd == "reset_estop":
        # robot_art_node 경유 — release_estop()이 _abort 플래그도 리셋
        result = await asyncio.to_thread(_bridge.call_service, 'release_estop', 10.0)
        db.add_log("E-STOP 해제", "INFO")
        await broadcast({"type": "log", "level": "INFO", "message": result.get('message', 'E-STOP 해제')})

    elif cmd == "home":
        result = await asyncio.to_thread(_bridge.call_service, 'home')
        level = "INFO" if result['success'] else "ERROR"
        await broadcast({"type": "log", "level": level, "message": result['message']})

    elif cmd == "gripper_open":
        result = await asyncio.to_thread(_bridge.call_service, 'gripper_open')
        await ws.send_text(json.dumps({"type": "log", "level": "INFO", "message": result['message']}))

    elif cmd == "gripper_close":
        result = await asyncio.to_thread(_bridge.call_service, 'gripper_close')
        await ws.send_text(json.dumps({"type": "log", "level": "INFO", "message": result['message']}))

    elif cmd == "pencil_grip":
        result = await asyncio.to_thread(_bridge.call_service, 'pencil_grip', 30.0)
        level = "INFO" if result['success'] else "ERROR"
        await broadcast({"type": "log", "level": level, "message": result['message']})

    elif cmd == "pencil_release":
        result = await asyncio.to_thread(_bridge.call_service, 'pencil_release', 30.0)
        level = "INFO" if result['success'] else "ERROR"
        await broadcast({"type": "log", "level": level, "message": result['message']})

    elif cmd == "frame_task":
        result = await asyncio.to_thread(_bridge.call_service, 'frame_task', 5.0)
        level = "INFO" if result['success'] else "ERROR"
        await broadcast({"type": "log", "level": level, "message": result['message']})

    elif cmd == "confirm_retry":
        await asyncio.to_thread(_bridge.call_service, 'confirm_retry')

    elif cmd == "jog":
        axis  = int(msg.get('axis',  6))
        speed = float(msg.get('speed', 0))
        ref   = int(msg.get('ref',   0))
        await asyncio.to_thread(_bridge.call_jog, axis, speed, ref)

    elif cmd == "jog_multi":
        vector = [float(v) for v in msg.get('vector', [0]*6)]
        speed  = float(msg.get('speed', 0))
        ref    = int(msg.get('ref', 0))
        await asyncio.to_thread(_bridge.call_jog_multi, vector, speed, ref)

    elif cmd == "set_robot_mode":
        mode   = int(msg.get('mode', 1))
        result = await asyncio.to_thread(_bridge.call_set_robot_mode, mode)
        label  = '직접교시(MANUAL)' if mode == 0 else 'AUTONOMOUS'
        level  = 'INFO' if result['success'] else 'ERROR'
        msg_text = f"로봇 모드 변경: {label}" if result['success'] else result['message']
        await ws.send_text(json.dumps({"type": "log", "level": level, "message": msg_text}))

    elif cmd == "calibrate_z":
        result = await asyncio.to_thread(_bridge.call_service, 'calibrate_z', 30.0)
        if result['success']:
            try:
                z_data = json.loads(result['message'])
                await ws.send_text(json.dumps({"type": "calibrate_z_result", **z_data}))
            except Exception:
                await ws.send_text(json.dumps({"type": "error", "message": "Z 측정 결과 파싱 실패"}))
        else:
            await ws.send_text(json.dumps({"type": "error", "message": result['message']}))

    # ── DB 직접 조회 (robot_art_node 불필요)
    elif cmd == "get_jobs":
        page  = int(msg.get("page", 1))
        limit = int(msg.get("limit", 20))
        result = db.get_jobs(page, limit)
        await ws.send_text(json.dumps({"type": "jobs", **result}))

    elif cmd == "get_logs":
        limit  = int(msg.get("limit", 100))
        job_id = msg.get("jobId")
        logs   = db.get_logs(limit, job_id)
        await ws.send_text(json.dumps({"type": "logs", "logs": logs}))

    elif cmd == "get_calibration":
        calib = db.get_active_calibration() or {}
        await ws.send_text(json.dumps({"type": "calibration", "data": calib}))

    elif cmd == "save_calibration":
        calib_id = db.save_calibration(data)
        db.add_log(f"캘리브레이션 저장 (id={calib_id})")
        await ws.send_text(json.dumps({
            "type": "log", "level": "INFO",
            "message": f"캘리브레이션 저장 완료 (id={calib_id})",
        }))

    elif cmd == "get_calibration_history":
        history = db.get_calibration_history()
        await ws.send_text(json.dumps({"type": "calibration_history", "data": history}))

    elif cmd == "get_settings":
        settings = db.get_settings()
        await ws.send_text(json.dumps({"type": "settings", "data": settings}))

    elif cmd == "save_settings":
        for key, value in data.items():
            db.set_setting(key, value)
        db.add_log("설정 저장")
        await ws.send_text(json.dumps({"type": "log", "level": "INFO", "message": "설정 저장 완료"}))

    elif cmd == "get_status":
        robot = _current_robot_state()
        if _last_status:
            status_data = {**_last_status, "type": "status", "nodeOnline": _node_online(), "robot": robot}
        else:
            status_data = {"type": "status", "nodeOnline": False, "message": "robot_art_node 미연결"}
        await ws.send_text(json.dumps(status_data))

    else:
        await ws.send_text(json.dumps({"type": "error", "message": f"알 수 없는 명령: {cmd}"}))


# ── WebSocket 엔드포인트 ────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    log.info(f"HMI 연결: {ws.client}")

    robot = _current_robot_state()
    robot_conn = {
        "ip"      : robot.get("robotIp", ""),
        "port"    : robot.get("robotPort", 0),
        "protocol": "ROS2",
    } if robot.get("ros2") else None
    await ws.send_text(json.dumps({
        "type"     : "connected",
        "message"  : "Robot Art Bridge 연결 완료",
        "robot"    : robot,
        "robotConn": robot_conn,
    }))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                parsed = json.loads(raw)
                await handle_command(ws, parsed)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "message": "잘못된 JSON 형식"}))
            except Exception as e:
                log.exception(f"명령 처리 오류: {e}")
                await ws.send_text(json.dumps({"type": "error", "message": str(e)}))

    except WebSocketDisconnect:
        log.info(f"HMI 연결 해제: {ws.client}")
    finally:
        _clients.discard(ws)


# ── HTTP ────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    status = _last_status.get("robot", {}).get("status", "unknown")
    return {"status": "ok", "robot": status}


@app.get("/jobs")
async def get_jobs(page: int = 1, limit: int = 20):
    return db.get_jobs(page, limit)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=WS_HOST, port=WS_PORT, reload=False)
