"""S3 工具模块"""
from typing import Dict
import re


def parse_s3_path(s3_path: str) -> Dict[str, str]:
    """
    解析 S3 路径为 bucket 和 key
    :param s3_path: S3 路径，格式：s3://bucket/key
    :return: 包含 bucket 和 key 的字典
    """
    match = re.match(r"s3://([^/]+)/(.+)", s3_path)
    if not match:
        raise ValueError(f"Invalid S3 path format: {s3_path}")
    return {
        "bucket": match.group(1),
        "key": match.group(2)
    }
