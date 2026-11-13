"""Code generated from sqd_quantum_worker namespace. Please do not edit."""

# ruff: noqa: F821
from typing import NamedTuple

from tierkreis.data.models import TKR, OpaqueType


class SamplesPort(NamedTuple):
    samples: TKR[OpaqueType["sqd_sbd.models.Samples"]]


class sample_lucj(NamedTuple):
    task: TKR[OpaqueType["sqd_sbd.models.WalkerTask"]]
    problem: TKR[OpaqueType["sqd_sbd.models.Problem"]]
    settings: TKR[OpaqueType["sqd_sbd.models.Settings"]]

    @staticmethod
    def out() -> type[SamplesPort]:
        return SamplesPort

    @property
    def namespace(self) -> str:
        return "sqd_quantum_worker"
