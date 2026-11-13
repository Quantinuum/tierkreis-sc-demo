#!/usr/bin/env python3
import argparse
import asyncio
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOLERANCE_HARTREE = 1e-5


def decode_result(outputs: dict[str, bytes]) -> dict[str, Any]:
    if set(outputs) != {"value"}:
        raise ValueError(
            f"Expected one workflow output named 'value', got {list(outputs)}"
        )
    result = json.loads(outputs["value"])
    if not isinstance(result, dict):
        raise TypeError("The workflow output is not an SQD result object")
    energy = result.get("energy")
    if isinstance(energy, bool) or not isinstance(energy, (int, float)):
        raise TypeError("The workflow result does not contain a numeric energy")
    if not math.isfinite(energy):
        raise ValueError("The workflow energy is not finite")
    return result


def compare_energy(energy: float, reference: float) -> None:
    if not math.isfinite(energy) or not math.isfinite(reference):
        raise ValueError("Energies must be finite")
    difference = abs(energy - reference)
    print(f"Tierkreis SQD: {energy:.10f} Ha")
    print(f"PySCF FCI:     {reference:.10f} Ha")
    print(f"Difference:    {difference:.3e} Ha (tolerance {TOLERANCE_HARTREE:.1e} Ha)")
    if difference > TOLERANCE_HARTREE:
        raise AssertionError(
            "Tierkreis SQD energy differs from the PySCF FCI reference"
        )


def pyscf_energies(fcidump_path: Path) -> tuple[float, float]:
    import numpy as np
    from pyscf import fci, scf
    from pyscf.tools import fcidump

    integrals = fcidump.read(str(fcidump_path), verbose=False)
    nelec = int(integrals["NELEC"])
    spin = int(integrals["MS2"])
    if abs(spin) > nelec or (nelec + spin) % 2:
        raise ValueError("Invalid electron count or spin in FCIDUMP")
    if spin != 0:
        raise ValueError("The SQD workflow requires a closed-shell molecule")
    mean_field = scf.newton(fcidump.to_scf(str(fcidump_path)))
    mean_field.verbose = 0
    mean_field.symmetry = False
    dm0 = np.zeros((int(integrals["NORB"]), int(integrals["NORB"])))
    for occupied in range(nelec // 2):
        dm0[occupied, occupied] = 2.0
    scf_energy = float(mean_field.kernel(dm0=dm0))
    if not mean_field.converged:
        raise RuntimeError("PySCF SCF did not converge")

    solver = fci.direct_spin1.FCI()
    energy, _ = solver.kernel(
        integrals["H1"],
        integrals["H2"],
        integrals["NORB"],
        ((nelec + spin) // 2, (nelec - spin) // 2),
        ecore=integrals["ECORE"],
    )
    if not solver.converged:
        raise RuntimeError("PySCF FCI did not converge")
    return scf_energy, float(energy)


async def run_workflow(
    inputs: dict[str, Any], config: Path, profile: str
) -> dict[str, bytes]:
    from tierkreis.cli.run import load_graph
    from tierkreis.runtime import flush_traces, load_runtime_config, new_from_config

    try:
        runtime = await new_from_config(load_runtime_config(config))
        with runtime:
            workflow_id = await runtime.save_workflow(
                None, load_graph("tkr.graphs.sqd:workflow")
            )
            encoded = {key: json.dumps(value).encode() for key, value in inputs.items()}
            run_id = await runtime.start_new_run(workflow_id, encoded, profile=profile)
            await runtime.wait_for(run_id, timeout=86400)
            return await runtime.get_raw_outputs(run_id)
    finally:
        flush_traces()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path("examples/sqd_he2_input.json")
    )
    parser.add_argument("--config", type=Path, default=Path("runtime.toml"))
    parser.add_argument("--profile", default="qfw-slurm")
    args = parser.parse_args()
    os.chdir(PROJECT_ROOT)
    inputs = json.loads(args.input.read_text())

    started = time.perf_counter()
    try:
        result = decode_result(
            asyncio.run(run_workflow(inputs, args.config, args.profile))
        )
    finally:
        print(
            f"Tierkreis workflow time: {time.perf_counter() - started:.2f} s",
            flush=True,
        )
    print("Tierkreis result:", json.dumps(result, indent=2), flush=True)

    started = time.perf_counter()
    try:
        scf_energy, fci_energy = pyscf_energies(Path(inputs["fcidump"]))
    finally:
        print(
            f"PySCF reference time: {time.perf_counter() - started:.2f} s", flush=True
        )
    print(f"PySCF SCF:     {scf_energy:.10f} Ha")
    compare_energy(float(result["energy"]), fci_energy)
    print("PASS: SQD agrees with the PySCF FCI reference")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FAIL: SQD end-to-end comparison failed", file=sys.stderr, flush=True)
        traceback.print_exc()
        sys.exit(1)
