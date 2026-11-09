"""The reference ffsim/Qiskit LUCJ circuit and measurement registers."""

import ffsim
import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

from sqd_sbd.models import Problem


def lucj_circuit(
    parameters: list[float], problem: Problem, layers: int, reset_mitigation: bool
) -> QuantumCircuit:
    qubits = QuantumRegister(2 * problem.norb, name="q")
    meas = ClassicalRegister(len(qubits), name="meas")
    test = ClassicalRegister(len(qubits), name="test")
    circuit = QuantumCircuit(qubits, meas, *([test] if reset_mitigation else []))
    if reset_mitigation:
        circuit.measure(qubits, test)
        circuit.barrier()
    circuit.append(
        ffsim.qiskit.PrepareHartreeFockJW(problem.norb, problem.nelec), qargs=qubits
    )
    operator = ffsim.UCJOpSpinBalanced.from_parameters(
        np.asarray(parameters, dtype=float),
        norb=problem.norb,
        n_reps=layers,
        interaction_pairs=problem.interaction_pairs(),
        with_final_orbital_rotation=True,
    )
    circuit.append(ffsim.qiskit.UCJOpSpinBalancedJW(operator), qubits)
    circuit.measure(qubits, meas)
    return circuit
