import time
import rclpy
import threading
import cv2
import numpy as np
import DR_init

# 로봇 기본 설정
ROBOT_ID = "dsr01"
ROBOT_MODEL = "m0609"

DR_init.__dsr__id = ROBOT_ID
DR_init.__dsr__model = ROBOT_MODEL

def main(args=None):
    rclpy.init(args=args)
    node = rclpy.create_node("/home/rokey/ws_cobot1_pjt/ws_edu/test.png", namespace=ROBOT_ID)
    DR_init.__dsr__node = node

    # DSR_ROBOT2 API 임포트
    try:
        from DSR_ROBOT2 import (
            movel,
            amovel,
            task_compliance_ctrl,
            set_desired_force,
            release_force,
            release_compliance_ctrl,
            DR_FC_MOD_REL,
            DR_BASE,
            DR_MV_MOD_REL
        )
        from DR_common2 import posx
    except ImportError as e:
        node.get_logger().error(f"Error importing DSR_ROBOT2 : {e}")
        return

    # ==========================================
    # 🤖 작업자 스레드: 맵핑 + 드로잉 로직
    # ==========================================
    def robot_task_sequence():
        node.get_logger().info("🎨 명암 드로잉 스레드 시작")

        # ------------------------------------------
        # [1단계] 이미지 변환 및 좌표 맵핑
        # ------------------------------------------
        try:
            # 이미지 로드 (동일 폴더에 my_drawing.jpg 필요)
            img = cv2.imread('my_drawing.jpg', cv2.IMREAD_GRAYSCALE)
            if img is None:
                node.get_logger().error("이미지를 찾을 수 없습니다! 경로를 확인하세요.")
                return
            
            # 해상도 설정 (예: 20x20 픽셀 -> 4mm씩 8cm x 8cm 그림)
            img = cv2.resize(img, (20, 20))
        except Exception as e:
            node.get_logger().error(f"이미지 처리 오류: {e}")
            return

        # 0~255 명암값을 0~8 레벨로 양자화
        levels = np.round((img / 255.0) * 8).astype(np.uint8)

        robot_commands = []
        START_X, START_Y = 400.0, 100.0
        PIXEL_SIZE = 1.0 # draw_pixel 함수의 pixel_size와 동일하게 설정

        for row in range(levels.shape[0]):
            for col in range(levels.shape[1]):
                level = levels[row, col]
                
                # 레벨 8(흰색)은 그리지 않고 통과
                if level == 8:
                    continue
                    
                # 힘 맵핑: 레벨 0 -> 10.0N, 레벨 7 -> 3.0N (양수 크기만 전달)
                target_force = 10.0 - float(level)
                
                target_x = START_X + (col * PIXEL_SIZE)
                target_y = START_Y - (row * PIXEL_SIZE)
                
                robot_commands.append({
                    'x': target_x, 
                    'y': target_y, 
                    'force': target_force
                })

        node.get_logger().info(f"총 {len(robot_commands)}개의 픽셀 추출 완료. 그리기를 시작합니다.")

        # ------------------------------------------
        # [2단계] 회원님께서 작성하신 단일 픽셀 셰이딩 함수
        # ------------------------------------------
        def draw_pixel(x, y, target_force):
            table_high = 242.0
            pixel_size = 1.0  
            pitch = 1.0       
            start_offset = pixel_size / 2.0
            
            # 1. 그리지 않는 픽셀은 스킵 (양수 크기 검사)
            if target_force <= 0:
                return
                
            # 2. 픽셀 좌표 상공(안전 거리)으로 이동 (리스트 형태로 묶음)
            hover_pos = posx([x-start_offset, y+start_offset, table_high+50.0, 0.0, 180.0, 0.0])
            movel(hover_pos, vel=100.0, acc=100.0) 
            time.sleep(0.1)
            
            # 3. 종이 표면 근처로 하강
            ready_pos = posx([x-start_offset, y+start_offset, table_high-1.0, 0.0, 180.0, 0.0])
            movel(ready_pos, vel=30.0, acc=50.0)
            time.sleep(0.1)
            
            # 4. 컴플라이언스(힘) 제어 활성화 
            task_compliance_ctrl([3000.0, 3000.0, 500.0, 100.0, 100.0, 100.0])
            time.sleep(0.1)
            
            # 5. Z축 방향으로 목표 힘 인가 (-target_force로 음수 변환됨)
            set_desired_force([0.0, 0.0, -target_force, 0.0, 0.0, 0.0], dir=[0, 0, 1, 0, 0, 0], mod=DR_FC_MOD_REL)
            time.sleep(2.0)
            
            # 6. 'ㄹ'자 패턴 반복해서 색칠하기
            lines = int(pixel_size / pitch)
            direction = 1 
            
            for i in range(lines+1):
                if not rclpy.ok(): break
                
                # 가로로 선 긋기
                amovel(posx([direction * pixel_size, 0.0, 0.0, 0.0, 0.0, 0.0]), vel=10.0, acc=20.0, ref=DR_BASE, mod=DR_MV_MOD_REL)
                time.sleep(0.2)
                
                if i < lines:
                    # 아래로 한 칸 내리기
                    amovel(posx([0.0, -pitch, 0.0, 0.0, 0.0, 0.0]), vel=10.0, acc=20.0, ref=DR_BASE, mod=DR_MV_MOD_REL)
                    time.sleep(0.1)
                    direction *= -1 
                    
            # 7. 힘 제어 종료 (연필 떼기)
            time.sleep(0.1)
            release_force()
            time.sleep(0.1)
            release_compliance_ctrl()
            time.sleep(0.1)
            
            # 8. 다시 안전 거리로 복귀
            movel(hover_pos, vel=100.0, acc=100.0)

        # ------------------------------------------
        # [3단계] 메인 그리기 루프
        # ------------------------------------------
        for idx, cmd in enumerate(robot_commands):
            if not rclpy.ok(): break
            node.get_logger().info(f"[{idx+1}/{len(robot_commands)}] 좌표: ({cmd['x']:.1f}, {cmd['y']:.1f}) | 힘: {cmd['force']}N")
            
            draw_pixel(cmd['x'], cmd['y'], cmd['force'])

        node.get_logger().info("✅ 모든 픽셀 드로잉 작업이 완료되었습니다!")

    # ==========================================
    # 메인 스레드: 스레드 생성 및 spin 통신
    # ==========================================
    task_thread = threading.Thread(target=robot_task_sequence, daemon=True)
    task_thread.start()

    try:
        node.get_logger().info("통신 스레드 가동: 제어기와 통신 중...")
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("사용자에 의해 종료됩니다.")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()