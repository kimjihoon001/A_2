import rclpy
from rclpy.node import Node
from dsr_msgs2.srv import ServoOff


class ServoOffClient(Node):

    def __init__(self):
        super().__init__('servo_off_client')
        self.client = self.create_client(ServoOff, '/dsr01/system/servo_off')

        while not self.client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('서비스 대기 중...')

    def send_request(self):
        req = ServoOff.Request()
        req.stop_type = ServoOff.Request.STOP_TYPE_QUICK
        self.client.call_async(req)


def main(args=None):
    rclpy.init(args=args)
    node = ServoOffClient()
    node.create_timer(0.1, node.send_request)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
