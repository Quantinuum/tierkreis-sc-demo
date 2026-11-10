from typing import NamedTuple

from tierkreis.builder import Graph
from tierkreis.data.core import EmptyModel
from tierkreis.data.models import TKR
from tierkreis.builtins import iadd, tkr_or, igt, tkr_not

from fmo_pyscf_worker import fci_energy, build_He_atom
from fmo_puccd_worker import (
    initial_guess_from_pyscf_mol,
    pauli_ham_from_pyscf_mol,
    compute_energy_qk_from_pyscf_mol,
    expectation_values_from_pyscf_mol,
    minimize_step,
)
from tierkreis.data.types import Workflow


class OptimizeAmpsInputs(NamedTuple):
    mol_str: TKR[str]
    params: TKR[list[float]]
    x_history: TKR[list[float]]

    current_iteration: TKR[int]
    maxiter_per_step: TKR[int]
    thresh: TKR[float]
    max_steps: TKR[int]


class OptimizeAmpsOutputs(NamedTuple):
    params: TKR[list[float]]
    x_history: TKR[list[float]]

    current_iteration: TKR[int]
    should_continue: TKR[bool]


def optimize_amps() -> Workflow[OptimizeAmpsInputs, OptimizeAmpsOutputs]:
    wf = Graph(OptimizeAmpsInputs, OptimizeAmpsOutputs)

    step_output = wf.task(
        minimize_step(
            wf.inputs.mol_str,
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
    not_converged = wf.task(tkr_not(step_output.converged))
    should_continue = wf.task(tkr_or(not_converged, max_steps_exceeded))

    return wf.finish_with_outputs(
        OptimizeAmpsOutputs(
            params=step_output.next_params,
            x_history=step_output.x_history,
            current_iteration=next_iteration,
            should_continue=should_continue,
        )
    )


class Outputs(NamedTuple):
    exact_energy: TKR[float]
    pauli_ham: TKR[dict[str, float]]
    initial_guess: TKR[list[float]]
    # First guess with qiskit
    guess_energy1: TKR[float]
    # Expectation Values
    guess_energy2: TKR[float]
    guess_orb_grad: TKR[list[float]]
    guess_orb_hess: TKR[list[list[float]]]

    vqe_params: TKR[list[float]]


def example_1_He() -> Workflow[EmptyModel, Outputs]:
    wf = Graph(EmptyModel, Outputs)

    # Step 1. Build He atom
    mol_str = wf.task(build_He_atom())

    # Step 2. Optional FCI energy
    exact_energy = wf.task(fci_energy(mol_str))

    # Step 3. Initialize a pairUCC object (hard to replicate)

    # Step 4. Get the system Hamiltonian.
    pauli_ham = wf.task(pauli_ham_from_pyscf_mol(mol_str))

    # Step 5. Print the ansatz circuit
    # Not yet implemented

    # Step 6. Prepare an initial guess for the VQE
    initial_guess = wf.task(initial_guess_from_pyscf_mol(mol_str))

    # Step 7. Measure expectation value using qiskit
    compute_energy_output = wf.task(
        compute_energy_qk_from_pyscf_mol(mol_str, initial_guess)
    )

    # Step 8. Compute expectation values
    expectation_values = wf.task(
        expectation_values_from_pyscf_mol(
            mol_str, compute_energy_output.evs, compute_energy_output.stds
        )
    )

    vqe_amps = wf.loop(
        optimize_amps(),
        OptimizeAmpsInputs(
            mol_str,
            initial_guess,
            x_history=wf.const([]),
            current_iteration=wf.const(0),
            maxiter_per_step=wf.const(10),
            thresh=wf.const(1e-4),
            max_steps=wf.const(1000),
        ),
    )

    return wf.finish_with_outputs(
        outputs=Outputs(
            exact_energy,
            pauli_ham,
            initial_guess,
            guess_energy1=compute_energy_output.guess_energy,
            guess_energy2=expectation_values.guess_energy2,
            guess_orb_grad=expectation_values.guess_orb_grad,
            guess_orb_hess=expectation_values.guess_orb_hess,
            vqe_params=vqe_amps.params,
        )
    )
