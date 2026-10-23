"""Code generated from fmo_quantum_worker namespace. Please do not edit."""

# ruff: noqa: F821
from typing import NamedTuple

from tierkreis.controller.data.models import TKR, OpaqueType


class MeasurementJobsPort(NamedTuple):
    jobs: TKR[list[OpaqueType["fmo_vqe.models.MeasurementJob"]]]


class MeasurementPort(NamedTuple):
    value: TKR[OpaqueType["fmo_vqe.models.Measurement"]]


class StatePort(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]


class prepare_puccd_measurement_circuits(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]

    @staticmethod
    def out() -> type[StatePort]:
        return StatePort

    @property
    def namespace(self) -> str:
        return "fmo_quantum_worker"


class build_measurement_shard_jobs(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]

    @staticmethod
    def out() -> type[MeasurementJobsPort]:
        return MeasurementJobsPort

    @property
    def namespace(self) -> str:
        return "fmo_quantum_worker"


class execute_measurement_job(NamedTuple):
    job: TKR[OpaqueType["fmo_vqe.models.MeasurementJob"]]

    @staticmethod
    def out() -> type[MeasurementPort]:
        return MeasurementPort

    @property
    def namespace(self) -> str:
        return "fmo_quantum_worker"
