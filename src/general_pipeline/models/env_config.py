"""虚拟环境配置模型"""
from pydantic import BaseModel, Field, field_validator
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
import os

from general_pipeline.utils.path_utils import ensure_dir_exists
from general_pipeline.utils.log_utils import get_logger
from general_pipeline.utils.exceptions import EnvInstallError
from general_pipeline.utils.s3_utils import parse_s3_path

logger = get_logger()


class BaseVirtualEnvConfig(BaseModel, ABC):
    """
    虚拟环境配置抽象基类，定义环境创建（install_env）和激活（activate_env）接口
    所有具体虚拟环境类型需继承此类并实现抽象方法
    """
    # 虚拟环境存储根路径（由Pipeline层初始化时注入，无需用户配置）
    env_root_path: Optional[Path] = Field(default=None, exclude=True)
    # 虚拟环境名称（算子唯一标识作为默认值，确保环境隔离）
    env_name: str = Field(description="虚拟环境名称，默认使用算子ID")

    model_config = {"arbitrary_types_allowed": True}

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


class UVVirtualEnvConfig(BaseVirtualEnvConfig):
    """UV虚拟环境配置模型（对应uv_project类型）"""
    # UV项目必需：pyproject.toml文件路径（相对算子代码根目录）
    pyproject_path: Path = Field(..., description="pyproject.toml文件路径（相对算子代码根目录）")
    # 可选：UV额外安装参数（如--no-cache、--python 3.11等）
    uv_extra_args: Optional[List[str]] = Field(default=None, description="UV安装额外参数")
    # 算子代码路径（需要注入）
    operator_code_path: Optional[Path] = Field(default=None, exclude=True)

    @field_validator("pyproject_path")
    @classmethod
    def validate_pyproject_path(cls, v):
        """校验pyproject_path是否以pyproject.toml结尾，确保路径正确性"""
        if v.name != "pyproject.toml":
            raise ValueError(f"UV项目的pyproject_path必须指向pyproject.toml文件，当前为：{v}")
        return v

    def install_env(self) -> None:
        """实现UV环境安装：创建虚拟环境 + 基于pyproject.toml安装依赖"""
        logger.info(f"开始安装UV虚拟环境：{self.get_full_env_path()}")
        ensure_dir_exists(self.env_root_path)

        # 1. 构建UV创建虚拟环境命令
        env_full_path = self.get_full_env_path()
        create_cmd = ["uv", "venv", str(env_full_path)]
        
        # 2. 执行创建命令
        result = subprocess.run(create_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise EnvInstallError(
                f"UV虚拟环境创建失败（{self.env_name}）：\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        # 3. 基于pyproject.toml安装依赖
        if self.operator_code_path:
            uv_python_path = env_full_path / "bin" / "python"
            install_cmd = [str(uv_python_path), "-m", "pip", "install", "-e", "."]
            if self.uv_extra_args:
                install_cmd.extend(self.uv_extra_args)
            
            result = subprocess.run(
                install_cmd,
                cwd=str(self.operator_code_path),
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
        env_path = self.get_full_env_path() / "bin"
        return {
            "PATH": f"{str(env_path)}:{os.environ.get('PATH', '')}",
            "UV_ENV_ACTIVATED": "true",
            "VIRTUAL_ENV": str(self.get_full_env_path())
        }


class PixiVirtualEnvConfig(BaseVirtualEnvConfig):
    """Pixi虚拟环境配置模型（对应pixi_project类型）"""
    # Pixi项目必需：pixi.toml文件路径（相对算子代码根目录）
    pixi_toml_path: Path = Field(..., description="pixi.toml文件路径（相对算子代码根目录）")
    # 可选：Pixi环境通道（如conda-forge、pypi等）
    pixi_channels: Optional[List[str]] = Field(default=["conda-forge"], description="Pixi环境通道")
    # 可选：Pixi额外安装参数
    pixi_extra_args: Optional[List[str]] = Field(default=None, description="Pixi安装额外参数")
    # 算子代码路径（需要注入）
    operator_code_path: Optional[Path] = Field(default=None, exclude=True)

    @field_validator("pixi_toml_path")
    @classmethod
    def validate_pixi_toml_path(cls, v):
        """校验pixi_toml_path是否以pixi.toml结尾，确保路径正确性"""
        if v.name != "pixi.toml":
            raise ValueError(f"Pixi项目的pixi_toml_path必须指向pixi.toml文件，当前为：{v}")
        return v

    def install_env(self) -> None:
        """实现Pixi环境安装：基于pixi.toml创建环境并安装依赖"""
        logger.info(f"开始安装Pixi虚拟环境：{self.get_full_env_path()}")
        ensure_dir_exists(self.env_root_path)
        
        if not self.operator_code_path:
            raise EnvInstallError("算子代码路径未注入Pixi虚拟环境配置")
            
        pixi_toml_full_path = self.operator_code_path / self.pixi_toml_path

        # 1. 校验pixi.toml文件是否存在
        if not pixi_toml_full_path.exists():
            raise FileNotFoundError(f"Pixi配置文件不存在：{pixi_toml_full_path}")

        # 2. 使用pixi install创建环境
        install_cmd = ["pixi", "install", "--manifest-path", str(pixi_toml_full_path)]
        if self.pixi_extra_args:
            install_cmd.extend(self.pixi_extra_args)

        result = subprocess.run(install_cmd, capture_output=True, text=True, check=False, cwd=str(self.operator_code_path))
        if result.returncode != 0:
            raise EnvInstallError(
                f"Pixi虚拟环境创建失败（{self.env_name}）：\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        logger.info(f"Pixi虚拟环境安装完成：{self.get_full_env_path()}")

    def activate_env(self) -> Dict[str, str]:
        """实现Pixi环境激活：返回包含PATH、CONDA_DEFAULT_ENV的环境变量字典"""
        env_bin_path = self.get_full_env_path() / "bin"
        return {
            "PATH": f"{str(env_bin_path)}:{os.environ.get('PATH', '')}",
            "CONDA_DEFAULT_ENV": self.env_name,
            "PIXI_ENV_ACTIVATED": "true",
            "CONDA_PREFIX": str(self.get_full_env_path())
        }


class CondaVirtualEnvConfig(BaseVirtualEnvConfig):
    """Conda虚拟环境配置模型（对应conda_project类型）"""
    # Conda项目必需：S3上的zstd压缩包路径
    s3_compress_path: str = Field(..., description="S3上conda环境zstd压缩包路径（如s3://conda-envs/env-v1.zst）")
    # 可选：解压后是否执行conda env update（用于修复环境路径）
    need_conda_update: bool = Field(default=True, description="解压后是否执行conda env update修复路径")
    # 可选：zstd解压额外参数
    zstd_extra_args: Optional[List[str]] = Field(default=None, description="zstd解压额外参数")
    # S3客户端（需要注入）
    s3_client: Optional[Any] = Field(default=None, exclude=True)

    def install_env(self) -> None:
        """实现Conda环境安装：从S3下载压缩包 + zstd解压 + 可选conda env update"""
        logger.info(f"开始安装Conda虚拟环境：{self.get_full_env_path()}")
        ensure_dir_exists(self.env_root_path)

        if not self.s3_client:
            logger.warning("S3客户端未配置，跳过S3下载步骤")
            return

        # 1. 从S3下载压缩包到临时目录
        temp_compress_path = self.env_root_path / f"{self.env_name}.zst"
        try:
            logger.info(f"从S3下载conda压缩包：{self.s3_compress_path} -> {temp_compress_path}")
            s3_info = parse_s3_path(self.s3_compress_path)
            self.s3_client.download_file(
                Bucket=s3_info["bucket"],
                Key=s3_info["key"],
                Filename=str(temp_compress_path)
            )
        except Exception as e:
            raise EnvInstallError(f"S3下载conda压缩包失败：{str(e)}")

        # 2. zstd解压压缩包到目标环境路径
        decompress_cmd = [
            "zstd", "-d", str(temp_compress_path),
            "-o", str(self.get_full_env_path()),
            "--recursive"
        ]
        if self.zstd_extra_args:
            decompress_cmd.extend(self.zstd_extra_args)
            
        result = subprocess.run(decompress_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise EnvInstallError(
                f"Conda环境解压失败（{self.env_name}）：\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        # 解压完成后删除临时压缩包
        temp_compress_path.unlink(missing_ok=True)

        # 3. 可选：执行conda env update修复解压后的环境路径
        if self.need_conda_update:
            conda_bin_path = self.get_full_env_path() / "bin" / "conda"
            if conda_bin_path.exists():
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
            "CONDA_SHLVL": "1"
        }
