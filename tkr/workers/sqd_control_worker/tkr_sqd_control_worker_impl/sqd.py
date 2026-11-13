"""SQD problem setup, differential evolution and subspace construction.

Ported from qcsc-prefect `algorithms/sbd` (Apache-2.0) with per-walker
deterministic random generators instead of module-global ones.
"""

import io
import re
import tempfile
from pathlib import Path
from typing import Any

import ffsim
import numpy as np
import numpy.typing as npt
import scipy.linalg
from pyscf import ao2mo, cc, scf
from pyscf.tools import fcidump
from qiskit.primitives.containers import BitArray
from qiskit_addon_sqd.configuration_recovery import (
    post_select_by_hamming_weight,
    recover_configurations,
)
from qiskit_addon_sqd.counts import bit_array_to_arrays, generate_bit_array_uniform

from sqd_sbd.models import (
    DEState,
    Problem,
    Samples,
    Settings,
    WalkerRecord,
    WalkerResult,
    WalkerTask,
)

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

# Independent random streams derived from one walker seed.
_RECOVERY_STREAM = 1
_SUBSAMPLE_STREAM = 2


def normalize_fcidump(text: str) -> str:
    text = re.sub(
        r"(\bISYM\s*=\s*\d+)\s+(?=UHF\s*=)", r"\1,", text, flags=re.IGNORECASE
    )
    return re.sub(r"(?<=\d)[dD](?=[+-]\d)", "E", text)


def _rng(seed: int, stream: int) -> np.random.Generator:
    return np.random.default_rng([seed, stream])


def _to_integers(matrix: npt.NDArray[np.bool_], norb: int) -> IntArray:
    weights = 1 << np.arange(norb - 1, -1, -1, dtype=np.int64)
    return matrix.astype(np.int64) @ weights


def load_problem(text: str) -> tuple[Problem, bytes]:
    """Run RHF and CCSD and return MO integrals plus the SBD `fcidump.txt`."""
    # TODO THIS IS AWFUL TRY TO REWORK
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "FCIDUMP"
        path.write_text(normalize_fcidump(text))
        # PySCF is untyped and `newton` returns a dynamically mixed-in class.
        # has to read a file unfortunately
        mean_field: Any = scf.newton(fcidump.to_scf(str(path)))
        norb = int(mean_field.mol.nao)
        mean_field.mol.verbose = 0
        mean_field.mol.stdout = io.StringIO()
        mean_field.verbose = 0
        mean_field.symmetry = False
        dm0 = np.zeros((norb, norb))
        for occupied in range(mean_field.mol.nelectron // 2):
            dm0[occupied, occupied] = 2.0
        mean_field.kernel(dm0=dm0)
        if not mean_field.converged:
            raise RuntimeError("Restricted Hartree-Fock did not converge")
        num_alpha, num_beta = (int(n) for n in mean_field.mol.nelec)
        if num_alpha != num_beta:
            raise ValueError("The SQD workflow requires a closed-shell molecule")
        coefficients = mean_field.mo_coeff
        h1 = coefficients.T @ mean_field.get_hcore() @ coefficients
        # `fcidump.to_scf` stores the two-electron integrals only in `_eri`.
        eri = mean_field._eri  # pyright: ignore[reportPrivateUsage]
        h2 = ao2mo.full(eri, coefficients, compact=False).reshape(
            norb, norb, norb, norb
        )
        ccsd = cc.CCSD(mean_field)
        ccsd.verbose = 0
        ccsd.kernel()
        occupancy, _ = scipy.linalg.eigh(mean_field.make_rdm1())
        occupancy = occupancy[::-1] / 2.0
        output = Path(directory) / "fcidump.txt"
        fcidump.from_integrals(str(output), h1, h2, norb, (num_alpha, num_beta))
        sbd_fcidump = output.read_bytes()
    problem = Problem(
        norb=norb,
        nelec=(num_alpha, num_beta),
        h1=h1.tolist(),
        h2=h2.tolist(),
        ecore=float(mean_field.mol.energy_nuc()),
        t2=np.asarray(ccsd.t2).tolist(),
        occupancy=(occupancy.tolist(), occupancy.tolist()),
        hf_energy=float(mean_field.e_tot),
        ccsd_energy=float(ccsd.e_tot),
    )
    return problem, sbd_fcidump


def _t2_to_parameters(problem: Problem, t2: FloatArray, layers: int) -> list[float]:
    pairs = problem.interaction_pairs()
    operator = ffsim.UCJOpSpinBalanced.from_t_amplitudes(
        t2=t2, n_reps=layers + 1, interaction_pairs=pairs
    )
    truncated = ffsim.UCJOpSpinBalanced(
        diag_coulomb_mats=operator.diag_coulomb_mats[:-1],
        orbital_rotations=operator.orbital_rotations[:-1],
        final_orbital_rotation=operator.orbital_rotations[-1],
    )
    return truncated.to_parameters(interaction_pairs=pairs).tolist()


def initial_population(problem: Problem, settings: Settings) -> list[list[float]]:
    """Walker 0 uses CCSD amplitudes; the others use randomly drifted ones."""
    t2 = np.asarray(problem.t2, dtype=float)
    rng = np.random.default_rng([settings.random_seed, 0])
    population = [_t2_to_parameters(problem, t2, settings.n_lucj_layers)]
    for _ in range(settings.num_walkers - 1):
        drift = settings.randomization_factor * (rng.random(t2.shape) - 0.5)
        # ffsim requires pair-symmetric amplitudes: t2[i, j, a, b] == t2[j, i, b, a].
        # for ffsim==0.0.85 TODO check if this can be removed
        drift = 0.5 * (drift + drift.transpose(1, 0, 3, 2))
        population.append(
            _t2_to_parameters(problem, t2 + drift, settings.n_lucj_layers)
        )
    return population


def mutation_and_crossover(state: DEState, settings: Settings) -> list[list[float]]:
    if state.best_index is None:
        raise ValueError("Mutation requires a selected best walker")
    population = np.asarray(state.populations, dtype=float)
    num_walkers, num_params = population.shape
    rng = np.random.default_rng([settings.random_seed, state.iteration + 1])
    mutant = np.zeros_like(population)
    for walker in range(num_walkers):
        r1, r2, r3, r4 = rng.choice(num_walkers, size=4, replace=False)
        drift = population[r1] - population[r2] + population[r3] - population[r4]
        mutant[walker] = population[state.best_index] + settings.fxc * drift
    for walker in range(num_walkers):
        keep = rng.random(num_params) > settings.cr_prob
        keep[rng.integers(num_params)] = False
        mutant[walker, keep] = population[walker, keep]
    return mutant.tolist()


def propose(state: DEState, problem: Problem, settings: Settings) -> list[WalkerTask]:
    population = (
        initial_population(problem, settings)
        if state.best_index is None
        else mutation_and_crossover(state, settings)
    )
    return [
        WalkerTask(iteration=state.iteration, walker=walker, parameters=parameters)
        for walker, parameters in enumerate(population)
    ]


def select(
    state: DEState, tasks: list[WalkerTask], results: list[WalkerResult]
) -> DEState:
    if len(tasks) != len(results):
        raise ValueError("Every walker task requires exactly one result")
    energies = [result.energy for result in results]
    best = int(np.argmin(energies))
    current_best = state.best_energy()
    new = state.model_copy(deep=True)
    if current_best is None or energies[best] < current_best:
        new.best_index = best
        new.carryover = results[best].carryover
    if not state.populations:
        new.energies = energies
        new.populations = [task.parameters for task in tasks]
    else:
        for walker, energy in enumerate(energies):
            if energy < state.energies[walker]:
                new.energies[walker] = energy
                new.populations[walker] = tasks[walker].parameters
    new.iteration = state.iteration + 1
    best_energy = new.best_energy()
    if best_energy is None:
        raise RuntimeError("Selection did not produce a best walker")
    new.best_energies = [*state.best_energies, best_energy]
    new.records = [*state.records, *(result.record for result in results)]
    return new


def random_samples(task: WalkerTask, problem: Problem, settings: Settings) -> Samples:
    bit_array = generate_bit_array_uniform(
        num_samples=settings.shots,
        num_bits=2 * problem.norb,
        rand_seed=task.seed(settings.random_seed),
    )
    counts = bit_array.get_counts()
    return Samples(
        bitstrings=list(counts),
        counts=list(counts.values()),
        num_bits=2 * problem.norb,
        shots=settings.shots,
        backend="random",
    )


def subsample_closed_shell(
    bitstrings: npt.NDArray[np.bool_],
    probabilities: FloatArray,
    carryover: list[int],
    problem: Problem,
    subspace_dim: int,
    rng: np.random.Generator,
) -> IntArray:
    """Pick alpha determinants: HF first, then carryover, then sampled strings."""
    # TODO Not 100% faithful, not sure if it matters
    norb = problem.norb
    if norb >= 63:
        raise ValueError("SBD determinants are limited to 62 orbitals")
    hartree_fock = (1 << problem.nelec[0]) - 1

    beta = _to_integers(bitstrings[:, :norb], norb)
    alpha = _to_integers(bitstrings[:, norb:], norb)
    unique, inverse = np.unique(np.concatenate((alpha, beta)), return_inverse=True)
    weights = np.bincount(
        inverse, weights=np.tile(probabilities, 2) / 2.0, minlength=len(unique)
    )
    kept = np.asarray([value for value in carryover if value != hartree_fock])
    kept = np.asarray(list(dict.fromkeys(kept.tolist())), dtype=np.int64)
    mask = (unique != hartree_fock) & ~np.isin(unique, kept)
    unique, weights = unique[mask], weights[mask]
    num_new = max(int(np.sqrt(subspace_dim)) - len(kept) - 1, 0)
    if len(unique) > num_new:
        unique = rng.choice(
            unique, size=num_new, replace=False, p=weights / weights.sum()
        )
    return np.concatenate(([hartree_fock], kept, unique)).astype(np.int64)


def prepare_sbd_input(
    task: WalkerTask,
    samples: Samples,
    carryover: list[int],
    problem: Problem,
    settings: Settings,
) -> tuple[bytes, list[str], WalkerRecord]:
    """Configuration recovery, post-selection and `AlphaDets.bin` encoding."""
    if samples.num_bits != 2 * problem.norb:
        raise ValueError("Samples do not match the number of spin orbitals")
    if not samples.bitstrings:
        raise ValueError("No samples survived reset mitigation")
    bit_array = BitArray.from_counts(
        dict(zip(samples.bitstrings, samples.counts, strict=True)),
        num_bits=samples.num_bits,
    )
    raw_bitstrings, raw_probabilities = bit_array_to_arrays(bit_array)
    seed = task.seed(settings.random_seed)
    num_alpha, num_beta = problem.nelec
    bitstrings, probabilities = recover_configurations(
        bitstring_matrix=raw_bitstrings,
        probabilities=raw_probabilities,
        avg_occupancies=(
            np.asarray(problem.occupancy[0]),
            np.asarray(problem.occupancy[1]),
        ),
        num_elec_a=num_alpha,
        num_elec_b=num_beta,
        rand_seed=_rng(seed, _RECOVERY_STREAM),
    )
    mask = post_select_by_hamming_weight(
        bitstrings, hamming_right=num_alpha, hamming_left=num_beta
    )
    bitstrings = bitstrings[mask]
    probabilities = np.abs(probabilities[mask])
    if not len(bitstrings):
        raise ValueError("No configurations survived post-selection")
    probabilities /= probabilities.sum()
    determinants = subsample_closed_shell(
        bitstrings,
        probabilities,
        carryover,
        problem,
        settings.sqd_dim,
        _rng(seed, _SUBSAMPLE_STREAM),
    )
    # TODO not sure if this packing is correct for the SBD input format
    width = (problem.norb + 7) // 8
    alpha_dets = b"".join(
        int(value).to_bytes(width, byteorder="big", signed=False)
        for value in determinants
    )
    record = WalkerRecord(
        iteration=task.iteration,
        walker=task.walker,
        backend=samples.backend,
        shot_retention_rate=sum(samples.counts) / samples.shots,
        num_post_determinants=len(bitstrings),
        num_alpha_determinants=len(determinants),
        net_subspace_dim=len(determinants) ** 2,
        circuit_builder=samples.circuit_builder,
        two_qubit_gates=samples.two_qubit_gates,
        depth=samples.depth,
    )
    return alpha_dets, settings.sbd.arguments(), record


def decode_carryover(data: bytes, norb: int) -> list[int]:
    """Decode SBD `carryover.bin`: MSB-first rows of `ceil(norb / 8)` bytes."""
    width = (norb + 7) // 8
    if len(data) % width:
        raise ValueError("carryover.bin size is not aligned with the determinant width")
    if not data:
        return []
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder="big")
    matrix = bits.reshape(-1, width * 8)[:, :norb].astype(bool)
    return _to_integers(matrix, norb).tolist()


def finish_walker(
    energy: float, carryover: bytes, record: WalkerRecord, problem: Problem
) -> WalkerResult:
    total = energy + problem.ecore
    if not np.isfinite(total):
        raise ValueError("SBD returned a non-finite energy")
    return WalkerResult(
        energy=total,
        carryover=decode_carryover(carryover, problem.norb),
        record=record.model_copy(update={"energy": total}),
    )
