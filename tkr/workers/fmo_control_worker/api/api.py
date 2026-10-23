"""Code generated from fmo_control_worker namespace. Please do not edit."""

# ruff: noqa: F821
from typing import NamedTuple

from tierkreis.controller.data.models import TKR, OpaqueType


class AmplitudeProposal(NamedTuple):
    candidates: TKR[list[OpaqueType["fmo_vqe.models.State"]]]
    state: TKR[OpaqueType["fmo_vqe.models.State"]]


class LoopPort(NamedTuple):
    should_continue: TKR[bool]
    state: TKR[OpaqueType["fmo_vqe.models.State"]]


class ResultPort(NamedTuple):
    result: TKR[OpaqueType["fmo_vqe.models.FMOResult"]]


class StatePort(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]


class load_fmo_fragments_from_manifest(NamedTuple):
    manifest: TKR[str]
    settings: TKR[OpaqueType["fmo_vqe.models.Settings"]]

    @staticmethod
    def out() -> type[TKR[list[OpaqueType["fmo_vqe.models.Fragment"]]]]:
        return TKR[list[OpaqueType["fmo_vqe.models.Fragment"]]]

    @property
    def namespace(self) -> str:
        return "fmo_control_worker"


class initialize_amplitude_optimization(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]

    @staticmethod
    def out() -> type[StatePort]:
        return StatePort

    @property
    def namespace(self) -> str:
        return "fmo_control_worker"


class propose_amplitude_candidates(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]

    @staticmethod
    def out() -> type[AmplitudeProposal]:
        return AmplitudeProposal

    @property
    def namespace(self) -> str:
        return "fmo_control_worker"


class record_amplitude_evaluations(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]
    results: TKR[list[OpaqueType["fmo_vqe.models.State"]]]

    @staticmethod
    def out() -> type[LoopPort]:
        return LoopPort

    @property
    def namespace(self) -> str:
        return "fmo_control_worker"


class begin_macro_iteration(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]

    @staticmethod
    def out() -> type[StatePort]:
        return StatePort

    @property
    def namespace(self) -> str:
        return "fmo_control_worker"


class check_macro_convergence(NamedTuple):
    state: TKR[OpaqueType["fmo_vqe.models.State"]]

    @staticmethod
    def out() -> type[LoopPort]:
        return LoopPort

    @property
    def namespace(self) -> str:
        return "fmo_control_worker"


class aggregate_fmo2_energy(NamedTuple):
    states: TKR[list[OpaqueType["fmo_vqe.models.State"]]]

    @staticmethod
    def out() -> type[ResultPort]:
        return ResultPort

    @property
    def namespace(self) -> str:
        return "fmo_control_worker"
