# General Pipeline - 通用数据产线框架

一套生产级、标准化的数据产线框架，支持层级化TOML配置、多云存储、Docker容器化部署、选择性执行和实时资源监控。

## ✨ 核心特性

### 架构设计
- **三层架构**：Pipeline（产线层）→ Node（节点层）→ Operator（算子层）
- **关注点分离**：ProjectInitiator（初始化）+ PipelineExecutor（执行）
- **Docker友好**：支持多阶段构建，初始化与运行分离

### 配置管理
- **TOML格式**：更强的类型安全性，更清晰的嵌套结构
- **层级化加载**：Pipeline/Node/Operator分文件管理，支持版本控制
- **动态覆盖**：从S3加载配置覆盖，支持环境特定配置
- **Pydantic验证**：强类型校验，早期发现配置错误

### 虚拟环境
- **多环境支持**：UV（pyproject.toml）、Pixi（pixi.toml）、Conda（S3压缩包）
- **自动复用**：相同环境只创建一次
- **灵活激活**：`activate_env_cmd()` 返回命令列表，适配不同激活方式

### 对象存储
- **多云支持**：AWS S3、火山引擎TOS、金山云KS3、阿里云OSS、腾讯云COS
- **统一接口**：`provider://bucket/key` 格式，自动路由到正确提供商
- **安全凭证**：从 `s3_aksk.env` 加载，不暴露在代码中
- **便捷方法**：`download_from_s3()` 和 `upload_to_s3()` 自动管理客户端

### 执行控制
- **选择性执行**：运行单个算子、单个节点或全部节点
- **执行层次**：`run()` → `run_node()` → `run_op()` 清晰分层
- **实时监控**：CPU、内存、磁盘IO、网络IO、GPU（可选）
- **超时控制**：算子级别超时设置

### 项目管理
- **根目录标记**：使用 `.project_root` 文件标识项目根
- **自动克隆**：使用GitPython自动克隆算子代码
- **配置导出**：集成配置自动导出到 `conf/integration/` 用于审计

## 📋 系统要求

- Python 3.11+
- Linux-amd64 操作系统
- Git
- 可选：UV、Pixi、Conda（根据使用的虚拟环境）
- 可选：boto3（如果使用对象存储功能）

## 🚀 快速开始

### 1. 安装

```bash
git clone https://github.com/HernandoR/general_pipeline.git
cd general_pipeline
pip install -e .
```

### 2. 设置项目根目录

```bash
touch .project_root
```

### 3. 配置S3凭证（如果需要）

```bash
cp s3_aksk.env.example s3_aksk.env
# 编辑 s3_aksk.env，添加您的凭证
```

### 4. 创建配置文件

参考 `examples/conf/` 目录结构创建配置：

```
conf/
├── pipeline.toml           # 主配置
├── nodes/
│   └── node_1_v1.0.toml   # 节点配置
└── operators/
    └── op_1_v1.0.toml     # 算子配置
```

### 5. 验证配置

```bash
pipeline-cli validate --conf conf/pipeline.toml --config-root conf/
```

### 6. 初始化项目

```bash
pipeline-cli init --conf conf/pipeline.toml --config-root conf/
```

### 7. 运行产线

```bash
# 运行全部
pipeline-cli run --conf conf/pipeline.toml --skip-init

# 运行单个节点
pipeline-cli run --conf conf/pipeline.toml --node node_1 --skip-init

# 运行单个算子
pipeline-cli run --conf conf/pipeline.toml --operator op_1 --skip-init
```

## 📝 配置示例

### Pipeline配置（pipeline.toml）

```toml
[pipeline]
pipeline_id = "data_pipeline_v1"
name = "数据处理产线"
work_dir = "./pipeline_workspace"

[pipeline.log_config]
level = "INFO"
rotation = "10 GB"
retention = 30

[pipeline.nodes]
refs = ["node_1:v1.0"]

[pipeline.operators]
refs = ["cleaner:v2.0"]
```

### Node配置（nodes/node_1_v1.0.toml）

```toml
[node_1]
node_id = "node_1"
operator_ids = ["cleaner"]
runner_count = 1

[node_1.resource]
cpu_request = 2.0
cpu_limit = 4.0
memory_request = 8.0
memory_limit = 16.0
gpu_request = 0
```

### Operator配置（operators/cleaner_v2.0.toml）

```toml
[cleaner]
operator_id = "cleaner"
git_repo = "https://github.com/example/cleaner.git"
git_tag = "v2.0.0"
upstream_dependencies = []
start_command = "python main.py"
timeout = 1800

[cleaner.extra_env_vars]
BATCH_SIZE = "100"

[cleaner.env_config]
env_name = "cleaner_env"
pyproject_path = "pyproject.toml"  # UV环境
```

## 🛠️ 算子开发

算子需要继承 `BasicRunner` 基类：

```python
from general_pipeline.core.basic_runner import BasicRunner
import os

class DataCleaner(BasicRunner):
    def run(self) -> int:
        # 路径由Pipeline注入
        # self.input_root - 输入数据目录
        # self.output_root - 输出数据目录  
        # self.workspace_root - 工作空间目录
        
        # 环境变量由Pipeline注入
        # PIPELINE_ID, NODE_ID, OPERATOR_ID
        
        # 实现数据处理逻辑
        data = self.load_data(self.input_root)
        cleaned = self.clean(data)
        self.save_data(cleaned, self.output_root)
        
        return 0  # 返回exit code: 0=成功

if __name__ == "__main__":
    cleaner = DataCleaner(
        pipeline_id=os.environ["PIPELINE_ID"],
        node_id=os.environ["NODE_ID"],
        operator_id=os.environ["OPERATOR_ID"],
        input_root=os.environ["INPUT_ROOT"],
        output_root=os.environ["OUTPUT_ROOT"],
        workspace_root=os.environ["WORKSPACE_ROOT"]
    )
    exit(cleaner.run())
```

## 🐳 Docker部署

### Dockerfile示例

```dockerfile
# 构建阶段 - 初始化
FROM python:3.11 as builder
WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制配置和代码
COPY conf/ conf/
COPY s3_aksk.env .
RUN touch .project_root

# 初始化：克隆代码、创建环境
RUN pipeline-cli init --conf conf/pipeline.toml --config-root conf/

# 运行阶段 - 仅执行
FROM python:3.11
WORKDIR /app

# 从构建阶段复制
COPY --from=builder /app /app

# 设置环境变量（可选：配置覆盖）
ENV PIPELINE_CONFIG_OVERRIDE_S3_PATH=""

# 运行产线
CMD ["pipeline-cli", "run", "--conf", "conf/pipeline.toml", "--skip-init"]
```

## 🔐 S3对象存储

### 凭证配置（s3_aksk.env）

```env
# 火山引擎TOS
TOS_MY_BUCKET_ENDPOINT=https://tos-cn-beijing.volces.com
TOS_MY_BUCKET_ACCESS_KEY=your_access_key
TOS_MY_BUCKET_SECRET_KEY=your_secret_key
TOS_MY_BUCKET_REGION=cn-beijing

# AWS S3
S3_ANOTHER_BUCKET_ENDPOINT=https://s3.amazonaws.com
S3_ANOTHER_BUCKET_ACCESS_KEY=your_access_key
S3_ANOTHER_BUCKET_SECRET_KEY=your_secret_key
S3_ANOTHER_BUCKET_REGION=us-east-1
```

### 使用S3

```python
from general_pipeline.utils.s3_utils import download_from_s3, upload_to_s3

# 下载到本地
local_file = download_from_s3("tos://my-bucket/data/file.csv", "/tmp/file.csv")

# 下载到内存
buffer = download_from_s3("tos://my-bucket/config/override.toml")
config = toml.loads(buffer.read().decode('utf-8'))

# 上传文件
upload_to_s3("/tmp/output.csv", "tos://my-bucket/results/output.csv")
```

### Conda环境从S3

```toml
[operator.env_config]
env_name = "my_conda_env"
s3_compress_path = "tos://envs-bucket/conda/my_env.zst"
need_conda_update = true
```

## ⚙️ 高级功能

### 配置覆盖

从S3动态加载配置覆盖：

```bash
export PIPELINE_CONFIG_OVERRIDE_S3_PATH="tos://config-bucket/prod-override.toml"
pipeline-cli run --conf conf/pipeline.toml
```

### 选择性执行

```bash
# 只运行特定算子（测试）
pipeline-cli run --conf conf/pipeline.toml --operator data_cleaner

# 只运行特定节点（部分执行）
pipeline-cli run --conf conf/pipeline.toml --node preprocessing_node

# 运行全部（生产）
pipeline-cli run --conf conf/pipeline.toml
```

### GPU监控

```python
from general_pipeline.core.resource_monitor import ResourceMonitor

# 启用GPU监控
monitor = ResourceMonitor(pid, monitor_gpu=True)
usage = monitor.get_resource_usage()
# 返回: {"cpu_usage": 45.2, "mem_usage_mb": 1024, "gpu_0_util": 80, ...}
```

### Base64编码敏感信息

```bash
# 编码
pipeline-cli encode "my_secret_access_key"
# 输出：base64://bXlfc2VjcmV0X2FjY2Vzc19rZXk=

# 在配置中使用
# （注意：现在推荐使用s3_aksk.env而不是在配置中存储凭证）
```

## 📂 项目结构

```
general_pipeline/
├── src/general_pipeline/
│   ├── cli/                      # CLI命令
│   ├── core/
│   │   ├── basic_runner.py       # 算子基类
│   │   ├── pipeline_executor.py  # 执行器（run/run_node/run_op）
│   │   ├── project_initiator.py  # 初始化器
│   │   └── resource_monitor.py   # 资源监控
│   ├── models/
│   │   ├── env_config.py         # 环境配置模型
│   │   ├── operator_config.py    # 算子配置模型
│   │   ├── node_config.py        # 节点配置模型
│   │   └── pipeline_config.py    # 产线配置模型
│   └── utils/
│       ├── codec.py              # Base64编解码
│       ├── config_loader.py      # 层级化配置加载器
│       ├── log_utils.py          # 日志工具
│       ├── path_utils.py         # 路径工具
│       ├── s3_utils.py           # S3工具（含S3Path模型）
│       ├── subprocess_utils.py   # 子进程工具
│       └── exceptions.py         # 自定义异常
├── examples/conf/                # 示例配置
│   ├── pipeline.toml
│   ├── nodes/
│   └── operators/
├── doc/                          # 架构文档
├── s3_aksk.env.example           # S3凭证模板
└── pyproject.toml
```

## 📚 文档

- [TOML迁移指南](TOML_MIGRATION_GUIDE.md) - 从YAML迁移到TOML
- [实现总结](REVIEW_ROUND_2_SUMMARY.md) - 详细实现说明
- [架构文档](doc/ai-instructions/) - 详细架构设计

## 🔄 退出码协议

- `0` - 成功
- `1` - 配置错误
- `2` - 输入错误
- `3` - 执行逻辑错误
- `4` - 资源异常（超时、内存不足等）
- `5` - 环境错误

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

基于 `doc/ai-instructions/` 中的架构规范构建。
