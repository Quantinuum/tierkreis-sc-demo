"""Code generated from example_worker namespace. Please do not edit."""

#ruff: noqa: F821
from typing import Literal, NamedTuple, Sequence, TypeVar, Generic, Protocol, Union
from types import NoneType
from tierkreis.controller.data.models import TKR, OpaqueType
from tierkreis.controller.data.types import PType, Struct, Workflow



class your_worker_task(NamedTuple):
    value: TKR[int]

    @staticmethod
    def out() -> type[TKR[int]]:
        return TKR[int]

    @property
    def namespace(self) -> str:
        return "example_worker" 
