import os

from qfw_qiskit import QFwBackend  # pyright: ignore[reportMissingImports]
from qiskit import QuantumCircuit

from tkr_sqd_quantum_worker_impl.compilation import compile_qfw


def run_counts(
    circuit: QuantumCircuit, shots: int
) -> tuple[dict[str, int], str, QuantumCircuit]:
    if not os.environ.get("QFW_RESERVATIONS"):
        raise RuntimeError("QFw sampling requires a Slurm QFW_RESERVATIONS binding")
    backend = QFwBackend()  # TODO do we need service runs
    compiled = compile_qfw(circuit, backend.target)
    counts = backend.run(compiled, shots=shots).result().get_counts(compiled)
    # QFw shutdown exits the process; the wrapper owns teardown after output writes.
    return (
        {str(key): int(value) for key, value in counts.items()},
        backend.name,
        compiled,
    )
