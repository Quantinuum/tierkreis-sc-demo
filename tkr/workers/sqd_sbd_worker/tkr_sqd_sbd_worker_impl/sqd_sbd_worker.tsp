@portmapping
model SBDOutput {
  energy: float;
  carryover: bytes;
  occ_a: bytes;
  occ_b: bytes;
}

interface sqd_sbd_worker {
  diagonalize(
    fcidump: bytes,
    alpha_dets: bytes,
    solver_args: Array<string>
  ): SBDOutput;
}
