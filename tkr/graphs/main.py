import asyncio
from typing import NamedTuple

from tierkreis._tierkreis import load_runtime_config, new_from_config
from tierkreis.builder import Graph
from tierkreis.models import OpaqueType, TKR, Workflow
from tierkreis.storage import FileStorage, read_outputs

from example_worker import your_worker_task

class GraphInputs(NamedTuple):
    value: TKR[int]


class GraphOutputs(NamedTuple):
    value: TKR[int]


def workflow() -> Workflow[GraphInputs, GraphOutputs]:
    g = Graph(GraphInputs, GraphOutputs)
    out = g.task(your_worker_task(g.inputs.value))
    return g.finish_with_outputs(GraphOutputs(value=out))

async def main() -> None:
    graph = workflow()
    inputs = {"value": 1}
    # loads the default from tierkreis.toml
    config = load_runtime_config()
    runtime = await new_from_config(config)
    with runtime:
        workflow_id = await runtime.save_workflow("my-workflow", graph)
        run_id = await runtime.start_new_run(workflow_id, inputs)
        await runtime.wait_for(run_id, timeout=30)
        output = await runtime.get_outputs(run_id)

    print("Value is: ", output)

if __name__ == "__main__":
    asyncio.run(main())

