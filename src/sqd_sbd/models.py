"""Typed SQD/SBD workflow values shared by the graph and the workers."""

from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field
from tierkreis.models import portmapping


class SBDSettings(BaseModel):
    """Options forwarded to the SBD `diag` driver."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    task_comm_size: int = Field(default=1, ge=1)
    adet_comm_size: int = Field(default=1, ge=1)
    bdet_comm_size: int = Field(default=1, ge=1)
    block: int = Field(default=10, ge=1)
    iteration: int = Field(default=2, ge=1)
    tolerance: float = Field(default=1e-4, gt=0)
    carryover_ratio: float = Field(default=0.1, gt=0, le=1)
    # SBD defaults to 0 (no carryover.bin entries); 1 keeps the dominant determinants.
    carryover_type: Literal[0, 1, 2, 3] = 1

    def arguments(self) -> list[str]:
        return [
            "--task_comm_size",
            str(self.task_comm_size),
            "--adet_comm_size",
            str(self.adet_comm_size),
            "--bdet_comm_size",
            str(self.bdet_comm_size),
            "--block",
            str(self.block),
            "--iteration",
            str(self.iteration),
            "--tolerance",
            str(self.tolerance),
            "--carryover_type",
            str(self.carryover_type),
            "--carryover_ratio",
            str(self.carryover_ratio),
            "--dump_matrix_form_wf",
            "matrixformwf.txt",
            "--rdm",
            "0",
        ]


class Settings(BaseModel):
    """Workflow parameters; mirrors qcsc-prefect `FlowParameters`."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    sqd_dim: int = Field(default=1_000_000, ge=1)
    shots: int = Field(default=100_000, ge=1)
    quantum_source: Literal["quantum", "random"] = "quantum"
    random_seed: int = Field(default=24, ge=0)
    n_lucj_layers: int = Field(default=2, ge=1)
    use_reset_mitigation: bool = True
    # Mutation draws four distinct walkers.
    num_walkers: int = Field(default=4, ge=4)
    iterations: int = Field(default=1, ge=1)
    randomization_factor: float = Field(default=0.2, ge=0)
    fxc: float = Field(default=0.6, ge=0)
    cr_prob: float = Field(default=0.9, ge=0, le=1)
    sbd: SBDSettings = Field(default_factory=SBDSettings)


class Problem(BaseModel):
    """Molecular integrals and CCSD data derived from the FCIDUMP."""

    model_config = ConfigDict(allow_inf_nan=False)
    norb: int
    nelec: tuple[int, int]
    h1: list[list[float]]
    h2: list[list[list[list[float]]]]
    ecore: float
    t2: list[list[list[list[float]]]]
    occupancy: tuple[list[float], list[float]]
    hf_energy: float
    ccsd_energy: float

    def interaction_pairs(self) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        """Heavy-hex LUCJ pairs: nearest neighbours and every 4th alpha-beta."""
        aa = [(p, p + 1) for p in range(self.norb - 1)]
        ab = [(p, p) for p in range(0, self.norb, 4)]
        return aa, ab


class WalkerTask(BaseModel):
    """One walker evaluation of a differential-evolution iteration."""

    model_config = ConfigDict(allow_inf_nan=False)
    iteration: int
    walker: int
    parameters: list[float]

    def seed(self, random_seed: int) -> int:
        """The reference's per-(iteration, walker) Cantor-pairing seed."""
        total = self.iteration + self.walker
        return random_seed + total * (total + 1) // 2 + self.walker


class Samples(BaseModel):
    """Measurement outcomes in Qiskit bit order (qubit 0 is the last character)."""

    bitstrings: list[str]
    counts: list[int]
    num_bits: int
    shots: int
    backend: str
    circuit_builder: str = ""
    two_qubit_gates: int = 0
    depth: int = 0


class WalkerRecord(BaseModel):
    """Per-walker telemetry, mirroring the reference `sqd-telemetry` table.

    Fields are non-nullable because workflow outputs cannot contain JSON null.
    Circuit fields are empty/zero for the random source.
    """

    iteration: int
    walker: int
    backend: str
    shot_retention_rate: float
    num_post_determinants: int
    num_alpha_determinants: int
    net_subspace_dim: int
    circuit_builder: str = ""
    two_qubit_gates: int = 0
    depth: int = 0
    energy: float = 0.0


class WalkerResult(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    energy: float
    carryover: list[int]
    record: WalkerRecord


class DEState(BaseModel):
    """Differential-evolution optimizer state; reference `OptimizerState`."""

    model_config = ConfigDict(allow_inf_nan=False)
    iteration: int = 0
    energies: list[float]
    populations: list[list[float]] = []
    carryover: list[int] = []
    best_index: int | None = None
    best_energies: list[float] = []
    records: list[WalkerRecord] = []

    def best_energy(self) -> float | None:
        if self.best_index is None:
            return None
        return self.energies[self.best_index]


class IterationSummary(BaseModel):
    iteration: int
    best_energy: float


class SQDResult(BaseModel):
    energy: float
    best_walker: int
    hf_energy: float
    ccsd_energy: float
    # Objects rather than list[float]: the runtime decodes 2-float lists as complex.
    history: list[IterationSummary]
    records: list[WalkerRecord]


@portmapping
class ProblemPort(NamedTuple):
    problem: Problem
    fcidump: bytes


@portmapping
class StatePort(NamedTuple):
    state: DEState


@portmapping
class ProposalPort(NamedTuple):
    tasks: list[WalkerTask]


@portmapping
class LoopPort(NamedTuple):
    state: DEState
    should_continue: bool


@portmapping
class SamplesPort(NamedTuple):
    samples: Samples


@portmapping
class SBDJobPort(NamedTuple):
    alpha_dets: bytes
    solver_args: list[str]
    record: WalkerRecord


@portmapping
class WalkerResultPort(NamedTuple):
    result: WalkerResult


@portmapping
class ResultPort(NamedTuple):
    result: SQDResult
