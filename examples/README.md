# 产线配置示例

本目录包含数据产线框架的层级化TOML配置示例。

## 目录结构

```
conf/
├── pipeline.toml                          # 主产线配置
├── nodes/
│   ├── node_1_v1.0.toml                  # 节点1配置（版本1.0）
│   └── node_2_v1.0.toml                  # 节点2配置（版本1.0）
├── operators/
│   ├── example_operator_1_v1.0.toml      # 算子1配置（版本1.0）
│   └── example_operator_2_v2.0.toml      # 算子2配置（版本2.0）
└── integration/                           # 自动生成的集成配置
    └── example_pipeline_v1_timestamp.toml
```

## 配置特点

### 层级化管理
- Pipeline/Node/Operator分文件存储
- 每个组件可独立版本管理
- 便于复用和维护

### 嵌套键结构
```toml
[pipeline]
pipeline_id = "example"

[pipeline.log_config]
level = "INFO"

[node_1]
node_id = "node_1"

[node_1.resource]
cpu_limit = 4.0
```

### 版本引用
```toml
[pipeline.nodes]
refs = ["node_1:v1.0", "node_2:v1.0"]

[pipeline.operators]
refs = ["op1:v1.0", "op2:v2.0"]
```

## 使用方法

### 1. 初始化项目

```bash
# 克隆算子代码、创建虚拟环境、导出集成配置
pipeline-cli init --conf conf/pipeline.toml --config-root conf/
```

### 2. 验证配置

```bash
pipeline-cli validate --conf conf/pipeline.toml --config-root conf/
```

### 3. 运行产线

```bash
# 运行全部
pipeline-cli run --conf conf/pipeline.toml --config-root conf/ --skip-init

# 运行单个节点
pipeline-cli run --conf conf/pipeline.toml --config-root conf/ --node node_1 --skip-init

# 运行单个算子
pipeline-cli run --conf conf/pipeline.toml --config-root conf/ --operator example_operator_1 --skip-init
```

### 4. S3配置覆盖

```bash
# 设置环境变量，从S3加载配置覆盖
export PIPELINE_CONFIG_OVERRIDE_S3_PATH="tos://config-bucket/prod-override.toml"
pipeline-cli run --conf conf/pipeline.toml --config-root conf/
```

## S3对象存储

### 凭证配置

1. 复制模板：
```bash
cp ../s3_aksk.env.example ../s3_aksk.env
```

2. 编辑 `s3_aksk.env`：
```env
# 火山引擎TOS
TOS_MY_BUCKET_ENDPOINT=https://tos-cn-beijing.volces.com
TOS_MY_BUCKET_ACCESS_KEY=your_access_key
TOS_MY_BUCKET_SECRET_KEY=your_secret_key
TOS_MY_BUCKET_REGION=cn-beijing
```

### S3路径格式

```toml
# Conda环境从TOS
[operator.env_config]
s3_compress_path = "tos://env-bucket/conda/my_env.zst"

# 配置覆盖从OSS
export PIPELINE_CONFIG_OVERRIDE_S3_PATH="oss://config-bucket/override.toml"
```

支持的提供商：
- `s3://` - AWS S3
- `tos://` - 火山引擎TOS
- `ks3://` - 金山云KS3
- `oss://` - 阿里云OSS
- `cos://` - 腾讯云COS

## 算子开发

算子需要继承 `BasicRunner` 基类：

```python
from general_pipeline.core.basic_runner import BasicRunner
import os

class MyOperator(BasicRunner):
    def run(self) -> int:
        # Pipeline自动注入的路径
        # self.input_root - 输入数据根目录
        # self.output_root - 输出数据根目录
        # self.workspace_root - 工作空间根目录
        
        # Pipeline自动注入的环境变量
        # PIPELINE_ID, NODE_ID, OPERATOR_ID
        # INPUT_ROOT, OUTPUT_ROOT, WORKSPACE_ROOT
        
        # 实现业务逻辑
        input_files = os.listdir(self.input_root)
        for file in input_files:
            # 处理文件
            pass
        
        # 写入输出
        output_file = os.path.join(self.output_root, "result.txt")
        with open(output_file, "w") as f:
            f.write("processed data")
        
        return 0  # 成功返回0

if __name__ == "__main__":
    operator = MyOperator(
        pipeline_id=os.environ["PIPELINE_ID"],
        node_id=os.environ["NODE_ID"],
        operator_id=os.environ["OPERATOR_ID"],
        input_root=os.environ["INPUT_ROOT"],
        output_root=os.environ["OUTPUT_ROOT"],
        workspace_root=os.environ["WORKSPACE_ROOT"]
    )
    exit(operator.run())
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

## Docker部署

### 多阶段构建

```dockerfile
# 构建阶段
FROM python:3.11 as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY conf/ conf/
COPY s3_aksk.env .
RUN touch .project_root
RUN pipeline-cli init --conf conf/pipeline.toml --config-root conf/

# 运行阶段
FROM python:3.11
WORKDIR /app
COPY --from=builder /app /app
CMD ["pipeline-cli", "run", "--conf", "conf/pipeline.toml", "--skip-init"]
```

## 版本管理

### 创建新版本

```bash
# 复制现有配置
cp conf/nodes/node_1_v1.0.toml conf/nodes/node_1_v1.1.toml

# 编辑新版本
# 修改配置...

# 在pipeline.toml中引用新版本
[pipeline.nodes]
refs = ["node_1:v1.1"]  # 使用新版本
```

### 回滚版本

```bash
# 只需修改引用
[pipeline.nodes]
refs = ["node_1:v1.0"]  # 回滚到旧版本
```

## 最佳实践

1. **每个组件独立文件**：便于版本控制和复用
2. **使用版本标签**：`node_id_version.toml` 格式
3. **S3凭证分离**：使用 `s3_aksk.env`，不要硬编码
4. **配置覆盖**：用S3存储环境特定配置
5. **Docker部署**：利用多阶段构建分离初始化和运行

## 故障排查

### 配置未找到

```bash
# 确认文件命名正确
ls conf/nodes/node_1_v1.0.toml  # 必须包含版本号

# 确认引用格式
[pipeline.nodes]
refs = ["node_1:v1.0"]  # 节点ID:版本号
```

### S3连接失败

```bash
# 检查凭证配置
cat s3_aksk.env

# 确认环境变量格式
{PROVIDER}_{BUCKET}_ENDPOINT
{PROVIDER}_{BUCKET}_ACCESS_KEY
{PROVIDER}_{BUCKET}_SECRET_KEY
```

### 项目根目录未找到

```bash
# 创建标记文件
touch .project_root

# 或指定根目录
pipeline-cli init --conf conf/pipeline.toml --project-root /path/to/project
```
