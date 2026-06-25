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


def _gray_to_force(gray: int) -> float | None:
    """
    회색값 → 힘 매핑 (모드별 분리).
    pixel(S자): 점 찍기 — 6/5.5/5/4 N
    contour(선 그리기): 6/5.5/5/4 N
    """
    if   gray <=  50: return 5.0
    elif gray <= 100: return 4.5
    elif gray <= 150: return 4.0
    elif gray <= 200: return 3.0
    else:             return None


def _build_contour_segments(pixels: list[dict], calibration: dict,
                            settings: dict | None = None) -> list[dict]:
    """
    Marching Squares로 등고선 추출 → 체인 연결 → 로봇 좌표 선분 리스트 반환.
    반환: [{'points': [(rx, ry), ...], 'force': float, 'z_up': float, 'z_dn': float}, ...]
    """
    from collections import defaultdict

    if not pixels:
        return []

    width  = max(p["x"] for p in pixels) + 1
    height = max(p["y"] for p in pixels) + 1
    grid = [[255] * width for _ in range(height)]
    for p in pixels:
        grid[p["y"]][p["x"]] = p["gray"]

    z_up = float(calibration["origin_z"])
    z_dn = float(calibration["pen_down_z"])
    ox   = float(calibration["origin_x"])
    oy   = float(calibration["origin_y"])
    if settings and settings.get("frameWidth") and settings.get("resWidth"):
        mm_x = float(settings["frameWidth"])  / float(settings["resWidth"])
        mm_y = float(settings["frameHeight"]) / float(settings["resHeight"])
    else:
        mm_x = float(calibration["pixel_spacing_mm"])
        mm_y = mm_x

    # 어두운 픽셀 bounding box 우하단 → 사용자 origin에 정렬
    dark_pts = [(p["x"], p["y"]) for p in pixels if p["gray"] <= 200]
    max_x_dark = max(d[0] for d in dark_pts) if dark_pts else width - 1
    max_y_dark = max(d[1] for d in dark_pts) if dark_pts else height - 1

    def to_robot(px: float, py: float) -> tuple[float, float]:
        return ox + (max_y_dark - py) * mm_y, oy + (max_x_dark - px) * mm_x

    # Marching Squares: TL=8, TR=4, BR=2, BL=1 (1 = gray < level = dark)
    MS_TABLE = {
        0:  [],
        1:  [('L', 'B')],
        2:  [('B', 'R')],
        3:  [('L', 'R')],
        4:  [('T', 'R')],
        5:  [('L', 'T'), ('B', 'R')],   # 안장점 → 두 선분
        6:  [('T', 'B')],
        7:  [('L', 'T')],
        8:  [('L', 'T')],
        9:  [('T', 'B')],
        10: [('T', 'R'), ('L', 'B')],   # 안장점 → 두 선분
        11: [('T', 'R')],
        12: [('L', 'R')],
        13: [('B', 'R')],
        14: [('L', 'B')],
        15: [],
    }

    def edge_pt(edge: str, cx: int, cy: int) -> tuple[float, float]:
        if edge == 'T': return cx + 0.5, float(cy)
        if edge == 'R': return float(cx + 1), cy + 0.5
        if edge == 'B': return cx + 0.5, float(cy + 1)
        return float(cx), cy + 0.5   # 'L'

    # (gray level, pen force) 쌍 — 어두울수록 강한 힘
    LEVELS = [(50, 10.0), (100, 7.0), (150, 5.0), (200, 3.0)]

    raw_segs: list[tuple[tuple, tuple, float]] = []  # (p1, p2, force)

    for level, force in LEVELS:
        for cy in range(height - 1):
            for cx in range(width - 1):
                tl = 1 if grid[cy][cx]       < level else 0
                tr = 1 if grid[cy][cx + 1]   < level else 0
                br = 1 if grid[cy + 1][cx + 1] < level else 0
                bl = 1 if grid[cy + 1][cx]   < level else 0
                case = tl * 8 + tr * 4 + br * 2 + bl
                for e1, e2 in MS_TABLE[case]:
                    raw_segs.append((edge_pt(e1, cx, cy), edge_pt(e2, cx, cy), force))

    if not raw_segs:
        return []

    # 끝점 → 인접 선분 색인 (체인 연결용)
    PREC = 2
    def key(pt: tuple) -> tuple:
        return round(pt[0] * PREC), round(pt[1] * PREC)

    adj: dict = defaultdict(list)
    for i, (p1, p2, _) in enumerate(raw_segs):
        adj[key(p1)].append((i, p2))
        adj[key(p2)].append((i, p1))

    used = [False] * len(raw_segs)
    result = []

    for start in range(len(raw_segs)):
        if used[start]:
            continue
        p1, p2, force = raw_segs[start]
        used[start] = True
        chain = [p1, p2]
        current = p2

        while True:
            nxt = None
            for seg_i, other in adj[key(current)]:
                if not used[seg_i]:
                    nxt = (seg_i, other)
                    break
            if nxt is None:
                break
            used[nxt[0]] = True
            chain.append(nxt[1])
            current = nxt[1]

        robot_pts = [to_robot(px, py) for px, py in chain]
        if len(robot_pts) >= 2:
            result.append({
                'points': robot_pts,
                'force' : force,
                'z_up'  : z_up,
                'z_dn'  : z_dn,
            })

    return result


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

    z_up = float(calibration["origin_z"])
    z_dn = float(calibration["pen_down_z"])
    ox   = float(calibration["origin_x"])
    oy   = float(calibration["origin_y"])
    if settings and settings.get("frameWidth") and settings.get("resWidth"):
        mm_per_px_x = float(settings["frameWidth"])  / float(settings["resWidth"])
        mm_per_px_y = float(settings["frameHeight"]) / float(settings["resHeight"])
    else:
        mm_per_px_x = float(calibration["pixel_spacing_mm"])
        mm_per_px_y = mm_per_px_x

    # 어두운 픽셀 bounding box 우하단 → 사용자 origin에 정렬
    dark = [(p["x"], p["y"]) for p in pixels if _gray_to_force(p["gray"]) is not None]
    if not dark:
        return []
    max_y = max(d[1] for d in dark)
    max_x = max(d[0] for d in dark)

    path = []
    for y in range(height):
        x_range = range(width) if y % 2 == 0 else range(width - 1, -1, -1)
        for x in x_range:
            gray = grid.get((x, y), 255)
            if _gray_to_force(gray) is None:
                continue
            # 우하단 기준 절대좌표: bottom→up = X+, right→left = Y+
            rx = ox + (max_y - y) * mm_per_px_y
            ry = oy + (max_x - x) * mm_per_px_x
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
        calib   = self.db.get_active_calibration()
        if calib is None:
            raise RuntimeError("활성 캘리브레이션 없음 — 캘리브레이션 탭에서 저장하세요")
        self.robot.load_config()
        dry_run = bool(settings.get("dryRun", False))

        if settings.get("drawMode") == "contour":
            self._run_contour(pixels, calib, settings, dry_run)
            return

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
            self._emit_log("연필 파지 중...")
            self.robot.pencil_grip()
            self._emit_log("연필 파지 완료")

            if path:
                first = path[0]
                self._emit_log("첫 픽셀 위치로 이동 후 Z 자동 측정...")
                self.robot.move_to_xy(first["rx"], first["ry"], first["z_up"])
                z_result = None
                for attempt in range(3):
                    try:
                        z_result = self.robot.auto_calibrate_z()
                        break
                    except Exception as e:
                        self._emit_log(f"Z 측정 실패 ({attempt+1}/3): {e} — Y방향 힘 적용 후 재시도", "WARNING")
                        self.robot.nudge_y()
                if z_result is None:
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

        try:
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

    def _run_contour(self, pixels: list[dict], calib: dict,
                     settings: dict, dry_run: bool):
        segments = _build_contour_segments(pixels, calib, settings=settings)

        self.status        = "running"
        self.total_pixels  = len(segments)
        self.current_pixel = 0
        self.message       = f"등고선 그리기 시작 — {self.total_pixels:,} 선분"
        self.robot.set_status("running")
        self._emit_log(f"등고선 시작: {len(segments):,}개 선분")
        if dry_run:
            self._emit_log("건식 실행 모드 — 실제 이동 없음", "WARNING")
        else:
            self._emit_log("연필 파지 중...")
            self.robot.pencil_grip()
            self._emit_log("연필 파지 완료")

        try:
            for i, seg in enumerate(segments):
                if self._stop_evt.is_set():
                    self._finish("cancelled", i)
                    return

                self.current_pen_force = seg['force']

                if not dry_run:
                    self.robot.draw_contour_segment(
                        seg['points'], seg['force'], seg['z_up'], seg['z_dn']
                    )
                    if self._stop_evt.is_set():
                        self._finish("cancelled", i)
                        return

                self.current_pixel = i + 1
                self.message = f"등고선 그리는 중... {self.current_pixel:,} / {self.total_pixels:,} 선분"

                if (i + 1) % 20 == 0:
                    pct     = (i + 1) / self.total_pixels * 100
                    elapsed = time.time() - self._start_time
                    self._emit_log(f"{pct:.1f}% 완료 ({elapsed:.0f}s 경과)")

                self._emit_progress()

            self._finish("success", len(segments))

        except Exception as e:
            import traceback
            self._emit_log(f"등고선 드로잉 오류: {e}\n{traceback.format_exc()}", "ERROR")
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
        try:
            self._emit_log("연필 반납 중...")
            self.robot.pencil_release()
            self._emit_log("연필 반납 완료")
        except Exception as e:
            self._emit_log(f"연필 반납 실패 (무시): {e}", "WARNING")

        if final_status == "success":
            try:
                self._emit_log("액자 조립 시작...")
                self.robot.set_status("running")
                self.robot.frame_assembly()
                self._emit_log("액자 조립 완료")
            except Exception as e:
                self._emit_log(f"액자 조립 오류: {e}", "ERROR")

        self.robot.set_status("idle")
        self._emit_log(f"작업 {final_status}: {completed:,}픽셀 / {duration:.1f}s")
        self._emit_progress()
