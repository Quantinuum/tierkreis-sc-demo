from tierkreis.worker import Worker

from sqd_sbd.models import Problem, SamplesPort, Settings, WalkerTask
from tkr_sqd_quantum_worker_impl import circuits, sampling

worker = Worker("sqd_quantum_worker")


@worker.task()
def sample_lucj(task: WalkerTask, problem: Problem, settings: Settings) -> SamplesPort:
    """Build and sample one walker's reference Qiskit LUCJ circuit."""
    circuit = circuits.lucj_circuit(
        task.parameters,
        problem,
        settings.n_lucj_layers,
        settings.use_reset_mitigation,
    )
    return SamplesPort(
        sampling.sample(
            circuit,
            settings.shots,
            settings.use_reset_mitigation,
            compilation=settings.compilation,
        )
    )
