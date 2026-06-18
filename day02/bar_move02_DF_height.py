def gripper_open():
    """그리퍼를 여는 함수"""
    set_digital_output(1, ON)
    set_digital_output(2, OFF)

def gripper_close(wait_time=2.5):
    """그리퍼를 닫고 확실히 쥘 때까지 대기하는 함수"""
    set_digital_output(2, ON)
    set_digital_output(1, OFF)
    wait(wait_time)


# 높이측정 후 블럭 집어올리기
def pick_block():
    gripper_close() # 닫힌 상태로 프로빙(탐색) 시작

    # 순응제어, 힘제어 ON (Z축 방향으로 -30N 누르기)
    task_compliance_ctrl([3000, 3000, 300, 3100, 3100, 3100])
    set_desired_force([0, 0, -30, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0])

    # 바닥에 닿을 때까지 대기 (안전을 위해 절댓값 abs 사용)
    while abs(get_tool_force()[2]) <= 5:
        wait(0.1)

    # 닿았을 때 높이 측정
    pick_pos = get_current_posx()[0]

    # 순응제어, 힘제어 OFF
    release_force()
    release_compliance_ctrl()

    # 그리퍼 살짝 올리고 열기
    pick_pos[2] += 20
    movel(pick_pos, v=50, a=100)
    gripper_open()

    # 그리퍼를 파지 깊이로 내리기 (접촉면 기준 20mm 아래)
    pick_pos[2] -= 40
    movel(pick_pos, v=50, a=100)
    gripper_close()

    # 블록 쥐고 안전 높이로 올리기
    pick_pos[2] = 363
    movel(pick_pos, v=50, a=100)


def place_block():
    # 순응제어, 힘제어 ON (Z축 방향으로 -30N 누르기)
    task_compliance_ctrl([3000, 3000, 300, 3000, 3000, 3000])
    set_desired_force([0, 0, -30, 0, 0, 0], dir=[0, 0, 1, 0, 0, 0])

    # 바닥에 닿을 때까지 대기
    while abs(get_tool_force()[2]) <= 5:
        wait(0.1)

    # [수정됨] 닿은 순간의 위치를 변수에 저장!
    place_pos = get_current_posx()[0]

    # 순응제어, 힘제어 OFF
    release_force()
    release_compliance_ctrl()

    # 살짝 들어 올려서 짓눌림 방지 후 그리퍼 열기
    place_pos[2] += 10
    movel(place_pos, v=50, a=100)
    gripper_open()

    # 복귀를 위해 위로 이탈
    place_pos[2] = 300
    movel(place_pos, v=50, a=100)


# 메인 작업 루프 (3x3 배열)
for x in range(3):
    for y in range(3):
        # [수정됨] Global_pos 원본이 훼손되지 않도록 .copy() 사용!
        start_pos = Global_pos[:]
        start_pos[0] += 54 * x
        start_pos[1] -= 53 * y

        # [수정됨] start_pos 원본이 훼손되지 않도록 .copy() 사용!
        goal_pos = start_pos[:]
        goal_pos[1] += 150

        # 해당 픽셀 위치로 이동하여 블록 집기
        movel(start_pos, v=50, a=100)
        pick_block()

        # 150mm 떨어진 목표 위치로 이동하여 블록 놓기
        movel(goal_pos, v=50, a=100)
        place_block()