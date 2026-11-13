set export
UV_PROJECT_ENVIRONMENT := justfile_directory() / ".venv"
VIRTUAL_ENV := UV_PROJECT_ENVIRONMENT
OMP_NUM_THREADS := "1"
OPENBLAS_NUM_THREADS := "1"
MKL_NUM_THREADS := "1"

setup:
    uv sync --locked

# Build the protocol-aware SBD MPI worker.
build-sbd:
    tkr/workers/sqd_sbd_worker/native/build_sbd.sh

stubs:
    uv run tkr init stubs --worker-directory tkr/workers
    uv sync --reinstall-package tkr-fmo-control-worker --reinstall-package tkr-fmo-chemistry-worker --reinstall-package tkr-fmo-quantum-worker --reinstall-package tkr-sqd-control-worker --reinstall-package tkr-sqd-quantum-worker --reinstall-package tkr-sqd-sbd-worker


lint:
    uv run ruff check src tkr/graphs tkr/workers
    uv run ruff format --check src tkr/graphs tkr/workers
    uv run pyright

visualize:
    uv run tkr serve
