# SQD quantum worker

Builds one LUCJ sampling circuit per DE walker and samples it. The single task
is `sample_lucj` in context `sqd_quantum`: subprocess locally, Slurm + QFw on
the cluster.
TODO: Think if it's worth to split non-quantum jobs off here
