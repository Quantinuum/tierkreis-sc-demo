"""Code generated from fmo_chemistry_worker namespace. Please do not edit."""

# ruff: noqa: F821
from typing import NamedTuple

from tierkreis.controller.data.models import TKR, OpaqueType


class DerivativeJobsPort(NamedTuple):
    jobs: TKR[list[OpaqueType["fmo_vqe.models.DerivativeJob"]]]


class DerivativePort(NamedTuple):
    value: TKR[OpaqueType["fmo_vqe.models.DerivativeBlock"]]


class LoopPort(NamedTuple):
    should_continue: TKR[bool]
    state: TKR[OpaqueType["fmo_vqe.models.State"]]


class StatePort(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]


class initialize_helium_from_pyscf(NamedTuple):
    settings: TKR[OpaqueType["fmo_vqe.models.Settings"]]

    @staticmethod
    def out() -> type[StatePort]:
        return StatePort

    @property
    def namespace(self) -> str:
        return "fmo_chemistry_worker"


class initialize_fragment_from_integrals(NamedTuple):
    fragment: TKR[OpaqueType["fmo_vqe.models.Fragment"]]

    @staticmethod
    def out() -> type[StatePort]:
        return StatePort

    @property
    def namespace(self) -> str:
        return "fmo_chemistry_worker"


class initialize_dimer_from_fcidump_file(NamedTuple):
    fcidump: TKR[str]
    settings: TKR[OpaqueType["fmo_vqe.models.Settings"]]

    @staticmethod
    def out() -> type[StatePort]:
        return StatePort

    @property
    def namespace(self) -> str:
        return "fmo_chemistry_worker"


class evaluate_energy_from_measurements(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]
    measurements: TKR[list[OpaqueType["fmo_vqe.models.Measurement"]]]

    @staticmethod
    def out() -> type[StatePort]:
        return StatePort

    @property
    def namespace(self) -> str:
        return "fmo_chemistry_worker"


class initialize_orbital_optimization(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]

    @staticmethod
    def out() -> type[StatePort]:
        return StatePort

    @property
    def namespace(self) -> str:
        return "fmo_chemistry_worker"


class build_orbital_derivative_jobs(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]

    @staticmethod
    def out() -> type[DerivativeJobsPort]:
        return DerivativeJobsPort

    @property
    def namespace(self) -> str:
        return "fmo_chemistry_worker"


class compute_orbital_derivative_block(NamedTuple):
    job: TKR[OpaqueType["fmo_vqe.models.DerivativeJob"]]

    @staticmethod
    def out() -> type[DerivativePort]:
        return DerivativePort

    @property
    def namespace(self) -> str:
        return "fmo_chemistry_worker"


class update_orbitals_and_check_convergence(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]
    blocks: TKR[list[OpaqueType["fmo_vqe.models.DerivativeBlock"]]]

    @staticmethod
    def out() -> type[LoopPort]:
        return LoopPort

    @property
    def namespace(self) -> str:
        return "fmo_chemistry_worker"
