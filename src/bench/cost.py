"""Cost side of the model comparison: params, FLOPs, disk size, CPU latency.

    python -m bench.cost                      # every model in the config
    python -m bench.cost --model lraspp_mnv3
    python -m bench.cost --resolutions 640 512 416 --runs 30

RUNNABLE ON A RASPBERRY PI. This module deliberately needs no dataset, no
checkpoint, no CUDA, and no smp unless a listed model requires it. Copy the repo
to the Pi, `pip install torch torchvision pyyaml`, run it, copy back
bench/cost.json.

Latency is the number that decides deployment, and it must be measured on the
target. A desktop figure predicts a Pi figure badly: different core count,
different SIMD width, no AVX-512, far less memory bandwidth, and thermal
throttling under sustained load. Treat any non-target measurement as indicative
of ordering at best.

Measurement hygiene:
  * single thread by default (`--threads 1`), because a deployed unit runs video
    decode and other work alongside the model, and multi-threaded numbers on a
    16-thread desktop flatter the heavy models most
  * warmup iterations discarded (lazy init, allocator warmup, autotune)
  * report p50 and p90, not just the mean -- a frame budget is set by the tail
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import yaml

from data.schema import REPO_ROOT, load_schema
from models import build_model

BENCH_DIR = REPO_ROOT / "bench"
DEFAULT_CONFIG = REPO_ROOT / "configs" / "bench.yaml"
DEFAULT_RESOLUTIONS = (640, 512, 416)


def host_info() -> dict[str, Any]:
    cpu = platform.processor() or platform.machine()
    # /proc/cpuinfo carries the real name on a Pi, where platform.processor() is
    # usually empty or just "aarch64".
    model_name = ""
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith(("model name", "Model")):
                model_name = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass

    return {
        "cpu": model_name or cpu,
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_threads": torch.get_num_threads(),
    }


def count_params(model: torch.nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


def disk_size_mb(model: torch.nn.Module, tmp: Path) -> float:
    """Serialised state_dict size -- what actually ships to the device."""
    tmp.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), tmp)
    mb = tmp.stat().st_size / 1e6
    tmp.unlink(missing_ok=True)
    # 3 dp, not 2: at 2 dp anything under ~5 KB reports a flat 0.0 MB, which reads
    # as "not measured" rather than "very small".
    return round(mb, 3)


def count_gflops(model: torch.nn.Module, size: int) -> float | None:
    """Forward FLOPs via torch's built-in counter (no fvcore/thop/ptflops).

    Returns None when the counter cannot handle the model, rather than guessing.
    """
    try:
        from torch.utils.flop_counter import FlopCounterMode
    except ImportError:
        return None

    x = torch.randn(1, 3, size, size)
    try:
        counter = FlopCounterMode(display=False)
        with counter, torch.no_grad():
            model(x)
        total = counter.get_total_flops()
    except Exception:
        return None
    # The counter reports a multiply-accumulate as 2 FLOPs, which matches the
    # convention behind the GFLOPs quoted in segmentation papers.
    return round(total / 1e9, 2)


def measure_latency(model: torch.nn.Module, size: int, runs: int, warmup: int) -> dict[str, float]:
    x = torch.randn(1, 3, size, size)
    model.eval()

    with torch.no_grad():
        for _ in range(warmup):
            model(x)

        times: list[float] = []
        for _ in range(runs):
            t0 = time.perf_counter()
            model(x)
            times.append((time.perf_counter() - t0) * 1000.0)

    times.sort()
    # 3 dp for the same reason as disk_size_mb: at 1 dp a sub-millisecond model
    # reports 0.0 ms, which reads as a broken measurement. The report formats
    # these with .0f, so the extra digits cost nothing in the rendered table.
    return {
        "mean_ms": round(statistics.fmean(times), 3),
        "p50_ms": round(times[len(times) // 2], 3),
        "p90_ms": round(times[min(len(times) - 1, int(len(times) * 0.9))], 3),
        "std_ms": round(statistics.pstdev(times), 3) if len(times) > 1 else 0.0,
        "fps": round(1000.0 / max(1e-9, statistics.fmean(times)), 2),
    }


def benchmark_model(
    name: str,
    spec: dict[str, Any],
    n_classes: int,
    resolutions: tuple[int, ...],
    runs: int,
    warmup: int,
) -> dict[str, Any]:
    args = dict(spec.get("args") or {})
    # Never download pretrained weights for a cost benchmark: the numbers are
    # identical either way, and the target device may well be offline.
    args["pretrained"] = False

    model = build_model(name, n_classes=n_classes, **args)
    model.eval()

    entry: dict[str, Any] = {
        "name": name,
        "params": count_params(model),
        "params_m": round(count_params(model) / 1e6, 2),
        "disk_mb": disk_size_mb(model, BENCH_DIR / f".{name}.tmp.pt"),
        "license": spec.get("license", "unknown"),
        "note": spec.get("note", ""),
        "gflops": {},
        "latency": {},
    }

    for size in resolutions:
        entry["gflops"][str(size)] = count_gflops(model, size)
        entry["latency"][str(size)] = measure_latency(model, size, runs, warmup)
        lat = entry["latency"][str(size)]
        print(
            f"  {name:22s} {size:>4d}  {lat['mean_ms']:>8.1f} ms  "
            f"p90 {lat['p90_ms']:>8.1f}  {lat['fps']:>6.2f} fps  "
            f"{entry['gflops'][str(size)]} GFLOPs"
        )
    return entry


def run(
    config: Path = DEFAULT_CONFIG,
    only: str | None = None,
    resolutions: tuple[int, ...] = DEFAULT_RESOLUTIONS,
    runs: int = 20,
    warmup: int = 5,
    threads: int = 1,
) -> dict[str, Any]:
    torch.set_num_threads(threads)
    schema = load_schema()
    n_classes = len(schema.names)

    cfg = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
    models: dict[str, Any] = cfg["models"]
    if only:
        if only not in models:
            raise SystemExit(f"{only!r} not in {config}. Available: {sorted(models)}")
        models = {only: models[only]}

    info = host_info()
    print(f"host: {info['cpu']} | torch {info['torch']} | threads {threads}")
    print(f"resolutions: {list(resolutions)}  runs: {runs} (+{warmup} warmup)\n")

    entries, failures = [], {}
    for name, spec in models.items():
        if spec.get("skip_cost"):
            continue
        try:
            entries.append(benchmark_model(name, spec, n_classes, resolutions, runs, warmup))
        except Exception as exc:
            # One uninstalled optional dependency must not void the whole table.
            print(f"  {name:22s} SKIPPED: {type(exc).__name__}: {exc}")
            failures[name] = f"{type(exc).__name__}: {exc}"

    report = {
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": info,
        "threads": threads,
        "runs": runs,
        "warmup": warmup,
        "resolutions": list(resolutions),
        "is_target_device": bool(cfg.get("is_target_device", False)),
        "models": entries,
        "failures": failures,
    }

    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    out = BENCH_DIR / "cost.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")
    if not report["is_target_device"]:
        print(
            "NOTE: is_target_device is false in the config. These numbers are a PROXY.\n"
            "      Re-run this module on the Pi 5 / Jetson before choosing a model."
        )
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--model", default=None, help="benchmark a single model")
    ap.add_argument("--resolutions", type=int, nargs="+", default=list(DEFAULT_RESOLUTIONS))
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument(
        "--threads",
        type=int,
        default=1,
        help="torch CPU threads. 1 by default -- a deployed unit will not have all cores free.",
    )
    args = ap.parse_args(argv)

    run(
        config=args.config,
        only=args.model,
        resolutions=tuple(args.resolutions),
        runs=args.runs,
        warmup=args.warmup,
        threads=args.threads,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
