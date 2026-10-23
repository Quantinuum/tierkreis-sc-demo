import math
import os
from collections.abc import Callable, Sequence
from importlib import import_module
from typing import Protocol, cast

import numpy as np
from qiskit import QuantumCircuit
from qiskit.primitives.containers import PubResult
from qiskit.providers import BackendV2
from qiskit.quantum_info import SparsePauliOp

from fmo_vqe.models import Measurement, MeasurementJob


class ResultJob(Protocol):
    def result(self) -> Sequence[PubResult]: ...


class Estimator(Protocol):
    def run(
        self,
        pubs: list[tuple[QuantumCircuit, list[SparsePauliOp]]],
        *,
        precision: float,
    ) -> ResultJob: ...


class QFwModule(Protocol):
    QFwBackend: Callable[..., BackendV2]
    QFwEstimatorV2: Callable[..., Estimator]


def measure(job: MeasurementJob, circuit: QuantumCircuit) -> Measurement:
    if not os.environ.get("FMO_QFW_ACTIVE"):
        raise RuntimeError("QFw measurements must run through the QFw Slurm launcher")
    if job.shots <= 0:
        raise ValueError("QFw requires a positive shot count")
    n = circuit.num_qubits
    identity = "I" * n
    words: list[str] = []
    for first in range(n):
        if job.basis == "Z":
            word = ["I"] * n
            word[n - 1 - first] = "Z"
            words.append("".join(word))
        for second in range(first + 1, n):
            word = ["I"] * n
            word[n - 1 - first] = word[n - 1 - second] = job.basis
            words.append("".join(word))
    if not words:
        return Measurement(
            basis=job.basis, shots=job.shots, moments={identity: 1.0}, backend="qfw"
        )
    # Templates already contain basis rotations, so the estimator measures Z.
    observables = [
        SparsePauliOp(word.replace("X", "Z").replace("Y", "Z")) for word in words
    ]
    module = cast(QFwModule, import_module("qfw_qiskit"))
    if not os.environ.get("QFW_RESERVATIONS"):
        raise RuntimeError("QFw measurements require a Slurm QFW_RESERVATIONS binding")
    backend = module.QFwBackend()
    estimator = module.QFwEstimatorV2(
        backend=backend, options={"seed_simulator": job.seed}
    )
    precision = math.nextafter(1 / math.sqrt(job.shots), math.inf)
    result = estimator.run([(circuit, observables)], precision=precision).result()[0]
    if result.metadata["shots"] != job.shots:
        raise RuntimeError("QFw estimator did not honor the requested shard shot count")
    values = np.asarray(result.data["evs"], dtype=float).reshape(-1)
    errors = np.asarray(result.data["stds"], dtype=float).reshape(-1)
    if len(values) != len(words) or len(errors) != len(words):
        raise RuntimeError("QFw returned an unexpected observable result shape")
    if not np.isfinite(values).all() or not np.isfinite(errors).all():
        raise RuntimeError("QFw returned non-finite estimates")
    # QFw shutdown exits the process; the wrapper owns teardown after output writes.
    return Measurement(
        basis=job.basis,
        shots=job.shots,
        moments={identity: 1.0, **dict(zip(words, values.tolist(), strict=True))},
        standard_errors={
            identity: 0.0,
            **dict(zip(words, errors.tolist(), strict=True)),
        },
        backend="qfw",
    )
