"""命令行接口"""
import os
import sys
from pathlib import Path

import click
import toml
from pydantic import ValidationError

from general_pipeline.core.pipeline_executor import PipelineExecutor
from general_pipeline.core.project_initiator import ProjectInitiator
from general_pipeline.models.pipeline_config import PipelineConfig
from general_pipeline.utils.codec import Base64Codec
from general_pipeline.utils.config_loader import HierarchicalConfigLoader
from general_pipeline.utils.log_utils import get_logger

logger = get_logger()


@click.group()
def cli():
    """General Pipeline CLI - 数据产线命令行工具"""
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


@cli.command("validate")
@click.option("--conf", "-c", required=True, help="产线配置文件路径（TOML格式）")
@click.option("--config-root", help="配置根目录（用于层级化加载）")
def validate_cmd(conf: str, config_root: str = None):
    """校验产线配置文件"""
    config_path = Path(conf)
    
    if not config_path.exists():
        click.echo(f"❌ 配置文件不存在：{config_path}", err=True)
        sys.exit(1)
    
    try:
        # 加载配置
        click.echo(f"正在加载配置文件：{config_path}")
        
        # 如果指定了配置根目录，使用层级化加载
        if config_root:
            loader = HierarchicalConfigLoader(Path(config_root))
            config_dict = loader.load_and_integrate(config_path)
        else:
            # 直接加载TOML文件
            with open(config_path, "r", encoding="utf-8") as f:
                config_dict = toml.load(f)
        
        # 验证配置
        click.echo("正在验证配置...")
        pipeline_config = PipelineConfig(**config_dict)
        
        # 验证依赖关系
        initiator = ProjectInitiator(pipeline_config)
        initiator.validate_dependencies()
        
        click.echo(f"✅ 配置验证通过：{config_path}")
        click.echo(f"   产线ID: {pipeline_config.pipeline_id}")
        click.echo(f"   产线名称: {pipeline_config.name}")
        click.echo(f"   算子数量: {len(pipeline_config.operators)}")
        click.echo(f"   节点数量: {len(pipeline_config.nodes)}")
        sys.exit(0)
        
    except ValidationError as e:
        click.echo(f"❌ 配置验证失败：", err=True)
        for error in e.errors():
            click.echo(f"   字段: {'.'.join(str(loc) for loc in error['loc'])}", err=True)
            click.echo(f"   错误: {error['msg']}", err=True)
        sys.exit(1)
        
    except Exception as e:
        click.echo(f"❌ 配置验证失败：{e}", err=True)
        sys.exit(1)


@cli.command("init")
@click.option("--conf", "-c", required=True, help="产线配置文件路径（TOML格式）")
@click.option("--config-root", help="配置根目录（用于层级化加载）")
@click.option("--project-root", "-p", help="项目根目录（默认自动查找）")
@click.option("--operators-dir", "-o", default="operators", help="算子代码目录名（默认：operators）")
def init(conf: str, config_root: str = None, project_root: str = None, operators_dir: str = "operators"):
    """初始化项目（验证配置、克隆代码、创建环境）"""
    config_path = Path(conf)
    
    if not config_path.exists():
        click.echo(f"❌ 配置文件不存在：{config_path}", err=True)
        sys.exit(1)
    
    try:
        # 加载配置
        click.echo(f"正在加载配置文件：{config_path}")
        
        # 如果指定了配置根目录，使用层级化加载并导出集成配置
        if config_root:
            loader = HierarchicalConfigLoader(Path(config_root))
            config_dict = loader.load_and_integrate(config_path)
            # 导出集成配置
            integrated_file = loader.dump_integrated_config(config_dict)
            click.echo(f"集成配置已保存到：{integrated_file}")
        else:
            # 直接加载TOML文件
            with open(config_path, "r", encoding="utf-8") as f:
                config_dict = toml.load(f)
        
        # 创建配置对象
        pipeline_config = PipelineConfig(**config_dict)
        
        # 创建初始化器并初始化
        click.echo(f"开始初始化项目：{pipeline_config.pipeline_id}")
        root_path = Path(project_root) if project_root else None
        initiator = ProjectInitiator(pipeline_config, project_root=root_path, operators_dir=operators_dir)
        initiator.initialize_all()
        
        click.echo(f"✅ 项目初始化完成")
        sys.exit(0)
        
    except Exception as e:
        click.echo(f"❌ 项目初始化失败：{e}", err=True)
        logger.error(f"项目初始化异常", exc_info=True)
        sys.exit(1)


@cli.command("run")
@click.option("--conf", "-c", required=True, help="产线配置文件路径（TOML格式）")
@click.option("--config-root", help="配置根目录（用于层级化加载）")
@click.option("--skip-init", is_flag=True, help="跳过初始化步骤（假设已经初始化）")
@click.option("--project-root", "-p", help="项目根目录（默认自动查找）")
@click.option("--operators-dir", "-o", default="operators", help="算子代码目录名（默认：operators）")
@click.option("--node", "-n", help="只运行指定节点")
@click.option("--operator", "-op", help="只运行指定算子")
def run(conf: str, config_root: str = None, skip_init: bool = False, project_root: str = None, 
        operators_dir: str = "operators", node: str = None, operator: str = None):
    """运行产线"""
    config_path = Path(conf)
    
    if not config_path.exists():
        click.echo(f"❌ 配置文件不存在：{config_path}", err=True)
        sys.exit(1)
    
    try:
        # 加载配置
        click.echo(f"正在加载配置文件：{config_path}")
        
        # 如果指定了配置根目录，使用层级化加载
        if config_root:
            loader = HierarchicalConfigLoader(Path(config_root))
            config_dict = loader.load_and_integrate(config_path)
        else:
            # 直接加载TOML文件
            with open(config_path, "r", encoding="utf-8") as f:
                config_dict = toml.load(f)
        # 创建配置对象
        pipeline_config = PipelineConfig(**config_dict)
        
        # 如果不跳过初始化，先执行初始化
        if not skip_init:
            click.echo(f"开始项目初始化：{pipeline_config.pipeline_id}")
            root_path = Path(project_root) if project_root else None
            initiator = ProjectInitiator(pipeline_config, project_root=root_path, operators_dir=operators_dir)
            initiator.initialize_all()
            click.echo(f"✅ 项目初始化完成")
        
        # 创建执行器并运行
        click.echo(f"开始运行产线：{pipeline_config.pipeline_id}")
        if operator:
            click.echo(f"  目标算子：{operator}")
        elif node:
            click.echo(f"  目标节点：{node}")
        
        executor = PipelineExecutor(pipeline_config)
        exit_code = executor.run(target_node=node, target_operator=operator)
        
        if exit_code == 0:
            click.echo(f"✅ 产线执行成功")
        else:
            click.echo(f"❌ 产线执行失败，exit_code={exit_code}", err=True)
        
        sys.exit(exit_code)
        
    except Exception as e:
        click.echo(f"❌ 产线执行失败：{e}", err=True)
        logger.error(f"产线执行异常", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
