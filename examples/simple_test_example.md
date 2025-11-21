# 简单测试示例

本示例展示如何创建一个最简单的算子并通过产线执行。

## 文件结构

```
simple_test_example/
├── operator/
│   ├── run.py          # 算子执行脚本
│   └── pyproject.toml  # 项目配置
└── pipeline_config.yaml # 产线配置
```

## 算子脚本 (run.py)

```python
#!/usr/bin/env python3
import os
from pathlib import Path

# 获取环境变量
pipeline_id = os.environ.get("PIPELINE_ID")
node_id = os.environ.get("NODE_ID")
operator_id = os.environ.get("OPERATOR_ID")
work_dir = os.environ.get("WORK_DIR")

# 创建输出
output_path = Path(work_dir) / "output" / pipeline_id / node_id / operator_id
output_path.mkdir(parents=True, exist_ok=True)

with open(output_path / "result.txt", "w") as f:
    f.write(f"Hello from {operator_id}!\n")

print("Operator completed successfully!")
```

## 运行步骤

1. 创建算子仓库并打 tag：
   ```bash
   cd operator
   git init
   git add .
   git commit -m "Initial commit"
   git tag v1.0.0
   ```

2. 验证配置：
   ```bash
   pipeline-cli validate --conf pipeline_config.yaml
   ```

3. 运行产线：
   ```bash
   pipeline-cli run --conf pipeline_config.yaml
   ```

4. 查看输出：
   ```bash
   cat /tmp/pipeline_workspace/output/test_pipeline/node_1/test_op/result.txt
   ```

## 注意事项

- 算子代码必须在 git 仓库中，并且需要打 tag
- 产线会自动克隆算子代码到工作目录
- 环境变量会自动注入到算子执行环境中
- 算子返回 exit code 0 表示成功，非 0 表示失败
