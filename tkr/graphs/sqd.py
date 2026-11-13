"""SQD with SBD diagonalization, driven by differential evolution over walkers.

Mirrors qcsc-prefect `riken_sqd_de`: each loop iteration proposes one LUCJ
parameter vector per walker, maps the walkers in parallel (sample → recover
configurations → SBD Davidson) and selects the next population.
"""

from typing import NamedTuple, TypeAlias

from sqd_control_worker import (
    finalize_sqd,
    finish_walker,
    initialize_de_state,
    load_sqd_problem,
    prepare_sbd_input,
    propose_walkers,
    sample_random_bitstrings,
    select_walkers,
    uses_random_samples,
)
from sqd_quantum_worker import sample_lucj
from sqd_sbd_worker import diagonalize
from tierkreis.builder import ExecutionContext, Graph
from tierkreis.models import TKR, OpaqueType, Workflow

SettingsRef: TypeAlias = TKR[OpaqueType["sqd_sbd.models.Settings"]]
ProblemRef: TypeAlias = TKR[OpaqueType["sqd_sbd.models.Problem"]]
StateRef: TypeAlias = TKR[OpaqueType["sqd_sbd.models.DEState"]]
TaskRef: TypeAlias = TKR[OpaqueType["sqd_sbd.models.WalkerTask"]]
WalkerResultRef: TypeAlias = TKR[OpaqueType["sqd_sbd.models.WalkerResult"]]
ResultRef: TypeAlias = TKR[OpaqueType["sqd_sbd.models.SQDResult"]]


class Inputs(NamedTuple):
    fcidump: TKR[str]
    settings: SettingsRef


class WalkerInputs(NamedTuple):
    task: TaskRef
    problem: ProblemRef
    fcidump: TKR[bytes]
    state: StateRef
    settings: SettingsRef


class IterationInputs(NamedTuple):
    state: StateRef
    problem: ProblemRef
    fcidump: TKR[bytes]
    settings: SettingsRef


class LoopOutput(NamedTuple):
    state: StateRef
    should_continue: TKR[bool]


def walker() -> Workflow[WalkerInputs, WalkerResultRef]:
    graph = Graph(WalkerInputs, WalkerResultRef)
    use_random = graph.task(
        uses_random_samples(graph.inputs.settings), context="control"
    )
    samples = graph.ifelse(
        use_random,
        graph.task(
            sample_random_bitstrings(
                graph.inputs.task, graph.inputs.problem, graph.inputs.settings
            ),
            context="control",
        ).samples,
        graph.task(
            sample_lucj(graph.inputs.task, graph.inputs.problem, graph.inputs.settings),
            context="sqd_quantum",
        ).samples,
    )
    job = graph.task(
        prepare_sbd_input(
            graph.inputs.task,
            samples,
            graph.inputs.state,
            graph.inputs.problem,
            graph.inputs.settings,
        ),
        context="control",
    )
    solved = graph.task(
        diagonalize(graph.inputs.fcidump, job.alpha_dets, job.solver_args),
        context="sbd",
    )
    result = graph.task(
        finish_walker(
            solved.energy, solved.carryover, job.record, graph.inputs.problem
        ),
        context="control",
    )
    return graph.finish_with_outputs(result.result)


def iteration() -> Workflow[IterationInputs, LoopOutput]:
    graph = Graph(IterationInputs, LoopOutput)
    with ExecutionContext(name="control"):
        proposal = graph.task(
            propose_walkers(
                graph.inputs.state, graph.inputs.problem, graph.inputs.settings
            )
        )
        walkers = graph.map(
            lambda task: WalkerInputs(
                task,
                graph.inputs.problem,
                graph.inputs.fcidump,
                graph.inputs.state,
                graph.inputs.settings,
            ),
            proposal.tasks,
        )
        results = graph.map(walker(), walkers)
        selected = graph.task(
            select_walkers(
                graph.inputs.state, proposal.tasks, results, graph.inputs.settings
            )
        )
    return graph.finish_with_outputs(
        LoopOutput(selected.state, selected.should_continue)
    )


def workflow() -> Workflow[Inputs, ResultRef]:
    graph = Graph(Inputs, ResultRef)
    with ExecutionContext(name="control"):
        problem = graph.task(load_sqd_problem(graph.inputs.fcidump))
        initial = graph.task(initialize_de_state(graph.inputs.settings))
        final = graph.loop(
            iteration(),
            IterationInputs(
                initial.state, problem.problem, problem.fcidump, graph.inputs.settings
            ),
            name="differential_evolution",
        )
        result = graph.task(finalize_sqd(final.state, problem.problem))
    return graph.finish_with_outputs(result.result)
