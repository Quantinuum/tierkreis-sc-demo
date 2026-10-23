from pathlib import Path

import numpy as np
from tierkreis import Worker

from fmo_vqe.models import (
    DerivativeBlock,
    DerivativeJob,
    DerivativeJobsPort,
    DerivativePort,
    Fragment,
    LoopPort,
    Measurement,
    Settings,
    State,
    StatePort,
)
from tkr_fmo_chemistry_worker_impl import chemistry

worker = Worker("fmo_chemistry_worker")


def merge(measurements: list[Measurement]) -> dict[str, float]:
    moments: dict[str, float] = {}
    for basis in ("X", "Y", "Z"):
        group = [item for item in measurements if item.basis == basis]
        if not group:
            raise ValueError(f"Missing {basis} measurements")
        if any(set(item.moments) != set(group[0].moments) for item in group):
            raise ValueError(f"Inconsistent {basis} measurement shards")
        if any(item.shots == 0 for item in group) and any(
            item.shots > 0 for item in group
        ):
            raise ValueError("Cannot mix sampled and exact measurement shards")
        weights = [item.shots or 1 for item in group]
        for word in group[0].moments:
            moments[word] = sum(
                weight * item.moments[word]
                for weight, item in zip(weights, group, strict=True)
            ) / sum(weights)
    return moments


@worker.task()
def initialize_helium_from_pyscf(settings: Settings) -> StatePort:
    return StatePort(chemistry.helium(settings))


@worker.task()
def initialize_fragment_from_integrals(fragment: Fragment) -> StatePort:
    return StatePort(chemistry.initialize(fragment))


@worker.task()
def initialize_dimer_from_fcidump_file(fcidump: str, settings: Settings) -> StatePort:
    return initialize_fragment_from_integrals(
        Fragment(
            identifier="He2",
            monomers=["He2"],
            fcidump=Path(fcidump).read_text(),
            settings=settings,
        )
    )


@worker.task()
def evaluate_energy_from_measurements(
    state: State, measurements: list[Measurement]
) -> StatePort:
    state = state.model_copy(update={"moments": merge(measurements)})
    state.energy = chemistry.energy(state)
    return StatePort(state)


@worker.task()
def initialize_orbital_optimization(state: State) -> StatePort:
    return StatePort(
        state.model_copy(update={"orbital_iteration": 0, "orbital_success": False})
    )


@worker.task()
def build_orbital_derivative_jobs(state: State) -> DerivativeJobsPort:
    size = len(state.h1) * (len(state.h1) - 1) // 2
    block_size = state.fragment.settings.derivative_block_size
    jobs = [
        DerivativeJob(
            state=state, rows=list(range(start, min(start + block_size, size)))
        )
        for start in range(0, size, block_size)
    ]
    return DerivativeJobsPort(jobs)


@worker.task()
def compute_orbital_derivative_block(job: DerivativeJob) -> DerivativePort:
    return DerivativePort(chemistry.derivative_block(job))


@worker.task()
def update_orbitals_and_check_convergence(
    state: State, blocks: list[DerivativeBlock]
) -> LoopPort:
    size = len(state.h1) * (len(state.h1) - 1) // 2
    gradient = np.zeros(size)
    hessian = np.zeros((size, size))
    for block in blocks:
        for row, value in block.gradient.items():
            gradient[int(row)] = value
        for row, column, value in block.hessian:
            hessian[row, column] = hessian[column, row] = value
    options = state.fragment.settings
    if float(np.linalg.norm(gradient)) < options.orbital_tolerance:
        return LoopPort(state.model_copy(update={"orbital_success": True}), False)
    if state.orbital_iteration >= options.orbital_budget:
        state.diagnostics = state.diagnostics + ["Orbital iteration budget exhausted"]
        return LoopPort(state, False)
    try:
        if np.linalg.cond(hessian) > 1e12:
            raise np.linalg.LinAlgError("Ill-conditioned orbital Hessian")
        step = np.linalg.solve(hessian, -gradient)
    except np.linalg.LinAlgError:
        step = -options.fallback_rate * gradient
        state.diagnostics = state.diagnostics + ["Orbital gradient-descent fallback"]
    state = chemistry.rotate(state, step)
    state.orbital_iteration += 1
    return LoopPort(state, True)
