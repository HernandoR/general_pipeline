"""S3 工具模块 - 支持多种云存储提供商"""
import os
from functools import wraps
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# 加载 s3_aksk.env 文件
load_dotenv("s3_aksk.env")

# 全局S3客户端池 - 按 provider 和 bucket 组织
_s3_clients: Dict[str, Dict[str, any]] = {}

# 全局S3配置注册表 - 按 (provider, bucket) 组织
_s3_config_registry: Dict[tuple[str, str], Dict[str, Any]] = {}


def register_s3_config(provider: str, bucket: str):
    """
    S3配置注册装饰器
    用于注册S3配置，支持从配置文件或代码中注册
    
    :param provider: 提供商名称 (s3, tos, ks3, oss, cos)
    :param bucket: 存储桶名称
    
    使用示例:
        @register_s3_config("tos", "my-bucket")
        def configure_tos_bucket():
            return {
                "endpoint": "https://tos-cn-beijing.volces.com",
                "access_key": "your_key",
                "secret_key": "your_secret",
                "region": "cn-beijing"
            }
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = func(*args, **kwargs)
            _s3_config_registry[(provider, bucket)] = config
            return config
        
        # 立即执行函数以注册配置
        wrapper()
        return wrapper
    
    return decorator


def get_s3_config(provider: str, bucket: str) -> Optional[Dict[str, Any]]:
    """
    从注册表获取S3配置
    
    :param provider: 提供商名称
    :param bucket: 存储桶名称
    :return: S3配置字典，如果不存在返回None
    """
    return _s3_config_registry.get((provider, bucket))


class S3Path(BaseModel):
    """
    S3路径模型，支持多种云存储提供商
    格式: provider://bucket/key/path
    支持的provider: s3, tos, ks3, oss, cos
    """
    provider: Literal["s3", "tos", "ks3", "oss", "cos"] = Field(
        description="云存储提供商：s3(AWS), tos(火山引擎), ks3(金山云), oss(阿里云), cos(腾讯云)"
    )
    bucket: str = Field(description="存储桶名称")
    key: str = Field(description="对象键路径")
    
    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        """验证key不能为空且不能以/开头"""
        if not v:
            raise ValueError("key不能为空")
        if v.startswith("/"):
            v = v.lstrip("/")
        return v
    
    @classmethod
    def from_string(cls, s3_path: str) -> "S3Path":
        """
        从字符串解析S3路径
        :param s3_path: 格式：provider://bucket/key 或 provider://bucket/key/path
        :return: S3Path实例
        """
        if "://" not in s3_path:
            raise ValueError(
                f"Invalid S3 path format: {s3_path}. "
                f"Expected format: provider://bucket/key (e.g., tos://my-bucket/path/to/file)"
            )
        
        provider, rest = s3_path.split("://", 1)
        parts = rest.split("/", 1)
        
        if len(parts) < 2:
            raise ValueError(
                f"Invalid S3 path format: {s3_path}. "
                f"Expected format: provider://bucket/key"
            )
        
        return cls(provider=provider, bucket=parts[0], key=parts[1])
    
    def to_string(self) -> str:
        """转换为字符串格式"""
        return f"{self.provider}://{self.bucket}/{self.key}"
    
    def __str__(self) -> str:
        return self.to_string()


def parse_s3_path(s3_path: str) -> S3Path:
    """
    解析 S3 路径
    :param s3_path: S3路径字符串，格式：provider://bucket/key
    :return: S3Path对象
    """
    return S3Path.from_string(s3_path)


def _load_s3_credentials(provider: str, bucket: str) -> tuple[str, str, str, Optional[str]]:
    """
    从注册表或环境变量加载S3凭证
    优先从注册表获取，如果没有则从环境变量获取
    
    环境变量格式：
    - {PROVIDER}_{BUCKET}_ENDPOINT
    - {PROVIDER}_{BUCKET}_ACCESS_KEY
    - {PROVIDER}_{BUCKET}_SECRET_KEY
    - {PROVIDER}_{BUCKET}_REGION (可选)
    
    :param provider: 提供商名称
    :param bucket: 存储桶名称
    :return: (endpoint, access_key, secret_key, region)
    """
    # 首先尝试从注册表获取
    config = get_s3_config(provider, bucket)
    if config:
        endpoint = config.get("endpoint")
        access_key = config.get("access_key")
        secret_key = config.get("secret_key")
        region = config.get("region")
        
        if all([endpoint, access_key, secret_key]):
            return endpoint, access_key, secret_key, region
    
    # 如果注册表中没有，从环境变量获取
    prefix = f"{provider.upper()}_{bucket.upper()}"
    
    endpoint = os.getenv(f"{prefix}_ENDPOINT")
    access_key = os.getenv(f"{prefix}_ACCESS_KEY")
    secret_key = os.getenv(f"{prefix}_SECRET_KEY")
    region = os.getenv(f"{prefix}_REGION")
    
    if not all([endpoint, access_key, secret_key]):
        raise ValueError(
            f"未找到 {provider}://{bucket} 的凭证配置。"
            f"请通过 @register_s3_config 装饰器注册，或在 s3_aksk.env 文件中设置:\n"
            f"  {prefix}_ENDPOINT=<endpoint_url>\n"
            f"  {prefix}_ACCESS_KEY=<access_key>\n"
            f"  {prefix}_SECRET_KEY=<secret_key>\n"
            f"  {prefix}_REGION=<region>  # 可选"
        )
    
    return endpoint, access_key, secret_key, region


def get_s3_client(provider: str, bucket: str) -> Optional[any]:
    """
    从全局池获取S3客户端
    
    :param provider: 提供商名称
    :param bucket: Bucket名称
    :return: S3客户端实例，如果不存在返回None
    """
    return _s3_clients.get(provider, {}).get(bucket)


def register_s3_client(provider: str, bucket: str, s3_client: any) -> None:
    """
    注册S3客户端到全局池
    
    :param provider: 提供商名称
    :param bucket: Bucket名称
    :param s3_client: boto3 S3客户端实例
    """
    if provider not in _s3_clients:
        _s3_clients[provider] = {}
    _s3_clients[provider][bucket] = s3_client


def get_or_create_s3_client(provider: str, bucket: str) -> any:
    """
    获取或创建S3客户端（自动从环境变量加载凭证）
    
    :param provider: 提供商名称
    :param bucket: Bucket名称
    :return: S3客户端实例
    """
    client = get_s3_client(provider, bucket)
    if client is None:
        try:
            import boto3
            endpoint, access_key, secret_key, region = _load_s3_credentials(provider, bucket)
            
            client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            register_s3_client(provider, bucket, client)
        except ImportError as e:
            raise ImportError("boto3 is required for S3 operations. Install it with: pip install boto3") from e
    
    return client


def download_from_s3(s3_path: str | S3Path, local_path: Optional[Path] = None) -> Path | BytesIO:
    """
    从S3下载文件到本地或内存
    
    :param s3_path: S3路径（字符串或S3Path对象）
    :param local_path: 本地保存路径（如果为None，返回BytesIO对象）
    :return: 本地文件路径或BytesIO对象
    """
    # 解析S3路径
    if isinstance(s3_path, str):
        s3_obj = parse_s3_path(s3_path)
    else:
        s3_obj = s3_path
    
    # 获取或创建S3客户端
    s3_client = get_or_create_s3_client(s3_obj.provider, s3_obj.bucket)
    
    # 下载文件
    try:
        if local_path is None:
            # 下载到内存
            buffer = BytesIO()
            s3_client.download_fileobj(s3_obj.bucket, s3_obj.key, buffer)
            buffer.seek(0)
            return buffer
        else:
            # 下载到本地文件
            local_path = Path(local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            s3_client.download_file(s3_obj.bucket, s3_obj.key, str(local_path))
            return local_path
    except Exception as e:
        raise RuntimeError(f"从S3下载文件失败: {s3_obj} -> {local_path}, 错误: {e}") from e


def upload_to_s3(local_path: Path | BytesIO, s3_path: str | S3Path) -> None:
    """
    上传本地文件或内存数据到S3
    
    :param local_path: 本地文件路径或BytesIO对象
    :param s3_path: S3路径（字符串或S3Path对象）
    """
    # 解析S3路径
    if isinstance(s3_path, str):
        s3_obj = parse_s3_path(s3_path)
    else:
        s3_obj = s3_path
    
    # 获取或创建S3客户端
    s3_client = get_or_create_s3_client(s3_obj.provider, s3_obj.bucket)
    
    # 上传文件
    try:
        if isinstance(local_path, BytesIO):
            # 从内存上传
            local_path.seek(0)
            s3_client.upload_fileobj(local_path, s3_obj.bucket, s3_obj.key)
        else:
            # 从本地文件上传
            s3_client.upload_file(str(local_path), s3_obj.bucket, s3_obj.key)
    except Exception as e:
        raise RuntimeError(f"上传文件到S3失败: {local_path} -> {s3_obj}, 错误: {e}") from e