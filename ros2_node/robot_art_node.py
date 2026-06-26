#!/usr/bin/env python3
"""
robot_art_node.py — 로봇 드로잉 전용 ROS2 노드

실행:
  source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash
  python3 ros2_node/robot_art_node.py

제공 서비스:
  /robot_art/start          (std_srvs/Trigger)
  /robot_art/stop           (std_srvs/Trigger)
  /robot_art/estop          (std_srvs/Trigger)
  /robot_art/release_estop  (std_srvs/Trigger)
  /robot_art/home           (std_srvs/Trigger)

발행 토픽:
  /robot_art/status  (std_msgs/String, JSON)  — 상태 0.2초 주기
  /robot_art/log     (std_msgs/String, JSON)  — 드로잉 로그

구독 토픽:
  /robot_art/pixels  (std_msgs/String, JSON)  — 픽셀 데이터 수신
"""

import sys
import os
import json
import threading
import logging

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import String
from std_srvs.srv import Trigger

# backend 경로 추가
_BACKEND = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, _BACKEND)

from config import STATUS_INTERVAL_SEC
from database import Database
from robot_controller import RobotController
from drawing_engine import DrawingEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('robot_art_node')


class RobotArtNode(Node):

    def __init__(self):
        super().__init__('robot_art_node')

        # 핵심 객체
        self.db     = Database()
        self.robot  = RobotController()
        self.engine = DrawingEngine(self.robot, self.db)

        # 엔진 콜백 → ROS2 토픽 발행
        self.engine.on_progress = self._pub_progress
        self.engine.on_log      = self._pub_log

        # ── 퍼블리셔 ───────────────────────────────────────────
        self.status_pub = self.create_publisher(String, '/robot_art/status', 10)
        self.log_pub    = self.create_publisher(String, '/robot_art/log',    10)

        # ── 구독자 ─────────────────────────────────────────────
        self._pending: dict = {}
        self._pending_lock = threading.Lock()
        self.create_subscription(String, '/robot_art/pixels', self._on_pixels, 10)

        # ── 서비스 ─────────────────────────────────────────────
        self.create_service(Trigger, '/robot_art/start',          self._svc_start)
        self.create_service(Trigger, '/robot_art/stop',           self._svc_stop)
        self.create_service(Trigger, '/robot_art/pause',          self._svc_pause)
        self.create_service(Trigger, '/robot_art/resume',         self._svc_resume)
        self.create_service(Trigger, '/robot_art/estop',          self._svc_estop)
        self.create_service(Trigger, '/robot_art/release_estop',  self._svc_release_estop)
        self.create_service(Trigger, '/robot_art/home',           self._svc_home)
        self.create_service(Trigger, '/robot_art/gripper_open',   self._svc_gripper_open)
        self.create_service(Trigger, '/robot_art/gripper_close',  self._svc_gripper_close)
        self.create_service(Trigger, '/robot_art/pencil_grip',    self._svc_pencil_grip)
        self.create_service(Trigger, '/robot_art/pencil_release', self._svc_pencil_release)
        self.create_service(Trigger, '/robot_art/calibrate_z',    self._svc_calibrate_z)
        self.create_service(Trigger, '/robot_art/frame_task',     self._svc_frame_task)
        self.create_service(Trigger, '/robot_art/confirm_retry',  self._svc_confirm_retry)

        # ── 상태 주기 발행 ──────────────────────────────────────
        self.create_timer(STATUS_INTERVAL_SEC, self._pub_status)

        # 초기화
        self.db.init()
        self.robot.connect()
        self.get_logger().info('RobotArt 노드 시작 — 서비스 대기 중')

    # ── 픽셀 수신 ────────────────────────────────────────────────
    def _on_pixels(self, msg: String):
        try:
            data = json.loads(msg.data)
            n = len(data.get('pixels', []))
            with self._pending_lock:
                self._pending = data
            self.get_logger().info(f'픽셀 수신: {n:,}개')
        except Exception as e:
            self.get_logger().error(f'픽셀 파싱 오류: {e}')

    # ── 서비스 핸들러 ────────────────────────────────────────────
    def _svc_start(self, req, res):
        with self._pending_lock:
            pixels     = self._pending.get('pixels', [])
            settings   = self._pending.get('settings', {})
            image_name = self._pending.get('imageName', 'image')
        if not pixels:
            res.success = False
            res.message = '픽셀 없음 — /robot_art/pixels 먼저 발행하세요'
            return res
        try:
            self.engine.start(pixels, settings, image_name)
            res.success = True
            res.message = f'그리기 시작: {len(pixels):,}픽셀'
        except Exception as e:
            res.success = False
            res.message = str(e)
        return res

    def _svc_stop(self, req, res):
        self.engine.stop()
        res.success = True
        res.message = '그리기 중단'
        return res

    def _svc_pause(self, req, res):
        self.engine.pause()
        res.success = True
        res.message = '일시정지'
        return res

    def _svc_resume(self, req, res):
        self.engine.resume()
        res.success = True
        res.message = '재개'
        return res

    def _svc_estop(self, req, res):
        self.engine.stop()
        threading.Thread(target=self.robot.emergency_stop, daemon=True).start()
        res.success = True
        res.message = 'E-STOP 활성화'
        return res

    def _svc_release_estop(self, req, res):
        self.robot.release_estop()
        res.success = True
        res.message = 'E-STOP 해제'
        return res

    def _svc_home(self, req, res):
        if self.engine.is_running():
            res.success = False
            res.message = '그리기 중에는 원점 복귀 불가'
            return res
        threading.Thread(target=self.robot.home, daemon=True).start()
        res.success = True
        res.message = '원점 복귀 시작'
        return res

    def _run_op(self, fn, *args):
        """개별 동작을 별도 스레드로 실행하고 robot status를 running/idle로 관리."""
        def _target():
            self.robot.set_status("running")
            try:
                fn(*args)
            finally:
                self.robot.set_status("idle")
        threading.Thread(target=_target, daemon=True).start()

    def _svc_gripper_open(self, req, res):
        self._run_op(self.robot.gripper_open)
        res.success = True
        res.message = '그리퍼 열기'
        return res

    def _svc_gripper_close(self, req, res):
        self._run_op(self.robot.gripper_close)
        res.success = True
        res.message = '그리퍼 닫기'
        return res

    def _svc_pencil_grip(self, req, res):
        if self.engine.is_running():
            res.success = False
            res.message = '그리기 중에는 연필 파지 불가'
            return res
        self._run_op(self.robot.pencil_grip)
        res.success = True
        res.message = '연필 파지 시작'
        return res

    def _svc_pencil_release(self, req, res):
        if self.engine.is_running():
            res.success = False
            res.message = '그리기 중에는 연필 반납 불가'
            return res
        self._run_op(self.robot.pencil_release)
        res.success = True
        res.message = '연필 반납 시작'
        return res

    def _svc_frame_task(self, req, res):
        if self.engine.is_running():
            res.success = False
            res.message = '그리기 중에는 액자 작업 불가'
            return res
        self._run_op(self.robot.run_frame_task)
        res.success = True
        res.message = '액자 작업 시작'
        return res

    def _svc_confirm_retry(self, req, res):
        self.robot.confirm()
        res.success = True
        res.message = '확인'
        return res

    def _svc_calibrate_z(self, req, res):
        if self.engine.is_running():
            res.success = False
            res.message = '그리기 중에는 Z 측정 불가'
            return res
        try:
            result   = self.robot.auto_calibrate_z()
            self.db.update_calibration_z(result['pen_up_z'], result['pen_down_z'])
            res.success = True
            res.message = json.dumps(result)
        except Exception as e:
            res.success = False
            res.message = str(e)
        return res

    # ── 발행 ────────────────────────────────────────────────────
    def _pub_status(self):
        data = {
            'type'           : 'status',
            'robot'          : self.robot.get_state(),
            'drawStatus'     : self.engine.status,
            'currentPixel'   : self.engine.current_pixel,
            'totalPixels'    : self.engine.total_pixels,
            'currentPenForce': self.engine.current_pen_force,
            'message'        : self.engine.message,
            'jobId'          : self.engine.job_id,
        }
        self._publish(self.status_pub, data)

    def _pub_progress(self, data: dict):
        self._publish(self.status_pub, data)

    def _pub_log(self, message: str, level: str):
        self._publish(self.log_pub, {'type': 'log', 'level': level, 'message': message})

    def _publish(self, pub, data: dict):
        msg = String()
        msg.data = json.dumps(data, ensure_ascii=False)
        pub.publish(msg)


def main():
    rclpy.init()
    node = RobotArtNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
