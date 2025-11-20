"""资源监控模块"""
import time
from typing import Dict, Optional

import psutil

from general_pipeline.utils.log_utils import get_logger

logger = get_logger()


class ResourceMonitor:
    """资源监控器，监控进程的CPU、内存、磁盘IO、网络IO"""

    def __init__(self, pid: int, monitor_interval: int = 5):
        """
        初始化资源监控器
        :param pid: 要监控的进程ID
        :param monitor_interval: 监控间隔（秒）
        """
        self.pid = pid
        self.monitor_interval = monitor_interval
        self.process: Optional[psutil.Process] = None
        try:
            self.process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            logger.error(f"进程 {pid} 不存在，无法监控")

    def get_resource_usage(self) -> Dict[str, float]:
        """
        获取当前资源使用情况
        :return: 资源使用字典
        """
        if not self.process or not self.process.is_running():
            return {}

        try:
            # CPU使用率（百分比）
            cpu_usage = self.process.cpu_percent(interval=0.1)

            # 内存使用（MB）
            mem_info = self.process.memory_info()
            mem_usage_mb = mem_info.rss / (1024 * 1024)

            # 磁盘IO（MB/s）- 需要两次采样计算差值
            try:
                io_counters_1 = self.process.io_counters()
                time.sleep(0.1)
                io_counters_2 = self.process.io_counters()
                disk_read_mb_s = (io_counters_2.read_bytes - io_counters_1.read_bytes) / (1024 * 1024) / 0.1
                disk_write_mb_s = (io_counters_2.write_bytes - io_counters_1.write_bytes) / (1024 * 1024) / 0.1
            except (AttributeError, psutil.AccessDenied):
                disk_read_mb_s = 0.0
                disk_write_mb_s = 0.0

            # 网络IO（MB/s）- 从系统级别获取
            try:
                net_io_1 = psutil.net_io_counters()
                time.sleep(0.1)
                net_io_2 = psutil.net_io_counters()
                net_sent_mb_s = (net_io_2.bytes_sent - net_io_1.bytes_sent) / (1024 * 1024) / 0.1
                net_recv_mb_s = (net_io_2.bytes_recv - net_io_1.bytes_recv) / (1024 * 1024) / 0.1
            except (AttributeError, psutil.AccessDenied):
                net_sent_mb_s = 0.0
                net_recv_mb_s = 0.0

            return {
                "cpu_usage": round(cpu_usage, 2),
                "mem_usage_mb": round(mem_usage_mb, 2),
                "disk_read_mb_s": round(disk_read_mb_s, 2),
                "disk_write_mb_s": round(disk_write_mb_s, 2),
                "net_sent_mb_s": round(net_sent_mb_s, 2),
                "net_recv_mb_s": round(net_recv_mb_s, 2)
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.warning(f"获取进程 {self.pid} 资源使用失败: {e}")
            return {}

    def log_resource_usage(self, pipeline_id: str, node_id: str, operator_id: str) -> None:
        """
        记录资源使用情况到日志
        :param pipeline_id: 产线ID
        :param node_id: 节点ID
        :param operator_id: 算子ID
        """
        resource_usage = self.get_resource_usage()
        if resource_usage:
            logger.info(
                f"资源监控 | pipeline_id={pipeline_id} | node_id={node_id} | "
                f"operator_id={operator_id} | resource={resource_usage}"
            )
