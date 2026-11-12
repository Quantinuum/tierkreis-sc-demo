from typing import NamedTuple, Optional

from numpy import pi
import numpy as np
import pyscf.gto.mole as mole
import scipy
from tierkreis.data.models import portmapping
from tierkreis.worker import Worker
from scipy.optimize import minimize

from tkr_fmo_puccd_worker_impl.puccd import (
    of2qiskit,
    pairUCC,
    puccd_finalize,
    puccd_initialize,
)

worker = Worker("fmo_puccd_worker")


class PairUCCData(NamedTuple):
    """The information required to construct a `pairUCC` object"""

    n_elec_pairs: int
    h1mo: list[float]
    h2mo: list[list[float]]
    enuc: float


class PairUCCState(NamedTuple):
    """The information that is mutated by `pairUCC` methods."""

    curr_e: float
    vqe_params: list[float]
    # TODO: we could serialize these as numpy arrays directly if needed
    gmo: list[list[float]]
    h1mo: list[float]
    h2mo: list[list[float]]

    evs: dict[str, float]
    stds: dict[str, float]

    @classmethod
    def from_puccd(cls, puccd: pairUCC) -> "PairUCCState":
        if isinstance(puccd.vqe_params, list):
            vqe_params = puccd.vqe_params
        else:
            vqe_params = puccd.vqe_params.tolist()

        return PairUCCState(
            curr_e=puccd.curr_e,
            vqe_params=vqe_params,
            gmo=puccd.gmo.tolist(),
            h1mo=puccd.h1mo.tolist(),
            h2mo=puccd.h2mo.tolist(),
            evs=puccd.evs,
            stds=puccd.stds,
        )


def rehydrate(data: PairUCCData, state: Optional[PairUCCState]) -> pairUCC:
    puccd = pairUCC(
        data.n_elec_pairs, np.array(data.h1mo), np.array(data.h2mo), data.enuc
    )

    if state is not None:
        puccd.curr_e = state.curr_e
        puccd.vqe_params = np.array(state.vqe_params)
        puccd.gmo = np.array(state.gmo)
        puccd.h1mo = np.array(state.h1mo)
        puccd.h2mo = np.array(state.h2mo)
        puccd.evs = state.evs
        puccd.stds = state.stds

    return puccd


@worker.task()
def pucc_from_pyscf_str(mol_str: str) -> PairUCCData:
    mol = mole.loads(mol_str)
    puccd = pairUCC.from_pyscf_Mole(mol)
    return PairUCCData(
        n_elec_pairs=puccd.n_elec_pairs,
        h1mo=puccd.h1mo.tolist(),
        h2mo=puccd.h2mo.tolist(),
        enuc=puccd.enuc,
    )


@worker.task()
def pucc_from_fcidump_filepath(filepath: str) -> PairUCCData:
    puccd = pairUCC.from_FCIDUMP(filepath)
    return PairUCCData(
        n_elec_pairs=puccd.n_elec_pairs,
        h1mo=puccd.h1mo.tolist(),
        h2mo=puccd.h2mo.tolist(),
        enuc=puccd.enuc,
    )


@worker.task()
def pauli_ham(data: PairUCCData) -> dict[str, float]:
    puccd = rehydrate(data, None)
    pauli_ham = of2qiskit(puccd.ham_qubit(), puccd.n_qubits)
    return {
        # Convert to native float for easier visualisation.
        pauli_str: float(expectation)
        for pauli_str, expectation in pauli_ham.items()
    }


@worker.task()
def initial_guess(data: PairUCCData) -> list[float]:
    puccd = rehydrate(data, None)
    guess = puccd.initial_guess_mp2d()
    # Convert to native float for easier visualisation.
    return [float(param) for param in guess.tolist()]


@portmapping
class ComputeEnergyOutput(NamedTuple):
    guess_energy: float
    state: PairUCCState


@worker.task()
def compute_energy_qk(
    data: PairUCCData,
    guess: list[float],
) -> ComputeEnergyOutput:
    puccd = rehydrate(data, None)

    puccd_initialize()
    qk_guess = puccd.compute_energy_qk(guess)
    puccd_finalize()
    return ComputeEnergyOutput(
        guess_energy=qk_guess, state=PairUCCState.from_puccd(puccd)
    )


@portmapping
class ExpectationValues(NamedTuple):
    guess_energy2: float
    guess_orb_grad: list[float]
    guess_orb_hess: list[list[float]]


@worker.task()
def expectation_values(
    data: PairUCCData,
    state: PairUCCState,
) -> ExpectationValues:
    puccd = rehydrate(data, state)

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
class MinimizeAmpsStepOutput(NamedTuple):
    next_params: list[float]
    state: PairUCCState
    x_history: list[float]
    converged: bool


@worker.task()
def minimize_amps_step(
    data: PairUCCData,
    state: PairUCCState,
    params: list[float],
    thresh: float,
    x_history: list[float],
    max_iter_per_step: int,
) -> MinimizeAmpsStepOutput:
    puccd = rehydrate(data, state)

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
    return MinimizeAmpsStepOutput(
        next_params=[float(param) for param in opt_result["x"]],
        # TODO: Unclear how stateful this actually is
        state=PairUCCState.from_puccd(puccd),
        x_history=x_history,
        converged=opt_result["success"],
    )


@worker.task()
def compute_energy(
    data: PairUCCData,
    params: list[float],
) -> float:
    puccd = rehydrate(data, None)
    return puccd.energy(params)


@worker.task()
def compute_orb_grad(
    data: PairUCCData,
    params: list[float],
) -> list[float]:
    puccd = rehydrate(data, None)
    return puccd.orb_grad(params).tolist()


@worker.task()
def minimize_orbs_converged(
    data: PairUCCData,
    state: PairUCCState,
    grad_norm_thresh: float,
) -> bool:
    puccd = rehydrate(data, state)

    curr_grad = puccd.orb_grad_qk()
    grad_norm = scipy.linalg.norm(curr_grad)
    return abs(grad_norm) < grad_norm_thresh


@portmapping
class MinimizeOrbsStepOutput(NamedTuple):
    state: PairUCCState


@worker.task()
def minimize_orbs_step(
    data: PairUCCData,
    state: PairUCCState,
    max_iter_per_step: int,
) -> MinimizeOrbsStepOutput:
    puccd = rehydrate(data, state)

    puccd_initialize()
    puccd.optimize_orbs_qk(True, maxiter=max_iter_per_step)
    puccd_finalize()

    return MinimizeOrbsStepOutput(
        state=PairUCCState.from_puccd(puccd),
    )
