"""命令行接口"""
import click
import sys
from pathlib import Path
from omegaconf import OmegaConf
from pydantic import ValidationError

from general_pipeline.utils.codec import Base64Codec
from general_pipeline.models.pipeline_config import PipelineConfig
from general_pipeline.core.pipeline_executor import PipelineExecutor
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
@click.option("--conf", "-c", required=True, help="产线配置文件路径")
def validate_cmd(conf: str):
    """校验产线配置文件"""
    config_path = Path(conf)
    
    if not config_path.exists():
        click.echo(f"❌ 配置文件不存在：{config_path}", err=True)
        sys.exit(1)
    
    try:
        # 加载配置
        click.echo(f"正在加载配置文件：{config_path}")
        omega_conf = OmegaConf.load(config_path)
        
        # 转换为字典
        config_dict = OmegaConf.to_container(omega_conf, resolve=True)
        
        # 验证配置
        click.echo("正在验证配置...")
        pipeline_config = PipelineConfig(**config_dict)
        
        # 验证依赖关系
        executor = PipelineExecutor(pipeline_config)
        executor.validate_dependencies()
        
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


@cli.command("run")
@click.option("--conf", "-c", required=True, help="产线配置文件路径")
def run(conf: str):
    """运行产线"""
    config_path = Path(conf)
    
    if not config_path.exists():
        click.echo(f"❌ 配置文件不存在：{config_path}", err=True)
        sys.exit(1)
    
    try:
        # 加载配置
        click.echo(f"正在加载配置文件：{config_path}")
        omega_conf = OmegaConf.load(config_path)
        
        # 处理环境变量覆盖
        env_override = OmegaConf.from_dotlist([])
        # 可以从环境变量 PIPELINE_CONF_OVERRIDE 读取覆盖项
        import os
        override_str = os.environ.get("PIPELINE_CONF_OVERRIDE", "")
        if override_str:
            override_pairs = [pair.strip() for pair in override_str.split(",") if pair.strip()]
            env_override = OmegaConf.from_dotlist(override_pairs)
            omega_conf = OmegaConf.merge(omega_conf, env_override)
        
        # 转换为字典
        config_dict = OmegaConf.to_container(omega_conf, resolve=True)
        
        # 创建配置对象
        pipeline_config = PipelineConfig(**config_dict)
        
        # 创建执行器并运行
        click.echo(f"开始运行产线：{pipeline_config.pipeline_id}")
        executor = PipelineExecutor(pipeline_config)
        exit_code = executor.run()
        
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
