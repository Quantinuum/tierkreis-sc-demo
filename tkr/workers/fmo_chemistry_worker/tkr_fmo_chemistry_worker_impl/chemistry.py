import tempfile
from itertools import combinations
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from pyscf import ao2mo, gto, scf
from pyscf.tools import fcidump
from scipy.linalg import expm

from fmo_vqe.models import DerivativeBlock, DerivativeJob, Fragment, Settings, State
from tkr_fmo_chemistry_worker_impl.fcidump import normalize_fcidump

type Array = NDArray[np.float64]


def helium(settings: Settings) -> State:
    molecule = gto.M(
        atom=[("He", (0, 0, 0))],
        basis="cc-pvdz",
        charge=0,
        spin=0,
        symmetry=False,
        max_memory=8000,
    )
    mean_field = scf.RHF(molecule)
    mean_field.conv_tol_grad = 1e-14
    mean_field.max_cycle = 200
    mean_field.kernel()
    if not mean_field.converged:
        raise RuntimeError("He cc-pVDZ restricted Hartree-Fock did not converge")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "He.FCIDUMP"
        fcidump.from_scf(mean_field, str(path), tol=1e-15)
        fragment = Fragment(
            identifier="He",
            monomers=["He"],
            fcidump=path.read_text(),
            settings=settings,
        )
    return initialize(fragment)


def initialize(fragment: Fragment) -> State:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "FCIDUMP"
        path.write_text(normalize_fcidump(fragment.fcidump))
        data = fcidump.read(str(path), verbose=False)
    n_orbitals = int(data["NORB"])
    n_electrons = int(data["NELEC"])
    if n_electrons % 2 or int(data.get("MS2", 0)) != 0:
        raise ValueError("Pair-UCCD requires an even-electron closed-shell FCIDUMP")
    n_pairs = n_electrons // 2
    if not 0 <= n_pairs <= n_orbitals:
        raise ValueError("Invalid electron count for the number of orbitals")
    h1 = np.asarray(data["H1"], dtype=float)
    h2 = np.asarray(ao2mo.restore(1, data["H2"], n_orbitals), dtype=float)
    if not np.isfinite(h1).all() or not np.isfinite(h2).all():
        raise ValueError("Non-finite molecular integrals")
    if not np.allclose(h1, h1.T):
        raise ValueError("One-electron integrals are not Hermitian")
    fock = np.diag(h1).copy()
    for occupied in range(n_pairs):
        fock += 2 * h2[:, :, occupied, occupied].diagonal()
        fock -= h2[:, occupied, occupied, :].diagonal()
    parameters: list[float] = []
    for occupied in reversed(range(n_pairs)):
        for virtual in range(n_pairs, n_orbitals):
            denominator = 2 * (fock[occupied] - fock[virtual])
            if abs(denominator) < 1e-12:
                raise ValueError(
                    "Degenerate diagonal MP2 denominator; supply a different orbital basis"
                )
            parameters.append(
                float(h2[occupied, virtual, occupied, virtual] / denominator)
            )
    return State(
        fragment=fragment,
        n_pairs=n_pairs,
        h1=h1.tolist(),
        h2=h2.tolist(),
        constant=float(data["ECORE"]),
        rotation=np.eye(n_orbitals).tolist(),
        parameters=parameters,
    )


def energy_weights(h1: Array, h2: Array) -> dict[str, float]:
    n_orbitals = len(h1)
    weights: dict[str, float] = {}

    def add(operators: list[tuple[int, str]], coefficient: float) -> None:
        word = ["I"] * n_orbitals
        for orbital, pauli in operators:
            if word[orbital] == pauli:
                word[orbital] = "I"
            else:
                word[orbital] = pauli
        key = "".join(reversed(word))
        weights[key] = weights.get(key, 0.0) + float(coefficient)

    effective = h1 - 0.5 * np.einsum("pkkq->pq", h2)
    for orbital in range(n_orbitals):
        add([], effective[orbital, orbital])
        add([(orbital, "Z")], -effective[orbital, orbital])
        for other in range(n_orbitals):
            coulomb = 0.5 * h2[orbital, orbital, other, other]
            add([], coulomb)
            add([(orbital, "Z")], -coulomb)
            add([(other, "Z")], -coulomb)
            add([(orbital, "Z"), (other, "Z")], coulomb)
            if orbital != other:
                exchange = 0.25 * h2[orbital, other, other, orbital]
                add([], exchange)
                add([(orbital, "Z")], -exchange)
                add([(other, "Z")], exchange)
                add([(orbital, "Z"), (other, "Z")], -exchange)
            if orbital > other:
                pair = 0.5 * h2[orbital, other, orbital, other]
                add([(orbital, "X"), (other, "X")], pair)
                add([(orbital, "Y"), (other, "Y")], pair)
    return weights


def contract(h1: Array, h2: Array, moments: dict[str, float]) -> float:
    return sum(
        coefficient * moments[word]
        for word, coefficient in energy_weights(h1, h2).items()
    )


def energy(state: State) -> float:
    return state.constant + contract(
        np.asarray(state.h1), np.asarray(state.h2), state.moments
    )


def differentiate(tensor: Array, pair: tuple[int, int]) -> Array:
    first, second = pair
    derivative = np.zeros_like(tensor)
    for axis in range(tensor.ndim):
        first_slice: list[slice | int] = [slice(None)] * tensor.ndim
        second_slice = first_slice.copy()
        first_slice[axis] = first
        second_slice[axis] = second
        derivative[tuple(second_slice)] += tensor[tuple(first_slice)]
        derivative[tuple(first_slice)] -= tensor[tuple(second_slice)]
    return derivative


def derivative_block(job: DerivativeJob) -> DerivativeBlock:
    state = job.state
    h1, h2 = np.asarray(state.h1), np.asarray(state.h2)
    pairs = list(combinations(range(len(h1)), 2))
    gradient: dict[str, float] = {}
    hessian: list[tuple[int, int, float]] = []
    for row in job.rows:
        first1, first2 = differentiate(h1, pairs[row]), differentiate(h2, pairs[row])
        gradient[str(row)] = contract(first1, first2, state.moments)
        for column in range(row, len(pairs)):
            second1, second2 = (
                differentiate(h1, pairs[column]),
                differentiate(h2, pairs[column]),
            )
            mixed1 = 0.5 * (
                differentiate(first1, pairs[column])
                + differentiate(second1, pairs[row])
            )
            mixed2 = 0.5 * (
                differentiate(first2, pairs[column])
                + differentiate(second2, pairs[row])
            )
            hessian.append((row, column, contract(mixed1, mixed2, state.moments)))
    return DerivativeBlock(gradient=gradient, hessian=hessian)


def rotate(state: State, step: Array) -> State:
    n_orbitals = len(state.h1)
    generator = np.zeros((n_orbitals, n_orbitals))
    for value, (first, second) in zip(
        step, combinations(range(n_orbitals), 2), strict=True
    ):
        generator[first, second] = value
        generator[second, first] = -value
    transform = expm(generator)
    h1 = transform.T @ np.asarray(state.h1) @ transform
    h2 = np.asarray(state.h2)
    for axis in range(4):
        h2 = np.moveaxis(np.tensordot(h2, transform, axes=(axis, 0)), -1, axis)
    result = state.model_copy(
        update={
            "h1": h1.tolist(),
            "h2": h2.tolist(),
            "rotation": (np.asarray(state.rotation) @ transform).tolist(),
        }
    )
    result.energy = energy(result)
    return result
