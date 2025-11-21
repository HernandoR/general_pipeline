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

    def __init__(
        self,
        pipeline_id: str,
        node_id: str,
        operator_id: str,
        input_root: str,
        output_root: str,
        workspace_root: str,
    ):
        """
        初始化算子
        :param pipeline_id: 产线ID
        :param node_id: 节点ID
        :param operator_id: 算子ID
        :param input_root: 输入根路径（由Pipeline传入）
        :param output_root: 输出根路径（由Pipeline传入）
        :param workspace_root: 工作空间根路径（由Pipeline传入）
        """
        self.pipeline_id = pipeline_id
        self.node_id = node_id
        self.operator_id = operator_id
        self.input_root = input_root
        self.output_root = output_root
        self.workspace_root = workspace_root
        self._init_paths()

    def _init_paths(self) -> None:
        """检查路径存在性并创建输出路径"""
        # 检查输入路径是否存在
        if not os.path.exists(self.input_root):
            logger.warning(f"输入路径不存在：{self.input_root}")

        # 检查工作空间根路径是否存在
        if not os.path.exists(self.workspace_root):
            logger.warning(f"工作空间根路径不存在：{self.workspace_root}")

        # 只创建输出路径（workspace/{runner_output_name}）
        os.makedirs(self.output_root, exist_ok=True)

        logger.debug(f"算子 {self.operator_id} 路径初始化完成")
        logger.debug(f"  输入路径: {self.input_root}")
        logger.debug(f"  输出路径: {self.output_root}")
        logger.debug(f"  工作空间: {self.workspace_root}")

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
