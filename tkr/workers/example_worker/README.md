# example_worker Worker
    
## Introduction

This is the root for a custom worker you just created.
Conceptually, a worker is a wrapper around some functionality you want to use in your graphs.
It can be as simple as a single function or a whole library.
The only requirement is that it has to be wrapped in a way that tierkreis can understand,
e.g. using the Worker class for python workers or an IDL file for external workers.
How to use existing functionality we will cover further down.

Workers act as an independent project, which means they don't need to share dependencies with you graph code.
This worker is automatically included in your top level project as a dependency so you can immediately use it in your graphs.
If you want to decouple it from your graph code, you can either define it as a workspace member
or publish it to a package index and install it as a dependency in your graph project instead of using a path dependency.

## Project structure

The recommend structure for a python worker is as follows:
```
example_worker/
├── api/
│    ├── api.py
│    └── pyproject.toml
├── tkr_example_worker_impl/
│    ├── lib/ (not generated)
│    ├── __init__.py
│    ├── impl.py
│    └── main.py
├── README.md (this file)
└── pyproject.toml
```
The `tkr_example_worker_impl` directory contains the worker tasks in `impl.py` which are used during runtime of a workflow.
For this the toplevel pyproject.toml defines a script entry point which points to the `main.py` file.
You should not edit this `main.py`.
The `lib` directory is a placeholder for your library code.
If you're using a preexisting codebase we recommend move your code base there and point the worker tasks at it.
You than can import the functionality in `worker_impl.py`.
The source code is packaged as `trk-example_worker-impl`.


The `api` directory contains the stubs which are used during construction of a graph.
They can be generated using the `trk init stubs` command and are not required to be present during runtime.
They are encapsulated in a separate package `tkr-example_worker` to avoid unnecessary dependencies during construction of the worker.
The worker project depends on the api but not the other way around,
so you can for example use the api in your graph code without having to install the whole worker.


## Developing your worker

Your new worker consist of two parts which are defined in the `worker_impl.py`:

1. The preabmle, declaring, your worker.
The name must be the same as the top level worker_directory
```python
worker = Worker(example_worker)
```

2. Task definitions using `@worker.task()`, make sure to use type hints, 
```python
@worker.task()
def your_worker_task(value: int) -> int:
    return value
```

To add more functionality to your worker, simply declare more `@worker.task()`s.
For this you can import existing code and wrap it in a function or copy minimal functionality there.

## Using your worker in a graph

Before you can use your worker in a graph you need to update it api with the `tkr init stubs` command.
This will generate api stubs for all functions annotated with `@worker.task()` into `api.py`.
To update the project settings make sure to `uv sync`.

You can use them as a task in the graph:
```python
def your_graph() -> Workflow[TKR[int], TKR[int]]:
    g = Graph(TKR[int], TKR[int])
    out = g.task(your_worker_task(g.inputs))
    g.finish_with_outputs(out)
    return g
```
If you used the `tkr init project` example, you will see a working graph code example in `tkr/graphs/main.py`.

### A note on imports

There are two ways to import your task code:
1. Using the `tkr-example_worker` package.
This is the recommended way, allowing you to import tasks as:
```python
from example_worker import your_worker_task
```
This will only work if you `uv add` one of the packages.
By default, the `tkr init project` will do this.

2. Importing the local python module
```python
from tkr.workers.example_worker import your_worker_task
```
This will only work if your code is locally available, and might need to run as python module (-m).

