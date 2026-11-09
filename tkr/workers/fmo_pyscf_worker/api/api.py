"""Code generated from fmo_pyscf_worker namespace. Please do not edit."""

from typing import NamedTuple

from tierkreis.data.models import TKR


class build_He_atom(NamedTuple):
    @staticmethod
    def out() -> type[TKR[str]]:
        return TKR[str]

    @property
    def namespace(self) -> str:
        return "fmo_pyscf_worker"


class fci_energy(NamedTuple):
    mole_str: TKR[str]
    conv_tol_grad: TKR[float] | None = None
    max_cycle: TKR[int] | None = None

    @staticmethod
    def out() -> type[TKR[float]]:
        return TKR[float]

    @property
    def namespace(self) -> str:
        return "fmo_pyscf_worker"
