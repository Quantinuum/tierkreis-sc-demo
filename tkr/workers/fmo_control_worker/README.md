# FMO control worker

Owns classical optimizer feedback and FMO2 aggregation; it does not run
circuits, parse integrals or launch Slurm itself.

Tasks are `load_fmo_fragments_from_manifest`,
`initialize_amplitude_optimization`, `propose_amplitude_candidates`,
`record_amplitude_evaluations`, `begin_macro_iteration`,
`check_macro_convergence` and `aggregate_fmo2_energy`.

- [Tasks](tkr_fmo_control_worker_impl/impl.py): manifest loading, amplitude
  initialization/proposals/history, macro convergence and final reduction.
- [Control logic](tkr_fmo_control_worker_impl/control.py): sequential COBYLA
  requests, two parallel SPSA perturbations, FMO2 double-count correction.
- [COBYLA continuation](tkr_fmo_control_worker_impl/optimizers.py): deterministic
  replay of recorded evaluations; no repeated quantum measurements.
- [Generated graph API](api/api.py): regenerate with `uv run tkr init stubs
  --worker-directory tkr/workers` from the project root.

**Placement:** context `control` resolves to `subprocess` in both profiles.
It supplies thread limits and the worker telemetry endpoint. QFw reservation
bounds belong only to the quantum context's scheduler arguments.

**Scientific reference:** pinned [puccd.py](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/puccd.py),
`optimize_amps_qk` and `optimize_ansatz_qk`; FMO2 reduction follows
[example_3_He4_FMO_VQE.py](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/example_3_He4_FMO_VQE.py).
SPSA is an optional alternative, not the reference's default optimizer.
Budget exhaustion is explicitly different from convergence.

The command `tkr-fmo-control-worker ARGUMENTS.json` implements the Tierkreis
worker protocol, not an interactive optimizer CLI.
