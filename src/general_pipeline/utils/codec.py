"""Base64 编解码工具模块，用于敏感信息保护"""
import base64
from typing import Optional


class Base64Codec:
    """Base64编解码工具类"""
    ENCODE_PREFIX = "base64://"  # 编码字段前缀标识

    @staticmethod
    def encode(plaintext: str) -> str:
        """
        对明文进行Base64编码，添加前缀标识
        :param plaintext: 敏感信息明文
        :return: 带前缀的编码串
        """
        if not plaintext:
            return plaintext
        # UTF-8编码后进行Base64编码
        encoded_bytes = base64.b64encode(plaintext.encode("utf-8"))
        return f"{Base64Codec.ENCODE_PREFIX}{encoded_bytes.decode('utf-8')}"

    @staticmethod
    def decode(encoded_str: Optional[str]) -> Optional[str]:
        """
        对带前缀的编码串进行Base64解码
        :param encoded_str: 带前缀的编码串
        :return: 敏感信息明文（非编码串返回原内容）
        """
        if not encoded_str or not encoded_str.startswith(Base64Codec.ENCODE_PREFIX):
            return encoded_str  # 非编码串直接返回
        # 去除前缀后解码
        raw_encoded = encoded_str[len(Base64Codec.ENCODE_PREFIX):]
        decoded_bytes = base64.b64decode(raw_encoded)
        return decoded_bytes.decode("utf-8")
