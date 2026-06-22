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

    def move_to_standby(pos_up, pos_standby):
        movel(pos_up, vel=50, acc=100)
        movel(pos_standby, vel=50, acc=100)
        time.sleep(2.5)

    def assemble_gear_with_force():
        task_compliance_ctrl([3000, 3000, 300, 3100, 3100, 3100])
        time.sleep(0.5)
        set_desired_force([0, 0, -30, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0], mod=DR_FC_MOD_REL)

        while not check_force_condition(DR_AXIS_Z, max=5):
            time.sleep(0.1)
        
        time.sleep(0.5)
        for i in range(10):
            if not rclpy.ok(): break
            time.sleep(0.3)
            amovel([0, 0, 0, 0, 0, 3], vel=20, acc=40, ref=1, mod=1)

        rclpy.spin_once(node, timeout_sec=0.1)
        current_z = get_current_posx()[0][2]

        current_z = get_current_posx()[0][2]
        if current_z <= 270:
            return True 
        else:
            return False 

    def handle_assembly_error(pos_safe):
        # 팝업 대신 터미널에 로그 출력
        node.get_logger().warn("🚨 조립 실패! 이물질을 제거해주세요. 완료 후 로봇의 툴을 쳐주세요(X축 4N 이상).")
        
        release_force()
        release_compliance_ctrl()
        movel(pos_safe, vel=50, acc=100) 

        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)

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

            rclpy.spin_once(node, timeout_sec=0.1)

            f = get_tool_force()
            if abs(f[0]) >= 4:
                return 0
            elif abs(f[2]) >= 4:
                return 1
            
    # --------------------
    # 픽셀 테스트 함수
    def draw_pixel(x, y, target_force):
        table_high = 242
        # 6. 픽셀을 빈틈없이 채우기 위한 래스터 스캔(Raster Scan) 셰이딩
        # 4mm x 4mm 영역을 'ㄹ'자 모양으로 촘촘하게 칠합니다.
        pixel_size = 4.0  # 픽셀 가로세로 크기 (mm)
        pitch = 1.0       # 선 간격 (mm) - 4B 연필심 두께 고려. 더 촘촘히 칠하려면 0.5 등으로 낮추세요.
        start_offset = pixel_size / 2.0
        
        # 1. 그리지 않는 픽셀은 스킵
        if target_force <= 0:
            return
            
        # 2. 픽셀 좌표 상공(안전 거리)으로 이동 (이동 시 movel 사용)
        hover_pos = posx(x-start_offset, y+start_offset, table_high+50, 0, 180, 0)
        movel(hover_pos, vel=100, acc=100) # 
        time.sleep(0.1)
        # 3. 종이 표면 근처로 하강 (Z축 0mm 위치라 가정)
        ready_pos = posx(x-start_offset, y+start_offset, table_high-1, 0, 180, 0)
        movel(ready_pos, vel=30, acc=50)
        
        # 4. 컴플라이언스(힘) 제어 활성화 
        # Z축 방향으로 부드럽게 반응하도록 설정
        time.sleep(0.1)
        task_compliance_ctrl(stx=[3000, 3000, 500, 100, 100, 100])
        
        # 5. Z축 방향으로 목표 힘(target_force) 인가 [cite: 13, 14]
        # 종이 방향(-Z)으로 일정한 힘을 유지
        time.sleep(0.1)
        set_desired_force(fd=[0, 0, -target_force, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0], mod=DR_FC_MOD_REL)
        
        # 6. 픽셀을 눈에 띄게 칠하기 위한 미세 지그재그 움직임 (Shading)
        # ref=DR_BASE : 로봇 베이스 좌표계 기준
        # mod=DR_MV_MOD_REL : 현재 위치 기준 상대 이동

        time.sleep(2)
        
        # 6-1. 시작점(좌측 상단)으로 미세 이동 (상대좌표)
        amovel(posx(-start_offset, start_offset, 0, 0, 0, 0), vel=10, acc=20, ref=DR_BASE, mod=DR_MV_MOD_REL)
        time.sleep(0.1)

        # 6-2. 'ㄹ'자 패턴으로 반복해서 색칠하기
        lines = int(pixel_size / pitch)
        direction = 1 # 1: 오른쪽으로 긋기, -1: 왼쪽으로 긋기
        
        for i in range(lines+1):
            # 가로로 선 긋기 (현재 방향으로 pixel_size 만큼 이동)
            amovel(posx(direction * pixel_size, 0, 0, 0, 0, 0), vel=10, acc=20, ref=DR_BASE, mod=DR_MV_MOD_REL)
            time.sleep(0.2)
            
            # 마지막 줄이 아니라면 아래로 한 칸(pitch) 내리기
            if i < lines:
                node.get_logger().info("한칸 내리기")
                node.get_logger().info(f"{i}")
                time.sleep(0.1)
                amovel(posx(0, -pitch, 0, 0, 0, 0), vel=10, acc=20, ref=DR_BASE, mod=DR_MV_MOD_REL)
                time.sleep(0.1)
                direction *= -1 # 다음 줄은 반대 방향으로 긋기 위해 방향 전환
                
        # 💡 로키의 팁: 
        # 이전 코드처럼 픽셀 정중앙으로 다시 복귀하는 모션은 생략했습니다. 
        # 어차피 8번 단계에서 절대좌표인 hover_pos(안전 높이)로 바로 떠오르기 때문에 동선 낭비를 줄이는 것이 효율적입니다.

        # 7. 힘 제어 종료 (연필 떼기)
        time.sleep(0.1)
        release_force()
        time.sleep(0.1)
        release_compliance_ctrl()
        
        # 8. 다시 안전 거리로 복귀
        time.sleep(0.1)
        movel(hover_pos, vel=100, acc=100)
            

    # ==========================================
    # 2. 메인 실행 블록 (Main Flow)
    # ==========================================

    # pixels = [
    # (400, 150, 5), # 어두운 픽셀 (5N의 힘)
    # (403, 150, 3), # 중간 픽셀 (3N의 힘)
    # (406, 150, 1)  # 밝은 픽셀 (그리지 않음)
    # ]

    pixels = [
    (400, 150, 10), # 어두운 픽셀 (5N의 힘)
    (404, 150, 9), # 중간 픽셀 (3N의 힘)
    (408, 150, 8),  # 밝은 픽셀 (그리지 않음)
    (412, 150, 7),
    (416, 150, 6),
    (420, 150, 5),
    (424, 150, 4),
    ]


    node.get_logger().info("픽셀 테스트 시작")

    # 메인 실행 루프
    for p in pixels:
        draw_pixel(p[0], p[1], p[2])
        node.get_logger().info("픽셀 테스트 진행")

    node.get_logger().info("픽셀 테스트 완료")

    # 노드 종료 처리
    rclpy.shutdown()

if __name__ == "__main__":
    main()
