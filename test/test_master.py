from __future__ import annotations

import os
import unittest

import gokart
from kubernetes import client

from kannon import Kannon


class TestStringMethods(unittest.TestCase):

    def test_create_task_queue(self) -> None:

        class Example(gokart.TaskOnKart):
            pass

        class Dict(gokart.TaskOnKart):

            def requires(self) -> dict[str, Example]:
                return dict(example=Example())

        class List(gokart.TaskOnKart):

            def requires(self) -> list[Example]:
                return [Example()]

        class ListInDict(gokart.TaskOnKart):

            def requires(self) -> dict[str, list[Example]]:
                return dict(example=[Example()])

        class Single(gokart.TaskOnKart):

            def requires(self) -> Example:
                return Example()

        cases = [Dict(), List(), ListInDict(), Single()]
        for case in cases:
            with self.subTest(case=case):
                master = Kannon(
                    api_instance=None,
                    template_job=client.V1Job(metadata=client.V1ObjectMeta()),
                    job_prefix="",
                    path_child_script=__file__,  # just pass any existing file as dummy
                    env_to_inherit=None,
                )
                master._create_task_queue(case)


class TestCreateChildJobObject(unittest.TestCase):

    def _get_template_job(self) -> client.V1Job:
        return client.V1Job(api_version="batch/v1",
                            kind="Job",
                            metadata=client.V1ObjectMeta(
                                name="dummy-job-name",
                                namespace="dummy-namespace",
                            ),
                            spec=client.V1JobSpec(template=client.V1PodTemplateSpec(spec=client.V1PodSpec(
                                service_account_name="dummy-service-account",
                                containers=[client.V1Container(
                                    name="job",
                                    image="dummy-image",
                                )],
                                restart_policy="Never",
                            ))))

    def tearDown(self) -> None:
        super().tearDown()
        os.environ.clear()

    def test_success_basic(self) -> None:

        class Example(gokart.TaskOnKart):
            pass

        serialized_task = gokart.TaskInstanceParameter().serialize(Example())
        template_job = self._get_template_job()
        master = Kannon(
            api_instance=None,
            template_job=template_job,
            job_prefix="",
            path_child_script=__file__,  # just pass any existing file as dummy
            env_to_inherit=None,
        )
        # set os env
        os.environ.update({"TASK_WORKSPACE_DIRECTORY": "/cache"})
        child_job_name = "test-job"
        child_job = master._create_child_job_object(child_job_name, serialized_task)

        # following should be copied from template_job
        self.assertEqual(child_job.api_version, template_job.api_version)
        self.assertEqual(child_job.kind, template_job.kind)
        self.assertEqual(child_job.metadata.namespace, template_job.metadata.namespace)
        self.assertEqual(child_job.spec.template.spec.service_account_name, template_job.spec.template.spec.service_account_name)
        self.assertEqual(child_job.spec.template.spec.containers[0].name, template_job.spec.template.spec.containers[0].name)
        self.assertEqual(child_job.spec.template.spec.containers[0].image, template_job.spec.template.spec.containers[0].image)
        self.assertEqual(child_job.spec.template.spec.restart_policy, template_job.spec.template.spec.restart_policy)
        # following should be overwritten
        self.assertEqual(child_job.spec.template.spec.containers[0].command, ["python", __file__, "--serialized-task", f"'{serialized_task}'"])
        self.assertEqual(child_job.metadata.name, child_job_name)
        # envvar TASK_WORKSPACE_DIRECTORY should be inherited
        child_env = child_job.spec.template.spec.containers[0].env
        self.assertEqual(len(child_env), 1)
        self.assertEqual(child_env[0], {"name": "TASK_WORKSPACE_DIRECTORY", "value": "/cache"})

    def test_success_custom_env(self) -> None:

        class Example(gokart.TaskOnKart):
            pass

        serialized_task = gokart.TaskInstanceParameter().serialize(Example())
        template_job = self._get_template_job()
        master = Kannon(
            api_instance=None,
            template_job=template_job,
            job_prefix="",
            path_child_script=__file__,  # just pass any existing file as dummy
            env_to_inherit=["TASK_WORKSPACE_DIRECTORY", "MY_ENV0", "MY_ENV1"],
        )
        # set os env
        os.environ.update({"TASK_WORKSPACE_DIRECTORY": "/cache", "MY_ENV0": "env0", "MY_ENV1": "env1"})
        child_job_name = "test-job"
        child_job = master._create_child_job_object(child_job_name, serialized_task)

        child_env = child_job.spec.template.spec.containers[0].env
        self.assertEqual(len(child_env), 3)
        self.assertEqual(child_env[0], {"name": "TASK_WORKSPACE_DIRECTORY", "value": "/cache"})
        self.assertEqual(child_env[1], {"name": "MY_ENV0", "value": "env0"})
        self.assertEqual(child_env[2], {"name": "MY_ENV1", "value": "env1"})

    def test_fail_command_set(self) -> None:

        class Example(gokart.TaskOnKart):
            pass

        serialized_task = gokart.TaskInstanceParameter().serialize(Example())
        template_job = self._get_template_job()
        template_job.spec.template.spec.containers[0].command = ["dummy-command"]
        master = Kannon(
            api_instance=None,
            template_job=template_job,
            job_prefix="",
            path_child_script=__file__,  # just pass any existing file as dummy
            env_to_inherit=None,
        )
        # set os env
        os.environ.update({"TASK_WORKSPACE_DIRECTORY": "/cache"})
        with self.assertRaises(AssertionError):
            master._create_child_job_object("test-job", serialized_task)

    def test_fail_default_env_not_exist(self) -> None:

        class Example(gokart.TaskOnKart):
            pass

        serialized_task = gokart.TaskInstanceParameter().serialize(Example())
        template_job = self._get_template_job()

        cases = [None, ["TASK_WORKSPACE_DIRECTORY", "MY_ENV0", "MY_ENV1"]]
        for case in cases:
            with self.subTest(case=case):
                master = Kannon(
                    api_instance=None,
                    template_job=template_job,
                    job_prefix="",
                    path_child_script=__file__,  # just pass any existing file as dummy
                    env_to_inherit=case,
                )
                with self.assertRaises(ValueError):
                    master._create_child_job_object("test-job", serialized_task)


if __name__ == '__main__':
    unittest.main()
