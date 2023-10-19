import logging
import os
from collections import deque
from copy import deepcopy
from time import sleep
from typing import Deque, Dict, List, Optional, Set

import gokart
import luigi
from gokart.target import make_target
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
        master_pod_name: Optional[str] = None,
        master_pod_uid: Optional[str] = None,
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
        self.master_pod_name = master_pod_name
        self.master_pod_uid = master_pod_uid

        self.task_id_to_job_name: Dict[str, str] = dict()

    def build(self, root_task: gokart.TaskOnKart) -> None:
        # check all config file paths exists
        luigi_parser_instance = luigi.configuration.get_config()
        config_paths = luigi_parser_instance._config_paths
        for config_path in config_paths:
            assert os.path.exists(config_path), f"Config file {config_path} does not exits."
        # save configs to remote cache
        workspace_dir = os.environ.get("TASK_WORKSPACE_DIRECTORY")
        remote_config_dir = os.path.join(workspace_dir, "kannon", "conf")
        remote_config_paths = [os.path.join(remote_config_dir, os.path.basename(config_path)) for config_path in config_paths]
        for remote_config_path in remote_config_paths:
            with open(config_path, "r") as f:
                make_target(remote_config_path).dump(f)

        # push tasks into queue
        logger.info("Creating task queue...")
        task_queue = self._create_task_queue(root_task)

        # consume task queue
        logger.info("Consuming task queue...")
        while task_queue:
            task = task_queue.popleft()
            if task.complete():
                logger.info(f"Task {self._gen_task_info(task)} is already completed.")
                continue
            if task.make_unique_id() in self.task_id_to_job_name:
                # check if task is still running on child job
                job_name = self.task_id_to_job_name[task.make_unique_id()]
                job_status = get_job_status(
                    self.api_instance,
                    job_name,
                    self.namespace,
                )
                if job_status == JobStatus.FAILED:
                    raise RuntimeError(f"Task {self._gen_task_info(task)} on job {job_name} has failed.")
                logger.info(f"Task {self._gen_task_info(task)} is still running on child job.")
                task_queue.append(task)  # re-enqueue task to check if it is done
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
                self._exec_bullet_task(task, remote_config_paths)
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
        visited_task_ids: Set[str] = set()

        def _rec_enqueue_task(task: gokart.TaskOnKart) -> None:
            """Traversal task tree in post-order to push tasks into task queue."""
            nonlocal task_queue, visited_task_ids

            visited_task_ids.add(task.make_unique_id())
            # run children
            children = flatten(task.requires())
            for child in children:
                if child.make_unique_id() in visited_task_ids:
                    continue
                _rec_enqueue_task(child)

            task_queue.append(task)
            logger.info(f"Task {self._gen_task_info(task)} is pushed to task queue")

        _rec_enqueue_task(root_task)
        logger.info(f"Total tasks in task queue: {len(task_queue)}")
        return task_queue

    def _exec_gokart_task(self, task: gokart.TaskOnKart) -> None:
        # Run on master job
        try:
            gokart.build(task)
        except Exception:
            raise RuntimeError(f"Task {self._gen_task_info(task)} on job master has failed.")

    def _exec_bullet_task(self, task: TaskOnBullet, remote_config_paths: list) -> None:
        logger.info(f"Task on bullet type = {type(task)}")
        # Save task instance as pickle object
        pkl_path = self._gen_pkl_path(task)
        make_target(pkl_path).dump(task)
        # Run on child job
        job_name = gen_job_name(self.job_prefix)
        job = self._create_child_job_object(
            job_name=job_name,
            task_pkl_path=pkl_path,
            remote_config_paths=remote_config_paths,
        )
        create_job(self.api_instance, job, self.namespace)
        logger.info(f"Created child job {job_name} with task {self._gen_task_info(task)}")
        self.task_id_to_job_name[task.make_unique_id()] = job_name

    def _create_child_job_object(
        self,
        job_name: str,
        task_pkl_path: str,
        remote_config_paths: str,
    ) -> client.V1Job:
        # TODO: use python -c to avoid dependency to execute_task.py
        cmd = [
            "python",
            self.path_child_script,
            "--task-pkl-path",
            f"'{task_pkl_path}'",
            "--remote-config-paths",
            ",".join(remote_config_paths),
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
        # add owner reference from child to parent if master pod info is available
        if self.master_pod_name and self.master_pod_uid:
            owner_reference = client.V1OwnerReference(
                api_version="batch/v1",
                kind="Pod",
                name=self.master_pod_name,  # owner pod name
                uid=self.master_pod_uid,  # owner pod uid
            )
            if job.metadata.owner_references:
                job.metadata.owner_references.append(owner_reference)
            else:
                job.metadata.owner_references = [owner_reference]
        else:
            logger.warning("Owner reference is not set because master pod info is not provided.")

        return job

    @staticmethod
    def _gen_task_info(task: gokart.TaskOnKart) -> str:
        return f"{task.get_task_family()}_{task.make_unique_id()}"

    @staticmethod
    def _gen_pkl_path(task: gokart.TaskOnKart) -> str:
        return os.path.join(task.workspace_directory, 'kannon', f'task_obj_{task.make_unique_id()}.pkl')

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
