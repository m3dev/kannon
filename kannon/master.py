import logging
import os
from collections import deque
from copy import deepcopy
from time import sleep
from typing import Deque, Dict, List, Optional, Set

import gokart
from kubernetes import client
from luigi.task import flatten

from .kube_util import JobStatus, create_job, gen_job_name, get_job_status
from .task import TaskOnBullet

logger = logging.getLogger(__name__)


class Kannon:

    def __init__(
        self,
        # k8s resources
        api_instance: client.BatchV1Api,
        template_job: client.V1Job,
        # kannon resources
        job_prefix: str,
        path_child_script: str = "./run_child.py",
        env_to_inherit: Optional[List[str]] = None,
    ) -> None:
        # validation
        if not os.path.exists(path_child_script):
            raise FileNotFoundError(f"Child script {path_child_script} does not exist.")

        self.template_job = template_job
        self.api_instance = api_instance
        self.namespace = template_job.metadata.namespace
        self.job_prefix = job_prefix
        self.path_child_script = path_child_script
        if env_to_inherit is None:
            env_to_inherit = ["TASK_WORKSPACE_DIRECTORY"]
        self.env_to_inherit = env_to_inherit

        self.task_id_to_job_name: Dict[str, str] = dict()

    def build(self, root_task: gokart.TaskOnKart):
        # push tasks into queue
        logger.info("Creating task queue...")
        task_queue = self._create_task_queue(root_task)

        # consume task queue
        launched_task_ids: Set[str] = set()
        logger.info("Consuming task queue...")
        while task_queue:
            task = task_queue.popleft()
            if task.complete():
                logger.info(f"Task {self._gen_task_info(task)} is already completed.")
                continue
            if task.make_unique_id() in launched_task_ids:
                logger.info(f"Task {self._gen_task_info(task)} is still running on child job.")
                task_queue.append(task)
                continue

            # TODO: enable user to specify duration to sleep for each task
            sleep(1.0)
            logger.info(f"Checking if task {self._gen_task_info(task)} is executable...")
            if not self._is_executable(task):
                task_queue.append(task)  # re-enqueue task to check if it's executable later
                logger.debug("Task is not executable yet. Re-enqueue task.")
                continue
            # execute task
            if isinstance(task, TaskOnBullet):
                logger.info(f"Trying to run task {self._gen_task_info(task)} on child job...")
                self._exec_bullet_task(task)
                launched_task_ids.add(task.make_unique_id())  # mark as already launched task
                task_queue.append(task)  # re-enqueue task to check if it is done
            elif isinstance(task, gokart.TaskOnKart):
                logger.info(f"Executing task {self._gen_task_info(task)} on master job...")
                self._exec_gokart_task(task)
                logger.info(f"Completed task {self._gen_task_info(task)} on master job.")
            else:
                raise TypeError(f"Invalid task type: {type(task)}")

        logger.info("All tasks completed!")

    def _create_task_queue(self, root_task: gokart.TaskOnKart) -> Deque[gokart.TaskOnKart]:
        task_queue: Deque[gokart.TaskOnKart] = deque()

        def _rec_enqueue_task(task: gokart.TaskOnKart) -> None:
            """Traversal task tree in post-order to push tasks into task queue."""
            nonlocal task_queue
            # run children
            children = flatten(task.requires())
            for child in children:
                _rec_enqueue_task(child)

            task_queue.append(task)
            logger.info(f"Task {self._gen_task_info(task)} is pushed to task queue")

        _rec_enqueue_task(root_task)
        return task_queue

    def _exec_gokart_task(self, task: gokart.TaskOnKart) -> None:
        # Run on master job
        try:
            gokart.build(task)
        except Exception:
            raise RuntimeError(f"Task {self._gen_task_info(task)} on job master has failed.")

    def _exec_bullet_task(self, task: TaskOnBullet) -> None:
        # Run on child job
        serialized_task = gokart.TaskInstanceParameter().serialize(task)
        job_name = gen_job_name(f"{self.job_prefix}-{task.get_task_family()}")
        job = self._create_child_job_object(
            job_name=job_name,
            serialized_task=serialized_task,
        )
        create_job(self.api_instance, job, self.namespace)
        logger.info(f"Created child job {job_name} with task {self._gen_task_info(task)}")
        task_unique_id = task.make_unique_id()
        self.task_id_to_job_name[task_unique_id] = job_name

    def _create_child_job_object(self, job_name: str, serialized_task: str) -> client.V1Job:
        # TODO: use python -c to avoid dependency to execute_task.py
        cmd = [
            "python",
            self.path_child_script,
            "--serialized-task",
            f"'{serialized_task}'",
        ]
        job = deepcopy(self.template_job)
        # replace command
        assert job.spec.template.spec.containers[0].command is None, \
            "command will be replaced by kannon, so you shouldn't set any command and args"
        job.spec.template.spec.containers[0].command = cmd
        # replace env
        child_envs = job.spec.template.spec.containers[0].env
        if not child_envs:
            child_envs = []
        for env_name in self.env_to_inherit:
            if env_name not in os.environ:
                raise ValueError(f"Envvar {env_name} does not exist.")
            child_envs.append({"name": env_name, "value": os.environ.get(env_name)})
        job.spec.template.spec.containers[0].env = child_envs
        # replace job name
        job.metadata.name = job_name

        return job

    @staticmethod
    def _gen_task_info(task: gokart.TaskOnKart) -> str:
        return f"{task.get_task_family()}_{task.make_unique_id()}"

    def _is_executable(self, task: gokart.TaskOnKart) -> bool:
        children = flatten(task.requires())

        for child in children:
            if not child.complete():
                return False
            if child.make_unique_id() not in self.task_id_to_job_name:
                continue
            job_name = self.task_id_to_job_name[child.make_unique_id()]
            job_status = get_job_status(
                self.api_instance,
                job_name,
                self.namespace,
            )
            if job_status == JobStatus.FAILED:
                raise RuntimeError(f"Task {self._gen_task_info(child)} on job {job_name} has failed.")
            if job_status == JobStatus.RUNNING:
                return False
        return True
