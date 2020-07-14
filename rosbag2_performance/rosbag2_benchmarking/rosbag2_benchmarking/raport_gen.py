# Copyright 2020, Robotec.ai sp. z o.o.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Module for report generation based on benchmark results."""

import csv
import pathlib

import numpy as np

import rclpy
from rclpy.node import Node

import yaml


class Report:
    """Class for keeping all benchmark results and generating report."""

    base_time = 0
    title = 'Benchmark'
    benchmark_path = ''

    bag_message_captured_percents = {}
    bag_message_captured_num = {}
    bag_message_captured_expected = {}

    workers = {}

    cpu_utilization = {}
    cpu_utilization_t = []
    cpu_utilization_v = [[]]
    cpu_utilization_avg = []
    disk_utilization = {}
    disk_utilization_t = []
    disk_utilization_r = []
    disk_utilization_w = []
    mem_utilization = {}
    mem_utilization_t = []
    mem_utilization_v = []

    def __init__(self, logger):
        """Initialize report."""
        self.logger = logger

    def dump_report_yaml(self):
        """Dump report into yaml file."""
        # messages
        total_captured = 0
        total_expected = 0
        for topic, val in self.bag_message_captured_percents.items():
            total_captured += self.bag_message_captured_num[topic]
            total_expected += self.bag_message_captured_expected[topic]

        # disk
        disk_std_w = float(np.std(self.disk_utilization_w))
        disk_mean_w = float(np.mean(self.disk_utilization_w))
        disk_std_r = float(np.std(self.disk_utilization_r))
        disk_mean_r = float(np.mean(self.disk_utilization_r))

        # cpu
        cpu_std = float(np.std(self.cpu_utilization_v))
        cpu_mean = float(np.mean(self.cpu_utilization_v))

        # mem
        mem_std = float(np.std(self.mem_utilization_v))
        mem_mean = float(np.mean(self.mem_utilization_v))
        mem_min = float(np.min(self.mem_utilization_v))
        mem_max = float(np.max(self.mem_utilization_v))

        data = {
            'bechmark': {
                'title': self.title,
            },
            'messages': {
                'captured': total_captured,
                'expected': total_expected,
                'percent': total_captured/total_expected * 100
            },
            'disk': {
                'write': {
                    'mean': disk_mean_w,
                    'std': disk_std_w,
                },
                'read': {
                    'mean': disk_mean_r,
                    'std': disk_std_r,
                },
            },
            'cpu': {
                'mean': cpu_mean,
                'std': cpu_std,
            },
            'memory': {
                'mean': mem_mean,
                'std': mem_std,
                'min': mem_min,
                'max': mem_max,
            }
        }
        with open(str(pathlib.Path(
                    self.benchmark_path
                    ).joinpath('report.yaml')), 'w') as outfile:
            yaml.dump(data, outfile, default_flow_style=False)

    def generate_plots(self):
        """Generate disk, cpu and memory utilization plots."""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(2, 3, figsize=(15, 6))
        fig.suptitle(self.title, fontsize=16)

        x = [(v - self.base_time)/1000000 for v in self.cpu_utilization_t]
        for cpu_timings in self.cpu_utilization_v:
            y = cpu_timings
            ax[0, 0].set_title('CPU utilization per core [%]')
            ax[0, 0].plot(x, y)

        y = self.cpu_utilization_avg
        ax[1, 0].set_title('CPU utilization average [%]')
        ax[1, 0].plot(x, y)

        x = [(v - self.base_time)/1000000 for v in self.disk_utilization_t]
        y = self.disk_utilization_r
        ax[0, 1].set_title('Disk read [MB/s]')
        ax[0, 1].plot(x, y)
        y = self.disk_utilization_w
        ax[1, 1].set_title('Disk write [MB/s]')
        ax[1, 1].plot(x, y)

        x = [(v - self.base_time)/1000000 for v in self.mem_utilization_t]
        y = self.mem_utilization_v
        ax[0, 2].set_title('Memory used [MB]')
        ax[0, 2].plot(x, y)

        plt.savefig(str(pathlib.Path(
            self.benchmark_path).joinpath('plots.jpg')))

    def get_messages_captured_str(self):
        """Generate capture report result in a string."""
        message = ''
        total_captured = 0
        total_expected = 0
        for topic, val in self.bag_message_captured_percents.items():
            total_captured += self.bag_message_captured_num[topic]
            total_expected += self.bag_message_captured_expected[topic]
            message += \
                "'{topic}': {captured}/{expected} ({percent:.4f}%)\n".format(
                    topic=topic,
                    captured=self.bag_message_captured_num[topic],
                    expected=self.bag_message_captured_expected[topic],
                    percent=val
                )
        message += \
            '\n Total: \n {captured}/{expected} ({percent:.4f}%)'.format(
                topic=topic,
                captured=total_captured,
                expected=total_expected,
                percent=total_captured/total_expected * 100
            )
        return message

    def get_workers_str(self):
        """Get workers report in a string."""
        message = ''
        for topic, val in self.workers.items():
            message += \
                "{type}:{name} - {instances} instance(s) \
                    on '{topic}' at {frequency}Hz\n".format(
                    type=val['type'],
                    instances=val['instances'],
                    name=val['name'],
                    topic=topic,
                    frequency=val['frequency']
                )
        return message

    def __str__(self):
        """Get full report in a string."""
        result_log = """
----------------------------------
Report

==================================
Workers:
{workers}
==================================
Messages captured:
{bag_message_captured}
==================================
""".format(
            bag_message_captured=self.get_messages_captured_str(),
            workers=self.get_workers_str())
        return result_log


class ReportGen(Node):
    """Report generator."""

    bag_metadata = {}
    bag_record_start_time = None

    def __init__(self):
        """Report generator."""
        super().__init__('report_gen')
        self.logger = rclpy.logging.get_logger('REPORT')
        self.result = Report(self.logger)

        self.declare_parameter('report_dir', str(pathlib.Path.cwd()))
        self.report_dir = pathlib.Path(
            self.get_parameter('report_dir').get_parameter_value().string_value
        ).expanduser()

        self.declare_parameter('description', '')
        config_path = self.get_parameter(
            'description'
        ).get_parameter_value().string_value
        if config_path == '':
            raise RuntimeError(
                'You must specify a description file: \n\
                 --ros-args -p description:=[PATH]')

        # Manage config file
        self.config = None
        path = pathlib.Path(config_path)
        if path.is_file():
            with open(path) as config_file:
                self.config = yaml.load(config_file)
        else:
            raise RuntimeError(
                '{} is not correct yaml config file.'.format(path))

        self.benchmark_path = pathlib.Path.joinpath(
            pathlib.Path(self.report_dir),
            pathlib.Path(
                str(self.config['benchmark']['id']) +
                '-' + self.config['benchmark']['tag']
            ))
        if self.__parse_bag_metadata():
            self.__generate_report()

    def __parse_bag_metadata(self):
        bag_dir = self.benchmark_path.joinpath('bag')
        metadata_file = bag_dir.joinpath('metadata.yaml')
        if not metadata_file.exists():
            self.logger.error(
                '{} does not exits. Skipping.'.format(str(metadata_file))
            )
            return False
        with open(metadata_file) as bag_metadata_file:
            bag_metadata = yaml.load(bag_metadata_file)
        self.bag_record_start_time = \
            bag_metadata.get('rosbag2_bagfile_information') \
            .get('starting_time') \
            .get('nanoseconds_since_epoch')
        for topic_metadata in bag_metadata.get('rosbag2_bagfile_information') \
                .get('topics_with_message_count'):
            self.bag_metadata.update({
                topic_metadata.get('topic_metadata').get('name'): {
                    'type': topic_metadata.get('topic_metadata').get('type'),
                    'message_count': topic_metadata.get('message_count'),
                    'serialization_format': topic_metadata.get(
                        'topic_metadata'
                    ).get('serialization_format')
                    }})
        return True

    def __generate_report(self):
        workers = self.config['workers']
        topic_msgs_accumulated = {}
        workers_result = {}

        # Workers info
        for worker in workers:
            for key in ['image', 'pointcloud2', 'bytearray']:
                if worker.get(key):
                    worker_info = worker.get(key)
                    for i in range(0,  worker_info['instances']):
                        # Get worker info from config file
                        if worker_info.get('same_topic', True):
                            worker_topic = worker_info['topic']
                            workers_result.update(
                                {
                                    '/' + worker_topic: {
                                        'name': worker_info['name'],
                                        'frequency': worker_info['frequency'],
                                        'instances': worker_info['instances'],
                                        'type': key
                                    }
                                })
                            # Currently accumulated number of messages
                            # for given topic
                            current_topic_msg_count = \
                                topic_msgs_accumulated.get('/'+worker_topic, 0)
                            # Update msg count for topic
                            current_topic_msg_count += \
                                worker_info['max_count'] * \
                                worker_info['instances']
                            topic_msgs_accumulated.update(
                                {
                                    '/' + worker_topic: current_topic_msg_count
                                })
                            break
                        else:
                            worker_topic = worker_info['topic'] + str(i)
                            workers_result.update(
                                {
                                    '/' + worker_topic: {
                                        'name': worker_info['name'],
                                        'frequency': worker_info['frequency'],
                                        'instances': 1,
                                        'type': key
                                    }
                                })
                            # Currently accumulated number of messages for
                            # given topic
                            current_topic_msg_count = \
                                topic_msgs_accumulated.get(
                                    '/'+worker_topic,
                                    0
                                )
                            # Update msg count for topic
                            current_topic_msg_count += worker_info['max_count']
                            topic_msgs_accumulated.update(
                                {
                                    '/' + worker_topic: current_topic_msg_count
                                })
        self.result.workers = workers_result

        # Calculate percent of msgs saved in bag
        for topic, expected_msg_count in topic_msgs_accumulated.items():
            val = self.bag_metadata[topic]['message_count']/expected_msg_count
            self.result.bag_message_captured_percents.update(
                {topic: val * 100}
            )
            self.result.bag_message_captured_num.update(
                {topic: self.bag_metadata[topic]['message_count']}
            )
            self.result.bag_message_captured_expected.update(
                {topic: expected_msg_count}
            )

        # CPU utilization
        path = self.benchmark_path.joinpath('system_cpu.csv')
        with open(path, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=';')
            first_record = True
            for row in reader:
                self.result.cpu_utilization_t.append(int(row[0]))
                cpus_number = len(row[2:])
                if first_record:
                    for i in range(2, cpus_number):
                        self.result.cpu_utilization_v.append([])
                    first_record = False

                self.result.cpu_utilization_avg.append(float(row[1]))
                for i in range(2, len(row)-1):
                    self.result.cpu_utilization_v[i-2].append(float(row[i]))

        # Disk utilization
        path = self.benchmark_path.joinpath('system_disk.csv')
        with open(path, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=';')
            for row in reader:
                self.result.disk_utilization.update(
                    {int(row[0]): [float(x) for x in row[1:]]}
                )
                self.result.disk_utilization_t.append(int(row[0]))
                self.result.disk_utilization_r.append(float(row[1])/1000)
                self.result.disk_utilization_w.append(float(row[2])/1000)

        # Memory utilization
        path = self.benchmark_path.joinpath('system_mem.csv')
        with open(path, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=';')
            for row in reader:
                self.result.mem_utilization.update(
                    {int(row[0]): [float(x) for x in row[1:]]}
                )
                self.result.mem_utilization_t.append(float(row[0]))
                self.result.mem_utilization_v.append(float(row[1])/1000000)

        # Print report
        self.result.base_time = self.bag_record_start_time
        self.result.benchmark_path = self.benchmark_path
        self.result.title = self.config['benchmark']['name']
        self.result.generate_plots()
        self.result.dump_report_yaml()
        self.logger.info(str(self.result))


def main():
    """Ros2 once-spin run."""
    rclpy.init()
    node = ReportGen()
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.1)
        rclpy.shutdown()
    node.destroy_node()


if __name__ == '__main__':
    main()
