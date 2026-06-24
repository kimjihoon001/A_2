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
    def slide_and_pinch_paper():

        # 1. 종이 더미의 정중앙 좌표 (그리퍼가 바닥을 향한 자세: Rx=0, Ry=180, Rz=0)
        pos_paper_center = posx(626.88, 254.63, 337.28, 0, -179.74, -0.07) 
        
        # 2. 절벽 끝단 좌표 (종이를 바깥쪽으로 50mm, 우측으로 50mm 밀어낸 위치)
        pos_cliff_edge = posx(590.36, 254.63, 337.28, 0.09, -179.74, -0.07) 
        
        # 3. 액자 정중앙 좌표 (⭐주의: 종이를 꼬집은 자세 그대로 눕혀서 가야 하므로 Rx=90)
        pos_frame_paper_prepare = posx(326.40, 212.26, 307.57, 90.72, -93.38, 178.12)
        pos_frame_paper0 = posx(348.04, 153.99, 323.44, 89.86, -125.51, -176.69)
        pos_frame_paper1 = posx(348.04, 154.04, 323.44, 21.52, -180, 114.92)


        push_force = 1.0  # 종이 누름 힘 (N)

        # 종이 파지 위치 5단계
        pinch_ready_pos0 = posx(286.19, 254.64, 328.10, 0.29, 89.99, 0.01)
        pinch_ready_pos1 = posx(286.18, 254.63, 122.70, 0.29, 90.00, 0.00)
        pinch_ready_pos2 = posx(328.45, 254.63, 122.70, 0.29, 90.00, 0.00)

        # 종이 정렬 위치 2개
        pos_paper_calx0 = posx(176.02, -28.46, 484.33, 18.16, -179.97, 18.11) # +x방향으로
        pos_paper_calx1 = posx(176.02, -28.46, 284.33, 18.16, -179.97, 18.11) # +x방향으로
        pos_paper_calx2 = posx(244.41, -28.46, 284.33, 18.16, -179.97, 18.11) # +x방향으로


        pos_paper_caly0 = posx(357.26, 80.49, 486.99, 2.48, -178.85, 2.41) # +y방향으로
        pos_paper_caly1 = posx(357.26, 80.49, 286.99, 2.48, -178.85, 2.41) # +y방향으로


        
        # ==========================================
        # 단계 1. 종이 누르고 절벽(더미 밖)으로 밀기
        # ==========================================
        # 시작전 홈위치 이동
        node.get_logger().info("--- test ---")

        gripper_open()
        home_pos = posj(8.5, 5.45, 82.85, 179.96, -91.70, -171.71)
        movej(home_pos, vel = 30, acc = 50)

        node.get_logger().info("--- [1] 종이 슬라이딩 시작 ---")
        
        # 1. 종이 상공으로 이동
        hover_pos = posx(pos_paper_center[0], pos_paper_center[1], pos_paper_center[2] + 50, pos_paper_center[3], pos_paper_center[4], pos_paper_center[5])
        movel(hover_pos, vel=100, acc=100, mod = 0)
        gripper_close()
        
        # 2. 종이 표면으로 하강
        ready_pos = posx(pos_paper_center[0], pos_paper_center[1], pos_paper_center[2] +15, pos_paper_center[3], pos_paper_center[4], pos_paper_center[5])
        movel(ready_pos, vel=30, acc=50, mod = 0)
        


        # 3. Z축 힘 제어 켜기 (5N으로 누르기)
        task_compliance_ctrl(stx=[500, 500, 500, 100, 100, 100])
        set_desired_force(fd=[0, 0, -1, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0], mod=DR_FC_MOD_REL)
        time.sleep(4.5)
        node.get_logger().info("힘제어 시작")
        
        # 4. 종이를 절벽 끝 방향으로 밀기
        move_pos = posx(pos_cliff_edge[0], pos_cliff_edge[1], pos_cliff_edge[2] + 20, pos_cliff_edge[3], pos_cliff_edge[4], pos_cliff_edge[5])
        amovel(move_pos, vel=30, acc=50, mod = 0, ref = 0) 
        time.sleep(3)
        
        # 5. 밀기 완료 후 힘 제어 풀고 수직 상승
        release_force()
        time.sleep(0.5)
        node.get_logger().info("힘제어 종료")
        release_compliance_ctrl()
        
        node.get_logger().info("--- 종이 20% 돌출 완료 ---")
        movel(posx(pos_cliff_edge[0], pos_cliff_edge[1], pos_cliff_edge[2] + 100, pos_cliff_edge[3], pos_cliff_edge[4], pos_cliff_edge[5]), vel=100, acc=100)
        
        # ==========================================
        # 단계 2. 허공에 뜬 종이 꼬집기 (Pinch)
        # # ==========================================
        node.get_logger().info("--- [2] 꼬집기(Pinch) 픽업 시작 ---")
        
        # 6. 그리퍼 열기
        gripper_open()
        
        # 7. 꼬집기 준비 자세로 이동 (충돌 방지를 위해 4단계로 나누어 진행)
        movel(pinch_ready_pos0, vel=50, acc=50)
        time.sleep(0.1)
        movel(pinch_ready_pos1, vel=50, acc=50)
        time.sleep(0.1)
        movel(pinch_ready_pos2, vel=50, acc=50)
        time.sleep(0.1)

        # 8. 종이 쪽으로 전진하여 그리퍼 사이에 종이 넣기
        movel(pinch_ready_pos2, vel=50, acc=50)
        time.sleep(0.1)
        
        # 9. 그리퍼 닫아서 종이 꼬집기
        gripper_close()
        
        # 10. 들어 올리기
        movel(pinch_ready_pos0, vel=50, acc=50)
        time.sleep(0.5)
        node.get_logger().info("--- 픽업 완료 ---")

        movel(pos_frame_paper_prepare, vel = 30, acc = 50)
        
        # ==========================================
        # 단계 3. 액자(정면)로 이동 및 안착
        # ==========================================
        node.get_logger().info("--- [3] 액자로 이동 ---")
        
        # 11. 액자 상공으로 이동
        # 손목이 꺾인 상태로 넓은 반경을 이동할 때는 movej (관절 이동)를 쓰는 것이 특이점 예방에 좋습니다.
        movel(pos_frame_paper0, vel=50, acc=50)    
        gripper_open()
        time.sleep(2)    
        # 12. 액자 안으로 하강
        movel(pos_frame_paper1, vel=[7.0,7.0], acc=[5.0,5.0])
        
        # 13. 그리퍼 열어서 종이 놓기
        gripper_open()
        
        # 14. 로봇 복귀
        movej(home_pos, vel = 30, acc = 50)
        node.get_logger().info("--- 액자 안착 완료 ---")

        # ==========================================
        # 단계 4. 캘리브레이션
        # ==========================================
        node.get_logger().info("--- [4] 캘리브레이션 시작 ---")
        gripper_close()
        movel(pos_paper_calx0, vel=50, acc=50)
        movel(pos_paper_calx1, vel=50, acc=50)

        time.sleep(0.5)
        task_compliance_ctrl(stx=[100, 3000, 3000, 100, 100, 100])
        time.sleep(0.5)
        set_desired_force(fd=[15, 0, 0, 0, 0, 0], dir=[1, 0, 0, 0, 0, 0], mod=DR_FC_MOD_REL)
        time.sleep(0.5)
        node.get_logger().info("힘제어 시작")

        time.sleep(10)
        
        release_force()
        time.sleep(0.5)
        node.get_logger().info("힘제어 종료")
        release_compliance_ctrl()

        movel(pos_paper_calx1, vel=50, acc=50)
        movel(pos_paper_calx0, vel=50, acc=50)



    # ==========================================
    # 2. 메인 실행 블록 (Main Flow) 에서 함수 호출
    # ==========================================
    
    slide_and_pinch_paper()

    # 노드 종료 처리
    rclpy.shutdown()

if __name__ == "__main__":
    main()
