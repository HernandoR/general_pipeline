.. _user-guide:

User Guide
==========

This guide covers the main concepts and usage patterns of General Pipeline.

Configuration Files
-------------------

General Pipeline uses YAML configuration files managed by OmegaConf.

Pipeline Configuration
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   pipeline:
     pipeline_id: my_pipeline
     name: My Pipeline
     work_dir: ./workspace
     
     log_config:
       level: INFO
       rotation: 10 GB
       
     nodes:
       refs:
         - node_1:v1.0
         
     operators:
       refs:
         - my_operator:v1.0

Node Configuration
~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   node_1:
     node_id: node_1
     operator_ids:
       - my_operator
     runner_count: 1
     
     resource:
       cpu_request: 2.0
       cpu_limit: 4.0
       memory_request: 8.0
       memory_limit: 16.0

Operator Configuration
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   my_operator:
     operator_id: my_operator
     git_repo: https://github.com/example/operator.git
     git_tag: v1.0.0
     upstream_dependencies: []
     start_command: python main.py
     timeout: 1800
     
     extra_env_vars:
       BATCH_SIZE: "100"
       
     env_config:
       env_name: my_env
       pyproject_path: pyproject.toml

Operator Development
--------------------

All operators must inherit from ``BasicRunner`` and implement two methods:

.. code-block:: python

   from general_pipeline.core import BasicRunner, register_operator
   from typing import List
   
   @register_operator("my_operator_v1")
   class MyOperator(BasicRunner):
       def run(self) -> int:
           """Execute operator business logic"""
           # Access paths
           # self.input_root - input directory
           # self.output_root - output directory
           # self.workspace_root - workspace directory
           
           # Your logic here
           return 0  # 0 = success
       
       def build_running_command(self) -> List[str]:
           """Build command for running this operator"""
           return [
               "python", "main.py",
               "--input", self.input_root,
               "--output", self.output_root
           ]

S3 Configuration
----------------

Register S3 configurations using the decorator:

.. code-block:: python

   from general_pipeline.utils import register_s3_config, download_from_s3
   
   @register_s3_config("tos", "my-bucket")
   def configure_bucket():
       return {
           "endpoint": "https://tos-cn-beijing.volces.com",
           "access_key": "your_key",
           "secret_key": "your_secret",
           "region": "cn-beijing"
       }
   
   # Use S3 operations
   data = download_from_s3("tos://my-bucket/data/file.csv")

Docker Deployment
-----------------

Multi-stage Dockerfile example:

.. code-block:: dockerfile

   # Build stage - initialization
   FROM python:3.11 as builder
   WORKDIR /app
   
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   
   COPY conf/ conf/
   COPY s3_aksk.env .
   RUN touch .project_root
   
   # Initialize: clone code, create environments
   RUN pipeline-cli init --conf conf/pipeline.yaml --config-root conf/
   
   # Runtime stage - execution only
   FROM python:3.11
   WORKDIR /app
   
   COPY --from=builder /app /app
   
   CMD ["pipeline-cli", "run", "--conf", "conf/pipeline.yaml", "--skip-init"]
