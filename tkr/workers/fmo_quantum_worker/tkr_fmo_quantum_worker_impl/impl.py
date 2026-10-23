from tierkreis import Worker

from fmo_vqe.models import (
    MeasurementJob,
    MeasurementJobsPort,
    MeasurementPort,
    State,
    StatePort,
)
from tkr_fmo_quantum_worker_impl import quantum

worker = Worker("fmo_quantum_worker")


@worker.task()
def prepare_puccd_measurement_circuits(state: State) -> StatePort:
    return StatePort(quantum.prepare(state))


@worker.task()
def build_measurement_shard_jobs(state: State) -> MeasurementJobsPort:
    return MeasurementJobsPort(quantum.measurement_jobs(state))


@worker.task()
def execute_measurement_job(job: MeasurementJob) -> MeasurementPort:
    return MeasurementPort(quantum.simulate(job))
