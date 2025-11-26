# OmegaConf Migration Guide

## Overview

The general_pipeline framework has been updated to use **OmegaConf** instead of the `toml` library for configuration management. OmegaConf provides several advantages:

- **Type Safety**: Better type checking and validation
- **Variable Interpolation**: Support for `${var}` style variable substitution
- **Structured Configs**: Integration with dataclasses and Pydantic models
- **Multi-format Support**: Native support for both YAML and structured configs
- **Backward Compatibility**: Can still load TOML files through conversion

## What Changed

### 1. Configuration Format Support

The framework now supports **both TOML and YAML** formats:

- **TOML files** (`.toml`): Still fully supported, loaded via `toml` library then converted to OmegaConf
- **YAML files** (`.yaml`, `.yml`): Natively supported by OmegaConf

### 2. Configuration Loading

The configuration loader automatically detects the file format based on the file extension:

```python
from general_pipeline.utils.config_loader import HierarchicalConfigLoader
from pathlib import Path

# Load TOML configuration
loader = HierarchicalConfigLoader(Path("conf"))
config = loader.load_pipeline_config(Path("conf/pipeline.toml"))

# Load YAML configuration
config = loader.load_pipeline_config(Path("conf/pipeline.yaml"))
```

### 3. CLI Commands

All CLI commands now accept both TOML and YAML formats:

```bash
# Using TOML
pipeline-cli validate --conf conf/pipeline.toml

# Using YAML
pipeline-cli validate --conf conf/pipeline.yaml

# Hierarchical loading works with both formats
pipeline-cli run --conf conf/pipeline.yaml --config-root conf/
```

## Migration Steps

### Option 1: Keep Using TOML (No Changes Required)

Your existing TOML configuration files will continue to work without any modifications. The framework automatically detects and loads TOML files.

### Option 2: Migrate to YAML

If you want to migrate to YAML format for better integration with OmegaConf features:

1. **Convert TOML to YAML**:

```python
from pathlib import Path
from omegaconf import OmegaConf
import toml

# Read TOML
with open('conf/pipeline.toml', 'r') as f:
    config_dict = toml.load(f)

# Convert to OmegaConf and save as YAML
config = OmegaConf.create(config_dict)
OmegaConf.save(config, 'conf/pipeline.yaml')
```

2. **Update file extensions**:
   - `pipeline.toml` → `pipeline.yaml`
   - `nodes/*.toml` → `nodes/*.yaml`
   - `operators/*.toml` → `operators/*.yaml`

3. **Update references** (if hardcoded in scripts)

## OmegaConf Features

### Variable Interpolation

YAML configurations can use variable interpolation:

```yaml
pipeline:
  pipeline_id: my_pipeline
  work_dir: ./workspace
  
  log_config:
    # Reference other variables
    log_path: ${pipeline.work_dir}/logs/${pipeline.pipeline_id}.log
```

### Structured Configs

Define configuration schemas using dataclasses:

```python
from dataclasses import dataclass
from omegaconf import OmegaConf

@dataclass
class PipelineConfig:
    pipeline_id: str
    work_dir: str
    
config = OmegaConf.structured(PipelineConfig)
```

### Configuration Merging

Easily merge configurations:

```python
from omegaconf import OmegaConf

base_config = OmegaConf.load("base.yaml")
override_config = OmegaConf.load("override.yaml")

# Merge with override taking precedence
merged = OmegaConf.merge(base_config, override_config)
```

## Examples

### TOML Configuration (Still Supported)

```toml
# pipeline.toml
[pipeline]
pipeline_id = "example_pipeline"
name = "Example Pipeline"
work_dir = "./workspace"

[pipeline.log_config]
level = "INFO"
rotation = "10 GB"

[pipeline.nodes]
refs = ["node_1:v1.0"]

[pipeline.operators]
refs = ["op_1:v1.0"]
```

### YAML Configuration (Recommended)

```yaml
# pipeline.yaml
pipeline:
  pipeline_id: example_pipeline
  name: Example Pipeline
  work_dir: ./workspace
  
  log_config:
    level: INFO
    rotation: 10 GB
  
  nodes:
    refs:
      - node_1:v1.0
  
  operators:
    refs:
      - op_1:v1.0
```

## API Changes

### Configuration Loading

**Before (toml only):**
```python
import toml

with open('config.toml', 'r') as f:
    config = toml.load(f)
```

**After (OmegaConf with TOML/YAML support):**
```python
from omegaconf import OmegaConf

# Automatic format detection in config_loader
from general_pipeline.utils.config_loader import HierarchicalConfigLoader

loader = HierarchicalConfigLoader(Path("conf"))
config = loader.load_pipeline_config(Path("conf/pipeline.yaml"))

# Or load directly
config = OmegaConf.load("config.yaml")  # For YAML
# For TOML, the config_loader handles it automatically
```

### Configuration Saving

**Before:**
```python
import toml

with open('config.toml', 'w') as f:
    toml.dump(config, f)
```

**After:**
```python
from omegaconf import OmegaConf

# Save as YAML (recommended)
config = OmegaConf.create(config_dict)
OmegaConf.save(config, "config.yaml")
```

## Benefits of OmegaConf

1. **Type Safety**: Catch configuration errors early with type checking
2. **Variable Interpolation**: Reduce duplication with `${variable}` references
3. **Validation**: Built-in validation for structured configs
4. **Flexibility**: Support for both YAML and programmatic config creation
5. **Integration**: Better integration with modern Python tools like Hydra
6. **Readability**: YAML is more readable for complex nested structures

## Troubleshooting

### Issue: "ParserError: expected '<document start>'"

**Cause**: OmegaConf tried to load a TOML file as YAML.

**Solution**: The config loader should handle this automatically. If you're loading directly, ensure you're using the config loader or manually loading TOML files with the `toml` library first.

### Issue: Configuration not loading correctly

**Check**:
1. File extension is correct (`.toml` or `.yaml`)
2. YAML syntax is valid (indentation matters!)
3. Use the HierarchicalConfigLoader for automatic format detection

## Best Practices

1. **Use YAML for new projects**: Take advantage of OmegaConf features
2. **Keep TOML for existing projects**: No need to migrate unless you need OmegaConf features
3. **Use variable interpolation**: Reduce duplication in configs
4. **Validate early**: Use Pydantic models to validate configs
5. **Use structured configs**: Define schemas for better type safety

## See Also

- [OmegaConf Documentation](https://omegaconf.readthedocs.io/)
- [YAML Specification](https://yaml.org/spec/1.2/spec.html)
- [TOML Specification](https://toml.io/en/)
