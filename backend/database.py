
# ================================================================
# database.py — SQLite 데이터베이스
# ================================================================

import sqlite3
import json
from datetime import datetime
from typing import Any
from config import DB_PATH


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row   # dict처럼 접근 가능
        return conn

    # ── 초기화 ──────────────────────────────────────────────────
    def init(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_name       TEXT    NOT NULL,
                    frame_size       TEXT,
                    paper_type       TEXT,
                    res_label        TEXT,
                    res_width        INTEGER,
                    res_height       INTEGER,
                    total_pixels     INTEGER,
                    completed_pixels INTEGER DEFAULT 0,
                    pen_force_min    REAL,
                    pen_force_max    REAL,
                    dry_run          INTEGER DEFAULT 0,
                    status           TEXT    DEFAULT 'pending',
                    started_at       TEXT,
                    ended_at         TEXT,
                    duration_sec     REAL,
                    notes            TEXT
                );

                CREATE TABLE IF NOT EXISTS logs (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp  TEXT    DEFAULT (datetime('now','localtime')),
                    level      TEXT    DEFAULT 'INFO',
                    message    TEXT    NOT NULL,
                    job_id     INTEGER REFERENCES jobs(id)
                );

                CREATE TABLE IF NOT EXISTS calibration (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    name              TEXT    DEFAULT 'default',
                    origin_x          REAL,
                    origin_y          REAL,
                    origin_z          REAL,
                    pen_down_z        REAL,
                    pixel_spacing_mm  REAL,
                    canvas_width_mm   REAL,
                    canvas_height_mm  REAL,
                    center_x          REAL,
                    center_y          REAL,
                    is_active         INTEGER DEFAULT 0,
                    created_at        TEXT    DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    description TEXT,
                    updated_at  TEXT DEFAULT (datetime('now','localtime'))
                );
            """)
        self._seed_settings()
        self._seed_calibration()

    # 드로잉 작업 기준 안전 한계값 (M0609 스펙 최대 1500mm/s 이지만 드로잉용으로 제한)
    _LIMITS: dict = {
        'move_speed':            (10,   500),
        'dot_hold_ms':           (50,  2000),
        'log_retention_days':    (1,    365),
        'skip_threshold':        (0,    255),
        'gripper_default_force': (1,    120),
    }

    def _seed_settings(self):
        """기본 설정값이 없으면 삽입"""
        defaults = [
            ("move_speed",           "200",  "픽셀 간 이동 속도 (mm/s) · 한계 10~500"),
            ("dot_hold_ms",          "150",  "펜 접촉 유지 시간 (ms) · 한계 50~2000"),
            ("log_retention_days",   "30",   "로그 보관 기간 (일) · 한계 1~365"),
            ("skip_threshold",       "245",  "스킵할 그레이값 상한 (0~255)"),
            ("gripper_default_force","20",   "그리퍼 기본 파지력 (N)"),
            ("robot_ip",             "192.168.1.100", "M0609 IP 주소"),
        ]
        with self._conn() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO settings (key, value, description) VALUES (?,?,?)",
                defaults
            )

    def _seed_calibration(self):
        with self._conn() as conn:
            exists = conn.execute("SELECT 1 FROM calibration WHERE is_active=1").fetchone()
            if exists:
                return
            conn.execute("""
                INSERT INTO calibration
                    (name, origin_x, origin_y, origin_z,
                     pen_down_z, pixel_spacing_mm,
                     canvas_width_mm, canvas_height_mm, is_active)
                VALUES ('default', 462.0, -16.0, 360.58, 359.58, 2.0, 210.0, 148.0, 1)
            """)

    # ── Jobs ────────────────────────────────────────────────────
    def create_job(self, data: dict) -> int:
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO jobs
                    (image_name, frame_size, paper_type, res_label,
                     res_width, res_height, total_pixels,
                     pen_force_min, pen_force_max, dry_run, status, started_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data.get("imageName", ""),
                data.get("frameSize", ""),
                data.get("paperType", ""),
                data.get("resLabel", ""),
                data.get("resWidth", 0),
                data.get("resHeight", 0),
                data.get("totalPixels", 0),
                data.get("penForceMin", 10),
                data.get("penForceMax", 50),
                1 if data.get("dryRun") else 0,
                "running",
                _now(),
            ))
            return cur.lastrowid

    def finish_job(self, job_id: int, status: str, completed: int, duration_sec: float):
        with self._conn() as conn:
            conn.execute("""
                UPDATE jobs
                SET status=?, completed_pixels=?, ended_at=?, duration_sec=?
                WHERE id=?
            """, (status, completed, _now(), round(duration_sec, 2), job_id))

    def get_jobs(self, page: int = 1, limit: int = 20) -> dict:
        offset = (page - 1) * limit
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            rows  = conn.execute(
                "SELECT * FROM jobs ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return {"total": total, "page": page, "limit": limit,
                "jobs": [dict(r) for r in rows]}

    def get_job(self, job_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    # ── Logs ────────────────────────────────────────────────────
    def add_log(self, message: str, level: str = "INFO", job_id: int | None = None):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO logs (level, message, job_id) VALUES (?,?,?)",
                (level, message, job_id)
            )

    def get_logs(self, limit: int = 100, job_id: int | None = None) -> list[dict]:
        with self._conn() as conn:
            if job_id:
                rows = conn.execute(
                    "SELECT * FROM logs WHERE job_id=? ORDER BY id DESC LIMIT ?",
                    (job_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(r) for r in rows]

    # ── Calibration ─────────────────────────────────────────────
    def save_calibration(self, data: dict) -> int:
        with self._conn() as conn:
            # 기존 활성 캘리브레이션 비활성화
            conn.execute("UPDATE calibration SET is_active=0")
            cur = conn.execute("""
                INSERT INTO calibration
                    (name, origin_x, origin_y, origin_z,
                     pen_down_z, pixel_spacing_mm,
                     canvas_width_mm, canvas_height_mm, is_active)
                VALUES (?,?,?,?,?,?,?,?,1)
            """, (
                data.get("name", "default"),
                data.get("origin_x"), data.get("origin_y"), data.get("origin_z"),
                data.get("pen_down_z"), data.get("pixel_spacing_mm"),
                data.get("canvas_width_mm"), data.get("canvas_height_mm"),
            ))
            return cur.lastrowid

    def update_calibration_z(self, pen_up_z: float, pen_down_z: float):
        """활성 캘리브레이션의 Z값만 현재 레코드에 업데이트."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE calibration SET origin_z=?, pen_down_z=? WHERE is_active=1",
                (pen_up_z, pen_down_z),
            )

    def get_active_calibration(self) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM calibration WHERE is_active=1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def get_calibration_history(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM calibration ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Settings ────────────────────────────────────────────────
    def get_settings(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute("SELECT key, value, description FROM settings").fetchall()
        return {r["key"]: {"value": r["value"], "description": r["description"]} for r in rows}

    def set_setting(self, key: str, value: Any):
        if key in self._LIMITS:
            lo, hi = self._LIMITS[key]
            value = max(lo, min(hi, float(value)))
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, datetime('now','localtime'))
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """, (key, str(value)))

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default
