"""层级化配置加载器"""
from pathlib import Path
from typing import Any, Dict, Optional

import toml

from general_pipeline.utils.log_utils import get_logger

logger = get_logger()


class HierarchicalConfigLoader:
    """
    层级化配置加载器
    
    配置目录结构:
    conf/
    ├── pipeline.toml           # 主产线配置
    ├── nodes/
    │   ├── node1_v1.0.toml     # 节点配置（带版本）
    │   └── node2_v1.0.toml
    ├── operators/
    │   ├── op1_v1.0.toml       # 算子配置（带版本）
    │   └── op2_v2.0.toml
    └── integration/             # 集成配置输出目录
        └── pipeline_20231120_120000.toml
    """
    
    def __init__(self, config_root: Path):
        """
        初始化配置加载器
        :param config_root: 配置根目录
        """
        self.config_root = Path(config_root)
        self.nodes_dir = self.config_root / "nodes"
        self.operators_dir = self.config_root / "operators"
        self.integration_dir = self.config_root / "integration"
        
        # 确保目录存在
        self.integration_dir.mkdir(parents=True, exist_ok=True)
    
    def load_pipeline_config(self, pipeline_file: Path) -> Dict[str, Any]:
        """
        加载主产线配置
        :param pipeline_file: 产线配置文件路径
        :return: 产线配置字典
        """
        if not pipeline_file.exists():
            raise FileNotFoundError(f"产线配置文件不存在: {pipeline_file}")
        
        logger.info(f"加载产线配置: {pipeline_file}")
        with open(pipeline_file, "r", encoding="utf-8") as f:
            config = toml.load(f)
        
        return config
    
    def load_node_config(self, node_id: str, version: str) -> Dict[str, Any]:
        """
        加载节点配置
        :param node_id: 节点ID
        :param version: 版本号
        :return: 节点配置字典
        """
        # 查找节点配置文件: node_id_version.toml
        node_file = self.nodes_dir / f"{node_id}_{version}.toml"
        
        if not node_file.exists():
            # 尝试不带版本的文件名
            node_file = self.nodes_dir / f"{node_id}.toml"
            if not node_file.exists():
                raise FileNotFoundError(f"节点配置文件不存在: {node_id}_{version}.toml or {node_id}.toml")
        
        logger.info(f"加载节点配置: {node_file}")
        with open(node_file, "r", encoding="utf-8") as f:
            config = toml.load(f)
        
        # 如果配置有嵌套结构（例如 [node_1]），提取内容
        if node_id in config:
            return config[node_id]
        
        return config
    
    def load_operator_config(self, operator_id: str, version: str) -> Dict[str, Any]:
        """
        加载算子配置
        :param operator_id: 算子ID
        :param version: 版本号
        :return: 算子配置字典
        """
        # 查找算子配置文件: operator_id_version.toml
        operator_file = self.operators_dir / f"{operator_id}_{version}.toml"
        
        if not operator_file.exists():
            # 尝试不带版本的文件名
            operator_file = self.operators_dir / f"{operator_id}.toml"
            if not operator_file.exists():
                raise FileNotFoundError(f"算子配置文件不存在: {operator_id}_{version}.toml or {operator_id}.toml")
        
        logger.info(f"加载算子配置: {operator_file}")
        with open(operator_file, "r", encoding="utf-8") as f:
            config = toml.load(f)
        
        # 如果配置有嵌套结构（例如 [example_operator_1]），提取内容
        if operator_id in config:
            return config[operator_id]
        
        return config
    
    def load_and_integrate(self, pipeline_file: Path) -> Dict[str, Any]:
        """
        加载并集成所有配置
        :param pipeline_file: 产线配置文件路径
        :return: 集成后的完整配置
        """
        # 1. 加载主产线配置
        raw_config = self.load_pipeline_config(pipeline_file)
        
        # 如果配置有嵌套结构（例如 [pipeline]），提取内容
        if "pipeline" in raw_config:
            pipeline_config = raw_config["pipeline"]
        else:
            pipeline_config = raw_config
        
        # 2. 加载并集成节点配置
        integrated_nodes = []
        nodes_refs = []
        
        # 处理不同的节点引用格式
        if "nodes" in pipeline_config:
            if isinstance(pipeline_config["nodes"], dict) and "refs" in pipeline_config["nodes"]:
                # 新格式: [pipeline.nodes] refs = [...]
                nodes_refs = pipeline_config["nodes"]["refs"]
            elif isinstance(pipeline_config["nodes"], list):
                # 旧格式: nodes = [...]
                nodes_refs = pipeline_config["nodes"]
        
        for node_ref in nodes_refs:
            # node_ref 可以是字符串 "node_id:version" 或字典
            if isinstance(node_ref, str):
                parts = node_ref.split(":")
                node_id = parts[0]
                version = parts[1] if len(parts) > 1 else "v1.0"
            elif isinstance(node_ref, dict):
                node_id = node_ref.get("node_id")
                version = node_ref.get("version", "v1.0")
            else:
                raise ValueError(f"不支持的节点引用格式: {node_ref}")
            
            node_config = self.load_node_config(node_id, version)
            integrated_nodes.append(node_config)
        
        pipeline_config["nodes"] = integrated_nodes
        
        # 3. 加载并集成算子配置
        integrated_operators = []
        operators_refs = []
        
        # 处理不同的算子引用格式
        if "operators" in pipeline_config:
            if isinstance(pipeline_config["operators"], dict) and "refs" in pipeline_config["operators"]:
                # 新格式: [pipeline.operators] refs = [...]
                operators_refs = pipeline_config["operators"]["refs"]
            elif isinstance(pipeline_config["operators"], list):
                # 旧格式: operators = [...]
                operators_refs = pipeline_config["operators"]
        
        for op_ref in operators_refs:
            # op_ref 可以是字符串 "operator_id:version" 或字典
            if isinstance(op_ref, str):
                parts = op_ref.split(":")
                operator_id = parts[0]
                version = parts[1] if len(parts) > 1 else "v1.0"
            elif isinstance(op_ref, dict):
                operator_id = op_ref.get("operator_id")
                version = op_ref.get("version", "v1.0")
            else:
                raise ValueError(f"不支持的算子引用格式: {op_ref}")
            
            operator_config = self.load_operator_config(operator_id, version)
            integrated_operators.append(operator_config)
        
        pipeline_config["operators"] = integrated_operators
        
        logger.info(f"配置集成完成: {len(integrated_operators)} 个算子, {len(integrated_nodes)} 个节点")
        return pipeline_config
    
    def dump_integrated_config(self, integrated_config: Dict[str, Any], filename: Optional[str] = None) -> Path:
        """
        导出集成配置到文件
        :param integrated_config: 集成后的配置
        :param filename: 文件名（可选，默认自动生成带时间戳的文件名）
        :return: 输出文件路径
        """
        if filename is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pipeline_id = integrated_config.get("pipeline_id", "pipeline")
            filename = f"{pipeline_id}_{timestamp}.toml"
        
        output_file = self.integration_dir / filename
        
        logger.info(f"导出集成配置到: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            toml.dump(integrated_config, f)
        
        return output_file
