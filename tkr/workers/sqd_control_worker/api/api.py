"""Code generated from sqd_control_worker namespace. Please do not edit."""

# ruff: noqa: F821
from typing import NamedTuple

from tierkreis.data.models import TKR, OpaqueType


class LoopPort(NamedTuple):
    should_continue: TKR[bool]
    state: TKR[OpaqueType["sqd_sbd.models.DEState"]]


class ProblemPort(NamedTuple):
    fcidump: TKR[bytes]
    problem: TKR[OpaqueType["sqd_sbd.models.Problem"]]


class ProposalPort(NamedTuple):
    tasks: TKR[list[OpaqueType["sqd_sbd.models.WalkerTask"]]]


class ResultPort(NamedTuple):
    result: TKR[OpaqueType["sqd_sbd.models.SQDResult"]]


class SBDJobPort(NamedTuple):
    alpha_dets: TKR[bytes]
    record: TKR[OpaqueType["sqd_sbd.models.WalkerRecord"]]
    solver_args: TKR[list[str]]


class SamplesPort(NamedTuple):
    samples: TKR[OpaqueType["sqd_sbd.models.Samples"]]


class StatePort(NamedTuple):
    state: TKR[OpaqueType["sqd_sbd.models.DEState"]]


class WalkerResultPort(NamedTuple):
    result: TKR[OpaqueType["sqd_sbd.models.WalkerResult"]]


class load_sqd_problem(NamedTuple):
    fcidump: TKR[str]

    @staticmethod
    def out() -> type[ProblemPort]:
        return ProblemPort

    @property
    def namespace(self) -> str:
        return "sqd_control_worker"


class initialize_de_state(NamedTuple):
    settings: TKR[OpaqueType["sqd_sbd.models.Settings"]]

    @staticmethod
    def out() -> type[StatePort]:
        return StatePort

    @property
    def namespace(self) -> str:
        return "sqd_control_worker"


class propose_walkers(NamedTuple):
    state: TKR[OpaqueType["sqd_sbd.models.DEState"]]
    problem: TKR[OpaqueType["sqd_sbd.models.Problem"]]
    settings: TKR[OpaqueType["sqd_sbd.models.Settings"]]

    @staticmethod
    def out() -> type[ProposalPort]:
        return ProposalPort

    @property
    def namespace(self) -> str:
        return "sqd_control_worker"


class uses_random_samples(NamedTuple):
    settings: TKR[OpaqueType["sqd_sbd.models.Settings"]]

    @staticmethod
    def out() -> type[TKR[bool]]:
        return TKR[bool]

    @property
    def namespace(self) -> str:
        return "sqd_control_worker"


class sample_random_bitstrings(NamedTuple):
    task: TKR[OpaqueType["sqd_sbd.models.WalkerTask"]]
    problem: TKR[OpaqueType["sqd_sbd.models.Problem"]]
    settings: TKR[OpaqueType["sqd_sbd.models.Settings"]]

    @staticmethod
    def out() -> type[SamplesPort]:
        return SamplesPort

    @property
    def namespace(self) -> str:
        return "sqd_control_worker"


class prepare_sbd_input(NamedTuple):
    task: TKR[OpaqueType["sqd_sbd.models.WalkerTask"]]
    samples: TKR[OpaqueType["sqd_sbd.models.Samples"]]
    state: TKR[OpaqueType["sqd_sbd.models.DEState"]]
    problem: TKR[OpaqueType["sqd_sbd.models.Problem"]]
    settings: TKR[OpaqueType["sqd_sbd.models.Settings"]]

    @staticmethod
    def out() -> type[SBDJobPort]:
        return SBDJobPort

    @property
    def namespace(self) -> str:
        return "sqd_control_worker"


class finish_walker(NamedTuple):
    energy: TKR[float]
    carryover: TKR[bytes]
    record: TKR[OpaqueType["sqd_sbd.models.WalkerRecord"]]
    problem: TKR[OpaqueType["sqd_sbd.models.Problem"]]

    @staticmethod
    def out() -> type[WalkerResultPort]:
        return WalkerResultPort

    @property
    def namespace(self) -> str:
        return "sqd_control_worker"


class select_walkers(NamedTuple):
    state: TKR[OpaqueType["sqd_sbd.models.DEState"]]
    tasks: TKR[list[OpaqueType["sqd_sbd.models.WalkerTask"]]]
    results: TKR[list[OpaqueType["sqd_sbd.models.WalkerResult"]]]
    settings: TKR[OpaqueType["sqd_sbd.models.Settings"]]

    @staticmethod
    def out() -> type[LoopPort]:
        return LoopPort

    @property
    def namespace(self) -> str:
        return "sqd_control_worker"


class finalize_sqd(NamedTuple):
    state: TKR[OpaqueType["sqd_sbd.models.DEState"]]
    problem: TKR[OpaqueType["sqd_sbd.models.Problem"]]

    @staticmethod
    def out() -> type[ResultPort]:
        return ResultPort

    @property
    def namespace(self) -> str:
        return "sqd_control_worker"
