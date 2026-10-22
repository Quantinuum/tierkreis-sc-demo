#TODO Implement your custom worker here.
from tierkreis import Worker
from tierkreis.exceptions import TierkreisError

worker = Worker("example_worker")

@worker.task()
def your_worker_task(value: int) -> int:
    return value

