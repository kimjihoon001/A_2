# ================================================================
# drawing_engine.py — 픽셀 → 로봇 경로 변환 + 드로잉 실행
# ================================================================

import time
import threading
import logging
from typing import Callable
from config import (READY_JOINTS, READY_VEL, READY_ACC)
from robot_controller import RobotController
from database import Database

log = logging.getLogger(__name__)


def _gray_to_force(gray: int, force_min: float = 3.0, force_max: float = 5.0) -> float | None:
    """4구간 계단식: gray<=50→max, <=100→2/3, <=150→1/3, <=200→min, >200→스킵"""
    if   gray <=  50: return force_max
    elif gray <= 100: return round(force_min + (force_max - force_min) * 2 / 3, 2)
    elif gray <= 150: return round(force_min + (force_max - force_min) * 1 / 3, 2)
    elif gray <= 200: return force_min
    else:             return None


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

    # 액자 안쪽 여백: 캘리브레이션은 액자 꼭짓점(우하단), 실제 그림은 여백만큼 안쪽
    FRAME_MARGIN_X = 51.5    # 로봇 X방향 여백 (mm)
    FRAME_MARGIN_Y = 20.5   # 로봇 Y방향 여백 (mm)

    z_up = float(calibration["origin_z"])
    z_dn = float(calibration["pen_down_z"])
    ox   = float(calibration["origin_x"]) + FRAME_MARGIN_X
    oy   = float(calibration["origin_y"]) + FRAME_MARGIN_Y
    mm_per_px_x = 1.67
    mm_per_px_y = 1.67

    force_min = float(settings.get("penForceMin", 3.0)) if settings else 3.0
    force_max = float(settings.get("penForceMax", 5.0)) if settings else 5.0

    # 픽셀 그리드 전체 우하단(width-1, height-1)을 원점(ox, oy)에 고정 정렬
    # max_x/max_y(어두운 픽셀 bounding box)를 쓰면 좌상단이 흰색일 때 원점이 달라짐
    has_dark = any(_gray_to_force(p["gray"], force_min, force_max) is not None for p in pixels)
    if not has_dark:
        return []

    path = []
    for y in range(height):
        x_range = range(width) if y % 2 == 0 else range(width - 1, -1, -1)
        for x in x_range:
            gray = grid.get((x, y), 255)
            if _gray_to_force(gray, force_min, force_max) is None:
                continue
            rx = ox + (height - 1 - y) * mm_per_px_y
            ry = oy + (width  - 1 - x) * mm_per_px_x
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
        self.robot.on_confirm_request = self._on_robot_confirm_request
        self.robot.on_step_change     = self._on_robot_step_change
        self._thread  : threading.Thread | None = None
        self._stop_evt: threading.Event = threading.Event()
        self._pause_evt: threading.Event = threading.Event()
        self._pause_evt.set()  # set = 실행 중, clear = 일시정지

        # 진행 상태 (메인 스레드에서 읽힘)
        self.status          = "idle"
        self.current_step    = ""
        self.current_pixel   = 0
        self.total_pixels    = 0
        self.current_pen_force = 0.0
        self.message         = "대기 중"
        self.job_id          : int | None = None
        self._start_time     : float = 0.0

        # HMI에 상태 전송하는 콜백 (main.py에서 주입)
        self.on_progress: Callable[[dict], None] | None = None
        self.on_log     : Callable[[str, str], None] | None = None

    def _on_robot_confirm_request(self, message: str):
        if self.on_progress:
            self.on_progress({"type": "confirm_request", "message": message})

    def _on_robot_step_change(self, step: str):
        self.current_step = step
        self.message = step
        self._emit_progress()

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
                "currentStep"   : self.current_step,
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
        self.current_step = ""
        self.robot._abort = False
        self.robot._motion_pause_evt.set()

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
        self._stop_evt.set()
        self._pause_evt.set()  # 일시정지 상태에서도 stop 감지되도록
        self.robot.abort()     # DSR move_stop + _abort 플래그

    def pause(self):
        self.robot.pause_motion()  # 그림·개별동작 모두 정지
        if self.status == 'running':
            self._pause_evt.clear()
            self.status = 'paused'
            self.message = '일시정지'
            self._emit_progress()

    def resume(self):
        self.robot.resume_motion()  # 그림·개별동작 모두 재개
        if self.status == 'paused':
            self.status = 'running'
            self.message = '재개 중...'
            self._emit_progress()
            self._pause_evt.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── 실제 드로잉 실행 (별도 스레드) ─────────────────────────
    def _run(self, pixels: list[dict], settings: dict):
        self._start_time = time.time()
        calib   = self.db.get_active_calibration()
        if calib is None:
            raise RuntimeError("활성 캘리브레이션 없음 — 캘리브레이션 탭에서 저장하세요")
        self.robot.load_config()
        dry_run = bool(settings.get("dryRun", False))

        force_min = float(self.db.get_setting("pen_force_min") or 3.0)
        force_max = float(self.db.get_setting("pen_force_max") or 8.0)
        settings  = {**settings, "penForceMin": force_min, "penForceMax": force_max}

        path = _build_path(pixels, calib, settings=settings)

        self.status        = "running"
        self.total_pixels  = len(path)
        self.current_pixel = 0
        self.message       = f"그리기 시작 — {self.total_pixels:,} 픽셀"
        self.robot.set_status("running")
        self._emit_log(f"그리기 시작: {len(pixels):,}px 입력 → {self.total_pixels:,}px 경로")
        if dry_run:
            self._emit_log("건식 실행 모드 — 실제 이동 없음", "WARNING")
        else:
            try:
                # 펜 잡기 전 종이 확인
                self.current_step = "종이확인"
                self._emit_log("종이 확인 중...")
                while not self.robot.check_paper():
                    if self.robot._check_abort():
                        self._finish("cancelled", 0)
                        return
                    self._emit_log("종이 미감지", "WARNING")
                    if not self.robot.wait_for_confirm("종이를 그림판에 올려놓고 확인을 눌러주세요"):
                        self._finish("failed", 0)
                        return
                self._emit_log("종이 확인 완료")

                if self.robot._check_abort():
                    self._finish("cancelled", 0)
                    return

                self.current_step = "연필파지"
                self._emit_log("연필 파지 전 홈 복귀 중...")
                self.robot.home()
                if self.robot._check_abort():
                    self._finish("cancelled", 0)
                    return
                self._emit_log("연필 파지 중...")
                self.robot.pencil_grip()
                self._emit_log("연필 파지 완료")

                if self.robot._check_abort():
                    self._finish("cancelled", 0)
                    return

                if path:
                    first = path[0]
                    self.current_step = "그리기준비"
                    self._emit_log("첫 픽셀 위치로 이동 후 Z 자동 측정...")
                    travel_z = float(calib.get("travel_z") or (first["z_up"] + 10.0))
                    self.robot.move_to_xy(first["rx"], first["ry"], travel_z)
                    z_result = None
                    for attempt in range(3):
                        if self.robot._check_abort():
                            break
                        try:
                            z_result = self.robot.auto_calibrate_z()
                            break
                        except Exception as e:
                            self._emit_log(f"Z 측정 실패 ({attempt+1}/3): {e} — Y방향 힘 적용 후 재시도", "WARNING")
                            self.robot.nudge_y()
                    if z_result is None:
                        if self.robot._check_abort():
                            self._finish("cancelled", 0)
                        else:
                            self._emit_log("Z 측정 3회 실패 — 그리기 취소", "ERROR")
                            self._finish("failed", 0)
                        return
                    new_z_up = z_result["pen_up_z"]
                    new_z_dn = z_result["pen_down_z"]
                    self.db.update_calibration_z(new_z_up, new_z_dn)
                    for step in path:
                        step["z_up"] = new_z_up
                        step["z_dn"] = new_z_dn
                    self._emit_log(f"Z 측정 완료: pen_up={new_z_up}mm, pen_down={new_z_dn}mm")
            except Exception as e:
                import traceback
                self._emit_log(f"준비 단계 오류: {e}\n{traceback.format_exc()}", "ERROR")
                self._finish("failed", 0)
                return

        self.current_step = "그리기"
        try:
            for i, step in enumerate(path):
                # 중단 요청 확인 (강제정지 또는 E-STOP)
                if self._stop_evt.is_set() or self.robot._check_abort():
                    self._finish("cancelled", i)
                    return
                # 일시정지 대기
                self._pause_evt.wait()

                force = _gray_to_force(step["gray"],
                                       float(settings.get("penForceMin", 3.0)),
                                       float(settings.get("penForceMax", 5.0)))
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
        draw_duration = time.time() - self._start_time
        self.db.finish_job(self.job_id, final_status, completed, draw_duration)

        # ── 연필 반납 (status는 아직 'running' 유지 → pause 가능) ──
        if not self.robot._abort:
            self.current_step = "연필반납"
            self.message = "연필 반납 중..."
            self._emit_progress()
            try:
                self._emit_log("연필 반납 중...")
                self.robot.pencil_release()
                self._emit_log("연필 반납 완료")
            except Exception as e:
                self._emit_log(f"연필 반납 실패 (무시): {e}", "WARNING")
        else:
            self._emit_log("강제정지 — 연필 반납 생략")

        # ── 액자 조립 (성공 시만) ──────────────────────────────────
        if final_status == "success":
            try:
                self._emit_log("액자 조립 시작...")
                self.robot.set_status("running")
                self.robot.frame_assembly()  # on_step_change로 current_step 자동 갱신
                self._emit_log("액자 조립 완료")
            except Exception as e:
                self._emit_log(f"액자 조립 오류: {e}", "ERROR")

        # ── 최종 상태 전환 ────────────────────────────────────────
        self.status = final_status
        self.current_step = ""
        self.message = {
            "success"  : f"완료! {completed:,}픽셀 ({draw_duration:.1f}s)",
            "failed"   : f"실패: {completed:,}픽셀",
            "cancelled": f"취소됨: {completed:,}픽셀",
        }.get(final_status, "완료")
        self.robot.set_status("idle")
        self._emit_log(f"작업 {final_status}: {completed:,}픽셀 / {draw_duration:.1f}s")
        self._emit_progress()
