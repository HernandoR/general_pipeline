# TOML Configuration Migration Guide

## Overview

The pipeline framework has been updated to use TOML configuration format with hierarchical loading support. This guide explains the changes and how to migrate from YAML to TOML.

## Key Changes

### 1. TOML Instead of YAML

**Before (YAML):**
```yaml
pipeline_id: "example_pipeline"
name: "Example Pipeline"
log_config:
  level: "INFO"
  rotation: "10 GB"
```

**After (TOML):**
```toml
pipeline_id = "example_pipeline"
name = "Example Pipeline"

[log_config]
level = "INFO"
rotation = "10 GB"
```

### 2. Hierarchical Configuration Structure

Configurations are now organized in separate files with version support:

```
conf/
├── pipeline.toml           # Main pipeline configuration
├── nodes/
│   ├── node_1_v1.0.toml   # Node configurations with versions
│   └── node_2_v1.0.toml
├── operators/
│   ├── op_1_v1.0.toml     # Operator configurations with versions
│   └── op_2_v2.0.toml
└── integration/            # Auto-generated integrated configs
    └── pipeline_20231120_120000.toml
```

### 3. Pipeline Configuration Format

**pipeline.toml:**
```toml
pipeline_id = "example_pipeline_v1"
name = "Example Pipeline"
description = "Pipeline description"
work_dir = "./pipeline_workspace"

[log_config]
level = "INFO"
rotation = "10 GB"
retention = 30

# Reference nodes and operators with versions
nodes = [
    "node_1:v1.0",
    "node_2:v1.0"
]

operators = [
    "op_1:v1.0",
    "op_2:v2.0"
]
```

### 4. Node Configuration Format

**nodes/node_1_v1.0.toml:**
```toml
node_id = "node_1"
operator_ids = ["op_1", "op_2"]
runner_count = 1

[resource]
cpu_request = 2.0
cpu_limit = 4.0
memory_request = 8.0
memory_limit = 16.0
gpu_request = 0
```

### 5. Operator Configuration Format

**operators/op_1_v1.0.toml:**
```toml
operator_id = "op_1"
git_repo = "https://github.com/example/op1.git"
git_tag = "v1.0.0"
upstream_dependencies = []
start_command = "python main.py"
timeout = 1800

[extra_env_vars]
INPUT_PATH = "/data/input"
OUTPUT_PATH = "/data/output"

[env_config]
env_name = "op1_env"
pyproject_path = "pyproject.toml"
```

## CLI Usage

### Hierarchical Configuration Loading

```bash
# Validate with hierarchical loading
pipeline-cli validate --conf conf/pipeline.toml --config-root conf/

# Initialize (creates environments, exports integrated config)
pipeline-cli init --conf conf/pipeline.toml --config-root conf/

# Run pipeline
pipeline-cli run --conf conf/pipeline.toml --config-root conf/
```

### Single-File Configuration (Backward Compatible)

You can still use a single integrated TOML file:

```bash
# Validate single file
pipeline-cli validate --conf integrated_config.toml

# Initialize
pipeline-cli init --conf integrated_config.toml

# Run
pipeline-cli run --conf integrated_config.toml
```

### Selective Execution

Run specific parts of the pipeline:

```bash
# Run single operator
pipeline-cli run --conf pipeline.toml --operator op_1

# Run single node
pipeline-cli run --conf pipeline.toml --node node_1

# Run all nodes (default)
pipeline-cli run --conf pipeline.toml
```

## S3 Configuration Changes

### Old Approach (Injection)
```python
# S3 client was injected into env_config
env_config.s3_client = boto3.client(...)
```

### New Approach (Centralized)
```python
from general_pipeline.utils.s3_utils import download_from_s3, register_s3_client

# Register S3 client once
register_s3_client("my_bucket", s3_client)

# Download from any registered bucket
download_from_s3("my_bucket/path/to/file.zst", local_path)
```

**Benefits:**
- No injection needed
- Automatic bucket discovery from path
- Clear error messages for unsupported buckets
- Simpler operator code

## Project Root Discovery

### Old Behavior
Used `.git` as project root indicator, fell back to current directory with warning.

### New Behavior
**Requires `.project_root` marker file** in project root directory. Raises clear error if not found.

**Setup:**
```bash
# Create marker file in project root
touch .project_root

# Or specify explicitly
pipeline-cli run --conf config.toml --project-root /path/to/project
```

## Version Management

### Node Versions
```
nodes/
├── node_1_v1.0.toml    # Version 1.0
├── node_1_v1.1.toml    # Version 1.1 (new version)
└── node_2_v1.0.toml
```

### Operator Versions
```
operators/
├── op_1_v1.0.toml      # Version 1.0
├── op_1_v2.0.toml      # Version 2.0 (breaking changes)
└── op_2_v1.0.toml
```

### Reference Specific Versions
```toml
# In pipeline.toml
nodes = [
    "node_1:v1.0",      # Use specific version
    "node_2:v1.1"
]

operators = [
    "op_1:v2.0",        # Use newer version
    "op_2:v1.0"
]
```

## Integrated Configuration Export

When using hierarchical loading with `--config-root`, an integrated configuration is automatically exported:

```bash
pipeline-cli init --conf conf/pipeline.toml --config-root conf/
```

**Output:**
```
conf/integration/example_pipeline_v1_20231120_120000.toml
```

This file contains the fully resolved configuration with all nodes and operators inlined. Use it for:
- Auditing what was deployed
- Reproducing exact configurations
- Single-file deployment scenarios

## Migration Checklist

- [ ] Convert all YAML configs to TOML format
- [ ] Organize configs into pipeline/nodes/operators structure
- [ ] Add version numbers to node and operator files
- [ ] Create .project_root marker file in project root
- [ ] Register S3 clients in initialization code (if using S3)
- [ ] Update CI/CD pipelines to use new CLI flags
- [ ] Test hierarchical loading with `--config-root`
- [ ] Verify selective execution with `--node` and `--operator`

## Examples

See `examples/conf/` directory for complete working examples:
- `examples/conf/pipeline.toml` - Main pipeline config
- `examples/conf/nodes/` - Node configurations
- `examples/conf/operators/` - Operator configurations

## Benefits of New Approach

1. **Version Control Friendly**: Each component tracked separately
2. **Reusability**: Share operators/nodes across pipelines
3. **Clear Versioning**: Explicit version numbers in filenames
4. **Type Safety**: TOML's stronger typing vs YAML
5. **Selective Execution**: Run only what you need
6. **Audit Trail**: Integrated configs capture exact deployment state
7. **Simpler Code**: No S3 client injection, centralized management

## Troubleshooting

### Error: "未找到项目根目录标记文件"
**Solution:** Create `.project_root` file in project root or use `--project-root` flag

### Error: "配置文件不存在"
**Solution:** Ensure TOML files exist at specified paths

### Error: "未找到bucket 'xxx' 的S3客户端"
**Solution:** Register S3 client before initialization:
```python
from general_pipeline.utils.s3_utils import register_s3_client
register_s3_client("bucket_name", s3_client)
```

### Error: "节点配置文件不存在"
**Solution:** Ensure node files use correct naming: `node_id_version.toml`

### Error: "算子配置文件不存在"
**Solution:** Ensure operator files use correct naming: `operator_id_version.toml`
