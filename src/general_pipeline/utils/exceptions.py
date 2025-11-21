"""自定义异常类"""


class EnvInstallError(Exception):
    """虚拟环境安装失败异常"""
    pass


class DuplicateEnvNameError(Exception):
    """虚拟环境名称重复异常（跨类型同名）"""
    pass


class ConfigValidationError(Exception):
    """配置验证失败异常"""
    pass


class DependencyMissingError(Exception):
    """依赖缺失异常"""
    pass
