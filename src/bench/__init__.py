"""Model comparison harness.

    python -m bench.cost       params / FLOPs / disk / CPU latency -- no data needed,
                               runnable on a Raspberry Pi
    python -m bench.accuracy   per-class IoU per resolution -- needs trained checkpoints
    python -m bench.report     merges both JSONs into docs/model_comparison.md

cost.py is deliberately independent of accuracy.py: the cost table is the half
that can be produced before any dataset is downloaded, and it is the half that
has to run on the target device.
"""
