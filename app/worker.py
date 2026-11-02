"""RQ worker entry point: python -m app.worker

Also exposes create_worker() for embedded mode (EMBED_WORKER=1), where the
API process runs a worker thread so one container serves the site, accepts
submissions, AND executes forecasts.
"""

import sys

from redis import Redis
from rq import Queue, SimpleWorker, Worker
from rq.timeouts import TimerDeathPenalty

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("worker")


def create_worker(embedded: bool = False) -> SimpleWorker | Worker:
    connection = Redis.from_url(settings.REDIS_URL)
    queues = [Queue("forecasts", connection=connection)]
    # The plain Worker forks per job: the standalone Linux/macOS path. An
    # embedded worker runs on a thread of the (multithreaded) API process,
    # where fork() is unsafe, so it executes jobs in-process instead; so does
    # Windows, which has no fork at all.
    if embedded or sys.platform == "win32":
        worker = SimpleWorker(queues, connection=connection)
        if embedded:
            # RQ's default job timeout arms SIGALRM, which only the main
            # thread may do; the timer variant interrupts the worker thread.
            worker.death_penalty_class = TimerDeathPenalty
        log.info(f"RQ SimpleWorker ({'embedded thread' if embedded else 'Windows'}: in-process execution).")
        return worker
    log.info("RQ Worker (forking).")
    return Worker(queues, connection=connection)


def main() -> None:
    from app.ai.selftest import start_model_self_test

    start_model_self_test()
    worker = create_worker()
    log.info("Starting worker on 'forecasts' queue.")
    worker.work()


if __name__ == "__main__":
    main()
