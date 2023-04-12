""" This script runs on master job. """
import logging

import gokart
import luigi
from kubernetes import config, client, utils
import fire

# TODO: Import task definition here!
import example_tasks

import sys
sys.path.append("./kannon/")
from kannon import Kannon

logging.basicConfig(level=logging.INFO)


def _create_general_case_instance():
    task_a = example_tasks.TaskA(param="a")
    task_b = example_tasks.TaskB(param="b", parent=task_a)
    
    task_c0 = example_tasks.TaskC(param="c0", parent=task_b)
    task_c1 = example_tasks.TaskC(param="c1", parent=task_b)
    task_c2 = example_tasks.TaskC(param="c2", parent=task_b)
    
    task_d0 = example_tasks.TaskD(param="d0", parent=task_c0)
    task_d1 = example_tasks.TaskD(param="d1", parent=task_c1)
    task_d2 = example_tasks.TaskD(param="d2", parent=task_c2)
    
    task_e0 = example_tasks.TaskE(param="e0", parent=task_d0)
    task_e1 = example_tasks.TaskE(param="e1", parent=task_d1)
    task_e2 = example_tasks.TaskE(param="e2", parent=task_d2)
    
    task_f = example_tasks.TaskF(param="f", parent_0=task_e0, parent_1=task_e1, parent_2=task_e2)
    
    task_g = example_tasks.TaskG(param="g", parent=task_f)
    
    return task_g

def _create_single_case_instance():
    task_a = example_tasks.TaskA(param="a")
    return task_a

def _get_template_job_object():
    return client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name="kannon-child",
            namespace="default",
        ),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    service_account_name="job-manager",
                    containers=[
                        client.V1Container(
                            name="job",
                            image="kannon_quick_starter",
                            image_pull_policy="IfNotPresent",
                            volume_mounts=[
                                client.V1VolumeMount(
                                    name="cache-volume",
                                    mount_path="/cache"
                                )
                            ]
                        )
                    ],
                    restart_policy="Never",
                    volumes=[
                        client.V1Volume(
                            name="cache-volume",
                            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                claim_name="cache-volume-claim"
                            )
                        )
                    ]
                )
            )
        )
    )


def main():
    # TODO: Load luigi config here!
    luigi.configuration.LuigiConfigParser.add_config_path("./conf/base.ini")

    # TODO: Load kube config here!
    config.load_incluster_config()
    v1 = client.BatchV1Api()
    # TODO: Create task instance here!
    # task_root = _create_single_case_instance()
    task_root = _create_general_case_instance()
    
    # TODO: Run Kannon.build!
    template_job = _get_template_job_object()
    Kannon(
        api_instance=v1,
        template_job=template_job,
        job_prefix="kannon-job",
    ).build(task_root)


if __name__ == "__main__":
    fire.Fire(main)