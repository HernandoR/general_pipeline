"""算子基类 BasicRunner"""
import os
from abc import ABC, abstractmethod

from general_pipeline.utils.log_utils import get_logger

logger = get_logger()


class BasicRunner(ABC):
    """
    算子基类，提供标准化路径管理和日志集成
    所有算子必须继承此类并实现 run() 方法
    """

    def __init__(self, pipeline_id: str, node_id: str, operator_id: str, work_dir: str):
        """
        初始化算子
        :param pipeline_id: 产线ID
        :param node_id: 节点ID
        :param operator_id: 算子ID
        :param work_dir: 产线根工作目录
        """
        self.pipeline_id = pipeline_id
        self.node_id = node_id
        self.operator_id = operator_id
        self.work_dir = work_dir
        self._init_paths()

    def _init_paths(self) -> None:
        """自动创建所有基础路径（绝对路径）"""
        # 输入根路径：上游算子输出数据源
        self.input_root = os.path.join(self.work_dir, "input", self.operator_id)
        # 产线输出根路径：算子最终输出（全局可见）
        self.pipeline_output_root = os.path.join(
            self.work_dir, "output", self.pipeline_id, self.node_id, self.operator_id
        )
        # 产线工作空间：算子临时文件目录
        self.pipeline_workspace = os.path.join(
            self.work_dir, "workspace", self.pipeline_id, self.node_id, self.operator_id
        )
        # 缓存根路径：可复用数据（如模型权重）
        self.cache_root = os.path.join(self.work_dir, "cache", self.operator_id)

        # 批量创建目录（避免路径不存在报错）
        for path in [self.input_root, self.pipeline_output_root,
                     self.pipeline_workspace, self.cache_root]:
            os.makedirs(path, exist_ok=True)

        logger.debug(f"算子 {self.operator_id} 路径初始化完成")
        logger.debug(f"  输入路径: {self.input_root}")
        logger.debug(f"  输出路径: {self.pipeline_output_root}")
        logger.debug(f"  工作空间: {self.pipeline_workspace}")
        logger.debug(f"  缓存路径: {self.cache_root}")

    @abstractmethod
    def run(self) -> int:
        """
        算子核心业务逻辑（子类必须重写）
        :return: exit_code
            0: 执行成功
            1: 配置错误
            2: 输入数据错误
            3: 执行逻辑错误
            4: 资源异常
            5: 环境错误
        """
        raise NotImplementedError("算子需重写 run() 方法并返回exit_code")

    def validate_input(self) -> bool:
        """
        输入数据校验（可选重写）
        :return: 校验通过返回True，失败返回False
        """
        if not os.path.exists(self.input_root):
            logger.error(f"算子 {self.operator_id} 输入目录不存在：{self.input_root}")
            return False
        if not os.listdir(self.input_root):
            logger.warning(f"算子 {self.operator_id} 输入目录为空：{self.input_root}")
        return True
