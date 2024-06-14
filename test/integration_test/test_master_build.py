from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock

import gokart
import luigi
from kubernetes import client
from luigi.task import flatten

from kannon import Kannon, TaskOnBullet


class MockTaskOnKart(gokart.TaskOnKart):
    wait_sec = 1.
    started_at: float | None = None

    def run(self) -> None:
        self.started_at = time.time()

    def complete(self) -> bool:
        if self.started_at is None:
            return False

        return time.time() > self.started_at + self.wait_sec


class MockTaskOnBullet(TaskOnBullet):
    wait_sec = 1.
    started_at: float | None = None

    def run(self) -> None:
        self.started_at = time.time()

    def complete(self) -> bool:
        if self.started_at is None:
            return False

        return time.time() > self.started_at + self.wait_sec


class MockKannon(Kannon):

    def __init__(self, *, max_child_jobs: int | None = None) -> None:
        super().__init__(
            api_instance=None,
            template_job=client.V1Job(metadata=client.V1ObjectMeta()),
            job_prefix="",
            path_child_script=__file__,  # just pass any existing file as dummy
            env_to_inherit=None,
            max_child_jobs=max_child_jobs,
        )

    def _exec_gokart_task(self, task: MockTaskOnKart) -> None:
        task.run()

    def _exec_bullet_task(self, task: MockTaskOnBullet, remote_config_path: str | None) -> None:
        self.task_id_to_job_name[task.make_unique_id()] = "dummy_job_name"
        task.run()

    def _check_child_task_status(self, task: MockTaskOnBullet) -> None:
        return None

    def _is_executable(self, task: MockTaskOnKart) -> bool:
        children = flatten(task.requires())
        for child in children:
            if not child.complete():
                return False
        return True


class TestConsumeTaskQueue(unittest.TestCase):

    def test_single_task_on_kart(self) -> None:
        self.maxDiff = None

        class Example(MockTaskOnKart):
            pass

        root_task = Example()

        master = MockKannon()
        with self.assertLogs() as cm:
            master.build(root_task)

        root_task_info = master._gen_task_info(root_task)
        self.assertEqual(cm.output, [
            'INFO:kannon.master:No dynamic config files are given.',
            'INFO:kannon.master:Creating task queue...',
            f'INFO:kannon.master:Task {root_task_info} is pushed to task queue',
            'INFO:kannon.master:Total tasks in task queue: 1',
            'INFO:kannon.master:Consuming task queue...',
            f'INFO:kannon.master:Checking if task {root_task_info} is executable...',
            f'INFO:kannon.master:Executing task {root_task_info} on master job...',
            f'INFO:kannon.master:Completed task {root_task_info} on master job.',
            'INFO:kannon.master:All tasks completed!',
        ])

    def test_single_task_on_bullet(self) -> None:
        self.maxDiff = None

        class Example(MockTaskOnBullet):
            pass

        root_task = Example()
        # FIXME: additional patch due to no sleep in this case
        root_task.complete = MagicMock(side_effect=[False, False, True])  # type:ignore

        master = MockKannon()
        with self.assertLogs() as cm:
            master.build(root_task)

        root_task_info = master._gen_task_info(root_task)
        self.assertEqual(cm.output, [
            'INFO:kannon.master:No dynamic config files are given.',
            'INFO:kannon.master:Creating task queue...',
            f'INFO:kannon.master:Task {root_task_info} is pushed to task queue',
            'INFO:kannon.master:Total tasks in task queue: 1',
            'INFO:kannon.master:Consuming task queue...',
            f'INFO:kannon.master:Checking if task {root_task_info} is executable...',
            f'INFO:kannon.master:Trying to run task {root_task_info} on child job...',
            f'INFO:kannon.master:Task {root_task_info} is still running on child job.',
            f'INFO:kannon.master:Task {root_task_info} is already completed.',
            'INFO:kannon.master:All tasks completed!',
        ])

    def test_three_task_on_bullet(self) -> None:
        self.maxDiff = None

        class Child(MockTaskOnBullet):
            param = luigi.IntParameter()

        c1 = Child(param=1)
        c1.wait_sec = 4
        c2 = Child(param=2)
        c2.wait_sec = 3
        c3 = Child(param=3)
        c3.wait_sec = 2

        class Parent(MockTaskOnKart):

            def requires(self) -> list[Child]:
                return [c1, c2, c3]

        root_task = Parent()

        master = MockKannon()
        with self.assertLogs() as cm:
            master.build(root_task)

        c1_task_info = master._gen_task_info(c1)
        c2_task_info = master._gen_task_info(c2)
        c3_task_info = master._gen_task_info(c3)
        root_task_info = master._gen_task_info(root_task)
        self.assertEqual(cm.output, [
            'INFO:kannon.master:No dynamic config files are given.',
            'INFO:kannon.master:Creating task queue...',
            f'INFO:kannon.master:Task {c1_task_info} is pushed to task queue',
            f'INFO:kannon.master:Task {c2_task_info} is pushed to task queue',
            f'INFO:kannon.master:Task {c3_task_info} is pushed to task queue',
            f'INFO:kannon.master:Task {root_task_info} is pushed to task queue',
            'INFO:kannon.master:Total tasks in task queue: 4',
            'INFO:kannon.master:Consuming task queue...',
            f'INFO:kannon.master:Checking if task {c1_task_info} is executable...',
            f'INFO:kannon.master:Trying to run task {c1_task_info} on child job...',
            f'INFO:kannon.master:Checking if task {c2_task_info} is executable...',
            f'INFO:kannon.master:Trying to run task {c2_task_info} on child job...',
            f'INFO:kannon.master:Checking if task {c3_task_info} is executable...',
            f'INFO:kannon.master:Trying to run task {c3_task_info} on child job...',
            f'INFO:kannon.master:Checking if task {root_task_info} is executable...',
            f'INFO:kannon.master:Task {c1_task_info} is still running on child job.',
            f'INFO:kannon.master:Task {c2_task_info} is still running on child job.',
            f'INFO:kannon.master:Task {c3_task_info} is still running on child job.',
            f'INFO:kannon.master:Checking if task {root_task_info} is executable...',
            f'INFO:kannon.master:Executing task {root_task_info} on master job...',
            f'INFO:kannon.master:Completed task {root_task_info} on master job.',
            f'INFO:kannon.master:Task {c1_task_info} is already completed.',
            f'INFO:kannon.master:Task {c2_task_info} is already completed.',
            f'INFO:kannon.master:Task {c3_task_info} is already completed.',
            'INFO:kannon.master:All tasks completed!',
        ])

    def test_three_task_on_bullet_with_max_child_jobs(self) -> None:
        self.maxDiff = None

        class Child(MockTaskOnBullet):
            param = luigi.IntParameter()

        c1 = Child(param=1)
        c1.wait_sec = 4
        c2 = Child(param=2)
        c2.wait_sec = 3
        c3 = Child(param=3)
        c3.wait_sec = 2

        class Parent(MockTaskOnKart):

            def requires(self) -> list[Child]:
                return [c1, c2, c3]

        root_task = Parent()

        master = MockKannon(max_child_jobs=2)
        with self.assertLogs() as cm:
            master.build(root_task)

        c1_task_info = master._gen_task_info(c1)
        c2_task_info = master._gen_task_info(c2)
        c3_task_info = master._gen_task_info(c3)
        root_task_info = master._gen_task_info(root_task)
        self.assertEqual(
            cm.output,
            [
                'INFO:kannon.master:No dynamic config files are given.',
                'INFO:kannon.master:Creating task queue...',
                f'INFO:kannon.master:Task {c1_task_info} is pushed to task queue',
                f'INFO:kannon.master:Task {c2_task_info} is pushed to task queue',
                f'INFO:kannon.master:Task {c3_task_info} is pushed to task queue',
                f'INFO:kannon.master:Task {root_task_info} is pushed to task queue',
                'INFO:kannon.master:Total tasks in task queue: 4',
                'INFO:kannon.master:Consuming task queue...',
                f'INFO:kannon.master:Checking if task {c1_task_info} is executable...',
                f'INFO:kannon.master:Trying to run task {c1_task_info} on child job...',
                f'INFO:kannon.master:Checking if task {c2_task_info} is executable...',
                f'INFO:kannon.master:Trying to run task {c2_task_info} on child job...',
                # c3 has to wait
                f'INFO:kannon.master:Checking if task {c3_task_info} is executable...',
                f'INFO:kannon.master:Reach max_child_jobs, waiting to run task {c3_task_info} on child job...',
                f'INFO:kannon.master:Checking if task {root_task_info} is executable...',
                f'INFO:kannon.master:Task {c1_task_info} is still running on child job.',
                f'INFO:kannon.master:Task {c2_task_info} is still running on child job.',
                f'INFO:kannon.master:Checking if task {c3_task_info} is executable...',
                f'INFO:kannon.master:Reach max_child_jobs, waiting to run task {c3_task_info} on child job...',
                f'INFO:kannon.master:Checking if task {root_task_info} is executable...',
                f'INFO:kannon.master:Task {c1_task_info} is already completed.',
                f'INFO:kannon.master:Task {c2_task_info} is already completed.',
                # now c3 can start
                f'INFO:kannon.master:Checking if task {c3_task_info} is executable...',
                f'INFO:kannon.master:Trying to run task {c3_task_info} on child job...',
                f'INFO:kannon.master:Checking if task {root_task_info} is executable...',
                f'INFO:kannon.master:Task {c3_task_info} is still running on child job.',
                f'INFO:kannon.master:Checking if task {root_task_info} is executable...',
                f'INFO:kannon.master:Executing task {root_task_info} on master job...',
                f'INFO:kannon.master:Completed task {root_task_info} on master job.',
                f'INFO:kannon.master:Task {c3_task_info} is already completed.',
                'INFO:kannon.master:All tasks completed!',
            ])


if __name__ == '__main__':
    unittest.main()
