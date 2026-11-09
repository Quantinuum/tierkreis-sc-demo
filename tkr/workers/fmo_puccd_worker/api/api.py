"""Code generated from fmo_puccd_worker namespace. Please do not edit."""

from typing import NamedTuple

from tierkreis.data.models import TKR


class your_worker_task(NamedTuple):
    value: TKR[int]

    @staticmethod
    def out() -> type[TKR[int]]:
        return TKR[int]

    @property
    def namespace(self) -> str:
        return "fmo_puccd_worker"
