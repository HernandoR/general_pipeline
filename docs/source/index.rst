General Pipeline Documentation
================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   user_guide
   api_reference
   migration_guide
   registration_guide

Overview
--------

General Pipeline is a production-grade, standardized data pipeline framework that supports:

* Hierarchical configuration with OmegaConf (YAML format)
* Multi-cloud storage (S3, TOS, KS3, OSS, COS)
* Docker containerization
* Selective execution
* Real-time resource monitoring

Key Features
------------

Architecture Design
~~~~~~~~~~~~~~~~~~~

* **Three-layer architecture**: Pipeline → Node → Operator
* **Separation of concerns**: ProjectInitiator (initialization) + PipelineExecutor (execution)
* **Docker-friendly**: Multi-stage builds, separate initialization and runtime

Configuration Management
~~~~~~~~~~~~~~~~~~~~~~~~

* **OmegaConf**: Type-safe configuration with variable interpolation
* **YAML format**: Clean, readable configuration files
* **Hierarchical loading**: Separate Pipeline/Node/Operator configs with version control
* **Dynamic override**: Load config overrides from S3
* **Pydantic validation**: Strong type checking, early error detection

Operator Management
~~~~~~~~~~~~~~~~~~~

* **Registration mechanism**: Use ``@register_operator`` decorator
* **Singleton pattern**: Ensures one instance per operator_id
* **Dynamic discovery**: Find operators by ID at runtime
* **Standardized interface**: All operators inherit from ``BasicRunner``

S3 Storage
~~~~~~~~~~

* **Multi-cloud support**: AWS S3, Huoshan Engine TOS, Kingsoft KS3, Alibaba OSS, Tencent COS
* **Registration mechanism**: Use ``@register_s3_config`` decorator
* **Unified interface**: ``provider://bucket/key`` format
* **Secure credentials**: Registry-based or environment variables

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
