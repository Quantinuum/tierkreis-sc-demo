from typing import NamedTuple

from tierkreis.builder import Graph
from tierkreis.data.core import EmptyModel
from tierkreis.data.models import TKR

from fmo_pyscf_worker import fci_energy, build_He_atom
from fmo_puccd_worker import (
    pucc_from_fcidump_filepath,
    pucc_from_pyscf_str,
)
from tierkreis.data.types import Workflow

from fmo_vqe.vqe_graph import Inputs, fmo_vqe


class Example1Outputs(NamedTuple):
    exact_energy: TKR[float]
    vqe_energy: TKR[float]
    oo_vqe_energy: TKR[float]


def example_1() -> Workflow[EmptyModel, Example1Outputs]:
    wf = Graph(EmptyModel, Example1Outputs)

    mol_str = wf.task(build_He_atom())
    exact_energy = wf.task(fci_energy(mol_str))
    data = wf.task(pucc_from_pyscf_str(mol_str))

    vqe_out = wf.eval(fmo_vqe(), Inputs(data))

    return wf.finish_with_outputs(
        outputs=Example1Outputs(
            exact_energy=exact_energy,
            vqe_energy=vqe_out.vqe_energy,
            oo_vqe_energy=vqe_out.oo_vqe_energy,
        )
    )


class FCIDumpInputs(NamedTuple):
    filepath: TKR[str]


class Example2Outputs(NamedTuple):
    vqe_energy: TKR[float]
    oo_vqe_energy: TKR[float]


def example_2() -> Workflow[FCIDumpInputs, Example2Outputs]:
    wf = Graph(FCIDumpInputs, Example2Outputs)

    data = wf.task(pucc_from_fcidump_filepath(wf.inputs.filepath))

    vqe_out = wf.eval(fmo_vqe(), Inputs(data))

    return wf.finish_with_outputs(
        outputs=Example2Outputs(
            vqe_energy=vqe_out.vqe_energy,
            oo_vqe_energy=vqe_out.oo_vqe_energy,
        )
    )
