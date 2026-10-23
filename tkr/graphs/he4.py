"""Example 3: map independent He4 monomer/dimer solves and reduce their FMO2 energy."""

from typing import NamedTuple

from fmo_control_worker import (
    aggregate_fmo2_energy,
    load_fmo_fragments_from_manifest,
)
from tierkreis.builder import ExecutionContext, Graph
from tierkreis.models import TKR, Workflow

from tkr.graphs.shared import ResultRef, SettingsRef, amplitudes, fragment


class Inputs(NamedTuple):
    manifest: TKR[str]
    settings: SettingsRef


def workflow() -> Workflow[Inputs, ResultRef]:
    graph = Graph(Inputs, ResultRef)
    with ExecutionContext(name="control"):
        fragments = graph.task(
            load_fmo_fragments_from_manifest(
                graph.inputs.manifest, graph.inputs.settings
            )
        )
        states = graph.map(fragment(amplitudes()), fragments)
        result = graph.task(aggregate_fmo2_energy(states))
    return graph.finish_with_outputs(result.result)
