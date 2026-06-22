# ================================================================
# drawing_engine.py — 픽셀 → 로봇 경로 변환 + 드로잉 실행
# ================================================================

import time
import threading
import logging
from typing import Callable
from config import (MOVE_SPEED, DRAW_SPEED,
                    DEFAULT_CALIBRATION,
                    READY_JOINTS, READY_VEL, READY_ACC)
from robot_controller import RobotController
from database import Database

log = logging.getLogger(__name__)


def _gray_to_force(gray: int) -> float | None:
    """
    계단식 회색값 → 힘 매핑 (10 N ~ 3 N, 4단계).
    0~50   → 10 N  (검정)
    51~100 →  7 N
    101~150→  5 N
    151~200→  3 N  (연회색)
    201~255→ None  (스킵)
    """
    if   gray <=  50: return 10.0
    elif gray <= 100: return  7.0
    elif gray <= 150: return  5.0
    elif gray <= 200: return  3.0
    else:             return  None


def _build_path(pixels: list[dict], calibration: dict,
                settings: dict | None = None) -> list[dict]:
    """
    픽셀 리스트를 뱀 패턴(S자) 로봇 경로로 변환.
    settings에 centerX/centerY/frameWidth/frameHeight/resWidth/resHeight가 있으면
    중심 좌표 기준으로 경로 계산. 없으면 calibration의 origin 사용.
    """
    if not pixels:
        return []

    width  = max(p["x"] for p in pixels) + 1
    height = max(p["y"] for p in pixels) + 1

    grid: dict[tuple, int] = {(p["x"], p["y"]): p["gray"] for p in pixels}

    z_up = float(calibration.get("origin_z") or 270.80)
    z_dn = float(calibration.get("pen_down_z") or 265.80)

    # 중심 좌표 방식 vs 원점+간격 방식
    use_origin = (
        settings and
        "originX" in settings and "originY" in settings and
        settings.get("frameWidth") and settings.get("frameHeight") and
        settings.get("resWidth")   and settings.get("resHeight")
    )

    if use_origin:
        ox          = float(settings["originX"])
        oy          = float(settings["originY"])
        mm_per_px_x = float(settings["frameWidth"])  / float(settings["resWidth"])
        mm_per_px_y = float(settings["frameHeight"]) / float(settings["resHeight"])
    else:
        ox = float(calibration.get("origin_x") or 436.80)
        oy = float(calibration.get("origin_y") or 157.38)
        mm_per_px_x = float(calibration.get("pixel_spacing_mm") or 4.0)
        mm_per_px_y = mm_per_px_x

    path = []
    for y in range(height):
        x_range = range(width) if y % 2 == 0 else range(width - 1, -1, -1)
        for x in x_range:
            gray = grid.get((x, y), 255)
            if _gray_to_force(gray) is None:
                continue
            rx = ox + x * mm_per_px_x
            ry = oy + y * mm_per_px_y
            path.append({
                "rx"  : rx,
                "ry"  : ry,
                "z_up": z_up,
                "z_dn": z_dn,
                "gray": gray,
                "px"  : x,
                "py"  : y,
            })
    return path


class DrawingEngine:
    """
    그리기 작업을 별도 스레드에서 실행하고
    진행 상황을 콜백으로 보고.
    """

    def __init__(self, robot: RobotController, db: Database):
        self.robot    = robot
        self.db       = db
        self._thread  : threading.Thread | None = None
        self._stop_evt: threading.Event = threading.Event()

        # 진행 상태 (메인 스레드에서 읽힘)
        self.status          = "idle"
        self.current_pixel   = 0
        self.total_pixels    = 0
        self.current_pen_force = 0.0
        self.message         = "대기 중"
        self.job_id          : int | None = None
        self._start_time     : float = 0.0

        # HMI에 상태 전송하는 콜백 (main.py에서 주입)
        self.on_progress: Callable[[dict], None] | None = None
        self.on_log     : Callable[[str, str], None] | None = None

    def _emit_log(self, msg: str, level: str = "INFO"):
        log.info(f"[{level}] {msg}")
        self.db.add_log(msg, level, self.job_id)
        if self.on_log:
            self.on_log(msg, level)

    def _emit_progress(self):
        if self.on_progress:
            self.on_progress({
                "type"          : "draw_progress",
                "drawStatus"    : self.status,
                "currentPixel"  : self.current_pixel,
                "totalPixels"   : self.total_pixels,
                "currentPenForce": round(self.current_pen_force, 2),
                "message"       : self.message,
                "jobId"         : self.job_id,
            })

    def start(self, pixels: list[dict], settings: dict, image_name: str):
        if self._thread and self._thread.is_alive():
            raise RuntimeError("이미 그리기 작업이 진행 중입니다.")

        self._stop_evt.clear()

        # DB에 작업 기록 생성
        self.job_id = self.db.create_job({
            "imageName"  : image_name,
            "frameSize"  : settings.get("frameSize", ""),
            "paperType"  : settings.get("paperType", ""),
            "resLabel"   : settings.get("resLabel", ""),
            "resWidth"   : settings.get("resWidth", 0),
            "resHeight"  : settings.get("resHeight", 0),
            "totalPixels": len(pixels),
            "penForceMin": settings.get("penForceMin", 10),
            "penForceMax": settings.get("penForceMax", 50),
            "dryRun"     : settings.get("dryRun", False),
        })

        self._thread = threading.Thread(
            target=self._run,
            args=(pixels, settings),
            daemon=True,
            name="DrawingThread",
        )
        self._thread.start()

    def stop(self):
        """외부에서 그리기 중단 요청"""
        self._stop_evt.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── 실제 드로잉 실행 (별도 스레드) ─────────────────────────
    def _run(self, pixels: list[dict], settings: dict):
        self._start_time = time.time()
        calib = self.db.get_active_calibration() or DEFAULT_CALIBRATION

        dry_run = bool(settings.get("dryRun", False))

        # 경로 생성 (gray 201~255는 _gray_to_force에서 None → 스킵)
        path = _build_path(pixels, calib, settings=settings)

        self.status        = "running"
        self.total_pixels  = len(path)
        self.current_pixel = 0
        self.message       = f"그리기 시작 — {self.total_pixels:,} 픽셀"
        self.robot.set_status("running")
        self._emit_log(f"그리기 시작: {len(pixels):,}px 입력 → {self.total_pixels:,}px 경로")
        if dry_run:
            self._emit_log("건식 실행 모드 — 실제 이동 없음", "WARNING")

        try:
            if not dry_run and path:
                # 준비 자세로 이동 (특이점 회피)
                self._emit_log("준비 자세로 이동 중...")
                self.robot.movej(READY_JOINTS, vel=READY_VEL, acc=READY_ACC)
                self._emit_log("준비 자세 완료")

            for i, step in enumerate(path):
                # 중단 요청 확인
                if self._stop_evt.is_set():
                    self._finish("cancelled", i)
                    return

                force = _gray_to_force(step["gray"])
                if force is None:
                    self.current_pixel = i + 1
                    continue
                self.current_pen_force = force

                if not dry_run:
                    self.robot.draw_pixel(step["rx"], step["ry"], force,
                                          step["z_up"], step["z_dn"])
                    if self._stop_evt.is_set():
                        self._finish("cancelled", i)
                        return


                self.current_pixel = i + 1
                self.message = f"그리는 중... {self.current_pixel:,} / {self.total_pixels:,} 픽셀"

                # 100픽셀마다 로그
                if (i + 1) % 100 == 0:
                    pct = (i + 1) / self.total_pixels * 100
                    elapsed = time.time() - self._start_time
                    self._emit_log(f"{pct:.1f}% 완료 ({elapsed:.0f}s 경과)")

                self._emit_progress()

            self._finish("success", len(path))

        except Exception as e:
            import traceback
            self._emit_log(f"드로잉 오류: {e}\n{traceback.format_exc()}", "ERROR")
            self._finish("failed", self.current_pixel)

    def _finish(self, final_status: str, completed: int):
        duration = time.time() - self._start_time
        self.status  = final_status
        self.message = {
            "success"  : f"완료! {completed:,}픽셀 인쇄 성공 ({duration:.1f}s)",
            "failed"   : f"실패: {completed:,}픽셀 완료 후 오류 발생",
            "cancelled": f"취소됨: {completed:,}픽셀 완료",
        }.get(final_status, "완료")

        self.db.finish_job(self.job_id, final_status, completed, duration)
        self.robot.set_status("idle")
        self._emit_log(f"작업 {final_status}: {completed:,}픽셀 / {duration:.1f}s")
        self._emit_progress()
