"""产线配置模型"""

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from general_pipeline.models.node_config import NodeConfig
from general_pipeline.models.operator_config import OperatorConfig


class LogConfig(BaseModel):
    """日志配置模型"""

    level: str = Field(default="INFO", description="日志级别")
    log_path: Optional[Path] = Field(default=None, description="日志文件路径")
    rotation: str = Field(default="10 GB", description="日志轮转规则")
    retention: int = Field(default=30, description="日志保留天数")


class PipelineConfig(BaseModel):
    """Pipeline核心配置模型"""

    # 产线唯一标识
    pipeline_id: str = Field(..., description="产线唯一标识")
    # 产线名称
    name: str = Field(..., description="产线名称")
    # 产线描述
    description: Optional[str] = Field(default=None, description="产线描述")
    # 算子配置列表
    operators: List[OperatorConfig] = Field(..., description="所有算子配置")
    # 节点配置列表
    nodes: List[NodeConfig] = Field(..., description="所有节点配置")
    # 本地工作目录（算子代码、虚拟环境存储路径）
    work_dir: Path = Field(
        default=Path("./pipeline_workspace"), description="产线本地工作目录"
    )
    # 日志配置
    log_config: Optional[LogConfig] = Field(default=None, description="Loguru日志配置")

    model_config = {"arbitrary_types_allowed": True}


class PplPathConfig(BaseModel):
    """生产物料路径配置模型"""

    input_root_path: Path = Field(..., description="输入物料根路径, 下层为adrn")
    output_root_path: Path = Field(..., description="输出物料根路径, 下层为adrn")
    workspace_root_path: Path = Field(
        ..., description="工作空间路径, 下层为operator_id"
    )
    poi_output_root_path: Optional[Path] = Field(
        ..., description="多趟产线POI工作空间路径, 下层为poi_id"
    )
    cache_root_path: Optional[Path] = Field(
        default=None, description="高速缓存根路径, pod 结束后被删除"
    )

    @field_validator(
        "input_root_path",
        "output_root_path",
        "workspace_root_path",
        "poi_output_root_path",
        "cache_root_path",
        mode="before",
    )
    @classmethod
    def ensure_path(cls, v):
        """确保路径为Path对象"""
        if isinstance(v, str):
            v = Path(v)
        # make sure exists
        v.mkdir(parents=True, exist_ok=True)
        return v
