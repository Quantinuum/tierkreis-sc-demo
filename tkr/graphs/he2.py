"""Example 2: load a He2 FCIDUMP and alternate amplitude/orbital optimization."""

from typing import NamedTuple

from fmo_chemistry_worker import initialize_dimer_from_fcidump_file
from tierkreis.builder import ExecutionContext, Graph
from tierkreis.models import TKR, Workflow

from tkr.graphs.shared import SettingsRef, StateRef, amplitudes, solve_state


class Inputs(NamedTuple):
    fcidump: TKR[str]
    settings: SettingsRef


def workflow() -> Workflow[Inputs, StateRef]:
    graph = Graph(Inputs, StateRef)
    with ExecutionContext(name="chemistry"):
        initialized = graph.task(
            initialize_dimer_from_fcidump_file(
                graph.inputs.fcidump, graph.inputs.settings
            )
        )
    result = graph.eval(solve_state(amplitudes()), initialized.state)
    return graph.finish_with_outputs(result)
