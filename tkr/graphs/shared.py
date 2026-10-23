"""Reusable measurement, amplitude and orbital-optimization subgraphs."""

from typing import NamedTuple, TypeAlias

from fmo_chemistry_worker import (
    build_orbital_derivative_jobs,
    compute_orbital_derivative_block,
    evaluate_energy_from_measurements,
    initialize_fragment_from_integrals,
    initialize_orbital_optimization,
    update_orbitals_and_check_convergence,
)
from fmo_control_worker import (
    begin_macro_iteration,
    check_macro_convergence,
    initialize_amplitude_optimization,
    propose_amplitude_candidates,
    record_amplitude_evaluations,
)
from fmo_quantum_worker import (
    build_measurement_shard_jobs,
    execute_measurement_job,
    prepare_puccd_measurement_circuits,
)
from tierkreis.builder import ExecutionContext, Graph
from tierkreis.models import TKR, OpaqueType, Workflow

StateRef: TypeAlias = TKR[OpaqueType["fmo_vqe.models.State"]]
FragmentRef: TypeAlias = TKR[OpaqueType["fmo_vqe.models.Fragment"]]
MeasurementRef: TypeAlias = TKR[OpaqueType["fmo_vqe.models.Measurement"]]
MeasurementJobRef: TypeAlias = TKR[OpaqueType["fmo_vqe.models.MeasurementJob"]]
DerivativeRef: TypeAlias = TKR[OpaqueType["fmo_vqe.models.DerivativeBlock"]]
DerivativeJobRef: TypeAlias = TKR[OpaqueType["fmo_vqe.models.DerivativeJob"]]
ResultRef: TypeAlias = TKR[OpaqueType["fmo_vqe.models.FMOResult"]]
SettingsRef: TypeAlias = TKR[OpaqueType["fmo_vqe.models.Settings"]]


class StateInput(NamedTuple):
    state: StateRef


class StateOutput(NamedTuple):
    state: StateRef


class LoopOutput(NamedTuple):
    state: StateRef
    should_continue: TKR[bool]


def measurement() -> Workflow[MeasurementJobRef, MeasurementRef]:
    graph = Graph(MeasurementJobRef, MeasurementRef)
    with ExecutionContext(name="quantum"):
        result = graph.task(execute_measurement_job(graph.inputs))
    return graph.finish_with_outputs(result.value)


def objective() -> Workflow[StateInput, StateOutput]:
    graph = Graph(StateInput, StateOutput)
    with ExecutionContext(name="control"):
        jobs = graph.task(build_measurement_shard_jobs(graph.inputs.state))
    with ExecutionContext(name="quantum"):
        results = graph.map(measurement(), jobs.jobs)
    with ExecutionContext(name="chemistry"):
        evaluated = graph.task(
            evaluate_energy_from_measurements(graph.inputs.state, results)
        )
    return graph.finish_with_outputs(StateOutput(evaluated.state))


def objective_item() -> Workflow[StateRef, StateRef]:
    graph = Graph(StateRef, StateRef)
    result = graph.eval(objective(), StateInput(graph.inputs))
    return graph.finish_with_outputs(result.state)


def amplitude_iteration() -> Workflow[StateInput, LoopOutput]:
    graph = Graph(StateInput, LoopOutput)
    with ExecutionContext(name="control"):
        proposal = graph.task(propose_amplitude_candidates(graph.inputs.state))
        results = graph.map(objective_item(), proposal.candidates)
        updated = graph.task(record_amplitude_evaluations(proposal.state, results))
    return graph.finish_with_outputs(LoopOutput(updated.state, updated.should_continue))


def amplitudes() -> Workflow[StateInput, StateOutput]:
    graph = Graph(StateInput, StateOutput)
    with ExecutionContext(name="control"):
        initial = graph.task(initialize_amplitude_optimization(graph.inputs.state))
        result = graph.loop(
            amplitude_iteration(),
            StateInput(initial.state),
            name="amplitudes",
        )
    return graph.finish_with_outputs(StateOutput(result.state))


def derivative_item() -> Workflow[DerivativeJobRef, DerivativeRef]:
    graph = Graph(DerivativeJobRef, DerivativeRef)
    with ExecutionContext(name="chemistry"):
        block = graph.task(compute_orbital_derivative_block(graph.inputs))
    return graph.finish_with_outputs(block.value)


def orbital_iteration() -> Workflow[StateInput, LoopOutput]:
    graph = Graph(StateInput, LoopOutput)
    with ExecutionContext(name="chemistry"):
        jobs = graph.task(build_orbital_derivative_jobs(graph.inputs.state))
        blocks = graph.map(derivative_item(), jobs.jobs)
        updated = graph.task(
            update_orbitals_and_check_convergence(graph.inputs.state, blocks)
        )
    return graph.finish_with_outputs(LoopOutput(updated.state, updated.should_continue))


def orbitals() -> Workflow[StateInput, StateOutput]:
    graph = Graph(StateInput, StateOutput)
    with ExecutionContext(name="chemistry"):
        initial = graph.task(initialize_orbital_optimization(graph.inputs.state))
        result = graph.loop(
            orbital_iteration(),
            StateInput(initial.state),
            name="orbital_rotations",
        )
    return graph.finish_with_outputs(StateOutput(result.state))


def macro_iteration(
    amplitude_solver: Workflow[StateInput, StateOutput],
) -> Workflow[StateInput, LoopOutput]:
    graph = Graph(StateInput, LoopOutput)
    with ExecutionContext(name="control"):
        started = graph.task(begin_macro_iteration(graph.inputs.state))
        optimized = graph.eval(amplitude_solver, StateInput(started.state))
        rotated = graph.eval(orbitals(), StateInput(optimized.state))
        result = graph.task(check_macro_convergence(rotated.state))
    return graph.finish_with_outputs(LoopOutput(result.state, result.should_continue))


def solve_state(
    amplitude_solver: Workflow[StateInput, StateOutput],
    *,
    macro: bool = True,
) -> Workflow[StateRef, StateRef]:
    graph = Graph(StateRef, StateRef)
    with ExecutionContext(name="control"):
        prepared = graph.task(prepare_puccd_measurement_circuits(graph.inputs))
        evaluated = graph.eval(objective(), StateInput(prepared.state))
        if macro:
            result = graph.loop(
                macro_iteration(amplitude_solver),
                StateInput(evaluated.state),
                name="oo_puccd",
            )
        else:
            optimized = graph.eval(amplitude_solver, StateInput(evaluated.state))
            result = graph.eval(orbitals(), StateInput(optimized.state))
    return graph.finish_with_outputs(result.state)


def fragment(
    amplitude_solver: Workflow[StateInput, StateOutput],
) -> Workflow[FragmentRef, StateRef]:
    graph = Graph(FragmentRef, StateRef)
    with ExecutionContext(name="chemistry"):
        initialized = graph.task(initialize_fragment_from_integrals(graph.inputs))
    result = graph.eval(solve_state(amplitude_solver), initialized.state)
    return graph.finish_with_outputs(result)
