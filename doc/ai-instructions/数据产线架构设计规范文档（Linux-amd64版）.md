## 目录

1. 架构概述
2. 核心设计规范
   2.1 环境管理：虚拟环境复用策略
   2.2 算子设计：BasicRunner 标准化基类
   2.3 调度执行：资源监控与退出机制
   2.4 配置管理：版本化与环境变量覆盖
   2.5 日志设计：单一文件存储
   2.6 测试方案：Pipeline Conf Validate
   2.7 部署方式：Pixi 统一依赖管理
3. 关键约束与注意事项
4. 核心依赖版本锁定
5. 附录
   5.1 核心术语解释
   5.2 文档使用说明

## 1. 架构概述

### 1.1 平台约束

仅支持 **Linux-amd64** 操作系统，不兼容 Windows、MacOS 及其他硬件架构。

### 1.2 核心目标

提供算子化、可复用的任务调度能力，简化数据处理流程的配置、执行与监控，核心聚焦：

* 虚拟环境高效复用，避免重复构建
* 算子标准化开发，降低集成成本
* 配置版本化管理，追溯历史变更
* 资源实时监控与明确错误反馈

## 2. 核心设计规范

### 2.1 环境管理：虚拟环境复用策略

#### 2.1.1 复用核心规则

* 唯一标识：以「**环境类型 + 环境名**」作为虚拟环境的唯一 Key（例：`conda_ml_env`、`pixi_data_env`）
* 复用逻辑：
  * 同类型 + 同名：直接复用已创建环境，跳过依赖安装
  * 不同类型 + 同名：抛出 `DuplicateEnvNameError` 异常，禁止跨类型复用
* 缓存清理：支持配置 `env_ttl`（默认 7 天），过期未使用环境自动删除释放磁盘

#### 2.1.2 环境类型与配置示例

| 环境类型  | 配置标识        | 核心字段                    | 复用 Key 格式       |
| ----- | ----------- | ----------------------- | --------------- |
| Conda | `conda_env` | `name`、`dependencies`   | `conda_${name}` |
| Pixi  | `pixi_env`  | `name`、`pyproject_toml` | `pixi_${name}`  |
| UV    | `uv_env`    | `name`、`requirements`   | `uv_${name}`    |

### 2.2 算子设计：BasicRunner 标准化基类

#### 2.2.1 基类核心能力

所有算子必须继承 `BasicRunner` 类，基类提供统一路径管理、日志集成，算子仅需实现业务逻辑。

#### 2.2.2 基类代码实现

```python
from loguru import logger
import os

class BasicRunner:
  def __init__(self, pipeline_id: str, node_id: str, operator_id: str, work_dir: str):
      self.pipeline_id = pipeline_id  # 产线ID
      self.node_id = node_id          # 节点ID
      self.operator_id = operator_id  # 算子ID
      self.work_dir = work_dir        # 产线根工作目录（调度器传入）
      self._init_paths()              # 初始化标准化路径

  def _init_paths(self) -> None:
      """自动创建所有基础路径（绝对路径）"""
      # 输入根路径：上游算子输出数据源
      self.input_root = os.path.join(self.work_dir, "input", self.operator_id)
      # 产线输出根路径：算子最终输出（全局可见）
      self.pipeline_output_root = os.path.join(
          self.work_dir, "output", self.pipeline_id, self.node_id, self.operator_id
      )
      # 产线工作空间：算子临时文件目录
      self.pipeline_workspace = os.path.join(
          self.work_dir, "workspace", self.pipeline_id, self.node_id, self.operator_id
      )
      # 缓存根路径：可复用数据（如模型权重）
      self.cache_root = os.path.join(self.work_dir, "cache", self.operator_id)
      
      # 批量创建目录（避免路径不存在报错）
      for path in [self.input_root, self.pipeline_output_root, 
                   self.pipeline_workspace, self.cache_root]:
          os.makedirs(path, exist_ok=True)

  def run(self) -> int:
      """算子核心业务逻辑（子类必须重写），返回exit_code"""
      raise NotImplementedError("算子需重写 run() 方法并返回exit_code")

  def validate_input(self) -> bool:
      """输入数据校验（可选重写），失败返回False"""
      if not os.listdir(self.input_root):
          logger.error(f"算子 {self.operator_id} 输入目录为空：{self.input_root}")
          return False
      return True
```

#### 2.2.3 算子开发规范

1. 必须继承 `BasicRunner`，重写 `run()` 方法，业务逻辑在该方法中实现
2. 输入数据从 `self.input_root` 读取，输出数据写入 `self.pipeline_output_root`
3. 临时文件存于 `self.pipeline_workspace`，可复用数据存于 `self.cache_root`
4. 执行结果通过 `exit_code` 反馈（详见 2.3.2）

### 2.3 调度执行：资源监控与退出机制

#### 2.3.1 资源监控（仅监控，无限制）

* 监控范围：算子进程（含子进程）的 **CPU 使用率、内存占用（MB）、磁盘 IO（MB/s）、网络 IO（MB/s）**
* 监控工具：集成 `psutil` 库
* 输出方式：资源指标与日志绑定，含 `pipeline_id`/`node_id`/`operator_id`/`timestamp`
* 监控频率：默认 5 秒 / 次，支持配置 `monitor_interval`（单位：秒）调整

#### 2.3.2 错误处理与 exit_code 规范

不支持重试，执行失败直接终止，通过 `exit_code` 标识原因：

| exit_code | 含义     | 适用场景               |
| ---------- | ------ | ------------------ |
| 0          | 执行成功   | 算子完成业务逻辑，输出合法      |
| 1          | 配置错误   | 配置格式错误、依赖缺失        |
| 2          | 输入数据错误 | 输入文件不存在、格式非法、校验失败  |
| 3          | 执行逻辑错误 | 业务代码异常（计算错误、IO 异常） |
| 4          | 资源异常   | 内存超限（仅告警）、磁盘满      |
| 5          | 环境错误   | 虚拟环境创建失败、依赖安装失败    |

### 2.4 配置管理：版本化与环境变量覆盖

#### 2.4.1 版本控制规则

1. 组件独立：`pipeline`/`node`/`算子` 版本更新需创建新配置文件（例：`operator_clean_v2.yaml`），不修改历史配置
2. 集成配置：产线集成时生成「时间戳 + 版本」命名的集成配置（例：`pipeline_integration_20251120_v1.yaml`），含所有组件版本信息

#### 2.4.2 环境变量覆盖规则

1. 覆盖入口：通过环境变量 `PIPELINE_CONF_OVERRIDE` 指定覆盖项，格式：`key1=value1,key2=value2`
   * 支持嵌套键：例 `node.0.operator.conf.batch_size=100`
2. 优先级：环境变量 > 集成配置 > 组件独立配置
3. 约束：仅允许覆盖参数值、超时时间等非核心字段，禁止修改 `pipeline_id`/`node_id` 等标识

### 2.5 日志设计：单一文件存储

#### 2.5.1 存储规则

* 路径：`{work_dir}/logs/pipeline_{pipeline_id}_{timestamp}.log`（`timestamp` 格式：YYYYMMDDHHMMSS）
* 轮转：按大小轮转（单个文件最大 10GB），保留最近 30 天日志

#### 2.5.2 日志格式（JSON）

```json
{
"timestamp": "2025-11-20T14:30:00.123",
"level": "INFO",
"pipeline_id": "data_process_pipeline",
"node_id": "node_001",
"operator_id": "data_clean_op",
"module": "basic_runner",
"message": "算子执行成功",
"resource": {
  "cpu_usage": 35.2,
  "mem_usage_mb": 1200,
  "disk_io_mb/s": 10.5
}
}
```

#### 2.5.3 日志分级

* DEBUG：调试信息（路径初始化、配置加载）
* INFO：流程信息（产线启动 / 停止、算子开始 / 结束）
* WARNING：非致命异常（缓存命中失败）
* ERROR：执行失败（算子报错、环境错误）
* CRITICAL：产线致命错误（核心配置缺失、磁盘满）

### 2.6 测试方案：Pipeline Conf Validate

#### 2.6.1 校验目标

验证产线集成配置的合法性，确保可解析、依赖组件可加载（不校验业务逻辑）。

#### 2.6.2 校验内容

1. 格式校验：YAML/JSON 语法合法，符合 OmegaConf Schema
2. 依赖校验：引用的 node/operator 配置文件存在、版本匹配
3. 路径校验：工作目录、日志目录可读写
4. 环境校验：虚拟环境配置无跨类型同名冲突
5. 字段校验：`pipeline_id`/`node_id` 等核心字段无缺失

#### 2.6.3 校验工具使用

```bash
# 命令格式
pipeline-validate --conf [集成配置文件路径]

# 示例
pipeline-validate --conf ./conf/pipeline_integration_20251120_v1.yaml
```

#### 2.6.4 校验结果

* 成功：输出 `Validation Passed: 集成配置合法`
* 失败：输出具体错误（例：`Validation Failed: node_001引用的operator不存在：data_clean_op_v2`）

### 2.7 部署方式：Pixi 统一依赖管理

#### 2.7.1 Pixi 配置文件（pixi.toml）

```toml
[project]
name = "data-pipeline"
version = "1.0.0"
platforms = ["linux-amd64"]  # 仅支持Linux-amd64

[dependencies]
python = ">=3.10,<3.12"       # 基础Python版本
omegaconf = "2.3.0"           # 配置解析
loguru = "0.7.2"              # 日志
psutil = "5.9.8"              # 资源监控
uv = "0.4.0"                  # UV环境管理
conda-cli = "24.5.0"          # Conda环境管理
pixi = "0.27.0"               # 依赖管理工具

[scripts]
# 启动产线
start = "python pipeline/runner.py --conf $PIPELINE_CONF"
# 校验配置
validate = "python pipeline/validator.py --conf $PIPELINE_CONF"
```

#### 2.7.2 部署步骤（Linux-amd64）

```bash
# 1. 安装Pixi
curl -fsSL https://pixi.sh/install.sh | bash

# 2. 克隆项目
git clone <项目仓库地址> && cd data-pipeline

# 3. 安装基础依赖（自动创建Pixi环境）
pixi install

# 4. 激活环境（可选）
pixi shell

# 5. 校验集成配置
pixi run validate --conf ./conf/pipeline_integration_20251120_v1.yaml

# 6. 启动产线（支持环境变量覆盖配置）
PIPELINE_CONF=./conf/pipeline_integration_20251120_v1.yaml \
PIPELINE_CONF_OVERRIDE="node.0.operator.conf.batch_size=100" \
pixi run start
```

## 3. 关键约束与注意事项

1. 平台约束：仅支持 Linux-amd64，不兼容其他系统 / 架构
2. 重试约束：无重试机制，执行失败需人工干预后重启
3. 权限约束：忽略细粒度权限管理，默认当前用户具备工作目录访问权限（建议非 root 用户执行）
4. 环境约束：禁止不同类型虚拟环境同名，否则抛出异常
5. 配置约束：旧版本配置不自动迁移，需手动创建新版本配置

## 4. 核心依赖版本锁定

| 依赖工具 / 库  | 最低版本要求 | 用途           |
| --------- | ------ | ------------ |
| Python    | 3.10   | 产线运行环境       |
| Pixi      | 0.27.0 | 基础依赖管理       |
| OmegaConf | 2.3.0  | 配置解析与校验      |
| Loguru    | 0.7.2  | 日志输出与格式化     |
| psutil    | 5.9.8  | 资源监控         |
| UV        | 0.4.0  | UV 虚拟环境管理    |
| Conda-cli | 24.5.0 | Conda 虚拟环境管理 |

## 5. 附录

### 5.1 核心术语解释

| 术语          | 定义                              |
| ----------- | ------------------------------- |
| Pipeline    | 数据产线，包含多个 Node 的完整处理流程          |
| Node        | 产线节点，包含一个或多个 Operator           |
| 如能让    | 算子，最小执行单元（实现具体业务逻辑）             |
| BasicRunner | 算子基类，提供标准化路径与日志                 |
| 集成配置        | 整合 Pipeline/Node/Operator 的统一配置 |

> （注：文档部分内容可能由 AI 生成）