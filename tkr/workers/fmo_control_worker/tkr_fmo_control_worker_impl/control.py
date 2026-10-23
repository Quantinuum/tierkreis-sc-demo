import hashlib

import numpy as np
from numpy.typing import NDArray
from tkr_fmo_control_worker_impl.optimizers import Evaluation, propose_cobyla

from fmo_vqe.models import AmplitudeProposal, FMOResult, LoopPort, State


def begin_amplitudes(state: State) -> State:
    return state.model_copy(
        update={
            "initial": state.parameters.copy(),
            "history": [],
            "amplitude_iteration": 0,
            "amplitude_done": False,
            "amplitude_success": False,
        }
    )


def propose(state: State, optimizer: str) -> AmplitudeProposal:
    options = state.fragment.settings
    if optimizer == "cobyla":
        proposal = propose_cobyla(
            state.initial,
            state.history,
            options.amplitude_tolerance,
            options.amplitude_budget,
        )
        candidate = state.model_copy(
            update={
                "parameters": proposal.parameters,
                "amplitude_done": proposal.done,
                "amplitude_success": proposal.success,
            }
        )
        if proposal.done and not proposal.success:
            candidate.diagnostics = state.diagnostics + [proposal.message]
        return AmplitudeProposal(state, [candidate])
    if optimizer != "spsa":
        raise ValueError(f"Unknown optimizer {optimizer}")
    budget = min(options.spsa_steps, options.amplitude_budget // 2)
    if (
        not state.parameters
        or state.amplitude_iteration >= budget
        or state.amplitude_done
    ):
        candidate = state.model_copy(
            update={
                "amplitude_done": True,
                "amplitude_success": not state.parameters or state.amplitude_success,
            }
        )
        if not candidate.amplitude_success:
            candidate.diagnostics = state.diagnostics + [
                "SPSA evaluation budget exhausted"
            ]
        return AmplitudeProposal(state, [candidate])
    radius = options.spsa_perturbation / (state.amplitude_iteration + 1) ** 0.101
    direction = spsa_direction(state)
    center = np.asarray(state.parameters)
    candidates = [
        state.model_copy(
            update={"parameters": (center + sign * radius * direction).tolist()}
        )
        for sign in (1, -1)
    ]
    return AmplitudeProposal(state, candidates)


def spsa_direction(state: State) -> NDArray[np.float64]:
    identity = f"{state.fragment.settings.seed}:{state.fragment.identifier}:{state.macro_iteration}:{state.amplitude_iteration}"
    seed = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], "little")
    return np.random.default_rng(seed).choice([-1.0, 1.0], size=len(state.parameters))


def record(state: State, results: list[State], optimizer: str) -> LoopPort:
    if len(results) == 1 and results[0].amplitude_done:
        return LoopPort(results[0], False)
    if optimizer == "cobyla":
        if len(results) != 1:
            raise ValueError("COBYLA requires one sequential objective")
        evaluated = results[0]
        updated = state.model_copy(
            update={
                "history": state.history
                + [Evaluation(evaluated.parameters, evaluated.energy)],
                "amplitude_iteration": state.amplitude_iteration + 1,
            }
        )
        return LoopPort(updated, True)
    if len(results) != 2:
        raise ValueError("SPSA requires two perturbation objectives")
    options = state.fragment.settings
    radius = options.spsa_perturbation / (state.amplitude_iteration + 1) ** 0.101
    gradient = (
        (results[0].energy - results[1].energy) / (2 * radius) * spsa_direction(state)
    )
    rate = options.spsa_rate / (state.amplitude_iteration + 1) ** 0.602
    parameters = np.clip(np.asarray(state.parameters) - rate * gradient, -np.pi, np.pi)
    success = float(np.linalg.norm(gradient)) < options.amplitude_tolerance
    updated = state.model_copy(
        update={
            "parameters": parameters.tolist(),
            "amplitude_iteration": state.amplitude_iteration + 1,
            "amplitude_done": success,
            "amplitude_success": success,
        }
    )
    return LoopPort(updated, True)


def aggregate(states: list[State]) -> FMOResult:
    monomers = {
        state.fragment.identifier: state.energy
        for state in states
        if len(state.fragment.monomers) == 1
    }
    total = sum(monomers.values())
    for state in states:
        endpoints = state.fragment.monomers
        if len(endpoints) == 1:
            continue
        total += state.energy - sum(monomers[endpoint] for endpoint in endpoints)
    return FMOResult(
        energy=total,
        fragment_energies={state.fragment.identifier: state.energy for state in states},
        fragment_converged={
            state.fragment.identifier: state.converged for state in states
        },
        converged=all(state.converged for state in states),
        diagnostics={state.fragment.identifier: state.diagnostics for state in states},
        fragment_iterations={
            state.fragment.identifier: {
                "macro": state.macro_iteration,
                "last_amplitude": state.amplitude_iteration,
                "last_orbital": state.orbital_iteration,
            }
            for state in states
        },
    )
