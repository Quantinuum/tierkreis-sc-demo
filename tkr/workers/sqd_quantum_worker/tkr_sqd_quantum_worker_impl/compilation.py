"""Qiskit compilation matching qcsc-prefect's pinned SQD transpile_core.

Reference: bf820ee7ed866ae5e867e48c5996076f6248b939 (Apache-2.0).
"""

import logging

from ffsim.qiskit import PRE_INIT
from qiskit import QuantumCircuit
from qiskit.passmanager import ConditionalController
from qiskit.transpiler import PassManager, Target, generate_preset_pass_manager
from qiskit.transpiler.passes import (
    ApplyLayout,
    BarrierBeforeFinalMeasurements,
    EnlargeWithAncilla,
    FullAncillaAllocation,
    Optimize1qGatesDecomposition,
    RemoveIdentityEquivalent,
    SabreLayout,
    SetLayout,
)
from qiskit_ibm_runtime.transpiler.passes import FoldRzzAngle

TRANSPILE_SEED = 6538
logger = logging.getLogger(__name__)


def compile_qfw(
    circuit: QuantumCircuit,
    target: Target,
    *,
    max_iterations: int = 8,
    swap_trials: int = 10,
    layout_trials: int = 1024,
) -> QuantumCircuit:
    """_transpile_circuit() and find_optimal_layout() in stanspile_core.py"""
    prepared = PRE_INIT.run(circuit)
    coupling_map = target.build_coupling_map()
    search = generate_preset_pass_manager(
        optimization_level=3, target=target, seed_transpiler=TRANSPILE_SEED
    )
    search.layout = PassManager(
        [
            BarrierBeforeFinalMeasurements(
                label="qiskit.transpiler.internal.routing.protection.barrier"
            ),
            SabreLayout(
                coupling_map=coupling_map,
                seed=TRANSPILE_SEED,
                max_iterations=max_iterations,
                swap_trials=swap_trials,
                layout_trials=layout_trials,
            ),
            ConditionalController(
                [
                    FullAncillaAllocation(coupling_map=coupling_map),
                    EnlargeWithAncilla(),
                    ApplyLayout(),
                ],
                condition=lambda properties: properties["final_layout"] is None,
            ),
        ]
    )
    if "rzz" in target.operation_names:
        search.post_optimization = _rzz_optimization(target)
    logger.info(
        "Searching QFw layout: max_iterations=%s, swap_trials=%s, layout_trials=%s",
        max_iterations,
        swap_trials,
        layout_trials,
    )
    trial = search.run(prepared)
    if trial.layout is None:
        raise RuntimeError("Qiskit SABRE search did not return a layout")
    layout = trial.layout.initial_virtual_layout(filter_ancillas=True)
    manager = generate_preset_pass_manager(
        optimization_level=3, target=target, seed_transpiler=TRANSPILE_SEED
    )
    manager.layout = PassManager(
        [
            BarrierBeforeFinalMeasurements(
                label="qiskit.transpiler.internal.routing.protection.barrier"
            ),
            SetLayout(layout),
            FullAncillaAllocation(coupling_map=coupling_map),
            EnlargeWithAncilla(),
            ApplyLayout(),
        ]
    )
    if "rzz" in target.operation_names:
        manager.post_optimization = _rzz_optimization(target)
    compiled = manager.run(prepared)
    logger.info(
        "QFw circuit compiled: qubits=%s, depth=%s, operations=%s",
        compiled.num_qubits,
        compiled.depth(),
        dict(compiled.count_ops()),
    )
    return compiled


def _rzz_optimization(target: Target) -> PassManager:
    return PassManager(
        [
            FoldRzzAngle(),
            Optimize1qGatesDecomposition(target=target),
            RemoveIdentityEquivalent(target=target),
        ]
    )
