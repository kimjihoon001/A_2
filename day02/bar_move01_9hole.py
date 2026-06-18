Global_home = posx(399.82,-50.28,363.78,170.36,179.43,170.25)

set_singular_handling(DR_AVOID)
set_velj(60.0)
set_accj(100.0)
set_velx(250.0, 80.625, DR_OFF)
set_accx(1000.0, 322.5)
gLoop162845253 = 0

while gLoop162845253 < 1:
    # CustomCodeNode
    # ==========================================
    # 0. 공통 헬퍼(Helper) 함수
    # ==========================================
    def bar_open():
        """그리퍼를 여는 함수"""
        set_digital_output(1, ON)
        set_digital_output(2, OFF)
    
    def bar_close(wait_time=2.5):
        """그리퍼를 닫고 확실히 쥘 때까지 대기하는 함수"""
        set_digital_output(2, ON)
        set_digital_output(1, OFF)
        wait(wait_time)

    def position_up(Global_home):
        """hole_up 좌표 초기화 함수"""
        holes = []
        pitch = 53
        for y_idx in range(3):
            hole = []
            for x_idx in range(3):   
                
                p = posx(
                    Global_home[0] + pitch * x_idx,
                    Global_home[1] - pitch * y_idx,
                    Global_home[2],
                    Global_home[3],
                    Global_home[4],
                    Global_home[5]
                )
                hole.append(p)
            holes.append(hole)
        return holes
    
    
    # ==========================================
    # 1. 작업 단계별 주요 함수
    # ==========================================
    def pick_bar_first(Global_home):
        """(0,0) hole bar 잡기"""
        bar_open()
        p = posx(
                    Global_home[0],
                    Global_home[1],
                    Global_home[2]-100,
                    Global_home[3],
                    Global_home[4],
                    Global_home[5]
                )
        movel(p, 50, 100)
        bar_close()
    
    def assemble_bar_with_force():
        """힘 제어를 사용하여 기어를 조립하고 성공 여부를 반환하는 단계"""
        # 순응 제어 & 힘 제어 On
        task_compliance_ctrl([3000, 3000, 300, 3000, 3000, 3000])
        set_desired_force([0, 0, -30, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0])
    
        # 바닥에 닿을 때까지 대기
        while True:
            f = get_tool_force()
            Scalar = (f[0]**2 + f[1]**2 + f[2]**2)**0.5
            if Scalar >=5:
                break
            wait(0.1)

        # 조립 성공 여부 판별
        current_z = get_current_posx()[0][2]
        if current_z <= 270:
            return True  # 성공
        else:
            return False # 실패
    
    def handle_assembly_error(pos_safe):
        """조립 실패 시 이물질을 제거하고 작업자 개입을 기다리는 단계"""
        tp_popup("이물질을 제거해주세요. 완료 후 로봇의 툴을 쳐주세요.")
        pos_safe_up(pos_safe)
        
        # 작업자가 로봇을 툭 칠 때까지(X축 4N 이상) 무한 대기
        while True:
            f = get_tool_force()
            Scalar = (f[0]**2 + f[1]**2 + f[2]**2)**0.5
            if Scalar >=4:
                break
    def pos_safe_up(pos_safe):
        p = posx(
                    pos_safe[0],
                    pos_safe[1],
                    pos_safe[2]+100,
                    pos_safe[3],
                    pos_safe[4],
                    pos_safe[5]
                )
        release_force()
        release_compliance_ctrl()
        movel(p, 50, 100)

    # ==========================================
    # 2. 메인 실행 블록 (Main Flow)
    # ==========================================
    def main():
        # 위치 변수 가져오기
        pos_home = Global_home
        # hole 위치 포지션 초기화
        holes_up = []
        holes_up = position_up(pos_home)
        
        # 초기 위치 이동후 집기
        movel(holes_up[0][0], v=50, a=100)
        wait(2.5)
        pick_bar_first(holes_up[0][0])
    
        # 8개 홀에 넣어 보기
        for i in range(3):
            for j in range(3):  
                movel(holes_up[i][j], 50, 100)
                
                # 다른 hole로 이동
                if j%3 == 0 or j%3 ==1:
                    movel(holes_up[i][j+1], 50, 100)                        
                else:
                    if i == 2 and j == 2:
                        movel(holes_up[0][0], 50, 100)
                    else:
                        movel(holes_up[i+1][0], 50, 100)
        
                # hole 조립 시도 루프
                while True:
                    is_success = assemble_bar_with_force()
                    if is_success:
                        # 성공 시 순응 제어 & 힘 제어 Off 루프 탈출
                        release_force()
                        release_compliance_ctrl()
                        break  
                    else:
                        # 실패 시 순응 제어 & 힘 제어 Off 재조립 시도
                        release_force()
                        release_compliance_ctrl()                       
        
        bar_open()
        move(pos_home)
    # 프로그램 시작
    main()
    gLoop162845253 = gLoop162845253 + 1