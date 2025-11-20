# 产线配置示例

本目录包含数据产线框架的示例配置文件。

## 文件说明

### pipeline_config_example.yaml

完整的产线配置示例，展示了：
- UV 和 Pixi 虚拟环境配置
- 算子依赖关系配置
- 节点资源配置
- 日志和工作目录配置
- Base64 编码的敏感信息保护

## 使用方法

### 1. 验证配置

```bash
pipeline-cli validate --conf examples/pipeline_config_example.yaml
```

### 2. 运行产线

```bash
pipeline-cli run --conf examples/pipeline_config_example.yaml
```

### 3. 环境变量覆盖

```bash
PIPELINE_CONF_OVERRIDE="log_config.level=DEBUG,work_dir=/tmp/pipeline" \
pipeline-cli run --conf examples/pipeline_config_example.yaml
```

## Base64 编码工具

对敏感信息（如 S3 密钥）进行编码：

```bash
# 编码
pipeline-cli encode "my_secret_key"
# 输出：编码结果：base64://bXlfc2VjcmV0X2tleQ==

# 解码
pipeline-cli decode "base64://bXlfc2VjcmV0X2tleQ=="
# 输出：解码结果：my_secret_key
```

## 算子开发

算子需要继承 `BasicRunner` 基类：

```python
from general_pipeline.core.basic_runner import BasicRunner

class MyOperator(BasicRunner):
    def run(self) -> int:
        # 读取输入
        input_files = os.listdir(self.input_root)
        
        # 处理数据
        # ...
        
        # 写入输出
        output_path = os.path.join(self.pipeline_output_root, "result.txt")
        with open(output_path, "w") as f:
            f.write("processed data")
        
        return 0  # 成功返回0

if __name__ == "__main__":
    import os
    operator = MyOperator(
        pipeline_id=os.environ["PIPELINE_ID"],
        node_id=os.environ["NODE_ID"],
        operator_id=os.environ["OPERATOR_ID"],
        work_dir=os.environ["WORK_DIR"]
    )
    exit_code = operator.run()
    exit(exit_code)
```

## Exit Code 说明

| exit_code | 含义 | 适用场景 |
|-----------|------|----------|
| 0 | 执行成功 | 算子完成业务逻辑，输出合法 |
| 1 | 配置错误 | 配置格式错误、依赖缺失 |
| 2 | 输入数据错误 | 输入文件不存在、格式非法、校验失败 |
| 3 | 执行逻辑错误 | 业务代码异常（计算错误、IO 异常） |
| 4 | 资源异常 | 内存超限、磁盘满、超时 |
| 5 | 环境错误 | 虚拟环境创建失败、依赖安装失败 |
