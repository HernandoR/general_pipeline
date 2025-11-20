# 数据产线 Python 项目规划 - 架构文档

## 1. 项目概述

### 1.1 项目目标

构建一套标准化、可扩展的数据产线框架，支持多来源虚拟环境管理、灵活的算子集成、资源可控的任务执行,同时提供统一的配置管理、日志记录和环境隔离能力，降低算子集成成本，提升产线可维护性和稳定性。

### 1.2 核心技术栈

| 技术组件      | 用途说明                       |
| --------- | -------------------------- |
| OmegaConf | 层级化配置管理，支持文件加载与环境变量注入      |
| Loguru    | 简洁高效的日志记录，支持多终端输出、文件轮转     |
| Pixi      | 项目环境管理，负责基础依赖安装与环境隔离       |
| Pathlib   | 面向对象的文件路径处理，统一路径操作规范       |
| Pydantic  | 配置数据验证与类型转换，确保配置合法性        |
| S3FS      | 远程存储交互，用于 conda 虚拟环境压缩包的下载 |

## 2. 架构设计

### 2.1 整体架构分层

项目采用三层架构设计，从上至下依次为**Pipeline 层（产线层）**、**Node 层（节点层）**、**Operator 层（算子层）**，各层职责边界清晰，依赖关系自上而下传递，配置信息自下而上集成：

```
┌─────────────────────────────────────────────────────┐
│ Pipeline层（产线层）                                 │
│ （配置集成、算子初始化、虚拟环境创建、产线调度）       │
├─────────────────────────────────────────────────────┤
│ Node层（节点层）                                     │
│ （资源控制、Runner管理、任务顺序执行）               │
├─────────────────────────────────────────────────────┤
│ Operator层（算子层）                                 │
│ （业务逻辑实现、依赖声明、环境需求、变量配置）       │
└─────────────────────────────────────────────────────┘
```

### 2.2 各层核心职责与设计规范

#### 2.2.1 Operator 层（算子层）

Operator 是数据产线的最小业务单元，由外部用户提供并集成至产线，需遵循统一的配置规范和集成标准。

##### 2.2.1.1 核心职责

* 封装具体的业务处理逻辑（如数据清洗、特征计算、模型推理等）。
* 明确声明自身的上游依赖算子（依赖关系）。
* 提供运行所需的 Python 环境类型及配置（虚拟环境来源）。
* 声明运行资源需求（CPU、内存、GPU 等，用于 Node 层资源调度参考）。
* 定义运行超时时间（避免任务阻塞）。
* 提供拓展变量（运行时注入环境变量）。

##### 2.2.1.2 配置规范（Pydantic 模型定义）

```python
from pydantic import BaseModel, Field, validator
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Any
from enum import Enum
import subprocess
from pipeline.utils.path_utils import ensure_dir_exists  # 项目自定义路径工具类
from pipeline.utils.log_utils import logger  # 项目自定义日志工具类


# ------------------------------
# 1. 虚拟环境操作抽象基类（定义接口）
# ------------------------------
class BaseVirtualEnvConfig(BaseModel, ABC):
    """
    虚拟环境配置抽象基类，定义环境创建（install_env）和激活（activate_env）接口
    所有具体虚拟环境类型需继承此类并实现抽象方法
    """
    # 虚拟环境存储根路径（由Pipeline层初始化时注入，无需用户配置）
    env_root_path: Optional[Path] = Field(default=None, exclude=True)
    # 虚拟环境名称（算子唯一标识作为默认值，确保环境隔离）
    env_name: str = Field(default=None, description="虚拟环境名称，默认使用算子ID")

    @validator("env_name", pre=True, always=True)
    def set_default_env_name(cls, v, values, **kwargs):
        """若未指定env_name，默认使用算子ID作为环境名称（需OperatorConfig传入算子ID）"""
        if v is None:
            # 从父级OperatorConfig的values中获取operator_id（依赖Pydantic嵌套模型的校验顺序）
            return values.get("operator_id")
        return v

    @abstractmethod
    def install_env(self) -> None:
        """
        抽象方法：创建并初始化虚拟环境（安装依赖）
        需各具体环境类型实现，失败时抛出EnvInstallError异常
        """
        pass

    @abstractmethod
    def activate_env(self) -> Dict[str, str]:
        """
        抽象方法：生成虚拟环境激活命令对应的环境变量（如PATH、CONDA_DEFAULT_ENV等）
        返回值：环境变量字典，供Operator执行时注入
        """
        pass

    def get_full_env_path(self) -> Path:
        """获取虚拟环境的完整路径（env_root_path + env_name），需先注入env_root_path"""
        if self.env_root_path is None:
            raise ValueError("env_root_path未注入，无法获取虚拟环境完整路径")
        return self.env_root_path / self.env_name


# ------------------------------
# 2. 具体虚拟环境类型模型（实现接口）
# ------------------------------
class UVVirtualEnvConfig(BaseVirtualEnvConfig):
    """UV虚拟环境配置模型（对应uv_project类型）"""
    # UV项目必需：pyproject.toml文件路径（相对算子代码根目录）
    pyproject_path: Path = Field(..., description="pyproject.toml文件路径（相对算子代码根目录）")
    # 可选：UV额外安装参数（如--no-cache、--python 3.11等）
    uv_extra_args: Optional[List[str]] = Field(default=None, description="UV安装额外参数")

    @validator("pyproject_path")
    def validate_pyproject_path(cls, v):
        """校验pyproject_path是否以pyproject.toml结尾，确保路径正确性"""
        if v.name != "pyproject.toml":
            raise ValueError(f"UV项目的pyproject_path必须指向pyproject.toml文件，当前为：{v}")
        return v

    def install_env(self) -> None:
        """实现UV环境安装：创建虚拟环境 + 基于pyproject.toml安装依赖"""
        logger.info(f"开始安装UV虚拟环境：{self.get_full_env_path()}")
        ensure_dir_exists(self.env_root_path)  # 确保环境根目录存在

        # 1. 构建UV创建虚拟环境命令
        create_cmd = [
            "uv", "venv",
            "--name", self.env_name,
            "--path", str(self.env_root_path)
        ]
        # 2. 执行创建命令
        result = subprocess.run(create_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise EnvInstallError(
                f"UV虚拟环境创建失败（{self.env_name}）：\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        # 3. 基于pyproject.toml安装依赖（需指定UV环境的Python路径）
        uv_python_path = self.get_full_env_path() / "bin" / "python"  # Linux/Mac路径，Windows需适配
        install_cmd = [str(uv_python_path), "-m", "uv", "pip", "install", "-e", "."]
        if self.uv_extra_args:
            install_cmd.extend(self.uv_extra_args)
        # 执行安装命令（需切换至算子代码根目录，确保pyproject.toml路径正确）
        operator_code_path = self._get_operator_code_path()  # 从父级OperatorConfig获取算子代码路径
        result = subprocess.run(
            install_cmd,
            cwd=str(operator_code_path),
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            raise EnvInstallError(
                f"UV依赖安装失败（{self.env_name}）：\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        logger.info(f"UV虚拟环境安装完成：{self.get_full_env_path()}")

    def activate_env(self) -> Dict[str, str]:
        """实现UV环境激活：返回包含PATH的环境变量字典"""
        env_path = self.get_full_env_path() / "bin"  # Linux/Mac的bin目录，Windows为Scripts
        # 激活逻辑：将UV环境的bin目录添加到PATH最前面，确保优先使用该环境的命令
        return {
            "PATH": f"{str(env_path)}:{os.environ.get('PATH', '')}",
            "UV_ENV_ACTIVATED": "true",
            "VIRTUAL_ENV": str(self.get_full_env_path())
        }

    def _get_operator_code_path(self) -> Path:
        """从父级OperatorConfig获取算子代码根目录（依赖嵌套模型的父级引用）"""
        # 需在OperatorConfig中通过Field(..., exclude=False)保留对父级的引用，或通过注入方式传递
        if hasattr(self, "operator_config") and hasattr(self.operator_config, "code_path"):
            return self.operator_config.code_path
        raise AttributeError("算子代码路径未注入UV虚拟环境配置")


class PixiVirtualEnvConfig(BaseVirtualEnvConfig):
    """Pixi虚拟环境配置模型（对应pixi_project类型）"""
    # Pixi项目必需：pixi.toml文件路径（相对算子代码根目录）
    pixi_toml_path: Path = Field(..., description="pixi.toml文件路径（相对算子代码根目录）")
    # 可选：Pixi环境通道（如conda-forge、pypi等）
    pixi_channels: Optional[List[str]] = Field(default=["conda-forge", "pypi"], description="Pixi环境通道")
    # 可选：Pixi额外安装参数（如--no-cache、--force等）
    pixi_extra_args: Optional[List[str]] = Field(default=None, description="Pixi安装额外参数")

    @validator("pixi_toml_path")
    def validate_pixi_toml_path(cls, v):
        """校验pixi_toml_path是否以pixi.toml结尾，确保路径正确性"""
        if v.name != "pixi.toml":
            raise ValueError(f"Pixi项目的pixi_toml_path必须指向pixi.toml文件，当前为：{v}")
        return v

    def install_env(self) -> None:
        """实现Pixi环境安装：基于pixi.toml创建环境并安装依赖"""
        logger.info(f"开始安装Pixi虚拟环境：{self.get_full_env_path()}")
        ensure_dir_exists(self.env_root_path)
        operator_code_path = self._get_operator_code_path()
        pixi_toml_full_path = operator_code_path / self.pixi_toml_path

        # 1. 校验pixi.toml文件是否存在
        if not pixi_toml_full_path.exists():
            raise FileNotFoundError(f"Pixi配置文件不存在：{pixi_toml_full_path}")

        # 2. 构建Pixi创建环境命令（指定环境路径和通道）
        create_cmd = [
            "pixi", "env", "create",
            "--file", str(pixi_toml_full_path),
            "--prefix", str(self.get_full_env_path())
        ]
        for channel in self.pixi_channels:
            create_cmd.extend(["--channel", channel])
        if self.pixi_extra_args:
            create_cmd.extend(self.pixi_extra_args)

        # 3. 执行创建命令
        result = subprocess.run(create_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise EnvInstallError(
                f"Pixi虚拟环境创建失败（{self.env_name}）：\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        logger.info(f"Pixi虚拟环境安装完成：{self.get_full_env_path()}")

    def activate_env(self) -> Dict[str, str]:
        """实现Pixi环境激活：返回包含PATH、CONDA_DEFAULT_ENV的环境变量字典"""
        env_bin_path = self.get_full_env_path() / "bin"  # Linux/Mac路径
        return {
            "PATH": f"{str(env_bin_path)}:{os.environ.get('PATH', '')}",
            "CONDA_DEFAULT_ENV": self.env_name,
            "PIXI_ENV_ACTIVATED": "true",
            "CONDA_PREFIX": str(self.get_full_env_path())
        }

    def _get_operator_code_path(self) -> Path:
        """同UV模型，获取算子代码根目录"""
        if hasattr(self, "operator_config") and hasattr(self.operator_config, "code_path"):
            return self.operator_config.code_path
        raise AttributeError("算子代码路径未注入Pixi虚拟环境配置")


class CondaVirtualEnvConfig(BaseVirtualEnvConfig):
    """Conda虚拟环境配置模型（对应conda_project类型）"""
    # Conda项目必需：S3上的zstd压缩包路径
    s3_compress_path: str = Field(..., description="S3上conda环境zstd压缩包路径（如s3://conda-envs/env-v1.zst）")
    # 可选：解压后是否执行conda env update（用于修复环境路径）
    need_conda_update: bool = Field(default=True, description="解压后是否执行conda env update修复路径")
    # 可选：zstd解压额外参数（如--threads 4等）
    zstd_extra_args: Optional[List[str]] = Field(default=None, description="zstd解压额外参数")

    def install_env(self) -> None:
        """实现Conda环境安装：从S3下载压缩包 + zstd解压 + 可选conda env update"""
        logger.info(f"开始安装Conda虚拟环境：{self.get_full_env_path()}")
        ensure_dir_exists(self.env_root_path)
        s3_client = self._get_s3_client()  # 从Pipeline层注入的S3配置获取客户端

        # 1. 从S3下载压缩包到临时目录
        temp_compress_path = self.env_root_path / f"{self.env_name}.zst"
        try:
            logger.info(f"从S3下载conda压缩包：{self.s3_compress_path} -> {temp_compress_path}")
            s3_client.download_file(
                Bucket=self._get_s3_bucket(),
                Key=self._get_s3_key(),
                Filename=str(temp_compress_path)
            )
        except Exception as e:
            raise EnvInstallError(f"S3下载conda压缩包失败：{str(e)}")

        # 2. zstd解压压缩包到目标环境路径
       解压_cmd = [
            "zstd", "-d", str(temp_compress_path),
            "-o", str(self.get_full_env_path()),  # 解压到环境目录（需确保目录不存在）
            "--recursive"  # 递归解压目录
        ]
        if self.zstd_extra_args:
            解压_cmd.extend(self.zstd_extra_args)
        result = subprocess.run(解压_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise EnvInstallError(
                f"Conda环境解压失败（{self.env_name}）：\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        # 解压完成后删除临时压缩包
        temp_compress_path.unlink(missing_ok=True)

        # 3. 可选：执行conda env update修复解压后的环境路径（避免路径依赖问题）
        if self.need_conda_update:
            conda_bin_path = self.get_full_env_path() / "bin" / "conda"
            update_cmd = [str(conda_bin_path), "env", "update", "--prefix", str(self.get_full_env_path()), "--prune"]
            result = subprocess.run(update_cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logger.warning(f"Conda env update警告（{self.env_name}）：\n{result.stderr}")
            else:
                logger.info(f"Conda env update完成（{self.env_name}）")

        logger.info(f"Conda虚拟环境安装完成：{self.get_full_env_path()}")

    def activate_env(self) -> Dict[str, str]:
        """实现Conda环境激活：返回标准conda激活后的环境变量字典"""
        env_bin_path = self.get_full_env_path() / "bin"
        return {
            "PATH": f"{str(env_bin_path)}:{os.environ.get('PATH', '')}",
            "CONDA_DEFAULT_ENV": self.env_name,
            "CONDA_ENV_ACTIVATED": "true",
            "CONDA_PREFIX": str(self.get_full_env_path()),
            # 清除可能的其他conda环境变量
            "CONDA_SHLVL": "1"
        }

    def _get_s3_client(self) -> Any:
        """从Pipeline层注入的S3配置获取S3客户端（如boto3.client）"""
        if hasattr(self, "pipeline_config") and hasattr(self.pipeline_config, "s3_client"):
            return self.pipeline_config.s3_client
        raise AttributeError("S3客户端未注入Conda虚拟环境配置")

    def _get_s3_bucket(self) -> str:
        """从s3_compress_path解析S3 Bucket（如s3://bucket/key -> bucket）"""
        from pipeline.utils.s3_utils import parse_s3_path  # 项目自定义S3工具类
        return parse_s3_path(self.s3_compress_path)["bucket"]

    def _get_s3_key(self) -> str:
        """从s3_compress_path解析S3 Key"""
        from pipeline.utils.s3_utils import parse_s3_path
        return parse_s3_path(self.s3_compress_path)["key"]


# ------------------------------
# 3. OperatorConfig 模型更新（关联具体虚拟环境模型）
# ------------------------------
class OperatorConfig(BaseModel):
    """Operator核心配置模型（更新：关联具体虚拟环境配置模型）"""
    # 算子唯一标识（建议格式：{仓库名}_{模块名}）
    operator_id: str = Field(..., description="算子唯一标识")
    # 代码仓库地址（git）
    git_repo: str = Field(..., description="算子代码git仓库地址")
    # 代码版本标签（git tag）
    git_tag: str = Field(..., description="算子代码版本标签")
    # 上游依赖算子ID列表（空列表表示无依赖）
    upstream_dependencies: List[str] = Field(default_factory=list, description="上游依赖算子ID")
    # 虚拟环境配置（使用Union关联三种具体环境模型，Pydantic自动根据字段匹配类型）
    env_config: Union[UVVirtualEnvConfig, PixiVirtualEnvConfig, CondaVirtualEnvConfig] = Field(
        ..., description="虚拟环境配置（UV/Pixi/Conda三选一）"
    )
    # 算子代码本地存储路径（由Pipeline层拉取代码后注入，无需用户配置）
    code_path: Optional[Path] = Field(default=None, exclude=True)
    # 启动命令（如：python run.py）</doubaocanvas>

##### 2.2.1.3 虚拟环境配置说明

根据`env_type`的不同，`env_config`需提供对应配置：

* **uv_project**：需包含`pyproject_path`（pyproject.toml 文件路径，相对算子代码根目录）。
* **pixi_project**：需包含`pixi_toml_path`（pixi.toml 文件路径，相对算子代码根目录）。
* **conda_project**：需包含`s3_compress_path`（S3 上的 conda 环境 zstd 压缩包路径）、`env_name`（解压后的环境名称）。

#### 2.2.2 Node 层（节点层）

Node 是产线资源控制和任务执行的最小单位，负责管理 Runner（任务执行进程），并按顺序调度本节点内的 Operator，同时控制资源使用上限。

##### 2.2.2.1 核心职责

* 声明节点的资源需求与限制（CPU、内存、GPU）。
* 管理本节点内的 Runner 数量（并发执行能力）。
* 按依赖顺序调度本节点内的 Operator 执行。
* 监控 Operator 运行状态，处理超时、失败等异常。

##### 2.2.2.2 配置规范（Pydantic 模型定义）

```python
from pydantic import BaseModel
from typing import List, Optional

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
```

#### 2.2.3 Pipeline 层（产线层）

Pipeline 是产线的顶层管理单元，负责整合所有配置、初始化算子、创建虚拟环境、调度节点执行，是配置集成和调试的最终单位。

##### 2.2.3.1 核心职责

* 加载并集成 Operator、Node 的配置，进行依赖校验和合法性检查。
* 从 git 仓库拉取 Operator 代码（按 git_tag），初始化至本地指定目录。
* 根据 Operator 的环境配置，创建对应的虚拟环境（uv/pixi 环境本地构建，conda 环境从 S3 下载解压）。
* 支持从环境变量注入配置，覆盖文件配置。
* 调度各 Node 按依赖顺序执行，统一管理日志输出。
* 提供产线启动、暂停、终止、重试等生命周期管理能力。

##### 2.2.3.2 配置规范（Pydantic 模型定义）

```python
from pydantic import BaseModel
from typing import List, Dict, Optional
from pathlib import Path

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
  s3_config: Optional[Dict[str, str]] = Field(default=None, description="S3连接配置（endpoint、access_key、secret_key等）")
  # 日志配置
  log_config: Optional[Dict[str, str]] = Field(default=None, description="Loguru日志配置（如日志路径、级别、轮转规则等）")
```

## 3. 核心流程设计

### 3.1 产线初始化流程（init_pipeline）

1. **配置加载与合并**：
* 从指定目录加载层级化配置文件（如 YAML 格式），通过 OmegaConf 构建基础配置。
* 读取环境变量中以`MI_PIPELINE_CONF_`开头的变量，按 "双下划线替代字典嵌套" 规则解析，覆盖基础配置（如`MI_PIPELINE_CONF_S3_CONFIG__ENDPOINT=http://s3.example.com`对应配置中`s3_config.endpoint`）。
* 通过 Pydantic 模型验证合并后的配置合法性，输出非法配置详情并终止初始化。
2. **算子代码拉取**：
* 遍历所有 Operator 配置，根据`git_repo`和`git_tag`，将算子代码克隆至`work_dir/operators/{operator_id}`目录。
* 校验算子代码中是否存在虚拟环境所需的配置文件（如 uv 项目的 pyproject.toml、pixi 项目的 pixi.toml），缺失则抛出异常。
3. **虚拟环境创建**：
* 遍历所有 Operator，按`env_type`创建对应虚拟环境，存储至`work_dir/envs/{operator_id}`目录：
  * **uv_project**：进入算子代码目录，执行`uv venv`创建虚拟环境，通过`pyproject.toml`安装依赖。
  * **pixi_project**：进入算子代码目录，执行`pixi install`创建虚拟环境，基于`pixi.toml`配置依赖。
  * **conda_project**：通过 S3FS 连接远程存储，下载`env_config.s3_compress_path`指定的 zstd 压缩包，解压至虚拟环境目录，执行`conda env update`完成环境激活准备。
4. **依赖关系校验**：
* 检查所有 Operator 的`upstream_dependencies`中声明的算子 ID 是否存在于配置中，不存在则抛出依赖缺失异常。
* 校验 Node 内的 Operator 依赖是否跨节点，确保上游依赖算子所在节点已优先调度（后续调度流程使用）。
5. **日志初始化**：
* 根据`log_config`配置 Loguru，设置日志级别（默认 INFO）、输出路径（默认`work_dir/logs/pipeline.log`）、轮转规则（如按大小轮转，单个日志文件最大 100MB，保留 10 个备份）。

### 3.2 产线执行流程（run_pipeline）

1. **节点调度排序**：
* 根据 Operator 的依赖关系，构建依赖图，对所有 Node 进行拓扑排序，确保上游依赖节点优先执行。
2. **节点任务执行**：
* 按排序后的节点顺序，依次启动每个 Node 的 Runner：
  * 检查 Node 的资源使用情况（CPU、内存、GPU），若当前资源已达`limit`，则等待资源释放。
  * 对 Node 内的 Operator 按依赖顺序排序，Runner 依次执行每个 Operator 的`start_command`：
    * 激活当前 Operator 的虚拟环境。
    * 将`extra_env_vars`注入执行环境。
    * 执行启动命令，通过 Loguru 捕获 stdout/stderr 日志，关联算子 ID 和节点 ID 输出。
    * 监控执行时间，超过`timeout`则终止进程，标记任务失败。
3. **状态监控与反馈**：
* 实时记录每个 Operator、Node 的执行状态（待执行、执行中、成功、失败、超时）。
* 若某个 Operator 执行失败，根据配置（可扩展）选择重试或终止产线，输出详细错误日志。
* 所有 Node 执行完成后，输出产线执行报告（成功 / 失败算子数量、总耗时、资源使用峰值等）。

## 4. 配置文件规范

### 4.1 配置文件结构（YAML 示例）

```yaml
# pipeline_config.yaml
pipeline_id: "data_process_pipeline_v1"
name: "数据处理产线V1"
description: "用于用户行为数据清洗、特征提取的产线"
work_dir: "./pipeline_workspace"
s3_config:
  endpoint: "http://s3.example.com"
  access_key: "xxx"
  secret_key: "xxx"
log_config:
  level: "INFO"
  log_path: "./pipeline_workspace/logs/pipeline.log"
  rotation: "100 MB"
  retention: 10
operators:
  - operator_id: "data_clean_operator"
    git_repo: "https://github.com/example/data-clean-operator.git"
    git_tag: "v1.0.0"
    upstream_dependencies: []
    env_type: "pixi_project"
    env_config:
      pixi_toml_path: "./pixi.toml"
    start_command: "python main.py"
    timeout: 1800
    extra_env_vars:
      DATA_INPUT_PATH: "/data/input"
      DATA_OUTPUT_PATH: "/data/cleaned"
  - operator_id: "feature_extract_operator"
    git_repo: "https://github.com/example/feature-extract-operator.git"
    git_tag: "v2.1.0"
    upstream_dependencies: ["data_clean_operator"]
    env_type: "conda_project"
    env_config:
      s3_compress_path: "conda_envs/feature-env_v2.1.0.zst"
      env_name: "feature-env"
    start_command: "python extract.py"
    timeout: 3600
nodes:
  - node_id: "node_1"
    operator_ids: ["data_clean_operator"]
    runner_count: 1
    resource:
      cpu_request: 2.0
      cpu_limit: 4.0
      memory_request: 8.0
      memory_limit: 16.0
      gpu_request: 0
  - node_id: "node_2"
    operator_ids: ["feature_extract_operator"]
    runner_count: 1
    resource:
      cpu_request: 4.0
      cpu_limit: 8.0
      memory_request: 16.0
      memory_limit: 32.0
      gpu_request: 1
      gpu_limit: 1
```

### 4.2 环境变量注入示例

通过环境变量覆盖 S3 配置和日志级别：

```bash
export MI_PIPELINE_CONF_S3_CONFIG__ENDPOINT=http://s3-new.example.com
export MI_PIPELINE_CONF_S3_CONFIG__ACCESS_KEY="new_xxx"
export MI_PIPELINE_CONF_LOG_CONFIG__LEVEL="DEBUG"
export MI_PIPELINE_CONF_WORK_DIR="./new_workspace"
```

## 5. 扩展与约束

### 5.1 可扩展点

* **虚拟环境类型扩展**：支持新增虚拟环境类型（如 poetry_project），需在`VirtualEnvType`枚举中添加类型，并在`init_pipeline`流程中补充对应的环境创建逻辑。
* **调度策略扩展**：支持自定义 Node 调度策略（如按资源利用率调度、按优先级调度），通过实现调度接口替换默认拓扑排序逻辑。
* **异常处理扩展**：支持自定义 Operator 失败重试策略（如重试次数、重试间隔）、失败降级逻辑，通过配置文件指定。

### 5.2 约束与限制

* Operator 的`upstream_dependencies`仅支持直接依赖（不支持间接依赖声明），间接依赖需通过直接依赖传递。
* 虚拟环境创建过程中，uv/pixi/conda 需提前安装在基础环境中（由 Pixi 管理的项目基础环境提供）。
* S3 存储的 conda 环境压缩包需以 zstd 格式压缩，且解压后需符合 conda 环境目录结构。
* 环境变量注入仅支持覆盖 Pipeline 层配置，不支持直接修改 Operator、Node 的底层配置（需通过 Pipeline 配置传递）。 

## 6. 补充模块：Base64 编解码模块（敏感信息保护）

### 6.1 模块背景与目标

考虑到项目对敏感信息加解密要求不高，需简化实现逻辑，同时避免 AKSK 等敏感信息以明文形式存储于 Git 仓库或配置文件。新增Base64 编解码模块，通过标准化的 Base64 编码对敏感信息进行转换存储，运行时解码使用，杜绝明文敏感数据直接暴露，兼顾安全性与易用性。

### 6.2 核心技术选型

| 技术组件 | 用途说明 |
| --- | --- |
| Python 内置base64模块 | 提供 Base64 编解码能力，无需额外依赖，轻量高效，满足基础敏感信息保护需求 |
| 编码标识约定 | 通过固定前缀标记编码字段，便于编解码模块自动识别（如base64://） |

**选型说明**：
* 放弃复杂对称加密算法，采用 Python 内置base64模块，减少第三方依赖，降低维护成本。
* 通过base64://前缀明确标记编码字段，避免编解码逻辑混淆，同时简化配置文件可读性。
* 核心目标：防止 Git 仓库中明文泄露敏感信息，不抵御高强度破解（符合项目低安全要求）。

### 6.3 模块架构与集成位置

Base64 编解码模块嵌入Pipeline 层的配置加载流程，与 OmegaConf 配置合并、Pydantic 验证联动，具体集成位置如下：

```
┌─────────────────────────────────────────────────────────────────┐
│ Pipeline层配置加载流程                                           │
│                                                                 │
│ 1. 配置文件加载（YAML） → 2. 编码字段自动解码 → 3. 环境变量注入覆盖  │
│                                                                 │
│ 4. Pydantic配置验证 → 5. 运行时使用明文 → 6. 内存中信息清理        │
└─────────────────────────────────────────────────────────────────┘
```

* **解码时机**：配置文件加载后、环境变量注入前，对标记为base64://的字段自动解码。
* **编码时机**：用户编写配置文件时，手动对敏感字段编码（可通过项目提供的命令行工具快速生成）。

### 6.4 编解码核心逻辑

#### 6.4.1 编码规则

* **输入**：敏感信息明文（如AKIAEXAMPLE）。
* **编码流程**：明文 → UTF-8 编码 → Base64 编码 → 拼接base64://前缀。
* **输出**：编码串（如base64://QUtJQUVYQU1QTEU=）。

#### 6.4.2 解码规则

* **输入**：配置文件中的编码串（如base64://QUtJQUVYQU1QTEU=）。
* **解码流程**：去除base64://前缀 → Base64 解码 → UTF-8 解码 → 明文。
* **输出**：敏感信息明文（如AKIAEXAMPLE）。

#### 6.4.3 核心代码逻辑（示例）

```python
import base64
from typing import Optional

class Base64Codec:
    """Base64编解码工具类"""
    ENCODE_PREFIX = "base64://"  # 编码字段前缀标识
    @staticmethod
    def encode(plaintext: str) -> str:
        """
        对明文进行Base64编码，添加前缀标识
        :param plaintext: 敏感信息明文
        :return: 带前缀的编码串
        """
        if not plaintext:
            return plaintext
        # UTF-8编码后进行Base64编码
        encoded_bytes = base64.b64encode(plaintext.encode("utf-8"))
        return f"{Base64Codec.ENCODE_PREFIX}{encoded_bytes.decode('utf-8')}"
    @staticmethod
    def decode(encoded_str: Optional[str]) -> Optional[str]:
        """
        对带前缀的编码串进行Base64解码
        :param encoded_str: 带前缀的编码串
        :return: 敏感信息明文（非编码串返回原内容）
        """
        if not encoded_str or not encoded_str.startswith(Base64Codec.ENCODE_PREFIX):
            return encoded_str  # 非编码串直接返回
        # 去除前缀后解码
        raw_encoded = encoded_str.lstrip(Base64Codec.ENCODE_PREFIX)
        decoded_bytes = base64.b64decode(raw_encoded)
        return decoded_bytes.decode("utf-8")
```

### 6.5 配置文件规范与集成

#### 6.5.1 敏感字段配置示例

用户编写配置文件时，对敏感字段进行编码后填入，示例：

```yaml
# 编码后的S3配置示例（access_key和secret_key为Base64编码）
s3_config:
  access_key: "base64://QUtJQUVYQU1QTEU="  # 明文：AKIAEXAMPLE
  secret_key: "base64://c2VjcmV0X2tleV9leGFtcGxl"  # 明文：secret_key_example
  endpoint: "http://s3.example.com"  # 非敏感字段，明文存储
```

#### 6.5.2 Pydantic 模型集成

在 Pydantic 配置模型中，通过validator装饰器自动触发解码逻辑，确保模型加载后敏感字段为明文：

```python
from pydantic import BaseModel, Field, validator
from typing import Optional

class S3Config(BaseModel):
    """S3配置模型（集成Base64自动解码）"""
    access_key: str = Field(..., description="S3 Access Key（支持Base64编码，前缀base64://）")
    secret_key: str = Field(..., description="S3 Secret Key（支持Base64编码，前缀base64://）")
    endpoint: str = Field(..., description="S3服务端点")
    @validator("access_key", "secret_key", pre=True)
    def auto_decode_base64(cls, v):
        """自动解码Base64编码的敏感字段"""
        return Base64Codec.decode(v)

# Pipeline配置模型保持不变
class PipelineConfig(BaseModel):
    # ... 其他字段不变
    s3_config: Optional[S3Config] = Field(default=None, description="S3连接配置（敏感字段支持Base64编码）")
```

#### 6.5.3 环境变量注入兼容

环境变量中注入的敏感信息，同样支持 Base64 编码格式（带base64://前缀），解码逻辑与配置文件一致：

```bash
# 环境变量注入编码后的access_key（明文：AKIAEXAMPLE）
export MI_PIPELINE_CONF_S3_CONFIG__ACCESS_KEY="base64://QUtJQUVYQU1QTEU="
```

OmegaConf 加载环境变量后，Pydantic 验证阶段会自动解码。

### 6.6 辅助工具：命令行编解码工具

为简化用户编码操作，提供命令行工具快速生成 Base64 编码串，避免手动编码错误：

```python
# pipeline/cli.py
import click
from pipeline.utils.codec import Base64Codec

@click.group()
def cli():
    pass

@cli.command("encode")
@click.argument("plaintext")
def encode(plaintext: str):
    """对明文进行Base64编码（输出带base64://前缀）"""
    encoded = Base64Codec.encode(plaintext)
    click.echo(f"编码结果：{encoded}")

@cli.command("decode")
@click.argument("encoded_str")
def decode(encoded_str: str):
    """对带base64://前缀的编码串解码"""
    plaintext = Base64Codec.decode(encoded_str)
    click.echo(f"解码结果：{plaintext}")

if __name__ == "__main__":
    cli()
```

使用示例：

```bash
# 编码明文AKIAEXAMPLE
python -m pipeline.cli encode "AKIAEXAMPLE"
# 输出：编码结果：base64://QUtJQUVYQU1QTEU=
# 解码编码串
python -m pipeline.cli decode "base64://QUtJQUVYQU1QTEU="
# 输出：解码结果：AKIAEXAMPLE
```

### 6.7 安全约束与最佳实践

* **编码字段标记**：所有敏感字段编码后必须添加base64://前缀，否则 Pydantic 模型不会自动解码，导致配置失效。
* **Git 提交规范**：严禁将未编码的明文敏感信息提交至 Git 仓库，建议在gitignore中排除本地测试用的配置文件（如pipeline_config.local.yaml）。
* **内存安全**：敏感信息解码后仅在内存中临时存储，使用完成后通过del语句清除，避免内存泄露。
* **适用场景**：仅用于保护 Git 仓库中的配置文件敏感信息，不建议用于传输过程中的敏感数据保护（Base64 为编码而非加密，易被破解）。