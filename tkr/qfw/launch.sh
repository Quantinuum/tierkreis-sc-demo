#!/usr/bin/env bash
set -euo pipefail

worker_module=${1:?worker module is required}
worker_args=$(realpath "${2:?worker argument JSON is required}")
if [[ ! -f ${worker_args} ]]; then
    printf 'Worker argument file does not exist: %s\n' "${worker_args}" >&2
    exit 2
fi


run_dir=$(mktemp -d "${QFW_DIR:?QFW_DIR is required}/qfw.XXXXXX")
mkdir -p "${QFW_RUN_DIR}"
export QFW_SHARED_ROOT=${QFW_SHARED_ROOT:-/workspace/qfw-container-base}
source "${QFW_INSTALL_PREFIX:-/opt/openqse/qfw}/bin/qfw-activate" \
    --venv "${QFW_VENV:-/opt/openqse/qfw-venv}"

cleanup() {
    status=$?
    trap - EXIT
    teardown_status=0
    qfw-teardown --run-dir "${run_dir}" || teardown_status=$?
    qfw-deactivate || teardown_status=$?
    if [[ ${teardown_status} -ne 0 ]]; then
        printf 'QFw cleanup failed (%s); diagnostics: %s\n' \
            "${teardown_status}" "${run_dir}" >&2
        if [[ ${status} -eq 0 ]]; then
            status=${teardown_status}
        fi
    fi
    exit "${status}"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

qfw-setup --run-dir "${run_dir}" --site-config "${QFW_SITE_CONFIG:-/etc/openqse/qfw/site.yaml}"
uv run --active --no-sync --python "${VIRTUAL_ENV}/bin/python" \
    qfw-srun --run-dir "${run_dir}" --nodes=1 --ntasks=1 -- -m "${worker_module}" "${worker_args}"
