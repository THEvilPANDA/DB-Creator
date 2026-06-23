from app.config import settings
from app.workers.tasks import provision_database


class WorkerSettings:
    functions = [provision_database]
    redis_settings = settings.REDIS_URL
    max_jobs = 10
    job_timeout = 300
