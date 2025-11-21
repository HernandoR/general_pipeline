"""产线执行器"""
import os
from typing import Dict

from general_pipeline.models.operator_config import OperatorConfig
from general_pipeline.models.pipeline_config import PipelineConfig
from general_pipeline.utils.log_utils import get_logger, setup_logger
from general_pipeline.utils.path_utils import ensure_dir_exists
from general_pipeline.utils.subprocess_utils import run_cmd_stream

logger = get_logger()


class PipelineExecutor:
    """产线执行器，负责调度和执行产线（不包含初始化）"""

    def __init__(self, config: PipelineConfig):
        """
        初始化产线执行器
        :param config: 产线配置
        """
        self.config = config
        self.operator_map: Dict[str, OperatorConfig] = {}
        
        # 初始化日志
        self._setup_logging()
        
        # 记录配置信息
        self._log_config()
        
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
                import time
                timestamp = time.strftime("%Y%m%d%H%M%S")
                log_path = self.config.work_dir / "logs" / f"pipeline_{self.config.pipeline_id}_{timestamp}.log"
            
            setup_logger(
                log_path=log_path,
                level=self.config.log_config.level,
                rotation=self.config.log_config.rotation,
                retention=self.config.log_config.retention
            )
        logger.info(f"产线初始化开始：{self.config.pipeline_id}")

    def _log_config(self) -> None:
        """记录配置信息"""
        logger.info("=" * 60)
        logger.info("产线配置信息:")
        logger.info(f"  Pipeline ID: {self.config.pipeline_id}")
        logger.info(f"  Pipeline Name: {self.config.name}")
        logger.info(f"  Description: {self.config.description or 'N/A'}")
        logger.info(f"  Work Dir: {self.config.work_dir}")
        logger.info(f"  Operators Count: {len(self.config.operators)}")
        logger.info(f"  Nodes Count: {len(self.config.nodes)}")
        
        for idx, operator in enumerate(self.config.operators, 1):
            logger.info(f"  Operator {idx}: {operator.operator_id}")
            logger.info(f"    - Git Repo: {operator.git_repo}")
            logger.info(f"    - Git Tag: {operator.git_tag}")
            logger.info(f"    - Dependencies: {operator.upstream_dependencies or 'None'}")
        
        for idx, node in enumerate(self.config.nodes, 1):
            logger.info(f"  Node {idx}: {node.node_id}")
            logger.info(f"    - Operators: {node.operator_ids}")
            logger.info(f"    - Runner Count: {node.runner_count}")
        
        logger.info("=" * 60)

    def _init_workspace(self) -> None:
        """初始化工作目录"""
        ensure_dir_exists(self.config.work_dir)
        
        # 创建标准目录结构
        for subdir in ["logs", "input", "output", "workspace"]:
            ensure_dir_exists(self.config.work_dir / subdir)
        
        logger.info(f"工作目录初始化完成：{self.config.work_dir}")

    def execute_operator(self, operator: OperatorConfig, node_id: str) -> int:
        """
        执行单个算子
        :param operator: 算子配置
        :param node_id: 节点ID
        :return: exit_code
        """
        logger.info(f"开始执行算子：{operator.operator_id}")
        
        # 准备路径
        input_root = str(self.config.work_dir / "input" / operator.operator_id)
        output_root = str(self.config.work_dir / "workspace" / operator.operator_id)
        workspace_root = str(self.config.work_dir / "workspace" / self.config.pipeline_id / node_id / operator.operator_id)
        
        # 准备环境变量
        env_vars = os.environ.copy()
        env_vars.update(operator.env_config.activate_env())
        env_vars.update(operator.extra_env_vars)
        
        # 添加标准环境变量
        env_vars.update({
            "PIPELINE_ID": self.config.pipeline_id,
            "NODE_ID": node_id,
            "OPERATOR_ID": operator.operator_id,
            "INPUT_ROOT": input_root,
            "OUTPUT_ROOT": output_root,
            "WORKSPACE_ROOT": workspace_root,
        })
        
        # 构建完整命令（包含环境激活命令）
        env_cmd = operator.env_config.activate_env_cmd()
        full_command = " ".join(env_cmd + [operator.start_command]) if env_cmd else operator.start_command
        
        # 执行命令并实时输出
        def log_output(line: str):
            logger.info(f"[{operator.operator_id}] {line}")
        
        exit_code = run_cmd_stream(
            command=full_command,
            cwd=operator.code_path,
            env=env_vars,
            timeout=operator.timeout,
            shell=True,
            on_output=log_output
        )
        
        logger.info(f"算子执行完成：{operator.operator_id}，exit_code={exit_code}")
        return exit_code

    def run(self) -> int:
        """
        运行产线（仅执行阶段，不包含初始化）
        :return: 整体exit_code
        """
        try:
            logger.info("开始执行产线")
            
            # 按节点执行算子
            for node in self.config.nodes:
                logger.info(f"开始执行节点：{node.node_id}")
                
                for operator_id in node.operator_ids:
                    operator = self.operator_map.get(operator_id)
                    if not operator:
                        logger.error(f"节点 {node.node_id} 中的算子 {operator_id} 不存在")
                        return 1
                    
                    if not operator.code_path:
                        logger.error(f"算子 {operator_id} 代码路径未设置，请先运行项目初始化")
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
