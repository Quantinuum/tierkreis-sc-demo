from dataclasses import dataclass
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, model_validator
from tierkreis.controller.data.models import portmapping


@dataclass
class Evaluation:
    parameters: list[float]
    energy: float


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    optimizer: Literal["cobyla", "spsa"] = "cobyla"
    amplitude_tolerance: float = Field(default=1e-5, gt=0)
    amplitude_budget: int = Field(default=1000, ge=1)
    orbital_tolerance: float = Field(default=1e-10, gt=0)
    orbital_budget: int = Field(default=1000, ge=1)
    macro_tolerance: float = Field(default=1e-7, gt=0)
    macro_budget: int = Field(default=20, ge=1)
    fallback_rate: float = Field(default=0.01, gt=0)
    shots: int = Field(default=0, ge=0)
    shards: int = Field(default=1, ge=1)
    seed: int = Field(default=10, ge=0)
    spsa_steps: int = Field(default=100, ge=1)
    spsa_rate: float = Field(default=0.1, gt=0)
    spsa_perturbation: float = Field(default=0.1, gt=0)
    derivative_block_size: int = Field(default=8, ge=1)

    @model_validator(mode="after")
    def validate_sampling(self) -> "Settings":
        if self.shots and self.shots < self.shards:
            raise ValueError("Each measurement shard requires at least one shot")
        return self


class Fragment(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    identifier: str
    monomers: list[str]
    fcidump: str
    settings: Settings = Field(default_factory=Settings)


class State(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    fragment: Fragment
    n_pairs: int
    h1: list[list[float]]
    h2: list[list[list[list[float]]]]
    constant: float
    rotation: list[list[float]]
    parameters: list[float]
    templates: list[str] = Field(default_factory=list)
    moments: dict[str, float] = Field(default_factory=dict)
    energy: float = 0.0
    initial: list[float] = Field(default_factory=list)
    history: list[Evaluation] = Field(default_factory=list)
    amplitude_iteration: int = 0
    amplitude_done: bool = False
    amplitude_success: bool = False
    orbital_iteration: int = 0
    orbital_success: bool = False
    macro_iteration: int = 0
    previous_energy: float = 0.0
    converged: bool = False
    diagnostics: list[str] = Field(default_factory=list)


class MeasurementJob(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    basis: Literal["X", "Y", "Z"]
    circuit: str
    parameters: list[float]
    shots: int = Field(ge=0)
    seed: int = Field(ge=0)


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    basis: Literal["X", "Y", "Z"]
    shots: int = Field(ge=0)
    moments: dict[str, float]
    standard_errors: dict[str, float] = Field(default_factory=dict)
    backend: str = "local"


class DerivativeJob(BaseModel):
    state: State
    rows: list[int]


class DerivativeBlock(BaseModel):
    gradient: dict[str, float]
    hessian: list[tuple[int, int, float]]


@portmapping
class StatePort(NamedTuple):
    state: State


@portmapping
class StatesPort(NamedTuple):
    states: list[State]


@portmapping
class AmplitudeProposal(NamedTuple):
    state: State
    candidates: list[State]


@portmapping
class LoopPort(NamedTuple):
    state: State
    should_continue: bool


@portmapping
class MeasurementJobsPort(NamedTuple):
    jobs: list[MeasurementJob]


@portmapping
class MeasurementPort(NamedTuple):
    value: Measurement


@portmapping
class DerivativeJobsPort(NamedTuple):
    jobs: list[DerivativeJob]


@portmapping
class DerivativePort(NamedTuple):
    value: DerivativeBlock


class FMOResult(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    energy: float
    fragment_energies: dict[str, float]
    fragment_converged: dict[str, bool]
    converged: bool
    diagnostics: dict[str, list[str]]
    fragment_iterations: dict[str, dict[str, int]] = Field(default_factory=dict)


@portmapping
class ResultPort(NamedTuple):
    result: FMOResult
