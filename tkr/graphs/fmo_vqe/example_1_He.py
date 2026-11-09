from typing import NamedTuple

from tierkreis.builder import Graph
from tierkreis.data.core import EmptyModel
from tierkreis.data.models import TKR

from fmo_pyscf_worker import fci_energy, build_He_atom


class Outputs(NamedTuple):
    exact_energy: TKR[float]


def example_1_He() -> Graph[EmptyModel, Outputs]:
    wf = Graph(EmptyModel, Outputs)
    mole_str = wf.task(build_He_atom())
    exact_energy = wf.task(fci_energy(mole_str))
    wf.finish_with_outputs(outputs=Outputs(exact_energy))
    return wf
