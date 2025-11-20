"""节点配置模型"""
from typing import List, Optional

from pydantic import BaseModel, Field


class NodeResourceConfig(BaseModel):
    """节点资源配置模型"""
    # CPU请求量（单位：核）
    cpu_request: float = Field(..., description="节点CPU请求量（核）")
    # CPU最大限制（单位：核）
    cpu_limit: float = Field(..., description="节点CPU最大限制（核）")
    # 内存请求量（单位：GB）
    memory_request: float = Field(..., description="节点内存请求量（GB）")
    # 内存最大限制（单位：GB）
    memory_limit: float = Field(..., description="节点内存最大限制（GB）")
    # GPU请求量（单位：张，0表示不使用GPU）
    gpu_request: int = Field(default=0, description="节点GPU请求量（张）")
    # GPU最大限制（单位：张）
    gpu_limit: Optional[int] = Field(default=None, description="节点GPU最大限制（张），默认与请求量一致")


class NodeConfig(BaseModel):
    """Node核心配置模型"""
    # 节点唯一标识
    node_id: str = Field(..., description="节点唯一标识")
    # 节点包含的算子ID列表（需满足依赖关系）
    operator_ids: List[str] = Field(..., description="本节点包含的算子ID列表")
    # 节点Runner数量（并发执行的算子数）
    runner_count: int = Field(default=1, description="节点内Runner数量，默认1个（顺序执行）")
    # 资源配置
    resource: NodeResourceConfig = Field(..., description="节点资源配置")
