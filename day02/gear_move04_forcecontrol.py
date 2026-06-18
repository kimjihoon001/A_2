# ==========================================
# 0. 공통 헬퍼(Helper) 함수
# ==========================================
def gripper_open():
    """그리퍼를 여는 함수"""
    set_digital_output(1, ON)
    set_digital_output(2, OFF)

def gripper_close(wait_time=2.5):
    """그리퍼를 닫고 확실히 쥘 때까지 대기하는 함수"""
    set_digital_output(2, ON)
    set_digital_output(1, OFF)
    wait(wait_time)


# ==========================================
# 1. 작업 단계별 주요 함수
# ==========================================
def pick_gear(pos_up, pos_down):
    """기어를 집어 올리는 단계"""
    gripper_open()
    movel(pos_up, v=50, a=100)
    movel(pos_down, v=50, a=100)
    gripper_close()

def move_to_standby(pos_up, pos_standby):
    """조립을 위해 대기 위치로 이동하는 단계"""
    movel(pos_up, v=50, a=100)
    movel(pos_standby, v=50, a=100)
    wait(2.5)

def assemble_gear_with_force():
    """힘 제어를 사용하여 기어를 조립하고 성공 여부를 반환하는 단계"""
    # 순응 제어 & 힘 제어 On
    task_compliance_ctrl([300, 300, 300, 100, 100, 100])
    set_desired_force([0, 0, -30, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0])

    # 바닥에 닿을 때까지 대기
    while get_tool_force()[2] <= 5:
        wait(0.1)

    # 기어가 맞물려 들어가도록 3°씩 10번 회전
    for i in range(10):
        movel([0, 0, 0, 0, 0, 3], v=20, a=40, mod=DR_MV_MOD_REL)

    # 조립 성공 여부 판별
    current_z = get_current_posx()[0][2]
    if current_z <= 270:
        return True  # 성공
    else:
        return False # 실패

def handle_assembly_error(pos_safe):
    """조립 실패 시 이물질을 제거하고 작업자 개입을 기다리는 단계"""
    tp_popup("이물질을 제거해주세요. 완료 후 로봇의 툴을 쳐주세요.")

    release_force()
    release_compliance_ctrl()
    movel(pos_safe, v=50, a=100) # 안전 위치로 후퇴

    # 작업자가 로봇을 툭 칠 때까지(X축 4N 이상) 무한 대기
    while True:
        f = get_tool_force()
        Scalar = (f[0]**2 + f[1]**2 + f[2]**2)**0.5
        if Scalar >=4:
            break
        wait(0.1)

def finish_task(pos_final):
    """모든 제어를 해제하고 로봇을 최종 대기 위치로 이동시키는 단계"""
    release_force()
    wait(0.5)
    release_compliance_ctrl()
    gripper_open()

    movel(pos_final, v=50, a=200)

    # 다음 임무를 위해 대기
    while True:
        f = get_tool_force()
        # x축 힘을 받으면 0번 임무 실행
        if abs(f[0]) >= 4:
            return 0
        # z축 힘을 받으면 1번 임무 실행
        elif abs(f[2]) >= 4:
            return 1
        wait(0.1)




# ==========================================
# 2. 메인 실행 블록 (Main Flow)
# ==========================================
def main():
    # 위치 변수 가져오기
    pos_left_up = Global_LUP
    pos_left_down = Global_LDOWN
    pos_right_up = Global_RUP
    pos_right_down = Global_RDOWN

    # R기어의 글로벌 좌표값을 리스트로 정리
    # 0번 인덱스는 비워두고 1, 2, 3번 인덱스에 매칭
    posR_right_up   = [None, Global_RGEAR1_RUP,   Global_RGEAR2_RUP,   Global_RGEAR3_RUP]
    posR_right_down = [None, Global_RGEAR1_RDOWN, Global_RGEAR2_RDOWN, Global_RGEAR3_RDOWN]
    posR_left_up    = [None, Global_RGEAR1_LUP,   Global_RGEAR2_LUP,   Global_RGEAR3_LUP]
    posR_left_down  = [None, Global_RGEAR1_LDOWN, Global_RGEAR2_LDOWN, Global_RGEAR3_LDOWN]

    # 1. 픽업
    pick_gear(pos_left_up, pos_left_down)

    # 2. 대기 위치로 이동
    move_to_standby(pos_left_up, pos_right_up)

    # 3. 조립 시도 루프
    while True:
        is_success = assemble_gear_with_force()

        if is_success:
            break # 성공 시 루프 탈출하고 마무리로 이동
        else:
            handle_assembly_error(pos_right_up) # 에러 처리 후 다시 루프 반복

    # 4. 작업 종료 및 복귀
    task = finish_task(pos_right_up)

    while True:
        # 0번 임무 시행
        if task == 0:
            pick_gear(pos_right_up, pos_right_down)
            move_to_standby(pos_right_up, pos_left_up)
            while True:
                is_success = assemble_gear_with_force()

                if is_success:
                    break # 성공 시 루프 탈출하고 마무리로 이동
                else:
                    handle_assembly_error(pos_left_up) # 에러 처리 후 다시 루프 반복

            task = finish_task(pos_left_up)

        # 1번 임무 실행
        if task == 1:
            # 3개의 R기어에 대한 동작을 for문으로 구현
            for i in (range(1,4)):
                pick_gear(posR_right_up[i],posR_right_down[i])
                move_to_standby(posR_right_up[i],posR_left_up[i])
                while True:
                    is_success = assemble_gear_with_force()

                    if is_success:
                        break
                    else:
                        handle_assembly_error(posR_left_up[i])

                release_force()
                wait(0.5)
                release_compliance_ctrl()
                gripper_open()
                move_to_standby(posR_left_up[i], posR_left_up[i])

            task = finish_task(pos_left_up)


# 프로그램 시작
main()