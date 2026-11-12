from typing import NamedTuple

from tierkreis.builder import Graph
from tierkreis.data.core import EmptyModel
from tierkreis.data.models import TKR
from tierkreis.builtins import iadd, tkr_or, igt, tkr_not

from fmo_pyscf_worker import fci_energy, build_He_atom
from fmo_puccd_worker import (
    PairUCCData,
    PairUCCState,
    initial_guess,
    pucc_from_pyscf_str,
    compute_energy_qk,
    expectation_values,
    minimize_amps_step,
    minimize_orbs_step,
    minimize_orbs_converged,
    compute_energy,
)
from tierkreis.data.types import Workflow


class OptimizeAmpsInputs(NamedTuple):
    data: TKR[PairUCCData]
    state: TKR[PairUCCState]
    params: TKR[list[float]]
    x_history: TKR[list[float]]

    current_iteration: TKR[int]
    maxiter_per_step: TKR[int]
    thresh: TKR[float]
    max_steps: TKR[int]


class OptimizeAmpsOutputs(NamedTuple):
    state: TKR[PairUCCState]
    params: TKR[list[float]]
    x_history: TKR[list[float]]

    current_iteration: TKR[int]
    should_continue: TKR[bool]


def optimize_amps() -> Workflow[OptimizeAmpsInputs, OptimizeAmpsOutputs]:
    wf = Graph(OptimizeAmpsInputs, OptimizeAmpsOutputs)

    step_output = wf.task(
        minimize_amps_step(
            wf.inputs.data,
            wf.inputs.state,
            wf.inputs.params,
            wf.inputs.thresh,
            wf.inputs.x_history,
            wf.inputs.maxiter_per_step,
        )
    )
    next_iteration = wf.task(
        iadd(wf.inputs.current_iteration, wf.inputs.maxiter_per_step)
    )
    max_steps_exceeded = wf.task(igt(next_iteration, wf.inputs.max_steps))
    finished = wf.task(tkr_or(step_output.converged, max_steps_exceeded))
    should_continue = wf.task(tkr_not(finished))

    return wf.finish_with_outputs(
        OptimizeAmpsOutputs(
            state=step_output.state,
            params=step_output.next_params,
            x_history=step_output.x_history,
            current_iteration=next_iteration,
            should_continue=should_continue,
        )
    )


class OptimizeOrbsInputs(NamedTuple):
    data: TKR[PairUCCData]
    state: TKR[PairUCCState]

    current_iteration: TKR[int]
    maxiter_per_step: TKR[int]
    thresh: TKR[float]
    max_steps: TKR[int]


class OptimizeOrbsOutputs(NamedTuple):
    state: TKR[PairUCCState]

    current_iteration: TKR[int]
    should_continue: TKR[bool]


def optimize_orbs() -> Workflow[OptimizeOrbsInputs, OptimizeOrbsOutputs]:
    wf = Graph(OptimizeOrbsInputs, OptimizeOrbsOutputs)

    step_output = wf.task(
        minimize_orbs_step(
            wf.inputs.data,
            wf.inputs.state,
            wf.inputs.maxiter_per_step,
        )
    )
    next_iteration = wf.task(
        iadd(wf.inputs.current_iteration, wf.inputs.maxiter_per_step)
    )
    max_steps_exceeded = wf.task(igt(next_iteration, wf.inputs.max_steps))
    converged = wf.task(
        minimize_orbs_converged(wf.inputs.data, step_output.state, wf.inputs.thresh)
    )
    finished = wf.task(tkr_or(converged, max_steps_exceeded))
    should_continue = wf.task(tkr_not(finished))

    return wf.finish_with_outputs(
        OptimizeOrbsOutputs(
            state=step_output.state,
            current_iteration=next_iteration,
            should_continue=should_continue,
        )
    )


class Inputs(NamedTuple):
    data: TKR[PairUCCData]


class Outputs(NamedTuple):
    initial_guess: TKR[list[float]]
    # First guess with qiskit
    guess_energy1: TKR[float]
    # Expectation Values
    guess_energy2: TKR[float]
    guess_orb_grad: TKR[list[float]]
    guess_orb_hess: TKR[list[list[float]]]

    vqe_params: TKR[list[float]]
    vqe_energy: TKR[float]
    oo_vqe_energy: TKR[float]


def fmo_vqe() -> Workflow[Inputs, Outputs]:
    wf = Graph(Inputs, Outputs)
    zero = wf.const(0)
    max_iter_per_step = wf.const(200)
    max_steps = wf.const(1000)

    # Step 6. Prepare an initial guess for the VQE
    guess = wf.task(initial_guess(wf.inputs.data))

    # Step 7. Measure expectation value using qiskit
    compute_energy_output = wf.task(compute_energy_qk(wf.inputs.data, guess))

    # Step 8. Compute expectation values
    ev = wf.task(
        expectation_values(
            wf.inputs.data,
            compute_energy_output.state,
        )
    )

    vqe_amps = wf.loop(
        optimize_amps(),
        OptimizeAmpsInputs(
            wf.inputs.data,
            compute_energy_output.state,
            guess,
            x_history=wf.const([]),
            current_iteration=zero,
            maxiter_per_step=max_iter_per_step,
            thresh=wf.const(1e-4),
            max_steps=max_steps,
        ),
    )

    vqe_energy = wf.task(compute_energy(wf.inputs.data, vqe_amps.params))

    vqe_orbs = wf.loop(
        optimize_orbs(),
        OptimizeOrbsInputs(
            wf.inputs.data,
            vqe_amps.state,
            current_iteration=zero,
            maxiter_per_step=max_iter_per_step,
            thresh=wf.const(1e-10),
            max_steps=max_steps,
        ),
    )

    oo_expectation_values = wf.task(
        expectation_values(
            wf.inputs.data,
            vqe_orbs.state,
        )
    )

    return wf.finish_with_outputs(
        outputs=Outputs(
            guess,
            guess_energy1=compute_energy_output.guess_energy,
            guess_energy2=ev.guess_energy2,
            guess_orb_grad=ev.guess_orb_grad,
            guess_orb_hess=ev.guess_orb_hess,
            vqe_params=vqe_amps.params,
            vqe_energy=vqe_energy,
            oo_vqe_energy=oo_expectation_values.guess_energy2,
        )
    )
