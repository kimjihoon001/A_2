import time
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
    def gripper_open():
        set_digital_output(1, ON)
        set_digital_output(2, OFF)

    def gripper_close(wait_time=2.5):
        set_digital_output(2, ON)
        set_digital_output(1, OFF)
        time.sleep(wait_time)

    # 종이 파지 코드
    def slide_and_pinch_frame():

        push_force = 20.0  # 액자 누름 힘 (N)

        # 액자 파지 위치
        pos_frame_start_hover = posj(-21.70, 11.11, 44.39, 179.93, -124.68, -110.83)
        pos_frame_start = posj(-21.77, 2.37, 95.62, 179.93, -82.18, -110.82)

        # 액자 하판 위치
        pos_frame_lower0 = posj(30.37, 6.95, 95.37, 95.84, -119.58, -76.33)
        pos_frame_lower1 = posj(47.33, 38.81, 91.33, 125.92, -124.66, -39.21)
        pos_frame_lower2 = posx(357.18, 240.87, 71.27, 89.14, -90.18, 179.43)
        
        # ==========================================
        # 단계 1. 액자 누르고 절벽(더미 밖)으로 밀기
        # ==========================================
        # 시작전 홈위치 이동

        time.sleep(0.1)
        gripper_open()
        home_pos = posx(367.35, 6.68, 422.88, 46.20, -179, 46.6)

        time.sleep(0.1)
        movel(home_pos, vel = 20, acc = 50, mod = 0, ref = 0)

        node.get_logger().info("--- [1] 액자 파지 시작 ---")
        
        time.sleep(0.1)
        # 1. 액자 상공으로 이동
        movej(pos_frame_start_hover, vel = 20, acc = 50)

        time.sleep(0.1)
        # # 2. 액자 위치로 하강
        movej(pos_frame_start, vel=20, acc=50)
        gripper_close()

        time.sleep(0.1)
        movej(pos_frame_start_hover, vel=20, acc=50)

        time.sleep(0.1)
        movej(pos_frame_lower0, vel=20, acc=50)

        time.sleep(0.1)
        movej(pos_frame_lower1, vel=20, acc=50)

        time.sleep(0.1)
        movel(pos_frame_lower2, vel=20, acc=50, mod = 0)
        gripper_open()






        
        # # 3. Z축 힘 제어 켜기 (20N으로 누르기)
        # task_compliance_ctrl(stx=[3000, 3000, 500, 100, 100, 100])
        # set_desired_force(fd=[0, 0, -push_force, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0], mod=DR_FC_MOD_REL)
        # time.sleep(0.5)
        # node.get_logger().info("힘제어 시작")
        
        # # 4. 액자를 절벽 끝 방향으로 밀기
        # move_pos = posx(pos_cliff_edge[0], pos_cliff_edge[1], pos_cliff_edge[2] -1, pos_cliff_edge[3], pos_cliff_edge[4], pos_cliff_edge[5])
        # amovel(move_pos, vel=30, acc=50, mod = 0, ref = 0) 
        # time.sleep(3)
        
        # # 5. 밀기 완료 후 힘 제어 풀고 수직 상승
        # release_force()
        # time.sleep(0.5)
        # node.get_logger().info("힘제어 종료")
        # release_compliance_ctrl()
        
        # node.get_logger().info("--- 종이 20% 돌출 완료 ---")
        # movel(posx(pos_cliff_edge[0], pos_cliff_edge[1], pos_cliff_edge[2] + 50, pos_cliff_edge[3], pos_cliff_edge[4], pos_cliff_edge[5]), vel=100, acc=100)
        
        # # ==========================================
        # # 단계 2. 허공에 뜬 종이 꼬집기 (Pinch)
        # # # ==========================================
        # node.get_logger().info("--- [2] 꼬집기(Pinch) 픽업 시작 ---")
        
        # # 6. 그리퍼 열기
        # gripper_open()
        
        # # 7. 꼬집기 준비 자세로 이동 (충돌 방지를 위해 4단계로 나누어 진행)
        # movel(pinch_ready_pos0, vel=50, acc=50)
        # time.sleep(0.1)
        # movel(pinch_ready_pos1, vel=50, acc=50)
        # time.sleep(0.1)
        # movel(pinch_ready_pos2, vel=50, acc=50)
        # time.sleep(0.1)

        # # 8. 종이 쪽으로 전진하여 그리퍼 사이에 종이 넣기
        # movel(pinch_ready_pos3, vel=50, acc=50)
        # time.sleep(0.1)
        
        # # 9. 그리퍼 닫아서 종이 꼬집기
        # gripper_close()
        
        # # 10. 들어 올리기
        # movel(pinch_ready_pos4, vel=50, acc=50)
        # time.sleep(0.5)
        # node.get_logger().info("--- 픽업 완료 ---")
        
        # # ==========================================
        # # 단계 3. 액자(정면)로 이동 및 안착
        # # ==========================================
        # node.get_logger().info("--- [3] 액자로 이동 ---")
        
        # # 11. 액자 상공으로 이동
        # # 손목이 꺾인 상태로 넓은 반경을 이동할 때는 movej (관절 이동)를 쓰는 것이 특이점 예방에 좋습니다.
        # frame_hover_pos = posx(pos_frame[0], pos_frame[1], pos_frame[2] + 100, 90, 180, 0) # 꼬집은 자세 유지
        # movej(frame_hover_pos, vel=50, acc=50)
        
        # # 12. 액자 안으로 하강
        # movel(pos_frame, vel=30, acc=50)
        
        # # 13. 그리퍼 열어서 종이 놓기
        # gripper_open()
        
        # # 14. 로봇 복귀
        # movel(frame_hover_pos, vel=50, acc=100)
        # node.get_logger().info("--- 액자 안착 완료 ---")


    # ==========================================
    # 0. 좌표 변수 선언 파트에 추가할 내용
    # ==========================================
    
    # 1. 종이 더미의 정중앙 좌표 (그리퍼가 바닥을 향한 자세: Rx=0, Ry=180, Rz=0)
    Paper_Center = posx(607.0, -185.0, 393.0, 123.0, -180.0, -60.0) 
    
    # 2. 절벽 끝단 좌표 (종이를 바깥쪽으로 50mm, 우측으로 50mm 밀어낸 위치)
    Cliff_Edge = posx(564.0, -182.0, 393.0, 168.0, 180.0, -14.0) 
    
    # 3. 액자 정중앙 좌표 (⭐주의: 종이를 꼬집은 자세 그대로 눕혀서 가야 하므로 Rx=90)
    Frame_Center = posx(400.0, 0.0, 10.0, 90.0, 180.0, 0.0)


    # ==========================================
    # 2. 메인 실행 블록 (Main Flow) 에서 함수 호출
    # ==========================================

    # node.get_logger().info("--- 연결 ---")
    # pos_frame_start = posj(-21.77, 2.41, 79.68, 179.93, -98.07, -110.83)
    # movej(pos_frame_start, vel = 30, acc = 50)
    # node.get_logger().info("--- 초기위치 ---")


    time.sleep(0.1)
    slide_and_pinch_frame()

    # 노드 종료 처리
    rclpy.shutdown()

if __name__ == "__main__":
    main()
