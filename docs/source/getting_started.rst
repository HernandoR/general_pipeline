Getting Started
===============

Installation
------------

.. code-block:: bash

   git clone https://github.com/HernandoR/general_pipeline.git
   cd general_pipeline
   pip install -e .

Setting Up Project Root
-----------------------

.. code-block:: bash

   touch .project_root

Configuration
-------------

Create configuration files following this structure:

.. code-block:: text

   conf/
   ├── pipeline.yaml           # Main configuration
   ├── nodes/
   │   └── node_1_v1.0.yaml   # Node configuration
   └── operators/
       └── op_1_v1.0.yaml     # Operator configuration

Validation
----------

.. code-block:: bash

   pipeline-cli validate --conf conf/pipeline.yaml --config-root conf/

Initialization
--------------

.. code-block:: bash

   pipeline-cli init --conf conf/pipeline.yaml --config-root conf/

Running
-------

.. code-block:: bash

   # Run everything
   pipeline-cli run --conf conf/pipeline.yaml --skip-init

   # Run single node
   pipeline-cli run --conf conf/pipeline.yaml --node node_1 --skip-init

   # Run single operator
   pipeline-cli run --conf conf/pipeline.yaml --operator op_1 --skip-init
