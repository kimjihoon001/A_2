import rclpy
from rclpy.node import Node
from dsr_msgs2.srv import SetRobotControl


class ServoOnClient(Node):

    def __init__(self):
        super().__init__('servo_on_client')
        self.client = self.create_client(SetRobotControl, '/dsr01/system/set_robot_control')

        while not self.client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('서비스 대기 중...')

    def send_request(self):
        req = SetRobotControl.Request()
        req.robot_control = 3  # CONTROL_RESET_SAFET_OFF → STATE_STANDBY
        future = self.client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        return future.result()


def main(args=None):
    rclpy.init(args=args)
    node = ServoOnClient()

    result = node.send_request()
    if result.success:
        node.get_logger().info('서보 온 성공')
    else:
        node.get_logger().error('서보 온 실패')

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
