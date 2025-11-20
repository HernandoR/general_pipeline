"""路径工具模块"""
from pathlib import Path


def ensure_dir_exists(path: Path) -> None:
    """
    确保目录存在，不存在则创建
    :param path: 目录路径
    """
    if path and not path.exists():
        path.mkdir(parents=True, exist_ok=True)
