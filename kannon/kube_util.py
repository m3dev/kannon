import enum
import logging
import random
from datetime import datetime

from kubernetes import client

logger = logging.getLogger(__name__)


class JobStatus(enum.Enum):
    RUNNING = 0
    SUCCEEDED = 1
    FAILED = 2

# Max length of job name is 63.
# https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#names
JOB_NAME_MAX_LENGTH = 63


def create_job(api_instance: client.BatchV1Api, job: client.V1Job, namespace: str) -> None:
    api_response = api_instance.create_namespaced_job(
        body=job,
        namespace=namespace,
    )
    logger.debug(f"Job created. status={api_response.status}")


def get_job_status(api_instance: client.BatchV1Api, job_name: str, namespace: str) -> JobStatus:
    api_response = api_instance.read_namespaced_job_status(name=job_name, namespace=namespace)
    if (api_response.status.succeeded is not None or api_response.status.failed is not None):
        final_status = (JobStatus.SUCCEEDED if api_response.status.succeeded else JobStatus.FAILED)
        return final_status
    return JobStatus.RUNNING


def gen_job_name(job_prefix: str) -> str:
    job_suffix = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(random.randint(0, 255)).zfill(3)}"
    job_prefix = job_prefix[:JOB_NAME_MAX_LENGTH - 1 - len(job_suffix)]
    job_name = f"{job_prefix}-{job_suffix}"
    job_name = job_name.replace("_", "-").lower()
    job_name = job_name[:JOB_NAME_MAX_LENGTH]
    return job_name
