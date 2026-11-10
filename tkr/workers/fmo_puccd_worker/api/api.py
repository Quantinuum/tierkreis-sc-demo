"""Code generated from fmo_puccd_worker namespace. Please do not edit."""

from typing import NamedTuple

from tierkreis.data.models import TKR


class ComputeEnergyOutput(NamedTuple):
    evs: TKR[dict[str, float]]
    guess_energy: TKR[float]
    stds: TKR[dict[str, float]]


class ExpectationValues(NamedTuple):
    guess_energy2: TKR[float]
    guess_orb_grad: TKR[list[float]]
    guess_orb_hess: TKR[list[list[float]]]


class MinimizeStepOutput(NamedTuple):
    converged: TKR[bool]
    next_params: TKR[list[float]]
    x_history: TKR[list[float]]


class pauli_ham_from_pyscf_mol(NamedTuple):
    mol_str: TKR[str]

    @staticmethod
    def out() -> type[TKR[dict[str, float]]]:
        return TKR[dict[str, float]]

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class initial_guess_from_pyscf_mol(NamedTuple):
    mol_str: TKR[str]

    @staticmethod
    def out() -> type[TKR[list[float]]]:
        return TKR[list[float]]

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class compute_energy_qk_from_pyscf_mol(NamedTuple):
    mol_str: TKR[str]
    guess: TKR[list[float]]

    @staticmethod
    def out() -> type[ComputeEnergyOutput]:
        return ComputeEnergyOutput

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class expectation_values_from_pyscf_mol(NamedTuple):
    mol_str: TKR[str]
    evs: TKR[dict[str, float]]
    stds: TKR[dict[str, float]]

    @staticmethod
    def out() -> type[ExpectationValues]:
        return ExpectationValues

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"


class minimize_step(NamedTuple):
    mol_str: TKR[str]
    params: TKR[list[float]]
    thresh: TKR[float]
    x_history: TKR[list[float]]
    max_iter_per_step: TKR[int]

    @staticmethod
    def out() -> type[MinimizeStepOutput]:
        return MinimizeStepOutput

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"
