# SQD control worker

Changes:

- Random numbers come from `numpy.random.default_rng([seed, stream])` per
  walker task instead of module-global generators. Results are reproducible
  for any execution order, so they differ from the reference's numbers.
- The first iteration accepts all walkers instead of comparing with zero.
- Carryover is de-duplicated before subsampling in every branch.
- `t2` drifts are symmetrised because current ffsim validates pair symmetry.
- SBD carryover is enabled explicitly (`sbd.carryover_type = 1`); the
  reference's arguments leave SBD at its default 0, which writes no carryover.


