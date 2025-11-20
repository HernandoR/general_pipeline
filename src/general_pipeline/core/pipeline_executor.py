"""产线执行器"""
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict

from general_pipeline.core.resource_monitor import ResourceMonitor
from general_pipeline.models.operator_config import OperatorConfig
from general_pipeline.models.pipeline_config import PipelineConfig
from general_pipeline.utils.exceptions import DependencyMissingError
from general_pipeline.utils.log_utils import get_logger, setup_logger
from general_pipeline.utils.path_utils import ensure_dir_exists

logger = get_logger()


class PipelineExecutor:
    """产线执行器，负责初始化、调度和执行产线"""

    def __init__(self, config: PipelineConfig):
        """
        初始化产线执行器
        :param config: 产线配置
        """
        self.config = config
        self.operator_map: Dict[str, OperatorConfig] = {}
        self.env_cache: Dict[str, Path] = {}  # 环境缓存：env_key -> env_path
        
        # 初始化日志
        self._setup_logging()
        
        # 初始化工作目录
        self._init_workspace()
        
        # 构建算子映射
        for operator in config.operators:
            self.operator_map[operator.operator_id] = operator

    def _setup_logging(self) -> None:
        """设置日志"""
        if self.config.log_config:
            log_path = self.config.log_config.log_path
            if not log_path:
                timestamp = time.strftime("%Y%m%d%H%M%S")
                log_path = self.config.work_dir / "logs" / f"pipeline_{self.config.pipeline_id}_{timestamp}.log"
            
            setup_logger(
                log_path=log_path,
                level=self.config.log_config.level,
                rotation=self.config.log_config.rotation,
                retention=self.config.log_config.retention
            )
        logger.info(f"产线初始化开始：{self.config.pipeline_id}")

    def _init_workspace(self) -> None:
        """初始化工作目录"""
        ensure_dir_exists(self.config.work_dir)
        
        # 创建标准目录结构
        for subdir in ["operators", "envs", "logs", "input", "output", "workspace", "cache"]:
            ensure_dir_exists(self.config.work_dir / subdir)
        
        logger.info(f"工作目录初始化完成：{self.config.work_dir}")

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
        克隆算子代码
        :param operator: 算子配置
        :return: 代码路径
        """
        code_path = self.config.work_dir / "operators" / operator.operator_id
        
        if code_path.exists():
            logger.info(f"算子代码已存在，跳过克隆：{code_path}")
            return code_path
        
        logger.info(f"开始克隆算子代码：{operator.git_repo} (tag: {operator.git_tag})")
        
        try:
            # 克隆代码
            subprocess.run(
                ["git", "clone", "--branch", operator.git_tag, "--depth", "1", 
                 operator.git_repo, str(code_path)],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"算子代码克隆完成：{code_path}")
            return code_path
        except subprocess.CalledProcessError as e:
            logger.error(f"算子代码克隆失败：{e.stderr}")
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
        
        # 设置环境根路径
        env_root_path = self.config.work_dir / "envs"
        env_config.env_root_path = env_root_path
        
        # 注入算子代码路径
        if hasattr(env_config, "operator_code_path"):
            env_config.operator_code_path = operator.code_path
        
        # 注入S3客户端（如果是Conda环境）
        if hasattr(env_config, "s3_client") and self.config.s3_config:
            try:
                import boto3
                s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.config.s3_config.endpoint,
                    aws_access_key_id=self.config.s3_config.access_key,
                    aws_secret_access_key=self.config.s3_config.secret_key,
                    region_name=self.config.s3_config.region
                )
                env_config.s3_client = s3_client
            except ImportError:
                logger.warning("boto3未安装，无法使用S3功能")
        
        # 安装环境
        env_full_path = env_config.get_full_env_path()
        if not env_full_path.exists():
            logger.info(f"开始创建虚拟环境：{env_key}")
            env_config.install_env()
        else:
            logger.info(f"虚拟环境已存在：{env_key}")
        
        # 加入缓存
        self.env_cache[env_key] = env_full_path

    def execute_operator(self, operator: OperatorConfig, node_id: str) -> int:
        """
        执行单个算子
        :param operator: 算子配置
        :param node_id: 节点ID
        :return: exit_code
        """
        logger.info(f"开始执行算子：{operator.operator_id}")
        
        # 准备环境变量
        env_vars = os.environ.copy()
        env_vars.update(operator.env_config.activate_env())
        env_vars.update(operator.extra_env_vars)
        
        # 添加标准环境变量
        env_vars.update({
            "PIPELINE_ID": self.config.pipeline_id,
            "NODE_ID": node_id,
            "OPERATOR_ID": operator.operator_id,
            "WORK_DIR": str(self.config.work_dir)
        })
        
        # 执行命令
        try:
            process = subprocess.Popen(
                operator.start_command,
                shell=True,
                cwd=str(operator.code_path),
                env=env_vars,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # 启动资源监控
            monitor = ResourceMonitor(process.pid)
            start_time = time.time()
            
            # 等待执行完成或超时
            while True:
                # 检查进程是否结束
                retcode = process.poll()
                if retcode is not None:
                    # 进程已结束
                    break
                
                # 检查超时
                elapsed_time = time.time() - start_time
                if elapsed_time > operator.timeout:
                    logger.error(f"算子执行超时（{operator.timeout}秒），强制终止")
                    process.send_signal(signal.SIGTERM)
                    time.sleep(5)
                    if process.poll() is None:
                        process.kill()
                    return 4  # 资源异常
                
                # 记录资源使用
                monitor.log_resource_usage(
                    self.config.pipeline_id, node_id, operator.operator_id
                )
                
                # 读取输出
                line = process.stdout.readline()
                if line:
                    logger.info(f"[{operator.operator_id}] {line.strip()}")
                
                time.sleep(monitor.monitor_interval)
            
            # 读取剩余输出
            for line in process.stdout:
                logger.info(f"[{operator.operator_id}] {line.strip()}")
            
            exit_code = process.returncode
            logger.info(f"算子执行完成：{operator.operator_id}，exit_code={exit_code}")
            return exit_code
            
        except Exception as e:
            logger.error(f"算子执行失败：{operator.operator_id}，错误：{e}")
            return 3  # 执行逻辑错误

    def run(self) -> int:
        """
        运行产线
        :return: 整体exit_code
        """
        try:
            # 1. 验证依赖关系
            self.validate_dependencies()
            
            # 2. 克隆算子代码
            for operator in self.config.operators:
                code_path = self.clone_operator_code(operator)
                operator.code_path = code_path
            
            # 3. 设置虚拟环境
            for operator in self.config.operators:
                self.setup_virtual_env(operator)
            
            # 4. 按节点执行算子
            for node in self.config.nodes:
                logger.info(f"开始执行节点：{node.node_id}")
                
                for operator_id in node.operator_ids:
                    operator = self.operator_map.get(operator_id)
                    if not operator:
                        logger.error(f"节点 {node.node_id} 中的算子 {operator_id} 不存在")
                        return 1
                    
                    exit_code = self.execute_operator(operator, node.node_id)
                    if exit_code != 0:
                        logger.error(f"算子执行失败，终止产线，exit_code={exit_code}")
                        return exit_code
                
                logger.info(f"节点执行完成：{node.node_id}")
            
            logger.info("产线执行完成")
            return 0
            
        except Exception as e:
            logger.error(f"产线执行异常：{e}", exc_info=True)
            return 3
