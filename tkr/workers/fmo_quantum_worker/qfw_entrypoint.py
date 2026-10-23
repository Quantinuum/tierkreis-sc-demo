import json
import os
import sys
import traceback
from pathlib import Path
from types import TracebackType


def fail_worker(
    exception_type: type[BaseException],
    exception: BaseException,
    trace: TracebackType | None,
) -> None:
    traceback.print_exception(exception_type, exception, trace)
    sys.stderr.flush()
    # DEFw embeds Python and can otherwise report success after an exception.
    os._exit(1)


def verify_outputs(arguments: Path) -> None:
    outputs = json.loads(arguments.read_text())["outputs"]
    if not outputs:
        raise ValueError("Quantum worker requires output paths")
    missing = [path for path in outputs.values() if not Path(path).is_file()]
    if missing:
        raise RuntimeError(f"QFw worker did not produce expected outputs: {missing}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--verify-outputs"]:
        verify_outputs(Path(sys.argv[2]))
    else:
        from tkr_fmo_quantum_worker_impl.main import main

        sys.excepthook = fail_worker
        main()
