# kannon

Kannon is a wrapper for the [gokart](https://github.com/m3dev/gokart) library that allows gokart tasks to be easily executed in a distributed and parallel manner on multiple [kubernetes](https://kubernetes.io/) jobs.

# Install
Kannon can be installed via `pip`.

```bash
pip install kannon
```

# Usage
It is required for users to prepare following two scripts and copy them into a docker container:
- A script to start task pipeline on master job.
- A script for child jobs to run assigned tasks.

Easy and self-contained quick starter will be available soon!

## A script to run job on master job
Required to:
- Import module where `gokart.TaskOnKart` and `kannon.TaskOnBullet` classes are defined.
- Load luigi and k8s configs.
- Create a task instance.
- Run `Kannon.build`.

```python
""" This script runs on master job. """
import logging

import gokart
import luigi
from kubernetes import config, client
import fire

# TODO: Import task definition here!
import example_tasks
from kannon import Kannon

logging.basicConfig(level=logging.INFO)


def main(
    container_name: str,
    image_name: str,
):
    # TODO: Load luigi config here!
    luigi.configuration.LuigiConfigParser.add_config_path("./conf/base.ini")

    # TODO: Load kube config here!
    config.load_incluster_config()
    v1 = client.BatchV1Api()
    # TODO: Create task instance here!
    task_root = [CREATE TASK INSTANCE HERE]
    
    # TODO: Run Kannon.build!
    Kannon(
        api_instance=v1,
        namespace="mynamespace",
        image_name=image_name,
        container_name=container_name,
        job_prefix="myjob",
        path_child_script="./run_child.py",
        env_to_inherit=["TASK_WORKSPACE_DIRECTORY"],
        service_account_name="myserviceaccount,
    ).build(task_root)


if __name__ == "__main__":
    Fire.fire(main)
```

## A script for child jobs to run assigned tasks
For now, it is required for users to prepare the following script. In the future release, it will not be required.

Required to:
- Import module where `gokart.TaskOnKart` and `kannon.TaskOnBullet` classes are defined.
- Load luigi config.
- Parse a serialized task instance.
- Run `gokart.build`.

```python
""" This script requires to be defined by user. """
import gokart
import luigi
import logging

# TODO: Import task definitions here!
import example_tasks

import fire

logging.basicConfig(level=logging.INFO)


def main(serialized_task: str):
    # TODO: Load luigi config here!
    luigi.configuration.LuigiConfigParser.add_config_path("./conf/base.ini")
    
    # TODO: Parse a serialized gokart.TaskOnKart here!
    task: gokart.TaskOnKart = gokart.TaskInstanceParameter().parse(serialized_task)
    # TODO: Run gokart.build!
    gokart.build(task)


if __name__ == "__main__":
    fire.Fire(main)
```

# Thanks

Kannon is a wrapper for gokart. Thanks to gokart and dependent projects!

- [gokart](https://github.com/m3dev/gokart)
