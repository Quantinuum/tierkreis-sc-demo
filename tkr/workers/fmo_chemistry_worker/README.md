# FMO chemistry worker

Owns molecular-integral and orbital calculations, not quantum execution.

Task names describe the calculation:
`initialize_helium_from_pyscf` runs He/cc-pVDZ RHF and initializes the pUCCD
state; `initialize_dimer_from_fcidump_file` reads a dimer file, while
`initialize_fragment_from_integrals` consumes an existing fragment's integrals.
`evaluate_energy_from_measurements` merges measurement shards and evaluates
energy. Orbital optimization uses `initialize_orbital_optimization`,
`build_orbital_derivative_jobs`, `compute_orbital_derivative_block` and
`update_orbitals_and_check_convergence`.

- [Tasks and measurement reduction](tkr_fmo_chemistry_worker_impl/impl.py):
  weighted shard merge, energy evaluation, orbital derivative jobs, Newton
  steps and explicit gradient-descent fallback.
- [Numerical implementation](tkr_fmo_chemistry_worker_impl/chemistry.py):
  He/cc-pVDZ PySCF RHF integrals for upstream example 1, FCIDUMP parsing,
  diagonal MP2 guess, pair Hamiltonian coefficients,
  gradient/Hessian row blocks and full tensor orbital rotations.
- [FCIDUMP syntax normalization](tkr_fmo_chemistry_worker_impl/fcidump.py):
  converts upstream Fortran exponents and header separators for PySCF.
- [Generated graph API](api/api.py): regenerate with `uv run tkr init stubs
  --worker-directory tkr/workers` from the project root.

**Placement:** context `chemistry` resolves to `subprocess` in the local profile
and the shared `slurm` executor in the QFw-Slurm profile.
Derivative row blocks run in a graph map.
Orbital iterations reuse the measured state moments; they do not rerun circuits.

**Scientific reference:** pinned [puccd.py](https://github.com/openQSE/chemistry_he/blob/afcd8f7cda176114c4ce6db2cd9f92d79bc2d9a0/puccd.py):
`from_pyscf_Mole`, `from_FCIDUMP`, `initial_guess_mp2d`, `ham_qubit`, `orb_grad_qubit2`,
`orb_hess_qubit2`, `rotate_orbitals`, `optimize_orbs_qk`.
The implementation uses linear solves rather than explicit matrix inversion.
Tests compare reference coefficients, energies, derivatives and finite differences.

Entry point: `tkr-fmo-chemistry-worker ARGUMENTS.json`.
