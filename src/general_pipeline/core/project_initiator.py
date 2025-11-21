"""项目初始化器"""
from pathlib import Path
from typing import Dict

import rootutils
from git import Repo

from general_pipeline.models.operator_config import OperatorConfig
from general_pipeline.models.pipeline_config import PipelineConfig
from general_pipeline.utils.exceptions import DependencyMissingError
from general_pipeline.utils.log_utils import get_logger
from general_pipeline.utils.s3_utils import get_or_create_s3_client

logger = get_logger()


class ProjectInitiator:
    """项目初始化器，负责验证配置、克隆代码、创建环境"""

    def __init__(self, config: PipelineConfig, project_root: Path = None, operators_dir: str = "operators"):
        """
        初始化项目初始化器
        :param config: 产线配置
        :param project_root: 项目根目录（如果为None，使用rootutils查找）
        :param operators_dir: 算子代码存储目录名（相对project_root）
        """
        self.config = config
        self.operator_map: Dict[str, OperatorConfig] = {}
        self.env_cache: Dict[str, Path] = {}
        
        # 确定项目根目录
        if project_root is None:
            try:
                self.project_root = rootutils.find_root(search_from=__file__, indicator=".project_root")
            except Exception as e:
                raise FileNotFoundError(
                    "未找到项目根目录标记文件 '.project_root'。"
                    "请在项目根目录创建一个空的 .project_root 文件，或通过 --project-root 参数指定项目根目录。"
                ) from e
        else:
            self.project_root = Path(project_root)
        
        self.operators_dir = operators_dir
        logger.info(f"项目根目录：{self.project_root}")
        logger.info(f"算子代码目录：{self.project_root / operators_dir}")
        
        # 构建算子映射
        for operator in config.operators:
            self.operator_map[operator.operator_id] = operator

    def validate_dependencies(self) -> None:
        """验证算子依赖关系"""
        logger.info("开始验证算子依赖关系")
        
        for operator in self.config.operators:
            for dep_id in operator.upstream_dependencies:
                if dep_id not in self.operator_map:
                    raise DependencyMissingError(
                        f"算子 {operator.operator_id} 依赖的算子 {dep_id} 不存在"
                    )
        
        logger.info("算子依赖关系验证通过")

    def clone_operator_code(self, operator: OperatorConfig) -> Path:
        """
        克隆算子代码（使用GitPython）
        :param operator: 算子配置
        :return: 代码路径
        """
        code_path = self.project_root / self.operators_dir / operator.operator_id
        
        if code_path.exists():
            logger.info(f"算子代码已存在，跳过克隆：{code_path}")
            return code_path
        
        logger.info(f"开始克隆算子代码：{operator.git_repo} (tag: {operator.git_tag})")
        
        try:
            # 使用GitPython克隆代码
            Repo.clone_from(
                operator.git_repo,
                str(code_path),
                branch=operator.git_tag,
                depth=1
            )
            logger.info(f"算子代码克隆完成：{code_path}")
            return code_path
        except Exception as e:
            logger.error(f"算子代码克隆失败：{e}")
            raise

    def setup_virtual_env(self, operator: OperatorConfig) -> None:
        """
        设置虚拟环境
        :param operator: 算子配置
        """
        env_config = operator.env_config
        env_type = type(env_config).__name__
        env_key = f"{env_type}_{env_config.env_name}"
        
        # 检查环境缓存
        if env_key in self.env_cache:
            logger.info(f"复用已存在的虚拟环境：{env_key}")
            return
        
        # 设置环境根路径（使用project_root）
        env_root_path = self.project_root / "envs"
        env_config.env_root_path = env_root_path
        
        # 注入算子代码路径
        if hasattr(env_config, "operator_code_path"):
            env_config.operator_code_path = operator.code_path
        
        # 如果有S3配置，注册S3客户端（不直接注入到env_config）
        if self.config.s3_config:
            # 注册所有可能的S3客户端
            # Conda环境会通过s3_utils自动查找
            if hasattr(env_config, "s3_compress_path"):
                try:
                    s3_path_info = env_config.s3_compress_path.replace("s3://", "").split("/", 1)
                    bucket_name = s3_path_info[0] if s3_path_info else "default"
                    
                    get_or_create_s3_client(
                        bucket_name=bucket_name,
                        endpoint=self.config.s3_config.endpoint,
                        access_key=self.config.s3_config.access_key,
                        secret_key=self.config.s3_config.secret_key,
                        region=self.config.s3_config.region
                    )
                except Exception as e:
                    logger.warning(f"S3客户端注册失败: {e}")

        
        # 安装环境
        env_full_path = env_config.get_full_env_path()
        if not env_full_path.exists():
            logger.info(f"开始创建虚拟环境：{env_key}")
            env_config.install_env()
        else:
            logger.info(f"虚拟环境已存在：{env_key}")
        
        # 加入缓存
        self.env_cache[env_key] = env_full_path

    def initialize_all(self) -> None:
        """
        完整初始化流程：验证依赖 -> 克隆代码 -> 创建环境
        """
        logger.info("开始项目初始化")
        
        # 1. 验证依赖关系
        self.validate_dependencies()
        
        # 2. 克隆所有算子代码
        for operator in self.config.operators:
            code_path = self.clone_operator_code(operator)
            operator.code_path = code_path
        
        # 3. 设置所有虚拟环境
        for operator in self.config.operators:
            self.setup_virtual_env(operator)
        
        logger.info("项目初始化完成")
