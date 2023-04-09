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
    job_name = f"{job_prefix}-{str(random.randint(0, 255)).zfill(3)}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    # TODO: validate job_name more precisely
    job_name = job_name[:50]
    job_name = job_name.replace("_", "-").lower()
    return job_name
