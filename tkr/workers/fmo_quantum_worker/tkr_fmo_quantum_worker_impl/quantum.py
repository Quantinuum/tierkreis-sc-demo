import base64
import hashlib
import io
import json
import os
from itertools import combinations

import numpy as np
from qiskit import QuantumCircuit, qpy, transpile
from qiskit.circuit import ParameterVector
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator

from fmo_vqe.models import Measurement, MeasurementJob, State


def prepare(state: State) -> State:
    n_orbitals = len(state.h1)
    circuit = QuantumCircuit(n_orbitals)
    circuit.x(list(range(state.n_pairs)))
    parameters = ParameterVector("t", len(state.parameters))
    index = 0
    for occupied in reversed(range(state.n_pairs)):
        for virtual in range(state.n_pairs, n_orbitals):
            circuit.s(occupied)
            circuit.s(virtual)
            circuit.h(occupied)
            circuit.cx(occupied, virtual)
            circuit.ry(parameters[index], occupied)
            circuit.ry(parameters[index], virtual)
            circuit.cx(occupied, virtual)
            circuit.h(occupied)
            circuit.sdg(occupied)
            circuit.sdg(virtual)
            index += 1
    templates: list[str] = []
    for basis in ("X", "Y", "Z"):
        rotated = circuit.copy()
        if basis == "Y":
            rotated.sdg(list(range(n_orbitals)))
        if basis != "Z":
            rotated.h(list(range(n_orbitals)))
        compiled = transpile(
            rotated,
            AerSimulator(),
            optimization_level=1,
            seed_transpiler=state.fragment.settings.seed,
        )
        stream = io.BytesIO()
        qpy.dump(compiled, stream)
        templates.append(base64.b64encode(stream.getvalue()).decode("ascii"))
    return state.model_copy(update={"templates": templates})


def measurement_jobs(state: State) -> list[MeasurementJob]:
    settings = state.fragment.settings
    shard_count = settings.shards if settings.shots else 1
    if settings.shots and settings.shots < shard_count:
        raise ValueError("Each measurement shard requires at least one shot")
    jobs: list[MeasurementJob] = []
    parameters_key = json.dumps([round(value, 12) for value in state.parameters])
    for basis, template in zip(("X", "Y", "Z"), state.templates, strict=True):
        for shard in range(shard_count):
            shots = settings.shots // shard_count + int(
                shard < settings.shots % shard_count
            )
            identity = f"{settings.seed}:{state.fragment.identifier}:{state.macro_iteration}:{len(state.history)}:{state.amplitude_iteration}:{parameters_key}:{basis}:{shard}"
            seed = int.from_bytes(
                hashlib.sha256(identity.encode()).digest()[:4], "little"
            )
            jobs.append(
                MeasurementJob(
                    basis=basis,
                    circuit=template,
                    parameters=state.parameters,
                    shots=shots,
                    seed=seed,
                )
            )
    return jobs


def simulate(job: MeasurementJob) -> Measurement:
    backend = os.environ["TKR_QUANTUM_BACKEND"]
    if backend not in ("local", "qfw"):
        raise ValueError(f"Unknown TKR_QUANTUM_BACKEND {backend!r}")
    stream = io.BytesIO(base64.b64decode(job.circuit))
    circuit = qpy.load(stream)[0].assign_parameters(job.parameters)
    if backend == "qfw":
        from tkr_fmo_quantum_worker_impl.qfw import measure

        return measure(job, circuit)
    n_qubits = circuit.num_qubits
    if job.shots:
        circuit.measure_all()
        counts = (
            AerSimulator()
            .run(circuit, shots=job.shots, seed_simulator=job.seed)
            .result()
            .get_counts()
        )
        outcomes = np.asarray(
            [int(bits.replace(" ", ""), 2) for bits in counts], dtype=np.uint64
        )
        probabilities = np.asarray(list(counts.values()), dtype=float) / job.shots
    else:
        probabilities = np.asarray(
            Statevector.from_instruction(circuit).probabilities()
        )
        outcomes = np.arange(len(probabilities), dtype=np.uint64)
    signs = 1.0 - 2.0 * (
        (outcomes[:, None] >> np.arange(n_qubits, dtype=np.uint64)) & 1
    )
    moments = {"I" * n_qubits: 1.0}
    if job.basis == "Z":
        for orbital in range(n_qubits):
            word = ["I"] * n_qubits
            word[n_qubits - 1 - orbital] = "Z"
            moments["".join(word)] = float(probabilities @ signs[:, orbital])
    for first, second in combinations(range(n_qubits), 2):
        word = ["I"] * n_qubits
        word[n_qubits - 1 - first] = job.basis
        word[n_qubits - 1 - second] = job.basis
        moments["".join(word)] = float(
            probabilities @ (signs[:, first] * signs[:, second])
        )
    return Measurement(
        basis=job.basis,
        shots=job.shots,
        moments=moments,
        standard_errors={
            word: float(np.sqrt(max(0.0, 1 - value**2) / job.shots))
            if job.shots
            else 0.0
            for word, value in moments.items()
        },
    )
