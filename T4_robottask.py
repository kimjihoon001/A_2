import time
import socket
import struct
import rclpy
import DR_init
# 로봇 기본 설정
ROBOT_ID = "dsr01"
ROBOT_MODEL = "m0609"

DR_init.__dsr__id = ROBOT_ID
DR_init.__dsr__model = ROBOT_MODEL

ON, OFF = 1, 0

def main(args=None):
    rclpy.init(args=args)
    node = rclpy.create_node("rokey_gear_assembly", namespace=ROBOT_ID)
    DR_init.__dsr__node = node

    # ROS 2 노드 바인딩 이후에 DSR_ROBOT2를 임포트해야 정상 작동합니다.
    try:
        from DSR_ROBOT2 import (
            set_digital_output,
            movel,
            movej,
            amovel,
            task_compliance_ctrl,
            set_desired_force,
            get_tool_force,
            get_current_posx,
            release_force,
            release_compliance_ctrl,
            check_force_condition,
            DR_MV_MOD_REL,
            DR_FC_MOD_REL,
            DR_AXIS_Z,
            DR_BASE,
            DR_TOOL,
        )
        from DR_common2 import posx, posj
    
    except ImportError as e:
        node.get_logger().error(f"Error importing DSR_ROBOT2 : {e}")
        return

    # ==========================================
    # 1. 헬퍼(Helper) 및 작업 단계별 주요 함수
    # ==========================================

    def get_gripper_width():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                # RG2 그리퍼의 IP와 Port (환경에 맞게 수정 필요)
                s.connect(('192.168.1.1', 502))
                req = struct.pack('>HHHBBHH', 1, 0, 6, 65, 0x03, 275, 1)
                s.sendall(req)
                resp = s.recv(256)
                if len(resp) >= 11:
                    return struct.unpack('>H', resp[9:11])[0] / 10.0
        except Exception as e:
            node.get_logger().error(f"그리퍼 너비 읽기 실패: {e}")
        return None

    def gripper_open():
        set_digital_output(1, ON)
        set_digital_output(2, OFF)

    def gripper_close(wait_time=2.5):
        set_digital_output(2, ON)
        set_digital_output(1, OFF)
        time.sleep(wait_time)

    # 액자 파지 코드
    def frame_lower_setup():
        node.get_logger().info("액자 하판 배치 시작")
        push_force = 20.0  # 액자 누름 힘 (N)

        # 액자 파지 위치
        pos_lowframe_start_hover = posj(-17.09, -4.66, 71.34, 179.97, -113.32, 72.06)
        pos_lowframe_start_hoverx = posx(291.95, -83.31, 569.94, 170.08, -180, 79.19)
        pos_lowframe_start = posx(291.95, -83.31, 352.89, 170.08, -180, 79.19)

        # 액자 하판 위치
        # pos_frame_lower0 = posj(30.37, 6.95, 95.37, 95.84, -119.58, -76.33)
        pos_frame_lower1 = posj(60.82, 29.56, 80.77, 120.95, -144.29, 126.52)
        pos_frame_lower2 = posx(269.77, 295.96, 74.64, 90.91, -89.97, -0.03)
        pos_frame_lower3 = posx(269.77, 345.96, 74.64, 90.91, -89.97, -0.03)
        pos_frame_lower4 = posx(269.77, 345.96, 174.64, 90.91, -89.97, -0.03)

        # 홈 위치(특이점 제어를 위해 j사용)
        home_pos = posj(-0.01, 0.01, 90.00, 180.02, -89.98, 0)
        # home_pos = posj(8.5, 5.45, 82.85, 179.96, -91.70, -171.71)
        
        # ==========================================
        # 단계 1. 액자 누르고 절벽(더미 밖)으로 밀기
        # ==========================================
        # 시작전 홈위치 이동

        time.sleep(0.05)
        gripper_open()
        time.sleep(0.05)
        movej(home_pos, vel = 30, acc = 50)

        while rclpy.ok():

            node.get_logger().info("--- [1] 액자 파지 시작 ---")
            
            time.sleep(0.05)
            # 1. 액자 상공으로 이동
            movej(pos_lowframe_start_hover, vel = 100, acc = 50)

            time.sleep(0.05)
            # # 2. 액자 위치로 하강
            movel(pos_lowframe_start, vel = [100,100], acc = [50,50])

            # 액자 파지
            time.sleep(0.05)
            gripper_close()

            # ==========================================
            # [예외 처리 추가] 액자가 정상적으로 잡혔는지 확인
            # ==========================================
            time.sleep(0.5)
            current_width = get_gripper_width()  # 현재 그리퍼 폭 읽기
            MIN_FRAME_WIDTH = 15.0  # 허용되는 최소 액자 두께 (mm) - 액자 실제 두께에 맞춰 수정하세요!

            if current_width is not None and current_width < MIN_FRAME_WIDTH:
                node.get_logger().error(f":경고: 예외 발생: 액자가 파지되지 않았습니다! (현재 폭: {current_width}mm)")
                gripper_open() # 안전을 위해 다시 열기
                movej(pos_lowframe_start_hover, vel=30, acc=50) # 홈 위치로 원복

                node.get_logger().info("작업을 중단합니다. 액자를 제자리에 놓아주세요.")
                time.sleep(10)
                continue # 실무에선 hmi 경고창 종료시까지 대기 후 이어서 진행할것
            elif current_width is not None:
                node.get_logger().info(f":흰색_확인_표시: 액자 파지 확인 완료. (현재 폭: {current_width}mm)")
            else:
                node.get_logger().warning("그리퍼 폭 센서를 읽을 수 없지만 작업을 계속 진행합니다.")
            # ==========================================

            # 액자 상공으로 복귀
            time.sleep(0.05)
            movel(pos_lowframe_start_hoverx, vel = [100,100], acc = [50,50])

            # 배치 위치 상공으로 이동
            time.sleep(0.05)
            movej(pos_frame_lower1, vel = 100, acc = 50)

            # 액자 배치 및 그리퍼 열기
            time.sleep(0.05)
            movel(pos_frame_lower2, vel = [100,100], acc = [30,30], mod = 0)
            time.sleep(0.05)
            gripper_open()
            time.sleep(0.5)

            # 충돌 방지를 위해 후진
            movel(pos_frame_lower3, vel = [100,100], acc = [50,50], mod = 0)
            time.sleep(0.05)
            movel(pos_frame_lower4, vel = [100,100], acc = [50,50], mod = 0)

            # 안전 위치로 복귀
            time.sleep(0.05)
            movej(home_pos, vel = 100, acc = 50)

            return True

    
    def frame_high_setup():

        # 액자 파지 위치
        pos_frame_highstart_hover = posx(295.35, -127.08, 583.96, 70.24, 179.95, -19.80)
        pos_frame_highstart_hoverx = posx(295.35, -127.08, 583.96, 70.24, 179.95, -19.80)
        pos_frame_highstart = posx(295.36, -127.08, 347.73, 67.75, 179.95, -22.29)

        # 액자 하판 위치
        pos_frame_high1 = posx(274.49, 328.02, 231.75, 90.06, -90.00, 0.00) # 검증 필요!
        pos_frame_high2 = posx(274.49, 328.02, 81.75, 90.06, -90.00, 0.00)
        pos_frame_high3= posx(274.49, 378.02, 81.75, 90.06, -90.00, 0.00)
        pos_frame_high4 = posx(274.49, 378.02, 181.75, 90.06, -90.00, 0.00)


        # 홈 위치(특이점 제어를 위해 j사용)
        home_pos = posj(-0.01, 0.01, 90.00, 180.02, -89.98, 0)

        while rclpy.ok():
            
            # ==========================================
            # 단계 1. 액자 누르고 절벽(더미 밖)으로 밀기
            # ==========================================
            # 시작전 홈위치 이동

            time.sleep(0.05)
            gripper_open()

            node.get_logger().info("--- [1] 액자 파지 시작 ---")
            
            time.sleep(0.05)
            # 1. 액자 상공으로 이동
            movel(pos_frame_highstart_hover, vel = 100, acc = 50)

            time.sleep(0.05)
            # # 2. 액자 위치로 하강
            movel(pos_frame_highstart, vel = [100,100], acc = [50,50])
            time.sleep(0.05)
            gripper_close()

            # ==========================================
            # [예외 처리 추가] 액자가 정상적으로 잡혔는지 확인
            # ==========================================
            time.sleep(0.5)
            current_width = get_gripper_width()  # 현재 그리퍼 폭 읽기
            MIN_FRAME_WIDTH = 15.0  # 허용되는 최소 액자 두께 (mm) - 액자 실제 두께에 맞춰 수정하세요!

            if current_width is not None and current_width < MIN_FRAME_WIDTH:
                node.get_logger().error(f":경고: 예외 발생: 액자가 파지되지 않았습니다! (현재 폭: {current_width}mm)")
                gripper_open() # 안전을 위해 다시 열기
                movel(pos_frame_highstart_hover, vel=30, acc=50) # 홈 위치로 원복

                node.get_logger().info("작업을 중단합니다. 액자를 제자리에 놓아주세요.")
                time.sleep(10)
                continue # 실무에선 hmi 경고창 종료시까지 대기 후 이어서 진행할것
            elif current_width is not None:
                node.get_logger().info(f":흰색_확인_표시: 액자 파지 확인 완료. (현재 폭: {current_width}mm)")
            else:
                node.get_logger().warning("그리퍼 폭 센서를 읽을 수 없지만 작업을 계속 진행합니다.")
            # ==========================================

            time.sleep(0.1)
            movel(pos_frame_highstart_hoverx, vel = [100,100], acc = [50,50])

            # time.sleep(0.05)
            # movej(pos_frame_high0, vel=20, acc=50)

            time.sleep(0.05)
            movel(pos_frame_high1, vel = [100,100], acc = [50,50])

            time.sleep(0.05)
            movel(pos_frame_high2, vel = [100,100], acc = [50,50], mod = 0)
            time.sleep(0.05)
            gripper_open()
            time.sleep(0.5)

            # 홈위치 복귀
            movel(pos_frame_high3, vel = [100,100], acc = [50,50], mod = 0)
            time.sleep(0.05)
            movel(pos_frame_high4, vel = [100,100], acc = [50,50], mod = 0)
            time.sleep(0.05)
            movej(home_pos, vel = 70, acc = 50)
            node.get_logger().info("--- 액자 파지 및 배치 작업 완료 ---")
            return True


    def Calibration_frame():
        # ==========================================
        # 단계 4. 캘리브레이션
        # ==========================================
        # 종이 정렬 위치 2개
        pos_paper_calx0 = posx(136.30, 3.09, 341.14, 48.36, 179.93, -41.67) # +x방향으로
        pos_paper_calx1 = posx(136.30, 3.09, 291.14, 48.36, 179.93, -41.67) # +x방향으로
        pos_paper_calx2 = posx(166.30, 3.09, 291.14, 48.36, 179.93, -41.67)


        # pos_paper_caly0 = posx(286.07, 158.74, 340.07, 68.05, 179.95, -21.99) # -y방향으로
        # pos_paper_caly1 = posx(286.07, 158.74, 290.07, 68.05, 179.95, -21.99) # -y방향으로
        # pos_paper_caly2 = posx(286.07, 101.20, 290.07, 68.05, 179.95, -21.99)

        pos_paper_caly0 = posx(286.07, 158.74, 340.07, 68.05, 179.95, 159.14) # -y방향으로
        pos_paper_caly1 = posx(286.07, 158.74, 290.07, 68.05, 179.95, 159.14) # -y방향으로
        pos_paper_caly2 = posx(286.07, 101.20, 290.07, 68.05, 179.95, 159.14)



        node.get_logger().info("--- [4] Y축 캘리브레이션 시작 ---")
        gripper_close()
        time.sleep(0.05)
        movel(pos_paper_caly0, vel=100, acc=50)
        time.sleep(0.05)
        movel(pos_paper_caly1, vel=100, acc=50)

        node.get_logger().info("순응제어 시작")
        time.sleep(0.5)
        task_compliance_ctrl(stx=[100, 3000, 3000, 100, 100, 100])
        time.sleep(0.5)
        amovel(pos_paper_caly2, vel = [30,30], acc = [30,30], ref = 0, mod = 0)

        time.sleep(3)
        node.get_logger().info("순응제어 종료")
        release_compliance_ctrl()

        time.sleep(0.05)
        movel(pos_paper_caly1, vel=100, acc=50)
        time.sleep(0.05)
        movel(pos_paper_caly0, vel=100, acc=50)

        node.get_logger().info("--- [4] X축 캘리브레이션 시작 ---")
        time.sleep(0.05)
        movel(pos_paper_calx0, vel=100, acc=50)
        time.sleep(0.05)
        movel(pos_paper_calx1, vel=100, acc=50)

        time.sleep(0.5)
        node.get_logger().info("순응제어 시작")
        task_compliance_ctrl(stx=[100, 3000, 3000, 100, 100, 100])
        time.sleep(0.5)

        amovel(pos_paper_calx2, vel = [30,30], acc = [30,30], ref = 0, mod = 0)
        time.sleep(3)
        
        release_force()
        time.sleep(0.5)
        node.get_logger().info("순응제어 종료")
        release_compliance_ctrl()
        time.sleep(0.05)
        movel(pos_paper_calx1, vel=100, acc=50)
        time.sleep(0.05)
        movel(pos_paper_calx0, vel=100, acc=50)

    # 종이 파지 코드
    def slide_and_pinch_paper():

        # 1. 종이 더미의 중앙 좌표 (그리퍼가 바닥을 향한 자세: Rx=0, Ry=180, Rz=0)
        pos_paper_center = posx(563.03, 75.97, 328.62, 9.86, 180.00, 98.32) 
        
        # 2. 절벽 끝단 좌표
        pos_cliff_edge = posx(563.03, 120.97, 328.63, 179.99, 180.00, -91.36) 
        
        # 3. 액자 위치 좌표
        pos_frame_paper_prepare = posx(288.95, 239.42, 444.60, 91, -135.9, 179)#안전위치
        pos_frame_paper0 = posx(288.97, 190, 367.05, 91.03, -135.90, 178.99)#종이배치위치1

        # 종이 파지 위치 5단계
        pinch_ready_pos0 = posx(565.45, 403.09, 193.32, 91.36, -90.00, 180.00)
        pinch_ready_pos1 = posx(565.45, 403.11, 103.32, 91.36, -90.00, 180.00)
        pinch_ready_pos2 = posx(565.45, 383.14, 103.32, 91.36, -90.00, 180.00)

        hover_pos = posx(pos_paper_center[0], pos_paper_center[1], pos_paper_center[2]+20, pos_paper_center[3], pos_paper_center[4], pos_paper_center[5])
        ready_pos = posx(pos_paper_center[0], pos_paper_center[1], pos_paper_center[2]+2, pos_paper_center[3], pos_paper_center[4], pos_paper_center[5])
        
        # ==========================================
        # 단계 1. 종이 누르고 절벽(더미 밖)으로 밀기
        # ==========================================
        # 시작전 홈위치 이동

        while rclpy.ok():

            node.get_logger().info("--- [1] 종이 슬라이딩 시작 ---")
            
            # 1. 종이 상공으로 이동
            time.sleep(0.05)
            movel(hover_pos, vel = [100,100], acc = [50,50], mod = 0)
            time.sleep(0.05)
            gripper_close()
            time.sleep(0.05)
            # 2. 종이 표면으로 하강
            movel(ready_pos, vel=30, acc=50, mod = 0)


            # 3. Z축 힘 제어 켜기 (5N으로 누르기)
            task_compliance_ctrl(stx=[500, 500, 500, 100, 100, 100])
            time.sleep(0.5)
            set_desired_force(fd=[0, 0, -2, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0], mod=DR_FC_MOD_REL)
            time.sleep(2)
            node.get_logger().info("힘제어 시작")

            # ==========================================
            # :경광등: [예외 처리] 현재 Z 높이를 확인하여 종이 소진 판별
            # ==========================================
            # 현재 로봇의 위치(TCP)를 Base 좌표계 기준으로 가져옵니다.
            current_pos, _ = get_current_posx(ref=DR_BASE)
            current_z = current_pos[2] # X, Y, Z, Rx, Ry, Rz 중 세 번째 값(Z)

            # 바닥(트레이) 높이보다 살짝 높은 값을 임계값으로 설정합니다.
            # (예: 바닥이 330.0mm라면 종이 1~2장 두께를 고려해 332.0mm로 설정)
            MIN_PAPER_Z = 324.0

            node.get_logger().info(f"현재 Z 높이: {current_z:.2f}mm")

            if current_z < MIN_PAPER_Z:
                node.get_logger().error(f":경고: 예외 발생: 종이가 없습니다! (현재 Z: {current_z:.2f}mm < {MIN_PAPER_Z}mm)")

                # 1. 안전을 위해 힘 제어 및 컴플라이언스 제어 즉시 해제
                release_force()
                time.sleep(0.1)
                release_compliance_ctrl()
                time.sleep(0.5)

                # 2. 로봇을 종이 위(충돌 없는 안전한 상공)로 들어올리기
                movel(hover_pos, vel=50, acc=50, mod=0)
                time.sleep(10)

                continue
            break
        
        # 4. 종이를 절벽 끝 방향으로 밀기
        move_pos = posx(pos_cliff_edge[0], pos_cliff_edge[1], pos_cliff_edge[2], pos_cliff_edge[3], pos_cliff_edge[4], pos_cliff_edge[5])
        amovel(move_pos, vel=30, acc=50, mod = 0, ref = 0) 
        time.sleep(3)
        
        # 5. 밀기 완료 후 힘 제어 풀고 수직 상승
        release_force()
        time.sleep(0.5)
        node.get_logger().info("힘제어 종료")
        release_compliance_ctrl()
        time.sleep(0.05)
        node.get_logger().info("--- 종이 20% 돌출 완료 ---")
        movel(posx(pos_cliff_edge[0], pos_cliff_edge[1], pos_cliff_edge[2]+100, pos_cliff_edge[3], pos_cliff_edge[4], pos_cliff_edge[5]), vel=100, acc=100)
        
        # ==========================================
        # 단계 2. 허공에 뜬 종이 꼬집기 (Pinch)
        # # ==========================================
        node.get_logger().info("--- [2] 꼬집기(Pinch) 픽업 시작 ---")
        time.sleep(0.05)
        # 6. 그리퍼 열기
        gripper_open()
        
        # 7. 꼬집기 준비 자세로 이동 (충돌 방지를 위해 4단계로 나누어 진행)
        movel(pinch_ready_pos0, vel = [100,100], acc = [50,50])
        time.sleep(0.05)
        movel(pinch_ready_pos1, vel = [100,100], acc = [50,50])
        time.sleep(0.05)
        movel(pinch_ready_pos2, vel = [50,50], acc = [50,50])
        time.sleep(0.05)

        # 9. 그리퍼 닫아서 종이 꼬집기
        gripper_close()
        time.sleep(0.05)
        # 10. 들어 올리기
        movel(pinch_ready_pos0, vel = [100,100], acc = [50,50])
        time.sleep(0.5)
        node.get_logger().info("--- 픽업 완료 ---")

        movel(pos_frame_paper_prepare, vel = [100,100], acc = [50,50])
        
        # ==========================================
        # 단계 3. 액자(정면)로 이동 및 안착
        # ==========================================
        node.get_logger().info("--- [3] 액자로 이동 ---")
        
        # 11. 액자 상공으로 이동
        movel(pos_frame_paper0, vel = [100,100], acc = [50,50])    
        time.sleep(0.05)
        gripper_open()
        time.sleep(2)    
        pos_paper_relese0 = posx(0,0,0,90,-40,-90)
        amovel(pos_paper_relese0, vel=[20.0,20.0], acc=[10.0,10.0], mod=1, ref = 0)
        time.sleep(3)

    def frameout():
        pos_frameout0 = posx(281.78, 288.83, 80.12, 90, -90, 0)
        pos_frameout1 = posx(281.78, 340.83, 80.12, 90, -90, 0)
        pos_frameout1_hover = posx(281.78, 340.83, 300.12, 90, -90, 0)

        pos_framefinal = posx(420, 51.77, 349.94, 7.48, 179.48, -173.96)
        pos_framefinal_hover = posx(420, 51.77, 549.94, 7.48, 179.48, -173.96)
        
        home_pos = posj(-0.01, 0.01, 90.00, 180.02, -89.98, 0) 
        movej(home_pos, vel = 100, acc = 50)
        time.sleep(0.05)
        gripper_open()
        time.sleep(0.05)
        movel(pos_frameout1_hover, vel = [100,100], acc = [50,50])
        time.sleep(0.05)
        movel(pos_frameout1, vel = [100,100], acc = [50,50])
        time.sleep(0.05)
        movel(pos_frameout0, vel = [100,100], acc = [50,50])
        time.sleep(0.05)
        gripper_close()
        time.sleep(0.05)
        movel(pos_frameout1_hover, vel = [100,100], acc = [50,50])
        time.sleep(0.05)

        movel(pos_framefinal_hover, vel = [100,100], acc = [50,50])
        time.sleep(0.05)
        movel(pos_framefinal, vel = [100,100], acc = [50,50])
        time.sleep(0.05)

        gripper_open()
        time.sleep(0.05)
        movel(pos_framefinal_hover, vel = [100,100], acc = [50,50])

    def pencil_grip():
        # 위치 변수들은 루프 밖에서 한 번만 선언
        pencil_high = 306.71
        pos_pencilcase_up = posx(477.01, -163.54, pencil_high + 150, 70.21, 179.94, -107.98)
        pos_pencilcase_down = posx(477.02, -163.54, pencil_high, 65.91, 179.94, -112.28)
        pos_pencilcase_home = posx(526.83, 54.46, 506.64, 62.97, 179.94, -117.13)

        while True:
            node.get_logger().info("--- 연필 파지 시작 ---")
            gripper_open()
            time.sleep(0.05)

            # 1. 연필통 상공으로 이동
            movel(pos_pencilcase_up, vel = [100,100], acc = [50,50], mod = 0)
            time.sleep(0.05)
            
            # 2. 연필 파지 위치로 하강
            movel(pos_pencilcase_down, vel = [100,100], acc = [50,50], mod = 0)
            time.sleep(0.05)
            
            # 3. 그리퍼 닫기
            gripper_close()
            time.sleep(0.5) # 그리퍼가 완전히 닫힐 때까지 대기

            # ==========================================
            # [예외 처리] 연필이 정상적으로 잡혔는지 확인
            # ==========================================
            current_width = get_gripper_width()
            MIN_PENCIL_WIDTH = 15.0  # 허용되는 최소 연필 두께 (mm) - 실제 연필 두께에 맞춰 수정하세요!

            if current_width is not None and current_width < MIN_PENCIL_WIDTH:
                node.get_logger().error(f"경고: 연필이 파지되지 않았습니다! (현재 폭: {current_width}mm)")
                
                # 안전을 위해 그리퍼를 열고 상공으로 대피
                gripper_open()
                movel(pos_pencilcase_up, vel=[100, 100], acc=[50, 50], mod=0)
                
                node.get_logger().info("작업을 다시 시도합니다. (2초 후 재시작)")
                time.sleep(10.0) # 무한 재시도 방지를 위한 쿨타임
                continue # 루프 처음으로 돌아가서 재시작

            elif current_width is not None:
                node.get_logger().info(f"연필 파지 확인 완료. (현재 폭: {current_width}mm)")
            else:
                node.get_logger().warning("그리퍼 폭 센서를 읽을 수 없지만 작업을 계속 진행합니다.")
            # ==========================================

            # 파지에 성공했을 경우 남은 동작 수행
            time.sleep(0.05)
            movel(pos_pencilcase_up, vel = [100,100], acc = [50,50], mod = 0)
            
            time.sleep(0.05)
            movel(pos_pencilcase_home, vel = [100,100], acc = [50,50], mod = 0)
            
            node.get_logger().info("--- 연필 파지 및 홈 이동 완료 ---")
            return True # 작업이 성공적으로 끝났으므로 루프 탈출 및 함수 종료



    def pencil_release():
        pencil_high = 306.71
        pos_pencilcase_up = posx(477.01, -163.54, pencil_high + 150, 70.21, 179.94, -107.98)
        pos_pencilcase_down = posx(477.02, -163.54, pencil_high, 65.91, 179.94, -112.28)
        pos_pencilcase_home = posx(526.83, 54.46, 506.64, 62.97, 179.94, -117.13)

        movel(pos_pencilcase_home, vel = [100,100], acc = [50,50], mod = 0)
        movel(pos_pencilcase_up, vel = [100,100], acc = [50,50], mod = 0)
        movel(pos_pencilcase_down, vel = [100,100], acc = [50,50], mod = 0)
        gripper_open()
        movel(pos_pencilcase_up, vel = [100,100], acc = [50,50], mod = 0)


    # ==========================================
    # 2. 메인 실행 블록 (Main Flow) 에서 함수 호출
    # ==========================================


    pencil_grip()
    pencil_release()


    node.get_logger().info("로봇 테스크 시작")
    frame_lower_setup()
    slide_and_pinch_paper()
    Calibration_frame() 
    frame_high_setup()
    Calibration_frame()
    frameout()

    # 노드 종료 처리
    rclpy.shutdown()

if __name__ == "__main__":
    main()
