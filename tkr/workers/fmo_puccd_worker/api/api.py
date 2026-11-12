"""Code generated from fmo_puccd_worker namespace. Please do not edit."""

from typing import NamedTuple, Protocol

from tierkreis.data.models import TKR
from tierkreis.data.types import Struct


class PairUCCState(Struct, Protocol):
    curr_e: float
    evs: dict[str, float]
    gmo: list[list[float]]
    h1mo: list[float]
    h2mo: list[list[float]]
    stds: dict[str, float]


class ComputeEnergyOutput(NamedTuple):
    guess_energy: TKR[float]
    state: TKR[PairUCCState]


class ExpectationValues(NamedTuple):
    guess_energy2: TKR[float]
    guess_orb_grad: TKR[list[float]]
    guess_orb_hess: TKR[list[list[float]]]


class MinimizeAmpsStepOutput(NamedTuple):
    converged: TKR[bool]
    next_params: TKR[list[float]]
    state: TKR[PairUCCState]
    x_history: TKR[list[float]]


class MinimizeOrbsStepOutput(NamedTuple):
    state: TKR[PairUCCState]


class PairUCCData(Struct, Protocol):
    enuc: float
    h1mo: list[float]
    h2mo: list[list[float]]
    n_elec_pairs: int


class pucc_from_pyscf_str(NamedTuple):
    mol_str: TKR[str]

    @staticmethod
    def out() -> type[TKR[PairUCCData]]:
        return TKR[PairUCCData]

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class pucc_from_fcidump_filepath(NamedTuple):
    filepath: TKR[str]

    @staticmethod
    def out() -> type[TKR[PairUCCData]]:
        return TKR[PairUCCData]

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class pauli_ham(NamedTuple):
    data: TKR[PairUCCData]

    @staticmethod
    def out() -> type[TKR[dict[str, float]]]:
        return TKR[dict[str, float]]

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class initial_guess(NamedTuple):
    data: TKR[PairUCCData]

    @staticmethod
    def out() -> type[TKR[list[float]]]:
        return TKR[list[float]]

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class compute_energy_qk(NamedTuple):
    data: TKR[PairUCCData]
    guess: TKR[list[float]]

    @staticmethod
    def out() -> type[ComputeEnergyOutput]:
        return ComputeEnergyOutput

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class expectation_values(NamedTuple):
    data: TKR[PairUCCData]
    state: TKR[PairUCCState]

    @staticmethod
    def out() -> type[ExpectationValues]:
        return ExpectationValues

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class minimize_amps_step(NamedTuple):
    data: TKR[PairUCCData]
    state: TKR[PairUCCState]
    params: TKR[list[float]]
    thresh: TKR[float]
    x_history: TKR[list[float]]
    max_iter_per_step: TKR[int]

    @staticmethod
    def out() -> type[MinimizeAmpsStepOutput]:
        return MinimizeAmpsStepOutput

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class compute_energy(NamedTuple):
    data: TKR[PairUCCData]
    params: TKR[list[float]]

    @staticmethod
    def out() -> type[TKR[float]]:
        return TKR[float]

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class compute_orb_grad(NamedTuple):
    data: TKR[PairUCCData]
    params: TKR[list[float]]

    @staticmethod
    def out() -> type[TKR[list[float]]]:
        return TKR[list[float]]

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class minimize_orbs_converged(NamedTuple):
    data: TKR[PairUCCData]
    state: TKR[PairUCCState]
    grad_norm_thresh: TKR[float]

    @staticmethod
    def out() -> type[TKR[bool]]:
        return TKR[bool]

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class minimize_orbs_step(NamedTuple):
    data: TKR[PairUCCData]
    state: TKR[PairUCCState]
    max_iter_per_step: TKR[int]

    @staticmethod
    def out() -> type[MinimizeOrbsStepOutput]:
        return MinimizeOrbsStepOutput

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"
