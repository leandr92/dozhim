from uuid import uuid4


def new_job_id() -> str:
    return str(uuid4())
