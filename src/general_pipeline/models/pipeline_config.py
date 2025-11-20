"""产线配置模型"""
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from general_pipeline.models.node_config import NodeConfig
from general_pipeline.models.operator_config import OperatorConfig
from general_pipeline.utils.codec import Base64Codec


class S3Config(BaseModel):
    """S3配置模型（集成Base64自动解码）"""
    access_key: str = Field(..., description="S3 Access Key（支持Base64编码，前缀base64://）")
    secret_key: str = Field(..., description="S3 Secret Key（支持Base64编码，前缀base64://）")
    endpoint: str = Field(..., description="S3服务端点")
    region: Optional[str] = Field(default=None, description="S3区域")

    @field_validator("access_key", "secret_key", mode="before")
    @classmethod
    def auto_decode_base64(cls, v):
        """自动解码Base64编码的敏感字段"""
        return Base64Codec.decode(v)


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
    work_dir: Path = Field(default=Path("./pipeline_workspace"), description="产线本地工作目录")
    # S3配置（用于下载conda环境压缩包）
    s3_config: Optional[S3Config] = Field(default=None, description="S3连接配置")
    # 日志配置
    log_config: Optional[LogConfig] = Field(default=None, description="Loguru日志配置")

    model_config = {"arbitrary_types_allowed": True}
