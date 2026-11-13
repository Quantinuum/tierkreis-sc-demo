"""Code generated from sqd_sbd_worker namespace. Please do not edit."""

from typing import NamedTuple

from tierkreis.data.models import TKR


class SBDOutput(NamedTuple):
    carryover: TKR[bytes]
    energy: TKR[float]
    occ_a: TKR[bytes]
    occ_b: TKR[bytes]


class diagonalize(NamedTuple):
    fcidump: TKR[bytes]
    alpha_dets: TKR[bytes]
    solver_args: TKR[list[str]]

    @staticmethod
    def out() -> type[SBDOutput]:
        return SBDOutput

    @property
    def namespace(self) -> str:
        return "sqd_sbd_worker"
