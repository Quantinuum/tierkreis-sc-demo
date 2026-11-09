from pathlib import Path

from tierkreis.worker import Worker

from sqd_sbd.models import (
    DEState,
    IterationSummary,
    LoopPort,
    Problem,
    ProblemPort,
    ProposalPort,
    ResultPort,
    Samples,
    SamplesPort,
    SBDJobPort,
    Settings,
    SQDResult,
    StatePort,
    WalkerRecord,
    WalkerResult,
    WalkerResultPort,
    WalkerTask,
)
from tkr_sqd_control_worker_impl import sqd

worker = Worker("sqd_control_worker")


@worker.task()
def load_sqd_problem(fcidump: str) -> ProblemPort:
    problem, sbd_fcidump = sqd.load_problem(Path(fcidump).read_text())
    return ProblemPort(problem, sbd_fcidump)


@worker.task()
def initialize_de_state(settings: Settings) -> StatePort:
    return StatePort(DEState(energies=[0.0] * settings.num_walkers))


@worker.task()
def propose_walkers(
    state: DEState, problem: Problem, settings: Settings
) -> ProposalPort:
    return ProposalPort(sqd.propose(state, problem, settings))


@worker.task()
def uses_random_samples(settings: Settings) -> bool:
    return settings.quantum_source == "random"


@worker.task()
def sample_random_bitstrings(
    task: WalkerTask, problem: Problem, settings: Settings
) -> SamplesPort:
    return SamplesPort(sqd.random_samples(task, problem, settings))


@worker.task()
def prepare_sbd_input(
    task: WalkerTask,
    samples: Samples,
    state: DEState,
    problem: Problem,
    settings: Settings,
) -> SBDJobPort:
    return SBDJobPort(
        *sqd.prepare_sbd_input(task, samples, state.carryover, problem, settings)
    )


@worker.task()
def finish_walker(
    energy: float, carryover: bytes, record: WalkerRecord, problem: Problem
) -> WalkerResultPort:
    return WalkerResultPort(sqd.finish_walker(energy, carryover, record, problem))


@worker.task()
def select_walkers(
    state: DEState,
    tasks: list[WalkerTask],
    results: list[WalkerResult],
    settings: Settings,
) -> LoopPort:
    new = sqd.select(state, tasks, results)
    return LoopPort(new, new.iteration < settings.iterations)


@worker.task()
def finalize_sqd(state: DEState, problem: Problem) -> ResultPort:
    energy = state.best_energy()
    if energy is None or state.best_index is None:
        raise ValueError("SQD finished without evaluating any walker")
    return ResultPort(
        SQDResult(
            energy=energy,
            best_walker=state.best_index,
            hf_energy=problem.hf_energy,
            ccsd_energy=problem.ccsd_energy,
            history=[
                IterationSummary(iteration=iteration, best_energy=best)
                for iteration, best in enumerate(state.best_energies)
            ],
            records=state.records,
        )
    )
