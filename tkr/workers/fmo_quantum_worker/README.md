# FMO quantum worker

Owns parameterized pUCCD circuits and one commuting measurement group per task.

Tasks are `prepare_puccd_measurement_circuits`,
`build_measurement_shard_jobs` and `execute_measurement_job`. The last name
covers both local simulation and QFw execution rather than implying that
hardware jobs are simulations.

- [Tasks](tkr_fmo_quantum_worker_impl/impl.py).
- [Circuit/job preparation and local measurements](tkr_fmo_quantum_worker_impl/quantum.py):
  X/Y/Z templates, optional shot sharding, exact Statevector or sampled Aer.
- [QFw measurements](tkr_fmo_quantum_worker_impl/qfw.py): real
  `QFwBackend`/`QFwEstimatorV2`, positive-shot and result checks.
  QFw failures never fall back to Aer.
- [Cluster launcher](launch.sh) and [DEFw entry point](qfw_entrypoint.py).
- [Generated graph API](api/api.py).

**Placement:** preparation/job creation uses context `control`. Measurements
use context `quantum`: local resolves to subprocess and cluster to Slurm.
The quantum profile sets `TKR_QUANTUM_BACKEND`, read by the measurement worker.
Its `--qpu` scheduler argument selects the reservation; `QFwBackend()` binds the
sole QPM in SPANK's `QFW_RESERVATIONS`, without a duplicate provider string.
Missing or ambiguous reservations fail explicitly. Reservation bounds exist only in scheduler
arguments and are enforced by QFw, not duplicated in worker environment variables.

The executor's `worker_commands.fmo_quantum_worker` points to the launcher.
Tierkreis passes the worker-argument JSON; Slurm has already allocated the job.
The launcher activates the site's QFw Python 3.12 environment, creates a unique
shared runtime, runs `qfw-setup`, runs this worker script via `qfw-srun`, verifies
output files, and tears down the task-owned runtime on success/failure/signals.
It does not start/stop site-owned QPMs. Logs remain beside argument assets.

QFw backend `shutdown()` terminates the interpreter before Tierkreis can write
outputs. Therefore the numerical function returns normally and the launcher
owns process/runtime teardown. Missing outputs and cleanup failures are errors.

**Scientific reference:** pinned [puccd.py](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/puccd.py),
`givens_rot_ansatz`, `prepare_state`, `commuting_observables`,
`measure_expectations_qk`. Templates already contain basis rotations; QFw
therefore measures commuting Z observables and maps them to logical Pauli words.

Entry point: `tkr-fmo-quantum-worker ARGUMENTS.json`; for QFw, use the configured
launcher instead of invoking this command outside a reservation.

See the [cluster guide](../../../CLUSTER.md#slurm-flags-do-not-submit-circuits)
for the complete reservation-to-QPU path, additional Slurm flags and hardware
provider requirements.
