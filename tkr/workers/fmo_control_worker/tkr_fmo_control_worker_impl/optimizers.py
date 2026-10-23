from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize

from fmo_vqe.models import Evaluation


@dataclass
class Proposal:
    parameters: list[float]
    done: bool
    success: bool
    message: str


class NeedsEvaluation(Exception):
    def __init__(self, parameters: list[float]) -> None:
        self.parameters = parameters


def propose_cobyla(
    initial: list[float], history: list[Evaluation], tolerance: float, budget: int
) -> Proposal:
    if not initial:
        return Proposal([], True, True, "No amplitude parameters")
    if budget < len(initial) + 2:
        raise ValueError(
            f"COBYLA requires at least {len(initial) + 2} evaluations for "
            f"{len(initial)} parameters; increase amplitude_budget"
        )
    cursor = 0

    def objective(parameters: NDArray[np.float64]) -> float:
        nonlocal cursor
        requested = parameters.tolist()
        if cursor == len(history):
            raise NeedsEvaluation(requested)
        recorded = history[cursor]
        precision = 8 * np.finfo(float).eps
        if not np.allclose(
            parameters, recorded.parameters, rtol=precision, atol=precision
        ):
            raise ValueError(
                "COBYLA replay diverged from the recorded objective sequence"
            )
        cursor += 1
        return recorded.energy

    try:
        result = minimize(
            objective,
            np.asarray(initial),
            method="COBYLA",
            bounds=[(-np.pi, np.pi)] * len(initial),
            tol=tolerance,
            options={"maxiter": budget},
        )
    except NeedsEvaluation as request:
        return Proposal(request.parameters, False, False, "Objective requested")
    return Proposal(result.x.tolist(), True, bool(result.success), str(result.message))
