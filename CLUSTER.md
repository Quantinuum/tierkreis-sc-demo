# Running on an existing QFw-SLURM cluster

The cluster supplies Slurm, QFw/DEFw, provider services and access. This
repository supplies Python graphs, workers and example data. **There is no
application Docker image to build.** Docker is only the local substitute for
an operator-managed cluster to which an application user normally has no
administrative access.

## 1. Operator prerequisites

The operator must provide:

- Working Slurm allocations and an authorized user/account.
- QFw activation, directory, gateway, scheduler integration and selected QPM.
- A compatible Linux Python environment with QFw and access to shared storage.
- Compatible Tierkreis Rust runtime/Python bindings and viewer assets, including
  support for the generic `tkr serve --host` command.
- Optionally an OTLP/gRPC collector accessible to workers on port 4317.

For this guide, the intended Tierkreis release includes the frontend/server
fixes and `tierkreis._tierkreis.flush_traces`. The current source dependency is
a temporary exception described below. It must also include `tkr run --profile`,
`--timeout`, CLI trace flushing and the relative file-storage-root fix.
No Tierkreis or cluster patches are
applied by this repository.

## 2. Local virtual cluster: commands you run

Skip this section on an already-provisioned real cluster.
Run these commands in the **QFw-SLURM-Cluster checkout**, not this project:

```sh
cd /Users/philipp.seitz/Projects/QFw-SLURM-Cluster
./do_configure.sh --telemetry --qfw-build-jobs 2
./do_build.sh --no-cache
```

Configure writes the image name, source refs, shared-workspace path and telemetry
selection into `qfw-install.env` and `.env`. Build creates that configured
cluster image; `--no-cache` reruns every Docker layer. At the inspected
`71738f7` checkout, the upstream Dockerfile has no persistent cache mounts:
this is a cold build of the cluster's software rather than reuse of local
uv/Cargo build directories. Base images still come from Docker's image store.
The build is substantial; two compilation jobs limit memory pressure.
Do not run the startup command if the build fails.

If downloading a released cluster image instead, use its published image tag
and **matching cluster checkout/release**, configure with `--image NAME:TAG`,
and skip the build. A new Compose checkout with an old image is not supported:
the previously installed image lacked the `aws`, `ibm-156-nh` and
`qec-backline-head` Slurm node definitions, causing `Unable to determine this
slurmd's NodeName` and preventing user/site provisioning.

For this local test, include the optional project mounts before startup:

```sh
export TKR_PROJECT_ROOT=/Users/philipp.seitz/Projects/tierkreis-sc-demo
export QFW_GRAFANA_PORT=127.0.0.1:3002
export COMPOSE_FILE="$PWD/docker-compose.yml:$PWD/docker-compose.telemetry.yml:$TKR_PROJECT_ROOT/deployment/compose.yaml:$TKR_PROJECT_ROOT/deployment/compose.telemetry.yaml"
./do_startup.sh
```

Startup creates containers, registers Slurm and provisions users/site config.
The explicit file list preserves telemetry while adding project mounts.
Use these exports in the same shell for subsequent cluster helper commands.
Grafana uses 3002 because the Tierkreis viewer uses 3000.
Do not recreate containers underneath active jobs.

Check provisioning before installing the application:

```sh
docker compose --env-file qfw-install.env ps -a
docker exec slurmctld sinfo -N
docker exec slurmctld id user-a
docker exec slurmctld test -r /etc/openqse/qfw/site.yaml
docker exec slurmctld chown user-a:user-a \
  /workspace/qfw-container-base/tierkreis-sc-demo/.runtime
```

The overlays are virtual-cluster plumbing only:

- [compose.yaml](deployment/compose.yaml) mounts this checkout, gives runtime
  state and test homes Linux-owned named volumes, and exposes viewer port 3000
  on host loopback. It does not install Python packages.
- [compose.telemetry.yaml](deployment/compose.telemetry.yaml) publishes gRPC
  port 4317 on host loopback for local processes. In-cluster exporters can
  already reach `otel-collector:4317` without this publication.

The overlay's home volume is a macOS bind-mount ownership workaround, not
something an application user should apply to a real cluster.

Start only the services needed for NWQSim, using the operator shell:

```sh
docker exec -it slurmctld bash
source /opt/openqse/qfw/bin/qfw-activate --venv /opt/openqse/qfw-venv
export QFW_SHARED_ROOT=/workspace/qfw-container-base
qfw-site-services --target directory start
qfw-site-services --target nwqsim start
qfw-site-services --target gateway start
qfw-site-services --target directory status
qfw-site-services --target nwqsim status
qfw-site-services --target gateway status
exit
```

Status `UP` alone is not proof that reservations or RPCs work. Inspect site
logs on failures; coordinate service recovery with the operator.

## 3. Install the project, not another cluster image

Clone this project onto shared Linux storage, accessible at the same absolute
path on the coordinator and compute nodes. All ten FCIDUMPs are already in
[examples/He4](examples/He4); no reference checkout or GAMESS is required.

### Intended stable-release setup

Once the assumed compatible Tierkreis release exists, replace the sibling
`tierkreis` source override in [pyproject.toml](pyproject.toml) with that
versioned dependency and regenerate `uv.lock`. This repository has **not**
made that dependency migration yet; the commands below are the intended
release-mode setup, not a claim about the currently published package.

In a site-approved environment that already contains QFw:

```sh
export UV_PROJECT_ENVIRONMENT=/path/to/site-approved/qfw-application-venv
uv --no-cache sync --locked --no-dev --inexact
```

This installs the workspace, including all worker entrypoints, editably.
`--inexact` preserves the environment's separately provisioned QFw packages.
The operator must check dependency compatibility with those packages; it does
not guarantee compatibility by itself. Do not modify a shared environment
without permission or while workflows run.

### Temporary local Tierkreis source

The actual source override is `../tierkreis/tierkreis`, relative to this
project. Make that source available **on Linux where installation occurs**,
including frontend assets and the required trace-flush API. It is not a
permanent cluster dependency. Never copy a macOS native extension to Linux.

Use an empty, explicitly named Cargo output directory for each installation,
and disable uv's download/build cache:

```sh
# Set these to new writable paths on the Linux installation host.
export UV_PROJECT_ENVIRONMENT=/path/to/site-approved/qfw-application-venv
export CARGO_TARGET_DIR="$(mktemp -d /tmp/fmo-tierkreis-target.XXXXXX)"
export CARGO_BUILD_JOBS=2
uv --no-cache sync --locked --no-dev --inexact
```

This builds Tierkreis from the sibling source without reusing a target directory.
A compatible Rust toolchain must be provisioned; the previous Linux validation
used 1.99.1. Retain build errors for diagnosis; remove the specific temporary
target directory after installation if no longer needed.
The Python `tkr serve` command uses the native extension directly, including
for remote viewing with `--host 0.0.0.0`; no separate server binary is needed.

### Installing on the virtual cluster

The host mount alone does not install dependencies. On the new stock cluster
image, first provision Tierkreis and scientific dependencies on every execution
node using the Linux procedure above (release or temporary source).
The old application's preinstalled dependencies were lost when its containers
were removed. **Do not use `--no-deps` on these fresh environments.**

With node-local environments, repeat installation on `slurmctld` and `c1`-`c8`.
With a shared Linux environment, install once and make its executables available
to all workers. The profile currently expects the site's QFw environment
`/opt/openqse/qfw-venv`; changing environments requires changing the launcher's
`QFW_VENV` and worker executable search path together.

For the temporary source setup, the sibling Tierkreis source must also be
mounted/copied into each installation host at the expected path. The optional
Compose overlay intentionally mounts only this project; it does not hide that
temporary extra requirement. Once a stable wheel is used, only this project
needs to be cloned/mounted.

Verify imports from outside the project directory so source shadowing does not
mask missing installations:

```sh
cd /tmp
/path/to/site-approved/qfw-application-venv/bin/python -c \
  'import fmo_vqe, tkr_fmo_chemistry_worker_impl, tkr_fmo_quantum_worker_impl; from tierkreis._tierkreis import flush_traces; print(fmo_vqe.__file__)'
```

## 4. Configure site paths and run

The supplied cluster config assumes the virtual-cluster project path
`/workspace/qfw-container-base/tierkreis-sc-demo`, account `qfw-test`,
provider `nwqsim`, and collector `http://otel-collector:4317`.
For a real site, update:

- [runtime.toml](runtime.toml): run from the shared project root so relative
  asset/launcher paths resolve consistently. Set `logging_config.otel_endpoint`
  to the coordinator's collector (for the virtual cluster,
  `http://otel-collector:4317`). No virtual-cluster absolute project paths
  are baked into this configuration.
- [resource contexts](resource_profiles/qfw-slurm): account, walltime/resources,
  collector endpoint, provider and reservation bounds.
- The worker environment/activation paths if QFw is not at the supplied paths.

Run on the coordinator in the installed application environment, from the
project root. On the virtual cluster, enter with:

```sh
docker exec -it --user user-a \
  --workdir /workspace/qfw-container-base/tierkreis-sc-demo slurmctld bash
export PATH=/opt/openqse/qfw-venv/bin:$PATH
```

Then run the desired example:

First set `settings.shots` to 4096 in each selected input JSON. Shots are a
scientific input, not a CLI override; the quantum profile selects QFw.

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
tkr run -g tkr.graphs.he:workflow -i examples/example_1_He_input.json \
  --profile qfw-slurm --timeout 86400 -o
tkr run -g tkr.graphs.he2:workflow -i examples/example_2_He2_input.json \
  --profile qfw-slurm --timeout 86400 -o
tkr run -g tkr.graphs.he4:workflow -i examples/example_3_He4_input.json \
  --profile qfw-slurm --timeout 86400 -o
```

No outer `salloc` is needed: Tierkreis submits individual task allocations.
These inputs have normal scientific budgets; a full He4 solve may exceed the
one-day coordinator timeout. Choose site-appropriate budgets/walltimes.
Finite-shot convergence is not guaranteed; inspect output diagnostics.

All runs share `.runtime/workflows.sqlite`. Unfinished runs may resume on
startup. Stop workflows and viewers before clearing state. The next workflow
recreates a deleted database; restart the viewer afterwards.

```sh
tkr serve
```

On the virtual cluster, use `--host 0.0.0.0` inside the coordinator and open
<http://localhost:3000>. The server uses the same runtime configuration and
database as `tkr run`, without starting or resuming workflow execution.
Keep the host port loopback-only. On a real site, use an authenticated tunnel;
the viewer has no authentication.

## 5. Telemetry

Rust and Python workers export OTLP/gRPC on 4317; QFw's instrumentation uses
HTTP on 4318. Both feed the same site collector. Grafana for the local setup
is <http://localhost:3002>. In Tempo:

```text
{ resource.service.name = "fmo-vqe" && span.run_id = "RUN-UUID" }
```

Worker services are `fmo_control_worker`, `fmo_chemistry_worker` and
`fmo_quantum_worker`. Allow for export/indexing delays. Runtime logs remain in
the asset/runtime directories; the application does not add an OTLP log exporter.
Configure coordinator export in the runtime's `logging_config.otel_endpoint`
and worker export in the profile environments. For intentionally uninstrumented
runs, remove the configured endpoints and unset the worker endpoint environment.

## Adapting to other backends

An executor selects **where a worker process runs**, not which quantum API it
calls. Placement-only changes can use different compatible executors/resource
contexts without changing scientific graphs.

- Another Slurm site: update shared paths, account/partition and resource contexts.
- Another QFw provider: keep the graph/worker; change `--qpu` in the
  [quantum context](resource_profiles/qfw-slurm/quantum.toml) and provision
  the site's QPM adapter. `QFwBackend()` selects the single QPM bound by
  `QFW_RESERVATIONS`; no duplicate provider string is needed.
- Another scheduler: verify Rust runtime support and replace the Slurm-specific
  allocation/launcher integration. Changing an executor alone does not create
  QFw reservations; the current launcher uses `qfw-srun` and SPANK.
- A non-QFw API: implement a `MeasurementJob -> Measurement` adapter and extend
  profile/worker dispatch consistently (currently `local` or `qfw`).
  Preserve basis rotations, logical Pauli moments, actual shots and standard
  errors. Handle authentication, target-specific compilation and errors;
  never silently fall back to a simulator. Current templates are compiled
  against Aer, not a hardware coupling map.

### Slurm flags do not submit circuits

[quantum.toml](resource_profiles/qfw-slurm/quantum.toml) passes static
`extra_scheduler_args` to `sbatch`. Add site partition/QoS/account flags there;
no new executor is needed. The six QFw options reserve/admit resources:
`--qpu=nwqsim`, `--workload-kind=hybrid`, `--circ-count=1`,
`--max-qubits=10`, `--max-depth=1000`, `--max-shots=4096`.
They are `sbatch`/`salloc` options, not `srun` flags.
The bounds are specified only there and enforced by QFw; there is no duplicated
application-side envelope. Actual shots remain a scientific input.

Actual execution is:

```text
Rust task -> sbatch/QFw reservation -> quantum launch.sh -> qfw-setup
 -> qfw-srun/SPANK obtains QFW_RESERVATIONS -> DEFw worker entrypoint
 -> QFwBackend/QFwEstimatorV2 -> reserved QPM -> NWQSim or hardware adapter
 -> serialized Measurement -> verify outputs -> task-owned teardown
```

The launcher never stops persistent QPM services. It owns teardown because QFw
backend shutdown can exit the interpreter before Tierkreis writes outputs.
Hardware additionally needs operator authorization, protected credentials, a
working device mapping/adapter and target-compatible compilation, not just a
different `--qpu` string.

## Current validation boundary

Before the cluster reset, bounded He run
`01a168b3-adeb-7890-ae76-6a10a99503ca` completed on QFw/NWQSim: 42 Slurm jobs
exited `0:0`, including 24 X/Y/Z measurements at 4096 shots, six COBYLA
evaluations and one orbital iteration. Energy was `-2.889353294970218` Hartree,
with convergence false due to the small budgets. Tempo returned runtime spans.
The first attempt stalled in DEFw reservation transport; operator-approved
NWQSim/gateway recovery allowed the retry to finish. The root cause is not fixed.

This used the earlier patched Linux runtime/application installation, not the
fresh stock cluster or the assumed future Tierkreis release. The runtime volumes
were subsequently deleted. Full-budget cluster examples and real hardware
execution remain unverified.
