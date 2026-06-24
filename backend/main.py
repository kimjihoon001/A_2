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
from dsr_msgs2.srv import ServoOff, SetRobotControl
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from config import WS_HOST, WS_PORT, STATUS_INTERVAL_SEC, DEFAULT_CALIBRATION
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
            for name in ('start', 'stop', 'home',
                         'gripper_open', 'gripper_close', 'calibrate_z')
        }

        # DSR 직접 서비스 클라이언트 (estop/release)
        self._servo_off_client = self.create_client(ServoOff,         '/dsr01/system/servo_off')
        self._servo_on_client  = self.create_client(SetRobotControl,  '/dsr01/system/set_robot_control')

        # 상태/로그 구독 (robot_art_node →)
        self.create_subscription(String, '/robot_art/status', self._on_status, 10)
        self.create_subscription(String, '/robot_art/log',    self._on_log,    10)

    # ── 픽셀 전송 ───────────────────────────────────────────────
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
        done = threading.Event()
        result_box: list = [None]
        req = SetRobotControl.Request()
        req.robot_control = 3  # CONTROL_RESET_SAFET_OFF → STATE_STANDBY
        future = self._servo_on_client.call_async(req)
        future.add_done_callback(lambda f: (result_box.__setitem__(0, f.result()), done.set()))
        if not done.wait(timeout=timeout):
            return {'success': False, 'message': 'set_robot_control 응답 타임아웃'}
        return {'success': result_box[0].success, 'message': 'E-STOP 해제'}

    # ── 구독 콜백 ──────────────────────────────────────────────
    def _on_status(self, msg: String):
        global _last_status, _last_status_time
        try:
            data = json.loads(msg.data)
            _last_status = data
            _last_status_time = time.time()
            if _loop:
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
    """최신 robot 상태 반환. node 오프라인이면 ros2/connected를 False로 override."""
    robot = _last_status.get("robot", {}) if _last_status else {}
    if not _node_online():
        robot = {**robot, "ros2": False, "connected": False, "powered": False}
    return robot


# ── 브리지 스레드 (SingleThreadedExecutor) ───────────────────────
def _ros_spin():
    from rclpy.executors import SingleThreadedExecutor
    executor = SingleThreadedExecutor()
    executor.add_node(_bridge)
    try:
        executor.spin()
    except Exception:
        pass


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

    elif cmd == "stop":
        result = await asyncio.to_thread(_bridge.call_service, 'stop')
        db.add_log("그리기 중단 요청 (HMI)", "WARNING")
        await ws.send_text(json.dumps({"type": "log", "level": "WARNING", "message": result['message']}))

    elif cmd == "estop":
        result = await asyncio.to_thread(_bridge.call_estop)
        db.add_log("E-STOP 활성화", "ERROR")
        await broadcast({"type": "log", "level": "ERROR", "message": result['message']})

    elif cmd == "reset_estop":
        result = await asyncio.to_thread(_bridge.call_release_estop)
        db.add_log("E-STOP 해제", "INFO")
        await broadcast({"type": "log", "level": "INFO", "message": result['message']})

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

    elif cmd == "calibrate_z":
        result = await asyncio.to_thread(_bridge.call_service, 'calibrate_z', 10.0)
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
        calib = db.get_active_calibration() or DEFAULT_CALIBRATION
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
