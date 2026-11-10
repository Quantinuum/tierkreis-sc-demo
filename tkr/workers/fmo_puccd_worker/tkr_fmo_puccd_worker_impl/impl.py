from typing import NamedTuple

from numpy import pi
import pyscf.gto.mole as mole
from tierkreis.data.models import portmapping
from tierkreis.worker import Worker
from scipy.optimize import OptimizeResult, minimize

from tkr_fmo_puccd_worker_impl.puccd import (
    of2qiskit,
    pairUCC,
    puccd_finalize,
    puccd_initialize,
)

worker = Worker("fmo_puccd_worker")


@worker.task()
def pauli_ham_from_pyscf_mol(mol_str: str) -> dict[str, float]:
    mol = mole.loads(mol_str)
    puccd = pairUCC.from_pyscf_Mole(mol)
    pauli_ham = of2qiskit(puccd.ham_qubit(), puccd.n_qubits)
    return {
        # Convert to native float for easier visualisation.
        pauli_str: float(expectation)
        for pauli_str, expectation in pauli_ham.items()
    }


@worker.task()
def initial_guess_from_pyscf_mol(mol_str: str) -> list[float]:
    mol = mole.loads(mol_str)
    puccd = pairUCC.from_pyscf_Mole(mol)
    guess = puccd.initial_guess_mp2d()
    # Convert to native float for easier visualisation.
    return [float(param) for param in guess.tolist()]


@portmapping
class ComputeEnergyOutput(NamedTuple):
    guess_energy: float
    evs: dict[str, float]
    stds: dict[str, float]


@worker.task()
def compute_energy_qk_from_pyscf_mol(
    mol_str: str, guess: list[float]
) -> ComputeEnergyOutput:
    mol = mole.loads(mol_str)
    puccd = pairUCC.from_pyscf_Mole(mol)
    puccd_initialize()
    qk_guess = puccd.compute_energy_qk(guess)
    puccd_finalize()
    evs, stds = puccd.evs, puccd.stds
    return ComputeEnergyOutput(guess_energy=qk_guess, evs=evs, stds=stds)


@portmapping
class ExpectationValues(NamedTuple):
    guess_energy2: float
    guess_orb_grad: list[float]
    guess_orb_hess: list[list[float]]


@worker.task()
def expectation_values_from_pyscf_mol(
    mol_str: str, evs: dict[str, float], stds: dict[str, float]
) -> ExpectationValues:
    mol = mole.loads(mol_str)
    puccd = pairUCC.from_pyscf_Mole(mol)
    puccd.evs = evs
    puccd.stds = stds

    puccd_initialize()
    guess_energy2 = puccd.expected_energy()
    guess_orb_grad = puccd.orb_grad_qk()
    guess_orb_hess = puccd.orb_hess_qk()
    puccd_finalize()
    return ExpectationValues(
        guess_energy2=guess_energy2,
        guess_orb_grad=guess_orb_grad,
        guess_orb_hess=guess_orb_hess.tolist(),
    )


@portmapping
class MinimizeStepOutput(NamedTuple):
    next_params: list[float]
    x_history: list[float]
    converged: bool


@worker.task()
def minimize_step(
    mol_str: str,
    params: list[float],
    thresh: float,
    x_history: list[float],
    max_iter_per_step: int,
) -> MinimizeStepOutput:
    mol = mole.loads(mol_str)
    puccd = pairUCC.from_pyscf_Mole(mol)

    cursor = 0
    history_len = len(x_history)

    # Extra objective and callback wrappers to
    # allow us to save and restore history.
    def objective(params: list[float]) -> float:
        nonlocal cursor

        if cursor < history_len:
            replay = x_history[cursor]
            cursor += 1
            return replay
        else:
            next = puccd.compute_energy_qk(params)
            x_history.append(next)
            return next

    bounds = [(-1.0 * pi, pi)] * len(params)
    puccd_initialize()
    opt_result = minimize(
        objective,
        params,
        method="COBYLA",
        tol=thresh,
        bounds=bounds,
        options={"maxiter": max_iter_per_step + history_len},
    )
    puccd_finalize()
    return MinimizeStepOutput(
        next_params=[float(param) for param in opt_result["x"]],
        x_history=x_history,
        converged=opt_result["success"],
    )
