"""Example 1: He RHF integrals, amplitude optimization, then orbital optimization."""

from typing import NamedTuple

from fmo_chemistry_worker import initialize_helium_from_pyscf
from tierkreis.builder import ExecutionContext, Graph
from tierkreis.models import Workflow

from tkr.graphs.shared import SettingsRef, StateRef, amplitudes, solve_state


class Inputs(NamedTuple):
    settings: SettingsRef


def workflow() -> Workflow[Inputs, StateRef]:
    graph = Graph(Inputs, StateRef)
    with ExecutionContext(name="chemistry"):
        initialized = graph.task(initialize_helium_from_pyscf(graph.inputs.settings))
    result = graph.eval(solve_state(amplitudes(), macro=False), initialized.state)
    return graph.finish_with_outputs(result)
