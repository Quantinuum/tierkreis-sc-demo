#TODO Implement your custom worker here.
from tierkreis.worker import Worker
from tierkreis.exceptions import TierkreisError

worker = Worker("fmo_puccd_worker")

@worker.task()
def your_worker_task(value: int) -> int:
    return value

