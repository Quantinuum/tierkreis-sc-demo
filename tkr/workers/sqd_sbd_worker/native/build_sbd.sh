#!/usr/bin/env bash
# Build the SBD `diag` driver using main.cc, tierkreis.hpp and a pinned SBD checkout.
#
# Linux: MPI C++, OpenMP, OpenBLAS, pkg-config and nlohmann-json headers.
# macOS: Homebrew open-mpi, libomp, pkg-config and nlohmann-json; Accelerate for BLAS.
set -euo pipefail

native_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_url=${SBD_REPO_URL:-https://github.com/r-ccs-cms/sbd.git}
sbd_commit=${SBD_COMMIT:-d3210615ec36581ec3a286b8e339492f20b4b529}
sbd_dir=${SBD_DIR:-${native_dir}/sbd}
output=${SBD_DIAG:-${native_dir}/diag}

if command -v mpicxx >/dev/null 2>&1; then
    compiler=mpicxx
elif command -v mpic++ >/dev/null 2>&1; then
    compiler=mpic++
else
    echo "No MPI C++ compiler wrapper (mpicxx or mpic++) was found." >&2
    exit 1
fi

if [[ ! -d ${sbd_dir}/.git ]]; then
    git clone --quiet "${repo_url}" "${sbd_dir}"
fi
if ! git -C "${sbd_dir}" cat-file -e "${sbd_commit}^{commit}" 2>/dev/null; then
    git -C "${sbd_dir}" fetch --quiet origin
fi
git -C "${sbd_dir}" -c advice.detachedHead=false checkout --quiet "${sbd_commit}"

if ! command -v pkg-config >/dev/null 2>&1 || ! pkg-config --exists nlohmann_json; then
    echo "nlohmann-json headers and pkg-config are required (macOS: brew install nlohmann-json pkg-config; Debian/Ubuntu: apt install nlohmann-json3-dev pkg-config)." >&2
    exit 1
fi
read -r -a json_flags <<<"$(pkg-config --cflags nlohmann_json)"
flags=(-std=c++17 -O3 -I"${native_dir}" -I"${sbd_dir}/include" "${json_flags[@]}")
if [[ $(uname -s) == Darwin ]]; then
    libomp=${LIBOMP_PREFIX:-$(brew --prefix libomp 2>/dev/null || true)}
    if [[ -z ${libomp} || ! -f ${libomp}/include/omp.h ]]; then
        echo "libomp is required on macOS: brew install open-mpi libomp" >&2
        exit 1
    fi
    flags+=(-Xpreprocessor -fopenmp -I"${libomp}/include")
    libs=(-L"${libomp}/lib" -lomp -Wl,-rpath,"${libomp}/lib" -framework Accelerate)
else
    flags+=(-fopenmp)
    libs=(-lopenblas)
fi

"${compiler}" "${flags[@]}" "${native_dir}/main.cc" -o "${output}" "${libs[@]}"
echo "Built ${output} (SBD ${sbd_commit})"
