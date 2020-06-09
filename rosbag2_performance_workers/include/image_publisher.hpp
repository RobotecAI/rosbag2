#include <chrono>
#include <string>
#include <vector>
#include <memory>

#include "rclcpp/clock.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "std_msgs/msg/header.hpp"
#include "std_msgs/msg/empty.hpp"

using std::placeholders::_1;
using namespace std::chrono_literals;  // NOLINT

std::vector<uint8_t> randomImageData(size_t size) {
  std::vector<uint8_t> pixels(size, 0);

  for (size_t i = 0; i < size; ++i) {
    pixels[i] = std::rand() % 255;
  }
  return pixels;
}

namespace nodes {

class ImagePublisher : public rclcpp::Node {
public:
  ImagePublisher(const std::string & name, const std::string & topic)
  : Node(name)
  {
    this->declare_parameter("dt");
    this->declare_parameter("max_count");
    this->declare_parameter("dimensions");
    this->declare_parameter("delay");
    this->declare_parameter("benchmark_path");

    auto parameters_client = std::make_shared<rclcpp::SyncParametersClient>(this);
    while (!parameters_client->wait_for_service(1s)) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(this->get_logger(), "Interrupted while waiting for the service. Exiting.");
        rclcpp::shutdown();
      }
      RCLCPP_INFO(this->get_logger(), "service not available, waiting again...");
    }

    dt = parameters_client->get_parameter<uint32_t>("dt", 10);
    max_count = parameters_client->get_parameter<uint32_t>("max_count", 100);
    dimensions = parameters_client->get_parameter<uint32_t>("dimensions", 1024);
    delay = parameters_client->get_parameter<uint32_t>("delay", 0);
    benchmark_path = parameters_client->get_parameter<std::string>("benchmark_path", "");

    publisher = this->create_publisher<sensor_msgs::msg::Image>(topic, 10);
    delay_timer = this->create_wall_timer(std::chrono::milliseconds(delay), std::bind(&ImagePublisher::delay_callback, this));
    random_image_data = randomImageData(dimensions * 4 * dimensions);  // image step * height
  }

private:
  void delay_callback()
  {
    std::cout << this->get_name() <<  ": Delay finished" << std::endl;
    timer = this->create_wall_timer(std::chrono::milliseconds(dt), std::bind(&ImagePublisher::timer_callback, this));
    delay_timer->cancel();
  }
  void timer_callback()
  {
    uint32_t static current_msg_count = 0;

    auto message = sensor_msgs::msg::Image();
    message.header = std_msgs::msg::Header();
    message.header.frame_id = "image_frame";
    message.header.stamp = rclcpp::Clock().now();

    message.encoding = "rgba8";
    message.height = static_cast<sensor_msgs::msg::Image::_height_type>(dimensions);
    message.width = static_cast<sensor_msgs::msg::Image::_width_type>(dimensions);
    message.step = static_cast<sensor_msgs::msg::Image::_step_type>(dimensions * 4);
    message.data = random_image_data;

    publisher->publish(message);

    std::cout << this->get_name() << ": " << current_msg_count << std::endl;
    if(++current_msg_count == max_count) {
      timer->cancel();
      rclcpp::shutdown();
    }

    //(piotr.jaroszek) TODO: raport data here and save to benchmark_path
  }

  std::vector<uint8_t> random_image_data;
  std::string benchmark_path;
  uint32_t dt;
  uint32_t max_count;
  uint32_t dimensions;
  uint32_t delay;
  rclcpp::TimerBase::SharedPtr timer;
  rclcpp::TimerBase::SharedPtr delay_timer;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr publisher;
};

}  // namespace nodes