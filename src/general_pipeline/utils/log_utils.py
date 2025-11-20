"""日志工具模块"""
from loguru import logger
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    log_path: Optional[Path] = None,
    level: str = "INFO",
    rotation: str = "10 GB",
    retention: int = 30,
    format_string: Optional[str] = None
) -> None:
    """
    配置 Loguru 日志
    :param log_path: 日志文件路径
    :param level: 日志级别
    :param rotation: 轮转规则
    :param retention: 保留天数
    :param format_string: 自定义格式字符串
    """
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stderr,
        level=level,
        format=format_string or "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # 如果指定了日志文件路径，添加文件输出
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_path),
            level=level,
            rotation=rotation,
            retention=f"{retention} days",
            format=format_string or "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            serialize=False  # 可以改为 True 输出 JSON 格式
        )


def get_logger():
    """获取 logger 实例"""
    return logger
