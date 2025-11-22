# Registration Mechanisms Guide

This guide explains the new registration mechanisms for S3 configurations and operators in the general_pipeline framework.

## Table of Contents

1. [S3 Configuration Registration](#s3-configuration-registration)
2. [Operator Registration](#operator-registration)
3. [Singleton Pattern for Operators](#singleton-pattern-for-operators)

---

## S3 Configuration Registration

### Overview

The framework now provides a decorator-based registration mechanism for S3 configurations, making it easier to manage multiple cloud storage providers and buckets.

### Features

- **Decorator-based registration**: Use `@register_s3_config` to register S3 configurations
- **Centralized management**: All S3 configs in one registry
- **Priority loading**: Registry takes precedence over environment variables
- **Multi-provider support**: S3, TOS, KS3, OSS, COS

### Basic Usage

#### Method 1: Using Decorator

```python
from general_pipeline.utils import register_s3_config

@register_s3_config("tos", "my-bucket")
def configure_tos_bucket():
    return {
        "endpoint": "https://tos-cn-beijing.volces.com",
        "access_key": "your_access_key",
        "secret_key": "your_secret_key",
        "region": "cn-beijing"
    }

# Configuration is automatically registered when the function is decorated
```

#### Method 2: Using Environment Variables (Backward Compatible)

The traditional environment variable approach still works:

```bash
# In s3_aksk.env
TOS_MY_BUCKET_ENDPOINT=https://tos-cn-beijing.volces.com
TOS_MY_BUCKET_ACCESS_KEY=your_access_key
TOS_MY_BUCKET_SECRET_KEY=your_secret_key
TOS_MY_BUCKET_REGION=cn-beijing
```

### Loading Priority

1. **Registry first**: Check `@register_s3_config` decorated configurations
2. **Environment variables**: Fall back to `s3_aksk.env` file
3. **Error**: Raise `ValueError` if neither is found

### Advanced Usage

#### Programmatic Registration

```python
from general_pipeline.utils import get_s3_config

# Register multiple buckets
@register_s3_config("s3", "prod-bucket")
def configure_prod():
    return {
        "endpoint": "https://s3.amazonaws.com",
        "access_key": "prod_key",
        "secret_key": "prod_secret",
        "region": "us-east-1"
    }

@register_s3_config("s3", "dev-bucket")
def configure_dev():
    return {
        "endpoint": "https://s3.amazonaws.com",
        "access_key": "dev_key",
        "secret_key": "dev_secret",
        "region": "us-west-2"
    }

# Retrieve configuration
config = get_s3_config("s3", "prod-bucket")
print(config)  # {'endpoint': '...', 'access_key': '...', ...}
```

#### Dynamic Configuration

```python
from general_pipeline.utils import register_s3_config
import os

# Load from environment or config file at runtime
@register_s3_config("tos", "dynamic-bucket")
def configure_dynamic():
    return {
        "endpoint": os.getenv("DYNAMIC_ENDPOINT"),
        "access_key": os.getenv("DYNAMIC_KEY"),
        "secret_key": os.getenv("DYNAMIC_SECRET"),
        "region": os.getenv("DYNAMIC_REGION", "cn-beijing")
    }
```

### Complete Example

```python
from general_pipeline.utils import register_s3_config, download_from_s3, upload_to_s3

# Register S3 configuration
@register_s3_config("tos", "data-bucket")
def configure_data_bucket():
    return {
        "endpoint": "https://tos-cn-beijing.volces.com",
        "access_key": "your_key",
        "secret_key": "your_secret",
        "region": "cn-beijing"
    }

# Now you can use S3 operations without environment variables
# The configuration will be automatically loaded from the registry
data = download_from_s3("tos://data-bucket/input/file.csv")
upload_to_s3(data, "tos://data-bucket/output/result.csv")
```

---

## Operator Registration

### Overview

The new operator registration mechanism provides a decorator to link operator IDs to their implementations, making it easy to discover and instantiate operators dynamically.

### Features

- **Decorator-based registration**: Use `@register_operator` to register operator classes
- **Dynamic lookup**: Find operator classes by operator_id
- **Type checking**: Ensures registered classes inherit from `BasicRunner`
- **Singleton pattern**: Each operator_id has only one instance

### Basic Usage

```python
from general_pipeline.core import BasicRunner, register_operator
from typing import List

@register_operator("data_cleaner_v1")
class DataCleanerOperator(BasicRunner):
    """Data cleaning operator"""
    
    def run(self) -> int:
        """Execute data cleaning logic"""
        print(f"Cleaning data in {self.input_root}")
        # Your data cleaning logic here
        return 0
    
    def build_running_command(self) -> List[str]:
        """Build command for running this operator"""
        return [
            "python", "clean.py",
            "--input", self.input_root,
            "--output", self.output_root
        ]
```

### Required Methods

All operators **must** implement two abstract methods:

#### 1. `run()` - Core Business Logic

```python
def run(self) -> int:
    """
    Execute the operator's core business logic
    
    Returns:
        int: Exit code (0=success, 1-5=various error types)
    """
    # Your implementation here
    return 0
```

#### 2. `build_running_command()` - Command Builder

```python
def build_running_command(self) -> List[str]:
    """
    Build the command for running this operator
    
    Returns:
        List[str]: Command as a list of strings
        
    Example:
        ["python", "main.py", "--arg", "value"]
    """
    return ["python", "main.py"]
```

### Dynamic Operator Discovery

```python
from general_pipeline.core import get_operator_class, list_registered_operators

# Get operator class by ID
OperatorClass = get_operator_class("data_cleaner_v1")
if OperatorClass:
    # Instantiate the operator
    operator = OperatorClass(
        pipeline_id="my_pipeline",
        node_id="node_1",
        operator_id="data_cleaner_v1",
        input_root="/data/input",
        output_root="/data/output",
        workspace_root="/workspace"
    )
    exit_code = operator.run()

# List all registered operators
operators = list_registered_operators()
print(f"Available operators: {operators}")
```

### Complete Operator Example

```python
from general_pipeline.core import BasicRunner, register_operator
from typing import List
import os

@register_operator("feature_extractor_v1")
class FeatureExtractorOperator(BasicRunner):
    """Extract features from raw data"""
    
    def validate_input(self) -> bool:
        """Validate input data exists and is correct format"""
        if not super().validate_input():
            return False
        
        # Check for required input files
        required_files = ["data.csv", "schema.json"]
        for filename in required_files:
            filepath = os.path.join(self.input_root, filename)
            if not os.path.exists(filepath):
                self.logger.error(f"Required file not found: {filename}")
                return False
        
        return True
    
    def run(self) -> int:
        """Execute feature extraction"""
        # Validate input
        if not self.validate_input():
            return 2  # Input error
        
        try:
            # Read input data
            input_file = os.path.join(self.input_root, "data.csv")
            
            # Process data (your logic here)
            print(f"Extracting features from {input_file}")
            
            # Write output
            output_file = os.path.join(self.output_root, "features.csv")
            # ... save features ...
            
            print(f"Features saved to {output_file}")
            return 0  # Success
            
        except FileNotFoundError:
            print("Input file not found")
            return 2  # Input error
        except Exception as e:
            print(f"Error during feature extraction: {e}")
            return 3  # Logic error
    
    def build_running_command(self) -> List[str]:
        """Build command for feature extraction"""
        return [
            "python", "extract_features.py",
            "--input", self.input_root,
            "--output", self.output_root,
            "--workspace", self.workspace_root,
            "--operator-id", self.operator_id
        ]
```

### Using with Configuration

Operators are typically instantiated by the pipeline executor based on configuration:

```yaml
# pipeline.yaml
pipeline:
  operators:
    refs:
      - feature_extractor_v1:v1.0
      - data_cleaner_v1:v1.0
```

When the pipeline runs, it will:
1. Look up the operator class using `get_operator_class("feature_extractor_v1")`
2. Instantiate the operator with proper paths and IDs
3. Call the operator's `run()` method

---

## Singleton Pattern for Operators

### Overview

All operators automatically follow the **Singleton pattern** based on their `operator_id`. This ensures:
- **Resource efficiency**: No duplicate instances
- **State consistency**: Same operator ID = same instance
- **Memory optimization**: Reuse existing instances

### How It Works

```python
from general_pipeline.core import BasicRunner, register_operator
from typing import List

@register_operator("singleton_test")
class TestOperator(BasicRunner):
    def run(self) -> int:
        return 0
    
    def build_running_command(self) -> List[str]:
        return ["python", "test.py"]

# Create two instances with same operator_id
op1 = TestOperator("pipeline1", "node1", "singleton_test", 
                   "/input", "/output", "/workspace")
op2 = TestOperator("pipeline1", "node1", "singleton_test", 
                   "/input", "/output", "/workspace")

# They are the same instance!
assert op1 is op2  # True
print(f"op1 id: {id(op1)}")  # e.g., 140673635795024
print(f"op2 id: {id(op2)}")  # e.g., 140673635795024 (same!)
```

### Implementation Details

The singleton pattern is implemented using a **metaclass** that combines:
- `ABCMeta`: For abstract base class functionality
- `SingletonMeta`: For singleton behavior

The singleton key is `(class, operator_id)`, so:
- Same class + same operator_id = same instance
- Same class + different operator_id = different instances
- Different class + same operator_id = different instances

### Example with Multiple Operators

```python
# Different operator IDs = different instances
op1 = TestOperator("pipeline1", "node1", "operator_1", "/in", "/out", "/ws")
op2 = TestOperator("pipeline1", "node1", "operator_2", "/in", "/out", "/ws")
assert op1 is not op2  # True - different operator_ids

# Same operator ID = same instance
op3 = TestOperator("pipeline1", "node1", "operator_1", "/in", "/out", "/ws")
assert op1 is op3  # True - same operator_id
```

### Benefits

1. **Memory Efficiency**: Avoid creating duplicate operator instances
2. **Consistency**: Same operator state across multiple references
3. **Simplicity**: No need to manually manage operator instances
4. **Thread-Safe**: Metaclass ensures thread-safe singleton creation

### Considerations

- **State Management**: Be careful with mutable state in singleton operators
- **Testing**: In tests, be aware that operators persist across test cases
- **Cleanup**: Singleton instances are kept in memory until program exit

---

## Best Practices

### S3 Configuration

1. **Use decorators for programmatic configs**: Better for code-based configuration management
2. **Use env vars for secrets**: Keep sensitive data in environment variables
3. **Register early**: Register S3 configs at module import time
4. **Document configurations**: Add docstrings to configuration functions

### Operator Registration

1. **Register at module level**: Use `@register_operator` decorator immediately after class definition
2. **Implement both methods**: Always implement `run()` and `build_running_command()`
3. **Validate inputs**: Override `validate_input()` for custom validation
4. **Return proper exit codes**: Follow the exit code convention (0=success, 1-5=errors)
5. **Use descriptive operator IDs**: Include version in ID (e.g., `cleaner_v2.0`)

### Singleton Pattern

1. **Avoid mutable state**: Use immutable data structures when possible
2. **Document side effects**: Note if operators modify shared resources
3. **Test carefully**: Consider singleton behavior in unit tests
4. **Use dependency injection**: Pass dependencies through constructor rather than global state

---

## Migration from Old Code

### Before (No Registration)

```python
# Old way - no registration
class DataCleaner(BasicRunner):
    def run(self) -> int:
        # ... implementation ...
        pass

# Manual instantiation everywhere
cleaner = DataCleaner(pipeline_id, node_id, operator_id, ...)
```

### After (With Registration)

```python
# New way - with registration
@register_operator("data_cleaner_v1")
class DataCleaner(BasicRunner):
    def run(self) -> int:
        # ... implementation ...
        pass
    
    def build_running_command(self) -> List[str]:
        return ["python", "clean.py"]

# Dynamic lookup
OperatorClass = get_operator_class("data_cleaner_v1")
cleaner = OperatorClass(pipeline_id, node_id, operator_id, ...)
```

---

## Troubleshooting

### S3 Issues

**Problem**: "未找到 S3 配置"
- **Solution**: Ensure either decorator registration or env vars are set
- **Check**: Call `get_s3_config(provider, bucket)` to verify registration

**Problem**: Configuration not loading
- **Solution**: Ensure decorator function is executed (imported)
- **Check**: Decorator should be at module level, not inside functions

### Operator Issues

**Problem**: "TypeError: 被装饰的类必须继承 BasicRunner"
- **Solution**: Ensure your operator class inherits from `BasicRunner`

**Problem**: "NotImplementedError: 需重写 build_running_command"
- **Solution**: Implement the `build_running_command()` abstract method

**Problem**: Singleton not working
- **Solution**: Ensure you're using the same `operator_id` for instances you expect to be the same

---

## See Also

- [OmegaConf Migration Guide](OMEGACONF_MIGRATION_GUIDE.md)
- [README.md](README.md)
- [API Documentation](doc/)
