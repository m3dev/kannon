""" This script runs on master job. """
import logging

import fire
import luigi
# import task definition
import tasks
from kubernetes import client, config

from kannon import Kannon

logging.basicConfig(level=logging.INFO)


def _create_task_instances():
    task_a = tasks.TaskA(param="a")
    task_b = tasks.TaskB(param="b", parent=task_a)

    task_c0 = tasks.TaskC(param="c0", parent=task_b)
    task_c1 = tasks.TaskC(param="c1", parent=task_b)
    task_c2 = tasks.TaskC(param="c2", parent=task_b)

    task_d0 = tasks.TaskD(param="d0", parent=task_c0)
    task_d1 = tasks.TaskD(param="d1", parent=task_c1)
    task_d2 = tasks.TaskD(param="d2", parent=task_c2)

    task_e0 = tasks.TaskE(param="e0", parent=task_d0)
    task_e1 = tasks.TaskE(param="e1", parent=task_d1)
    task_e2 = tasks.TaskE(param="e2", parent=task_d2)

    task_f = tasks.TaskF(param="f", parent_0=task_e0, parent_1=task_e1, parent_2=task_e2)

    task_g = tasks.TaskG(param="g", parent=task_f)

    return task_g


def _get_template_job_object():
    return client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name="kannon-child",
            namespace="kannon-quick-starter",
        ),
        spec=client.V1JobSpec(template=client.V1PodTemplateSpec(spec=client.V1PodSpec(
            service_account_name="job-manager",
            containers=[
                client.V1Container(name="job",
                                   image="kannon_quick_starter",
                                   image_pull_policy="IfNotPresent",
                                   volume_mounts=[client.V1VolumeMount(name="kannon-cache-volume", mount_path="/cache")])
            ],
            restart_policy="Never",
            volumes=[client.V1Volume(name="kannon-cache-volume", persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name="kannon-cache-volume-claim"))]))))


def main():
    # Load luigi config
    luigi.configuration.LuigiConfigParser.add_config_path("./conf/base.ini")

    # Load kube config
    config.load_incluster_config()
    v1 = client.BatchV1Api()
    # create task instance
    task_root = _create_task_instances()

    # create template job object
    template_job = _get_template_job_object()
    # run master job
    Kannon(
        api_instance=v1,
        template_job=template_job,
        job_prefix="quick-starter",
    ).build(task_root)


if __name__ == "__main__":
    fire.Fire(main)
