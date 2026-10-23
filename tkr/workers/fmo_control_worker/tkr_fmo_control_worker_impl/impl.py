import json
from pathlib import Path

from tierkreis import Worker
from tkr_fmo_control_worker_impl import control

from fmo_vqe.models import (
    AmplitudeProposal,
    Fragment,
    LoopPort,
    ResultPort,
    Settings,
    State,
    StatePort,
)

worker = Worker("fmo_control_worker")


@worker.task()
def load_fmo_fragments_from_manifest(
    manifest: str, settings: Settings
) -> list[Fragment]:
    contents = json.loads(Path(manifest).read_text())
    directory = Path(contents["directory"])
    return [
        Fragment(
            identifier=item["identifier"],
            monomers=item["monomers"],
            fcidump=(directory / item["file"]).read_text(),
            settings=settings,
        )
        for item in contents["fragments"]
    ]


@worker.task()
def initialize_amplitude_optimization(state: State) -> StatePort:
    return StatePort(control.begin_amplitudes(state))


@worker.task()
def propose_amplitude_candidates(state: State) -> AmplitudeProposal:
    return control.propose(state, state.fragment.settings.optimizer)


@worker.task()
def record_amplitude_evaluations(state: State, results: list[State]) -> LoopPort:
    return control.record(state, results, state.fragment.settings.optimizer)


@worker.task()
def begin_macro_iteration(state: State) -> StatePort:
    return StatePort(
        state.model_copy(
            update={
                "previous_energy": state.energy,
                "macro_iteration": state.macro_iteration + 1,
            }
        )
    )


@worker.task()
def check_macro_convergence(state: State) -> LoopPort:
    converged = (
        abs(state.energy - state.previous_energy)
        < state.fragment.settings.macro_tolerance
        and state.orbital_success
        and state.amplitude_success
    )
    done = converged or state.macro_iteration >= state.fragment.settings.macro_budget
    diagnostics = state.diagnostics.copy()
    if done and not converged:
        diagnostics.append("Macro iteration budget exhausted")
    return LoopPort(
        state.model_copy(update={"converged": converged, "diagnostics": diagnostics}),
        not done,
    )


@worker.task()
def aggregate_fmo2_energy(states: list[State]) -> ResultPort:
    return ResultPort(control.aggregate(states))
