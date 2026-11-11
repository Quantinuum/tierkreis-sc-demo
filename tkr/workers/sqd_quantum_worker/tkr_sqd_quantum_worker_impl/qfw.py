import os
from typing import Literal

from qiskit import QuantumCircuit

from tkr_sqd_quantum_worker_impl.compilation import compile_mqt, compile_qfw


def run_counts(
    circuit: QuantumCircuit,
    shots: int,
    *,
    compilation: Literal["qfw", "mqt"] = "qfw",
) -> tuple[dict[str, int], str, QuantumCircuit]:
    if not os.environ.get("QFW_RESERVATIONS"):
        raise RuntimeError("QFw sampling requires a Slurm QFW_RESERVATIONS binding")
    from qfw_qiskit import QFwBackend  # pyright: ignore[reportMissingImports]

    backend = QFwBackend()  # TODO do we need service runs
    if compilation == "qfw":
        compiled = compile_qfw(circuit, backend.target)
    elif compilation == "mqt":
        # compiled = compile_mqt(circuit, backend.target)
        compiled = backend.compile(circuit, "mqt")
    else:
        raise ValueError(f"Unknown compilation {compilation!r}")
    counts = backend.run(compiled, shots=shots).result().get_counts(compiled)
    # QFw shutdown exits the process; the wrapper owns teardown after output writes.
    return (
        {str(key): int(value) for key, value in counts.items()},
        backend.name,
        compiled,
    )
