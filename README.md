# chemistry_he examples on Tierkreis's Rust runtime

Typed implementations of the three examples in
[openQSE/chemistry_he](https://github.com/openQSE/chemistry_he), pinned to
`afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0`. Python builds the graphs and
implements the workers; orchestration runs in Rust.

**For cluster setup, all three run commands, Slurm/QPU flags and the QFw
execution path, see [CLUSTER.md](CLUSTER.md).**

## Examples

| Upstream example | Project input | Computation |
| --- | --- | --- |
| [1: He from PySCF](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/example_1_He.py) | [example_1_He_input.json](examples/example_1_He_input.json) | He atom, cc-pVDZ, RHF integrals, MP2 guess, amplitude optimization, then orbital optimization |
| [2: He2 from FCIDUMP](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/example_2_He2_from_FCIDUMP.py) | [example_2_He2_input.json](examples/example_2_He2_input.json) | One supplied dimer FCIDUMP, alternating amplitude/orbital optimization |
| [3: He4 FMO-VQE](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/example_3_He4_FMO_VQE.py) | [example_3_He4_input.json](examples/example_3_He4_input.json) | Four monomers and six dimers, independent solves, FMO2 reduction |

Example 2 selects `examples/He4/He1-4.FCIDUMP-2-1` by default, since upstream accepts
any supplied dimer path. Example 3 uses the explicit
[He4 connectivity manifest](examples/he4_manifest.json). No GAMESS executable
is required: these are upstream's precomputed integrals, bundled under
[examples/He4](examples/He4), unchanged from the pinned upstream revision above.
No `.reference` checkout is needed to run the examples. GAMESS production,
auxiliary smoke examples and video recording are intentionally out of scope.
Their previous implementations and supporting wiring are preserved in the
named Git stash `deferred: GAMESS, smoke workflows and video recording`.
Use `git stash list` / `git stash show -p` to inspect it and restore selected
files or hunks if needed. The stash preserves the three new example entrypoints;
it also contains the older documentation and legacy input files.

The workflows implement the scientific calculation, not upstream's optional
FCI diagnostic, Hamiltonian printing or circuit-image generation. Example 1
calls the orbital optimizer without upstream's obsolete positional-parameter
argument. Budget exhaustion is reported, not represented as convergence.
Example 1 has no macro loop; examples 2 and 3 do.

## Local setup and execution

Requires Python 3.12+ and `uv`. The project pins the Tierkreis 3.0 release
candidate (`tierkreis==3.0.0rc0`) and installs it from PyPI; no sibling
Tierkreis checkout or Rust build is required.

```sh
uv sync --locked
```

Cluster provisioning belongs to the operator, not an application Dockerfile.
For installation into a site-provided QFw environment, see
[the installation guide](CLUSTER.md#3-install-the-project-not-another-cluster-image).
Start the QFw telemetry stack using [the cluster guide](CLUSTER.md#2-local-virtual-cluster-commands-you-run).
The runtime and profiles enable OTLP/gRPC export; local runs use host port 4317.

From the project root:

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
uv run tkr run -g tkr.graphs.he:workflow -i examples/example_1_He_input.json --profile local --timeout 86400 -o
uv run tkr run -g tkr.graphs.he2:workflow -i examples/example_2_He2_input.json --profile local --timeout 86400 -o
uv run tkr run -g tkr.graphs.he4:workflow -i examples/example_3_He4_input.json --profile local --timeout 86400 -o
```

Each graph has its own direct JSON port inputs; there is no application runner
or example-selection flag. The input settings expose the scientific
iteration budgets/tolerances; these are not artificially reduced demonstration
budgets. Local runs use exact statevectors unless a positive `settings.shots`
is provided in the input JSON. All invocations use the configured `.runtime/workflows.sqlite`
database, retaining multiple runs in one history. The visualizer uses that same
database.
Clearing `.runtime` resets history; the next workflow run recreates it.
Stop workflows and the viewer before clearing runtime state. Unfinished runs
in a retained database may resume when the runtime starts.
Task assets and logs persist in `.runtime`.
Use `-o` to print outputs. Single-system outputs contain the final state;
example 3 outputs the FMO2
result with fragment energies and convergence diagnostics.

```sh
uv run tkr serve
# Optional: --port 3001
```

Open <http://localhost:3000>. The viewer only reads persisted state; it never
starts or resumes a workflow. Unstarted maps have no concrete iterations yet.
Native log HTTP endpoints remain stubs; inspect persisted runtime/worker logs.

## Graphs, workers and placement

The separate [He](tkr/graphs/he.py), [He2](tkr/graphs/he2.py) and
[He4](tkr/graphs/he4.py) entrypoints compose typed evals, maps and loops from
[shared.py](tkr/graphs/shared.py):

Graphs import tasks directly, for example
`from fmo_chemistry_worker import initialize_helium_from_pyscf`.
Worker APIs use explicit action names, also shown in the runtime visualizer.

```text
He: PySCF/RHF -> prepare -> initial objective -> amplitudes -> orbitals
He2: FCIDUMP -> prepare -> initial objective -> loop(amplitudes -> orbitals)
He4: load manifest -> map(monomers + dimers, He2-style solver) -> FMO2 total
objective: map(X/Y/Z groups x shot shards, measurements) -> energy
orbitals: loop(map(gradient/Hessian blocks) -> Newton step -> rotate)
```

Monomers and dimers have no artificial ordering barrier. COBYLA proposals
remain sequential because each depends on previous results; the retained
interchangeable SPSA solver maps its two proposals concurrently. Orbital
updates reuse the measured moments and do not rerun circuits.

| Worker | Local executor | Cluster context / executor |
| --- | --- | --- |
| [Control](tkr/workers/fmo_control_worker/README.md): manifest loading, optimizer feedback, convergence, FMO2 | `subprocess` | `control` / `subprocess` |
| [Chemistry](tkr/workers/fmo_chemistry_worker/README.md): PySCF, FCIDUMP, contraction, derivatives, rotations | `subprocess` | `chemistry` / `slurm` |
| [Quantum](tkr/workers/fmo_quantum_worker/README.md): circuit/job preparation | `subprocess` | `control` / `subprocess` |
| Quantum: measurements | `subprocess` | `quantum` / `slurm` |

[runtime.toml](runtime.toml) registers each executor once. The same graph always
uses named `control`, `chemistry` and `quantum` contexts; it contains no
local/cluster switch. The [local profile](resource_profiles/local) maps all three
to subprocess, while [qfw-slurm](resource_profiles/qfw-slurm) maps chemistry
and measurements to Slurm. Select with `--profile local` (default) or
`--profile qfw-slurm`. Registering Slurm does not submit jobs on local runs.
Run from the project root so relative input and launcher paths resolve on the
shared filesystem. File storage canonicalizes its root before passing asset
locations to workers. The memory executor supplies built-ins.
Worker-specific implementations and launchers live in their worker packages;
only shared typed graph/worker models live in [src/fmo_vqe](src/fmo_vqe).
Manifest loading belongs to the control worker; FCIDUMP normalization belongs
to the chemistry worker. Normalization converts upstream Fortran exponents and
header syntax for PySCF; it is parsing compatibility, not file verification.

For another scheduler or quantum provider, see
[adapting backends](CLUSTER.md#adapting-to-other-backends).
An executor changes **where a worker runs**, not **which quantum API it calls**.
QFw-supported providers reuse the graph/worker; a non-QFw API needs a compatible
measurement worker adapter, not just a scheduler change.

After worker signature changes, regenerate and reinstall APIs with `just stubs`.
The development-only `tierkreis[stubs]` extra supplies Ruff for formatting
generated worker APIs; it is not a separate type-stub package or runtime
requirement. `tomli-w` is no longer needed: `tkr serve` reads the runtime
configuration directly without a temporary TOML file.

### Quantum backend, provider and environment

The quantum context's `TKR_QUANTUM_BACKEND` selects `local` simulation or the
`qfw` API inside the measurement worker. Backend and provider are not scientific
inputs and do not branch the graph. No separate backend/provider CLI flag is
needed. Programmatic callers pass the selected profile to `start_new_run`.

To change from NWQSim to another **QFw-supported provider**, edit
[qfw-slurm/quantum.toml](resource_profiles/qfw-slurm/quantum.toml):

```toml
[extra_scheduler_args]
"--qpu" = "SITE-PROVIDER"
"--max-qubits" = "10"
"--max-depth" = "1000"
"--max-shots" = "4096"
```

Change the existing entries, not add a second table. Slurm/QFw reserves the
selected resource and SPANK supplies `QFW_RESERVATIONS` to the worker.
`QFwBackend()` binds the sole reserved QPM without a duplicate provider string.
Multiple reserved QPMs are intentionally unsupported by this worker and QFw
rejects that ambiguous selection. Keep `TKR_QUANTUM_BACKEND=qfw`.
The operator must provision the matching QPM/adapter, authorization and protected
credentials. A rename alone does not enable hardware or target compilation.
Set `settings.shots` in each input JSON to a positive value within the
reservation limit (for example, 4096).

Reservation bounds live **only in scheduler arguments**. QFw's admission and
execution path enforce them; the worker no longer mirrors them in `FMO_QFW_*`
variables or performs the former pre-submission envelope check.
`FMO_QFW_ACTIVE` remains an internal launcher guard, not a profile setting.

`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS` and `MKL_NUM_THREADS` cap numerical
library threads at one to match the one-CPU task allocation; they are execution
policy, not chemistry parameters. `OTEL_EXPORTER_OTLP_ENDPOINT` selects the
deployment's worker collector. The coordinator endpoint is configured in
`logging_config.otel_endpoint` in [runtime.toml](runtime.toml); it is independent
of worker profiles. To change collectors, update the runtime logging endpoint
and profile environments.

## Scientific cross-reference

All source links pin the tested upstream revision.

| Operation | Upstream | Implementation |
| --- | --- | --- |
| RHF integrals, FCIDUMP, MP2 initialization | [`from_pyscf_Mole`, `from_FCIDUMP`](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/puccd.py#L220) | [chemistry.py](tkr/workers/fmo_chemistry_worker/tkr_fmo_chemistry_worker_impl/chemistry.py) |
| Pair-UCCD Givens ansatz, X/Y/Z observables | [`givens_rot_ansatz`](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/puccd.py#L429) | [quantum.py](tkr/workers/fmo_quantum_worker/tkr_fmo_quantum_worker_impl/quantum.py) |
| Amplitude optimization | [`optimize_amps_qk`](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/puccd.py#L887) | [optimizers.py](tkr/workers/fmo_control_worker/tkr_fmo_control_worker_impl/optimizers.py), [control.py](tkr/workers/fmo_control_worker/tkr_fmo_control_worker_impl/control.py) |
| Orbital gradient/Hessian and rotations | [`orb_grad_qubit2`, `orb_hess_qubit2`](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/puccd.py#L583) | [chemistry.py](tkr/workers/fmo_chemistry_worker/tkr_fmo_chemistry_worker_impl/chemistry.py), [orbital tasks](tkr/workers/fmo_chemistry_worker/tkr_fmo_chemistry_worker_impl/impl.py) |
| FMO2 reduction | [`example_3_He4_FMO_VQE.py`](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/example_3_He4_FMO_VQE.py) | [aggregate](tkr/workers/fmo_control_worker/tkr_fmo_control_worker_impl/control.py) |

The FMO2 total is `sum_i E(i) + sum_{i<j} (E(i,j) - E(i) - E(j))`.
Nuclear constants are included once per fragment. Manifests are assumed to
describe the intended monomers and complete set of dimer pairs; no separate
file or connectivity verification is performed.

## Tests and validation status

```sh
uv run ruff check src tkr/graphs tkr/workers
uv run ruff format --check src tkr/graphs tkr/workers
uv run pyright
```

Tests are not required to run the application. The scientific comparisons and
runtime/deployment regression tests are preserved in the named Git stash
`deferred: scientific and runtime regression tests` (stash commit
`9e7327fc7562a933c2e8073f232f6b499a694c73`). To restore only their source files
without applying unrelated historical worktree changes:

```sh
git restore --source=9e7327fc7562a933c2e8073f232f6b499a694c73^3 -- tests
uv add --dev 'pytest>=9' 'pytest-asyncio>=1' 'openfermion>=1.7'
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run pytest tests
```

The archived tests cover coefficients/circuits/energies/derivatives, finite
differences, monomer/dimer solves and the complete He4 comparison. Tests that
compare against upstream Python code additionally require a separate reference
checkout (not needed by workflow execution):

```sh
git clone https://github.com/openQSE/chemistry_he.git .reference
git -C .reference checkout afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0
```

The archive predates the graph/CLI split; update its imports and deployment
fixtures before rerunning the suite.

Under bounded parity-test settings, the
previous full He4 result differed from the corrected reference by **0.227795
mEh total**, with **0.092101 mEh maximum fragment error** (acceptance: 1 mEh
total and 0.5 mEh per fragment). This is not a production convergence guarantee.
Upstream can retain moments from the last COBYLA evaluation instead of its
selected optimum; comparisons remeasure the selected optimum before orbitals.

The current He example completed end-to-end on QFw/NWQSim with bounded
settings: six COBYLA evaluations, one orbital iteration and 4096 shots.
All 42 Slurm jobs completed, including 24 quantum measurement tasks, and
runtime traces were found in Tempo. This validates execution, not convergence.
The first attempt stalled in QFw reservation handling; operator-approved
NWQSim/gateway recovery allowed the retry to complete. The underlying DEFw
transport issue is not claimed fixed. See the
[cluster validation record](CLUSTER.md#current-validation-boundary).
Full-budget cluster examples and real hardware execution remain unverified.

## Runtime/deployment limitations

- GAMESS execution and video recording are deliberately removed.
- Tierkreis is pinned to the `3.0.0rc0` release candidate. Upgrade the pin and
  regenerate `uv.lock` when a newer compatible release is adopted.
- Rust HPC profiles select static resource envelopes, not arbitrary dynamic
  graph-derived scheduler requests. Change reservation bounds in the quantum
  profile's scheduler arguments; no matching worker environment is required.
- Per-task Slurm submission and QFw setup favor isolation over minimum latency.
  No application-managed persistent QPU allocation/pooling is implemented.
