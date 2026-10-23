#!/usr/bin/env bash
set -euo pipefail

worker_args=$(realpath "${1:?worker argument JSON is required}")
if [[ ! -f ${worker_args} ]]; then
    printf 'Worker argument file does not exist: %s\n' "${worker_args}" >&2
    exit 2
fi
worker_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
run_parent=$(mktemp -d "$(dirname "${worker_args}")/qfw.XXXXXX")
run_dir=${run_parent}/runtime
export QFW_SHARED_ROOT=${QFW_SHARED_ROOT:-/workspace/qfw-container-base}
source "${QFW_INSTALL_PREFIX:-/opt/openqse/qfw}/bin/qfw-activate" \
    --venv "${QFW_VENV:-/opt/openqse/qfw-venv}"

cleanup() {
    status=$?
    trap - EXIT
    teardown_status=0
    qfw-teardown --run-dir "${run_dir}" --keep-run-dir || teardown_status=$?
    qfw-deactivate || teardown_status=$?
    if [[ ${teardown_status} -ne 0 ]]; then
        printf 'QFw cleanup failed (%s); diagnostics: %s\n' \
            "${teardown_status}" "${run_parent}" >&2
        if [[ ${status} -eq 0 ]]; then
            status=${teardown_status}
        fi
    fi
    exit "${status}"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

qfw-setup --site-config "${QFW_SITE_CONFIG:-/etc/openqse/qfw/site.yaml}" \
    --run-dir "${run_dir}"
export FMO_QFW_ACTIVE=1
qfw-srun --run-dir "${run_dir}" --nodes=1 --ntasks=1 -- \
    "${worker_root}/qfw_entrypoint.py" "${worker_args}"
python "${worker_root}/qfw_entrypoint.py" --verify-outputs "${worker_args}"
