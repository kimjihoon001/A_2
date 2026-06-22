# ================================================================
# main.py — FastAPI WebSocket 서버
#
# 실행: uvicorn main:app --host 0.0.0.0 --port 8765 --reload
# HMI 연결: ws://[이 PC IP]:8765/ws
# ================================================================

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from config import WS_HOST, WS_PORT, STATUS_INTERVAL_SEC, DEFAULT_CALIBRATION
from database import Database
from robot_controller import RobotController
from drawing_engine import DrawingEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

# ── 싱글턴 객체 ─────────────────────────────────────────────────
db     = Database()
robot  = RobotController()
engine = DrawingEngine(robot, db)

# 연결된 HMI 클라이언트 목록 (멀티 클라이언트 지원)
_clients: set[WebSocket] = set()


async def broadcast(data: dict):
    """연결된 모든 HMI에 메시지 전송"""
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


# ── 드로잉 엔진 콜백 — 스레드 → asyncio 이벤트 루프 ────────────
def _on_draw_progress(data: dict):
    asyncio.run_coroutine_threadsafe(broadcast(data), _loop)

def _on_draw_log(msg: str, level: str):
    asyncio.run_coroutine_threadsafe(
        broadcast({"type": "log", "level": level, "message": msg}),
        _loop,
    )

engine.on_progress = _on_draw_progress
engine.on_log      = _on_draw_log

_loop: asyncio.AbstractEventLoop = None   # type: ignore


# ── 상태 주기적 전송 ─────────────────────────────────────────────
async def _status_broadcast_loop():
    while True:
        await asyncio.sleep(STATUS_INTERVAL_SEC)
        if not _clients:
            continue
        robot_st = robot.get_state()
        await broadcast({
            "type"          : "status",
            "robot"         : robot_st,
            "drawStatus"    : engine.status,
            "currentPixel"  : engine.current_pixel,
            "totalPixels"   : engine.total_pixels,
            "currentPenForce": engine.current_pen_force,
            "message"       : engine.message,
            "jobId"         : engine.job_id,
        })


# ── 앱 생명주기 ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop
    _loop = asyncio.get_event_loop()

    db.init()
    log.info("DB 초기화 완료")

    robot.connect()
    log.info(f"서버 시작 — ws://{WS_HOST}:{WS_PORT}/ws")

    asyncio.create_task(_status_broadcast_loop())

    yield

    robot.disconnect()
    log.info("서버 종료")


app = FastAPI(title="Robot Art Server", lifespan=lifespan)


# ── 명령 처리기 ─────────────────────────────────────────────────
async def handle_command(ws: WebSocket, msg: dict):
    cmd  = msg.get("cmd", "")
    data = msg.get("data", {})

    # ── 그리기 제어
    if cmd == "start_drawing":
        pixels     = msg.get("pixels", [])
        settings   = msg.get("settings", {})
        image_name = msg.get("imageName", "unknown")
        if not pixels:
            await ws.send_text(json.dumps({"type": "error", "message": "픽셀 데이터가 없습니다."}))
            return
        try:
            await asyncio.to_thread(engine.start, pixels, settings, image_name)
            await ws.send_text(json.dumps({
                "type": "log", "level": "INFO",
                "message": f"그리기 시작: {image_name} ({len(pixels):,}픽셀)",
            }))
        except RuntimeError as e:
            await ws.send_text(json.dumps({"type": "error", "message": str(e)}))

    elif cmd == "stop":
        engine.stop()
        db.add_log("그리기 중단 요청 (HMI)", "WARNING")
        await ws.send_text(json.dumps({"type": "log", "level": "WARNING", "message": "그리기 중단 요청"}))

    # ── 비상정지
    elif cmd == "estop":
        engine.stop()
        await asyncio.to_thread(robot.emergency_stop)
        db.add_log("E-STOP 활성화", "ERROR")
        await broadcast({"type": "log", "level": "ERROR", "message": "E-STOP 활성화"})

    elif cmd == "reset_estop":
        robot.release_estop()
        db.add_log("E-STOP 해제", "INFO")
        await broadcast({"type": "log", "level": "INFO", "message": "E-STOP 해제"})

    # ── 원점 복귀
    elif cmd == "home":
        if engine.is_running():
            await ws.send_text(json.dumps({"type": "error", "message": "그리기 중에는 원점 복귀 불가"}))
            return
        await asyncio.to_thread(robot.home)
        await broadcast({"type": "log", "level": "INFO", "message": "원점 복귀 완료"})

    # ── 그리퍼
    elif cmd == "gripper_open":
        force = float(msg.get("force", 20))
        await asyncio.to_thread(robot.gripper_open, force)
        await ws.send_text(json.dumps({"type": "log", "level": "INFO", "message": f"그리퍼 열기 ({force}N)"}))

    elif cmd == "gripper_close":
        force = float(msg.get("force", 20))
        await asyncio.to_thread(robot.gripper_close, force)
        await ws.send_text(json.dumps({"type": "log", "level": "INFO", "message": f"그리퍼 닫기 ({force}N)"}))

    # ── 작업 이력 조회
    elif cmd == "get_jobs":
        page  = int(msg.get("page", 1))
        limit = int(msg.get("limit", 20))
        result = db.get_jobs(page, limit)
        await ws.send_text(json.dumps({"type": "jobs", **result}))

    # ── 로그 조회
    elif cmd == "get_logs":
        limit  = int(msg.get("limit", 100))
        job_id = msg.get("jobId")
        logs   = db.get_logs(limit, job_id)
        await ws.send_text(json.dumps({"type": "logs", "logs": logs}))

    # ── 캘리브레이션
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

    # ── 설정
    elif cmd == "get_settings":
        settings = db.get_settings()
        await ws.send_text(json.dumps({"type": "settings", "data": settings}))

    elif cmd == "save_settings":
        for key, value in data.items():
            db.set_setting(key, value)
        db.add_log("설정 저장")
        await ws.send_text(json.dumps({"type": "log", "level": "INFO", "message": "설정 저장 완료"}))

    # ── 현재 상태 즉시 조회
    elif cmd == "get_status":
        robot_st = robot.get_state()
        await ws.send_text(json.dumps({
            "type"           : "status",
            "robot"          : robot_st,
            "drawStatus"     : engine.status,
            "currentPixel"   : engine.current_pixel,
            "totalPixels"    : engine.total_pixels,
            "currentPenForce": engine.current_pen_force,
            "message"        : engine.message,
            "jobId"          : engine.job_id,
        }))

    else:
        await ws.send_text(json.dumps({"type": "error", "message": f"알 수 없는 명령: {cmd}"}))


# ── WebSocket 엔드포인트 ────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    client = ws.client
    log.info(f"HMI 연결: {client}")

    # 연결 즉시 현재 상태 + 로봇 연결 정보 전송
    await ws.send_text(json.dumps({
        "type"      : "connected",
        "message"   : "Robot Art Server 연결 완료",
        "robot"     : robot.get_state(),
        "robotConn" : {
            "ip"      : robot.robot_ip,
            "port"    : robot.robot_port,
            "protocol": "ROS2" if robot.get_state().get("ros2") else "Simulation",
        },
    }))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                await handle_command(ws, msg)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "message": "잘못된 JSON 형식"}))
            except Exception as e:
                log.exception(f"명령 처리 오류: {e}")
                await ws.send_text(json.dumps({"type": "error", "message": str(e)}))

    except WebSocketDisconnect:
        log.info(f"HMI 연결 해제: {client}")
    finally:
        _clients.discard(ws)


# ── HTTP 헬스체크 ────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "robot": robot.get_state()["status"]}


@app.get("/jobs")
async def get_jobs(page: int = 1, limit: int = 20):
    return db.get_jobs(page, limit)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=WS_HOST, port=WS_PORT, reload=False)
