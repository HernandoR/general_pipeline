# General Pipeline - 通用数据产线框架

一套标准化、可扩展的数据产线框架，支持多来源虚拟环境管理、灵活的算子集成、资源可控的任务执行。

## 特性

- **三层架构设计**：Pipeline（产线层）→ Node（节点层）→ Operator（算子层）
- **多虚拟环境支持**：UV、Pixi、Conda 环境自动管理和复用
- **算子标准化**：基于 BasicRunner 基类的统一开发规范
- **资源监控**：实时监控 CPU、内存、磁盘 IO、网络 IO
- **配置管理**：基于 OmegaConf 和 Pydantic 的层级化配置，支持环境变量覆盖
- **敏感信息保护**：Base64 编码保护配置文件中的敏感信息
- **日志管理**：基于 Loguru 的统一日志记录和管理

## 系统要求

- Python 3.11+
- Linux-amd64 操作系统
- Git
- 可选：UV、Pixi、Conda（根据使用的虚拟环境类型）

## 安装

1. 克隆仓库：
   ```bash
   git clone https://github.com/HernandoR/general_pipeline.git
   cd general_pipeline
   ```

2. 安装依赖：
   ```bash
   pip install -e .
   ```

## 快速开始

### 1. 创建产线配置

参考 `examples/pipeline_config_example.yaml` 创建配置文件。

### 2. 验证配置

```bash
pipeline-cli validate --conf examples/pipeline_config_example.yaml
```

### 3. 运行产线

```bash
pipeline-cli run --conf examples/pipeline_config_example.yaml
```

### 4. 使用 Base64 编码保护敏感信息

```bash
# 编码敏感信息
pipeline-cli encode "my_secret_key"
# 输出：编码结果：base64://bXlfc2VjcmV0X2tleQ==

# 在配置文件中使用编码后的值
# s3_config:
#   access_key: "base64://bXlfc2VjcmV0X2tleQ=="
```

## 算子开发

算子需要继承 `BasicRunner` 基类并实现 `run()` 方法：

```python
from general_pipeline.core.basic_runner import BasicRunner
import os

class MyOperator(BasicRunner):
    def run(self) -> int:
        # 从 self.input_root 读取输入数据
        # 处理数据
        # 将结果写入 self.pipeline_output_root
        
        return 0  # 返回 exit code

if __name__ == "__main__":
    operator = MyOperator(
        pipeline_id=os.environ["PIPELINE_ID"],
        node_id=os.environ["NODE_ID"],
        operator_id=os.environ["OPERATOR_ID"],
        work_dir=os.environ["WORK_DIR"]
    )
    exit(operator.run())
```

详见 [算子开发指南](examples/README.md)。

## 配置文件结构

产线配置文件采用 YAML 格式，主要包含以下部分：

```yaml
pipeline_id: "my_pipeline"
name: "我的产线"
work_dir: "./pipeline_workspace"

# 算子配置
operators:
  - operator_id: "op1"
    git_repo: "https://github.com/example/op1.git"
    git_tag: "v1.0.0"
    upstream_dependencies: []
    start_command: "python main.py"
    env_config:
      env_name: "op1_env"
      pyproject_path: "pyproject.toml"  # UV 环境

# 节点配置
nodes:
  - node_id: "node1"
    operator_ids: ["op1"]
    runner_count: 1
    resource:
      cpu_request: 2.0
      cpu_limit: 4.0
      memory_request: 8.0
      memory_limit: 16.0
```

详见 [配置示例](examples/pipeline_config_example.yaml)。

## 命令行工具

### pipeline-cli

主命令行工具，提供以下子命令：

- `encode <plaintext>`: 对明文进行 Base64 编码
- `decode <encoded_str>`: 对编码串进行解码
- `validate --conf <config_file>`: 验证产线配置文件
- `run --conf <config_file>`: 运行产线

### pipeline-validate

快捷验证命令（等同于 `pipeline-cli validate`）。

## 环境变量覆盖

通过环境变量 `PIPELINE_CONF_OVERRIDE` 可以覆盖配置文件中的参数：

```bash
PIPELINE_CONF_OVERRIDE="log_config.level=DEBUG,work_dir=/tmp/pipeline" \
pipeline-cli run --conf config.yaml
```

## 项目结构

```
general_pipeline/
├── src/general_pipeline/
│   ├── cli/              # 命令行接口
│   ├── core/             # 核心模块
│   │   ├── basic_runner.py      # 算子基类
│   │   ├── pipeline_executor.py # 产线执行器
│   │   └── resource_monitor.py  # 资源监控
│   ├── models/           # 配置模型
│   │   ├── env_config.py        # 虚拟环境配置
│   │   ├── operator_config.py   # 算子配置
│   │   ├── node_config.py       # 节点配置
│   │   └── pipeline_config.py   # 产线配置
│   └── utils/            # 工具模块
│       ├── codec.py             # Base64 编解码
│       ├── log_utils.py         # 日志工具
│       ├── path_utils.py        # 路径工具
│       ├── s3_utils.py          # S3 工具
│       └── exceptions.py        # 自定义异常
├── examples/             # 示例配置
├── doc/                  # 文档
└── pyproject.toml        # 项目配置
```

## 架构文档

详细的架构设计文档请参考：
- [数据产线 Python 项目规划 - 架构文档](doc/ai-instructions/数据产线Python项目规划-架构文档.md)
- [数据产线架构设计规范文档（Linux-amd64 版）](doc/ai-instructions/数据产线架构设计规范文档（Linux-amd64版）.md)

## 贡献

欢迎提交 Issue 和 Pull Request。

## 许可证

MIT License
