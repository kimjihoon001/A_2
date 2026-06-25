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
            DR_FC_MOD_REL,
            DR_AXIS_Z,
            DR_BASE,
            
        )
        from DR_common2 import posx, posj
    
    except ImportError as e:
        node.get_logger().error(f"Error importing DSR_ROBOT2 : {e}")
        return

    # ==========================================
    # 0. 좌표 변수 선언 (🚨 실제 티칭된 좌표값으로 반드시 채워 넣으세요!)
    # ==========================================
    Global_RDOWN = posx(427.77,150.61,268.74,22.67,-179.54,23.18)
    Global_RUP = posx(427.77,150.61,368.74,22.67,-179.54,23.18)
    Global_LDOWN = posx(429.19,-148.92,268.20,31.85,-179.01,32.79)
    Global_LUP = posx(429.19,-148.92,368.20,31.85,-179.01,32.79)
    Global_RGEAR1_RDOWN = posx(368.10,143.23,268.92,178.17,179.28,179.25)
    Global_RGEAR1_RUP = posx(368.10,143.23,368.92,178.17,179.28,179.25)
    Global_RGEAR1_LUP = posx(368.10,-156.77,368.92,178.17,179.28,179.25)
    Global_RGEAR1_LDOWN = posx(368.10,-156.77,268.92,178.17,179.28,179.25)
    Global_RGEAR2_RDOWN = posx(463.98,95.87,268.16,167.12,178.73,168.63)
    Global_RGEAR2_RUP = posx(463.98,95.87,368.16,167.12,178.73,168.63)
    Global_RGEAR2_LUP = posx(463.98,-204.13,368.16,167.12,178.73,168.63)
    Global_RGEAR2_LDOWN = posx(463.98,-204.13,268.16,167.12,178.73,168.63)
    Global_RGEAR3_RDOWN = posx(456.16,201.17,267.98,169.14,178.93,170.59)
    Global_RGEAR3_RUP = posx(456.16,201.17,367.98,169.14,178.93,170.59)
    Global_RGEAR3_LUP = posx(456.16,-98.83,367.98,169.14,178.93,170.59)
    Global_RGEAR3_LDOWN = posx(456.16,-98.83,267.98,169.14,178.93,170.59)

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

    def pick_gear(pos_up, pos_down):
        node.get_logger().info("--- [1] 그리퍼 열기 시도 ---")
        gripper_open()
        
        node.get_logger().info("--- [2] pos_up 좌표로 이동 시도 ---")
        movel(pos_up, vel=50, acc=100)
        
        node.get_logger().info("--- [3] pos_down 좌표로 이동 시도 ---")
        movel(pos_down, vel=50, acc=100)
        
        node.get_logger().info("--- [4] 그리퍼 닫기 시도 ---")
        gripper_close()
        node.get_logger().info("--- 픽업 단계 완료 ---")
        time.sleep(0.5)

    def move_to_standby(pos_up, pos_standby):
        movel(pos_up, vel=50, acc=100)
        movel(pos_standby, vel=50, acc=100)
        time.sleep(2.5)

    def assemble_gear_with_force():
        task_compliance_ctrl([3000, 3000, 300, 3100, 3100, 100])
        time.sleep(0.5)
        set_desired_force([0, 0, -30, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0], mod=DR_FC_MOD_REL)

        while not check_force_condition(DR_AXIS_Z, max=5):
            time.sleep(0.1)
        
        time.sleep(0.5)

        for i in range(10):
            if not rclpy.ok(): break
            amovel([0, 0, 0, 0, 0, 3], vel=20, acc=40, ref=1, mod=1)
            time.sleep(0.5)

        current_z = get_current_posx()[0][2]
        if current_z <= 270:
            return True 
        else:
            return False 

    def handle_assembly_error(pos_safe):
        # 팝업 대신 터미널에 로그 출력
        node.get_logger().warn("🚨 조립 실패! 이물질을 제거해주세요. 완료 후 로봇의 툴을 쳐주세요(X축 4N 이상).")
        
        release_force()
        time.sleep(0.5)
        release_compliance_ctrl()
        movel(pos_safe, vel=50, acc=100) 

        while rclpy.ok():
            time.sleep(0.5)

            f = get_tool_force()
            Scalar = (f[0]**2 + f[1]**2 + f[2]**2)**0.5
            if Scalar >= 4:
                node.get_logger().info("✅ 외부 충돌 감지됨. 작업을 재개합니다.")
                break

    def finish_task(pos_final):
        release_force()
        time.sleep(0.5)
        release_compliance_ctrl()
        gripper_open()

        movel(pos_final, vel=50, acc=200)
        node.get_logger().info("작업 완료. 다음 임무를 대기합니다 (X축 충돌: 임무 0, Z축 충돌: 임무 1).")

        while rclpy.ok():

            time.sleep(0.5)

            f = get_tool_force()
            if abs(f[0]) >= 4:
                return 0
            elif abs(f[2]) >= 4:
                return 1
            

    # ==========================================
    # 2. 메인 실행 블록 (Main Flow)
    # ==========================================
    node.get_logger().info("🚀 기어 조립 노드를 시작합니다.")

    # 🚨 추가: 초기 특이점(Singularity) 탈출을 위한 준비 자세로 이동
    node.get_logger().info("초기 특이점 회피를 위한 movej 이동 중...")
    JReady = posj([0, 0, 90, 0, 90, 0])
    movej(JReady, vel=30, acc=30)
    time.sleep(1.0) # 안전을 위해 잠시 대기

    pos_left_up = Global_LUP
    pos_left_down = Global_LDOWN
    pos_right_up = Global_RUP
    pos_right_down = Global_RDOWN

    posR_right_up   = [None, Global_RGEAR1_RUP,   Global_RGEAR2_RUP,   Global_RGEAR3_RUP]
    posR_right_down = [None, Global_RGEAR1_RDOWN, Global_RGEAR2_RDOWN, Global_RGEAR3_RDOWN]
    posR_left_up    = [None, Global_RGEAR1_LUP,   Global_RGEAR2_LUP,   Global_RGEAR3_LUP]
    posR_left_down  = [None, Global_RGEAR1_LDOWN, Global_RGEAR2_LDOWN, Global_RGEAR3_LDOWN]

    # 초기 조립 시퀀스
    pick_gear(pos_left_up, pos_left_down)
    time.sleep(0.5)
    move_to_standby(pos_left_up, pos_right_up)

    while rclpy.ok():
        if assemble_gear_with_force():
            break
        else:
            handle_assembly_error(pos_right_up)

    task = finish_task(pos_right_up)

    # 무한 임무 대기 루프
    while rclpy.ok():
        if task == 0:
            node.get_logger().info("▶️ 0번 임무 시작")
            pick_gear(pos_right_up, pos_right_down)
            move_to_standby(pos_right_up, pos_left_up)
            
            while rclpy.ok():
                if assemble_gear_with_force():
                    break
                else:
                    handle_assembly_error(pos_left_up)
            
            task = finish_task(pos_left_up)

        elif task == 1:
            node.get_logger().info("▶️ 1번 임무 시작")
            for i in range(1, 4):
                if not rclpy.ok(): break
                
                pick_gear(posR_right_up[i], posR_right_down[i])
                move_to_standby(posR_right_up[i], posR_left_up[i])
                
                while rclpy.ok():
                    if assemble_gear_with_force():
                        break
                    else:
                        handle_assembly_error(posR_left_up[i])

                release_force()
                time.sleep(0.5)
                release_compliance_ctrl()
                gripper_open()
                move_to_standby(posR_left_up[i], posR_left_up[i])

            task = finish_task(pos_left_up)

    # 노드 종료 처리
    rclpy.shutdown()

if __name__ == "__main__":
    main()