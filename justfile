set export
UV_PROJECT_ENVIRONMENT := justfile_directory() / ".venv"
VIRTUAL_ENV := UV_PROJECT_ENVIRONMENT
OMP_NUM_THREADS := "1"
OPENBLAS_NUM_THREADS := "1"
MKL_NUM_THREADS := "1"

setup:
    uv sync --locked

stubs:
    uv run tkr init stubs --worker-directory tkr/workers
    uv sync --reinstall-package tkr-fmo-control-worker --reinstall-package tkr-fmo-chemistry-worker --reinstall-package tkr-fmo-quantum-worker

run:
    uv run tkr run -g tkr.graphs.he4:workflow -i examples/example_3_He4_input.json --profile local --timeout 86400 -o

lint:
    uv run ruff check src tkr/graphs tkr/workers
    uv run ruff format --check src tkr/graphs tkr/workers
    uv run pyright

visualize:
    uv run tkr serve

visualize-cluster:
    docker exec -it --user user-a --workdir /workspace/qfw-container-base/tierkreis-sc-demo slurmctld /opt/openqse/qfw-venv/bin/tkr serve --host 0.0.0.0
