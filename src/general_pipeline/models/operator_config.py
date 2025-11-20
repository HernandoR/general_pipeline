"""算子配置模型"""
from pydantic import BaseModel, Field, field_validator
from pathlib import Path
from typing import List, Dict, Optional, Union

from general_pipeline.models.env_config import (
    UVVirtualEnvConfig,
    PixiVirtualEnvConfig,
    CondaVirtualEnvConfig
)
from general_pipeline.utils.codec import Base64Codec


class OperatorConfig(BaseModel):
    """Operator核心配置模型"""
    # 算子唯一标识（建议格式：{仓库名}_{模块名}）
    operator_id: str = Field(..., description="算子唯一标识")
    # 代码仓库地址（git）
    git_repo: str = Field(..., description="算子代码git仓库地址")
    # 代码版本标签（git tag）
    git_tag: str = Field(..., description="算子代码版本标签")
    # 上游依赖算子ID列表（空列表表示无依赖）
    upstream_dependencies: List[str] = Field(default_factory=list, description="上游依赖算子ID")
    # 虚拟环境配置（使用Union关联三种具体环境模型）
    env_config: Union[UVVirtualEnvConfig, PixiVirtualEnvConfig, CondaVirtualEnvConfig] = Field(
        ..., description="虚拟环境配置（UV/Pixi/Conda三选一）"
    )
    # 算子代码本地存储路径（由Pipeline层拉取代码后注入，无需用户配置）
    code_path: Optional[Path] = Field(default=None, exclude=True)
    # 启动命令（如：python run.py）
    start_command: str = Field(..., description="算子启动命令")
    # 超时时间（秒）
    timeout: int = Field(default=3600, description="算子执行超时时间（秒）")
    # 额外环境变量
    extra_env_vars: Dict[str, str] = Field(default_factory=dict, description="额外环境变量")
    # 资源需求（可选，用于调度参考）
    resource_request: Optional[Dict[str, float]] = Field(default=None, description="资源需求声明")

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("extra_env_vars", mode="before")
    @classmethod
    def decode_env_vars(cls, v):
        """自动解码环境变量中的Base64编码值"""
        if isinstance(v, dict):
            return {k: Base64Codec.decode(val) if isinstance(val, str) else val for k, val in v.items()}
        return v
