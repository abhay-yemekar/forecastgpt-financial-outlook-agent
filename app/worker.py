"""RQ worker entry point: python -m app.worker

Also exposes create_worker() for embedded mode (EMBED_WORKER=1), where the
API process runs a worker thread so one container serves the site, accepts
submissions, AND executes forecasts.
"""

import sys

from redis import Redis
from rq import Queue, SimpleWorker, Worker

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("worker")


def create_worker() -> SimpleWorker | Worker:
    connection = Redis.from_url(settings.REDIS_URL)
    queues = [Queue("forecasts", connection=connection)]
    # The plain Worker forks per job (the production/Linux path). SimpleWorker
    # executes jobs in-process, which is what works on Windows and inside an
    # embedded thread (no fork available there either).
    if sys.platform == "win32":
        log.info("RQ SimpleWorker (Windows: in-process execution).")
        return SimpleWorker(queues, connection=connection)
    log.info("RQ Worker (forking).")
    return Worker(queues, connection=connection)


def main() -> None:
    worker = create_worker()
    log.info("Starting worker on 'forecasts' queue.")
    worker.work()


if __name__ == "__main__":
    main()
