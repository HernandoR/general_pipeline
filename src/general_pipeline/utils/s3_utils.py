"""S3 工具模块"""
from typing import Dict, Optional

# 全局S3客户端池
_s3_clients: Dict[str, any] = {}


def parse_s3_path(s3_path: str) -> Dict[str, str]:
    """
    解析 S3 路径为 bucket 和 key
    S3路径格式: bucket_name/key/path 或 s3://bucket_name/key/path
    第一部分会被视为 bucket name
    
    :param s3_path: S3 路径
    :return: 包含 bucket 和 key 的字典
    """
    # 移除 s3:// 前缀（如果有）
    path = s3_path.replace("s3://", "")
    
    # 分割路径，第一部分是bucket，其余是key
    parts = path.split("/", 1)
    if len(parts) < 2:
        raise ValueError(f"Invalid S3 path format: {s3_path}, expected format: bucket/key")
    
    return {
        "bucket": parts[0],
        "key": parts[1]
    }


def register_s3_client(bucket_name: str, s3_client: any) -> None:
    """
    注册S3客户端到全局池
    
    :param bucket_name: Bucket名称，用作客户端标识
    :param s3_client: boto3 S3客户端实例
    """
    _s3_clients[bucket_name] = s3_client


def get_s3_client(bucket_name: str) -> Optional[any]:
    """
    从全局池获取S3客户端
    
    :param bucket_name: Bucket名称
    :return: S3客户端实例，如果不存在返回None
    """
    return _s3_clients.get(bucket_name)


def get_or_create_s3_client(bucket_name: str, endpoint: str, access_key: str, secret_key: str, region: Optional[str] = None) -> any:
    """
    获取或创建S3客户端
    
    :param bucket_name: Bucket名称
    :param endpoint: S3端点
    :param access_key: 访问密钥
    :param secret_key: 密钥
    :param region: 区域（可选）
    :return: S3客户端实例
    """
    client = get_s3_client(bucket_name)
    if client is None:
        try:
            import boto3
            client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            register_s3_client(bucket_name, client)
        except ImportError as e:
            raise ImportError("boto3 is required for S3 operations. Install it with: pip install boto3") from e
    return client
