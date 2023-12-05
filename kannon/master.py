from __future__ import annotations

import logging
import os
from collections import deque
from copy import deepcopy
from time import sleep

import gokart
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
        env_to_inherit: list[str] | None = None,
        master_pod_name: str | None = None,
        master_pod_uid: str | None = None,
        dynamic_config_path: str | None = None,
        max_child_jobs: int | None = None,
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
        self.dynamic_config_path = dynamic_config_path

        if max_child_jobs is not None and max_child_jobs <= 0:
            raise ValueError(f"max_child_jobs must be positive integer, but got {max_child_jobs}")
        self.max_child_jobs = max_child_jobs

        self.task_id_to_job_name: dict[str, str] = dict()

    def build(self, root_task: gokart.TaskOnKart) -> None:
        # check all config file paths exists
        # TODO: support multiple dynamic config files
        remote_config_path = None
        if self.dynamic_config_path:
            logger.info("Handling dynamic config files...")
            logger.info(f"Handling given config file {self.dynamic_config_path}")
            # save configs to remote cache
            if "TASK_WORKSPACE_DIRECTORY" not in os.environ:
                raise ValueError("TASK_WORKSPACE_DIRECTORY is essential.")
            remote_config_dir = os.path.join(os.environ["TASK_WORKSPACE_DIRECTORY"], "kannon", "conf")

            # TODO: support other format than .ini
            if not self.dynamic_config_path.endswith(".ini"):
                raise ValueError(f"Format {self.dynamic_config_path} is not supported.")
            # load local config and save it to remote cache
            local_conf_content = make_target(self.dynamic_config_path).load()
            remote_config_path = os.path.join(remote_config_dir, os.path.basename(self.dynamic_config_path))
            make_target(remote_config_path).dump(local_conf_content)
            logger.info(f"local config file {self.dynamic_config_path} is saved at remote {remote_config_path}.")
        else:
            logger.info("No dynamic config files are given.")

        # push tasks into queue
        logger.info("Creating task queue...")
        task_queue = self._create_task_queue(root_task)

        # consume task queue
        running_task_ids: set[str] = set()
        logger.info("Consuming task queue...")
        while task_queue:
            task = task_queue.popleft()
            if task.complete():
                logger.info(f"Task {self._gen_task_info(task)} is already completed.")
                if task.make_unique_id() in running_task_ids:
                    running_task_ids.remove(task.make_unique_id())
                continue
            if task.make_unique_id() in running_task_ids:
                # check if task is still running on child job
                self._check_child_task_status(task)
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
                if self.max_child_jobs is not None and len(running_task_ids) >= self.max_child_jobs:
                    task_queue.append(task)  # re-enqueue task to check later
                    logger.info(f"Reach max_child_jobs, waiting to run task {self._gen_task_info(task)} on child job...")
                    continue
                logger.info(f"Trying to run task {self._gen_task_info(task)} on child job...")
                self._exec_bullet_task(task, remote_config_path)
                running_task_ids.add(task.make_unique_id())  # mark as already launched task
                task_queue.append(task)  # re-enqueue task to check if it is done
            elif isinstance(task, gokart.TaskOnKart):
                logger.info(f"Executing task {self._gen_task_info(task)} on master job...")
                self._exec_gokart_task(task)
                logger.info(f"Completed task {self._gen_task_info(task)} on master job.")
            else:
                raise TypeError(f"Invalid task type: {type(task)}")

        logger.info("All tasks completed!")

    def _create_task_queue(self, root_task: gokart.TaskOnKart) -> deque[gokart.TaskOnKart]:
        task_queue: deque[gokart.TaskOnKart] = deque()
        visited_task_ids: set[str] = set()

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

    def _exec_bullet_task(self, task: TaskOnBullet, remote_config_path: str | None) -> None:
        # Save task instance as pickle object
        pkl_path = self._gen_pkl_path(task)
        make_target(pkl_path).dump(task)
        # Run on child job
        job_name = gen_job_name(self.job_prefix)
        job = self._create_child_job_object(
            job_name=job_name,
            task_pkl_path=pkl_path,
            remote_config_path=remote_config_path,
        )
        create_job(self.api_instance, job, self.namespace)
        logger.info(f"Created child job {job_name} with task {self._gen_task_info(task)}")
        self.task_id_to_job_name[task.make_unique_id()] = job_name

    def _create_child_job_object(
        self,
        job_name: str,
        task_pkl_path: str,
        remote_config_path: str | None = None,
    ) -> client.V1Job:
        # TODO: use python -c to avoid dependency to execute_task.py
        cmd = [
            "python",
            self.path_child_script,
            "--task-pkl-path",
            f"'{task_pkl_path}'",
        ]
        if remote_config_path:
            cmd.append("--remote-config-path")
            cmd.append(remote_config_path)
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

    def _check_child_task_status(self, task: TaskOnBullet) -> None:
        if task.make_unique_id() not in self.task_id_to_job_name:
            raise ValueError(f"Task {self._gen_task_info(task)} is not found in `task_id_to_job_name`")
        job_name = self.task_id_to_job_name[task.make_unique_id()]
        job_status = get_job_status(
            self.api_instance,
            job_name,
            self.namespace,
        )
        if job_status == JobStatus.FAILED:
            raise RuntimeError(f"Task {self._gen_task_info(task)} on job {job_name} has failed.")

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
