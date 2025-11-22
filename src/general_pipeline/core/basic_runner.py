"""算子基类 BasicRunner"""
import os
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type

from general_pipeline.utils.log_utils import get_logger

logger = get_logger()

# 全局算子注册表 - 按 operator_id 组织
_operator_registry: Dict[str, Type["BasicRunner"]] = {}


def register_operator(operator_id: str):
    """
    算子注册装饰器
    用于将算子类与operator_id关联，支持通过operator_id查找算子类
    
    :param operator_id: 算子唯一标识
    
    使用示例:
        @register_operator("data_cleaner_v1")
        class DataCleanerOperator(BasicRunner):
            def run(self) -> int:
                # 实现数据清洗逻辑
                return 0
            
            def build_running_command(self) -> List[str]:
                return ["python", "main.py"]
    """
    def decorator(cls: Type["BasicRunner"]) -> Type["BasicRunner"]:
        if not issubclass(cls, BasicRunner):
            raise TypeError(f"被装饰的类 {cls.__name__} 必须继承 BasicRunner")
        
        if operator_id in _operator_registry:
            logger.warning(f"算子 {operator_id} 已经注册，将被新的类 {cls.__name__} 覆盖")
        
        _operator_registry[operator_id] = cls
        logger.debug(f"算子 {operator_id} 注册成功: {cls.__name__}")
        
        return cls
    
    return decorator


def get_operator_class(operator_id: str) -> Optional[Type["BasicRunner"]]:
    """
    根据operator_id获取算子类
    
    :param operator_id: 算子唯一标识
    :return: 算子类，如果不存在返回None
    """
    return _operator_registry.get(operator_id)


def list_registered_operators() -> List[str]:
    """
    列出所有已注册的算子ID
    
    :return: 算子ID列表
    """
    return list(_operator_registry.keys())


class SingletonMeta(type):
    """
    单例元类，确保每个算子类只有一个实例
    考虑到不同的初始化参数，使用参数组合作为key
    """
    _instances: Dict[tuple, Any] = {}
    
    def __call__(cls, *args, **kwargs):
        # 使用类和关键参数的组合作为key
        # 对于算子，主要是operator_id应该作为单例的key
        operator_id = kwargs.get("operator_id") or (args[2] if len(args) > 2 else None)
        key = (cls, operator_id)
        
        if key not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[key] = instance
            logger.debug(f"创建新的算子实例: {cls.__name__} (operator_id={operator_id})")
        else:
            logger.debug(f"返回已存在的算子实例: {cls.__name__} (operator_id={operator_id})")
        
        return cls._instances[key]


class BasicRunner(ABC, metaclass=SingletonMeta):
    """
    算子基类，提供标准化路径管理和日志集成
    所有算子必须继承此类并实现 run() 和 build_running_command() 方法
    使用单例模式，确保同一个operator_id只有一个实例
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

    @abstractmethod
    def build_running_command(self) -> List[str]:
        """
        构建运行命令（子类必须重写）
        返回完整的命令列表，用于执行算子
        
        :return: 命令列表，例如 ["python", "main.py", "--input", "/path/to/input"]
        
        示例:
            def build_running_command(self) -> List[str]:
                return [
                    "python", "run.py",
                    "--input", self.input_root,
                    "--output", self.output_root
                ]
        """
        raise NotImplementedError("算子需重写 build_running_command() 方法并返回命令列表")

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
