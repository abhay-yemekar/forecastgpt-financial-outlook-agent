"""RQ worker entry point: python -m app.worker"""

import sys

from redis import Redis
from rq import Queue, SimpleWorker, Worker

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("worker")


def main() -> None:
    connection = Redis.from_url(settings.REDIS_URL)
    queues = [Queue("forecasts", connection=connection)]
    # The plain Worker forks per job (the production/Linux path). SimpleWorker
    # executes jobs in-process, which is what works on Windows (no os.fork).
    if sys.platform == "win32":
        worker = SimpleWorker(queues, connection=connection)
        log.info("Starting RQ SimpleWorker on 'forecasts' (Windows: in-process execution).")
    else:
        worker = Worker(queues, connection=connection)
        log.info("Starting RQ Worker on 'forecasts'.")
    worker.work()


if __name__ == "__main__":
    main()
