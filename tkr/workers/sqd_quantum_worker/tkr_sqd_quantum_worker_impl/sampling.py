"""Sample Qiskit LUCJ circuits on Aer or QFw."""

import os
from collections import Counter
from collections.abc import Mapping

from qiskit import QuantumCircuit

from sqd_sbd.models import Samples
from tkr_sqd_quantum_worker_impl.qfw import run_counts


def split_counts(
    counts: Mapping[str, int], circuit: QuantumCircuit, reset_mitigation: bool
) -> tuple[dict[str, int], int]:
    """Keep meas outcomes whose test register is zero, with or without spaces."""
    registers = list(reversed(circuit.cregs))
    names = {register.name for register in registers}
    if "meas" not in names or (reset_mitigation and "test" not in names):
        raise ValueError("LUCJ counts require meas and enabled reset-check registers")
    width = sum(register.size for register in registers)
    kept: Counter[str] = Counter()
    total = 0
    for key, count in counts.items():
        bits = key.replace(" ", "")
        if len(bits) != width or set(bits) - {"0", "1"}:
            raise ValueError(f"Count key {key!r} does not match {width} classical bits")
        if count < 0:
            raise ValueError(f"Negative shot count for {key!r}: {count}")
        values: dict[str, str] = {}
        offset = 0
        for register in registers:
            values[register.name] = bits[offset : offset + register.size]
            offset += register.size
        total += count
        if reset_mitigation and "1" in values["test"]:
            continue
        kept[values["meas"]] += count
    return dict(kept), total


def sample(
    circuit: QuantumCircuit,
    shots: int,
    reset_mitigation: bool,
) -> Samples:
    backend = os.environ.get("TKR_QUANTUM_BACKEND", "qfw")
    if backend == "qfw":
        counts, name, compiled = run_counts(circuit, shots)
        name = f"qfw:{name}"
    else:
        raise ValueError(f"Unknown TKR_QUANTUM_BACKEND {backend!r}")

    kept, total = split_counts(counts, compiled, reset_mitigation)
    if total != shots:
        raise RuntimeError(f"{name} returned {total} shots instead of {shots}")
    return Samples(
        bitstrings=list(kept),
        counts=list(kept.values()),
        num_bits=circuit.num_qubits,
        shots=shots,
        backend=name,
        circuit_builder="ffsim_qiskit",
        two_qubit_gates=sum(
            instruction.operation.num_qubits == 2
            and instruction.operation.name != "barrier"
            for instruction in compiled.data
        ),
        depth=compiled.depth(),
    )
