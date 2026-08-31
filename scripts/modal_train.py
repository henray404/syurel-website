"""Run a training config on a Modal GPU instead of the laptop.

    modal run scripts/modal_train.py --config configs/train/combined_v2_segformer_b0_640.yaml
    modal run scripts/modal_train.py --config <cfg> --smoke      # 1 step, ~3 min, cheap

Nothing about training changes out here. This file only assembles the filesystem
layout src/train/train.py already expects, then calls it. Local runs stay exactly
as documented in CLAUDE.md.

GPU CHOICE. L4, at Modal's $0.80/hr. T4 is $0.59/hr but roughly 2.5x slower on
this workload and has 16 GB, so the cheaper card finishes LATER and costs MORE
overall. A10 ($1.10) and L40S ($1.95) finish sooner but land at the same total or
worse for a job this size. Override with --gpu if that trade ever changes.

LAYOUT. data/schema.py derives REPO_ROOT from `parents[2]` of its own path, so the
source must sit at /root/repo/src/... for /root/repo/data and /root/repo/runs to
resolve. Both are Volumes; only `runs` is written.
"""

from __future__ import annotations

import json

import modal

REPO = "/root/repo"

image = (
    modal.Image.debian_slim(python_version="3.12")
    # albumentations imports cv2, which wants libglib even in the headless build.
    .apt_install("libglib2.0-0")
    .pip_install(
        # The Linux wheel of torch is already a CUDA build; no index_url needed.
        "torch>=2.4",
        "torchvision>=0.19",
        "albumentations>=1.4",
        "segmentation-models-pytorch>=0.5.0",
        "tensorboard>=2.15",
        "numpy>=1.24",
        "pillow>=10.0",
        "pyyaml>=6.0",
        "opencv-python-headless>=4.8",
        "tqdm>=4.66",
    )
    .add_local_dir("src", f"{REPO}/src")
    .add_local_dir("configs", f"{REPO}/configs")
)

app = modal.App("syurell-train")
data_vol = modal.Volume.from_name("syurell-data")
runs_vol = modal.Volume.from_name("syurell-runs", create_if_missing=True)


@app.function(
    image=image,
    gpu="L4",
    volumes={f"{REPO}/data": data_vol, f"{REPO}/runs": runs_vol},
    timeout=2 * 60 * 60,
)
def train_remote(config_rel: str, smoke: bool = False, overrides: dict | None = None) -> dict:
    import sys
    import threading
    from pathlib import Path

    sys.path.insert(0, f"{REPO}/src")

    import torch
    import yaml

    from train.train import train

    if overrides:
        # Cross-validation needs 12 near-identical configs. Writing 12 YAML files
        # would put the fold wiring in twelve places; patching one base config here
        # keeps it in one. train.py copies the effective config into
        # runs/<name>/config.yaml, so provenance survives either way.
        cfg = yaml.safe_load((Path(REPO) / config_rel).read_text(encoding="utf-8"))
        for dotted, value in overrides.items():
            node = cfg
            *parents, leaf = dotted.split(".")
            for key in parents:
                node = node.setdefault(key, {})
            node[leaf] = value
        config_rel = f"/tmp/{cfg['name']}.yaml"
        Path(config_rel).write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        print(f"[modal] {cfg['name']}: {overrides}", flush=True)

    print(f"[modal] gpu={torch.cuda.get_device_name(0)} torch={torch.__version__}", flush=True)

    # Checkpoints only become durable on commit(). Without this, a container that
    # times out or is preempted throws the whole run away -- so commit on a timer
    # and treat the final commit as a flush, not as the only save.
    stop = threading.Event()

    def flush() -> None:
        while not stop.wait(300):
            try:
                runs_vol.commit()
                print("[modal] volume committed", flush=True)
            except Exception as exc:  # a failed commit must never kill training
                print(f"[modal] commit failed: {exc}", flush=True)

    threading.Thread(target=flush, daemon=True).start()
    try:
        cfg_path = Path(config_rel)
        summary = train(cfg_path if cfg_path.is_absolute() else Path(REPO) / config_rel, smoke=smoke)
    finally:
        stop.set()
        runs_vol.commit()

    run_dir = Path(REPO) / "runs" / str(summary["run"])
    metrics = (run_dir / "metrics.csv").read_text(encoding="utf-8").splitlines()
    return {
        "summary": summary,
        "metrics_header": metrics[0] if metrics else "",
        "metrics_tail": metrics[-5:],
        "files": sorted(p.name for p in run_dir.iterdir()),
    }


#: One entry per cross-validation arm. `split` names the fold training list; the
#: rest are config overrides on top of cv_base.yaml. Keeping the arms here rather
#: than in one YAML each means an arm differs from the baseline in exactly the keys
#: written on its own line, which is what makes the paired difference attributable.
ARM_SPECS: dict[str, dict] = {
    # Baseline: the recipe the project already used, on fold splits.
    "lama": {"split": "lama"},
    # MEASURED WORSE (-0.058 IoU, 1/6 folds). Kept so the ablation stays runnable.
    "v3": {
        "split": "v3",
        "data.relabel": {"iwhr": {"water": "ignore"}, "risid": {"background": "ignore"}},
    },
    # Is the pseudo-labelled data net positive AT ALL? 200 real masks against 2510
    # SAM masks, and the assumption has never been tested on more than one split.
    "riptonly": {"split": "riptonly"},
    # bench/accuracy.json has debris IoU still CLIMBING at the top of its sweep:
    # 0.4164 / 0.4586 / 0.4743 at 416 / 512 / 640. 640 is simply the largest size
    # ever tried. Small debris is where this model fails (IoU 0.172 under 3000 px
    # against 0.525 above), so the untested direction is up. batch 8 because 896 is
    # ~2x the activation memory of 640.
    "res896": {"split": "lama", "data.size": 896, "data.batch_size": 8},
    # Capacity check. The registry has no b1, so b2: ~24M parameters against B0's
    # 3.7M. Expected to do little -- 200 real masks is the binding constraint, not
    # model size -- but this is the cheap way to find out rather than assert.
    # batch 8 for the activation memory.
    "b2": {"split": "lama", "model.name": "segformer_b2", "data.batch_size": 8},
}


@app.local_entrypoint()
def cv(folds: int = 6, arms: str = "lama,v3") -> None:
    """Leave-one-location-out cross-validation, all folds in parallel.

        modal run scripts/modal_train.py::cv --arms lama,riptonly,res896,b1

    Modal runs these as separate containers, so N folds cost the same GPU-hours as
    N sequential folds but finish in the time of the slowest one.
    """
    jobs = []
    for arm in arms.split(","):
        spec = dict(ARM_SPECS[arm])
        split = spec.pop("split")
        for fold in range(1, folds + 1):
            over = {
                "name": f"cv_{arm}_fold{fold}",
                "data.train_split": f"fold{fold}_train_{split}",
                "data.val_split": f"fold{fold}_val",
                **spec,
            }
            jobs.append(("configs/train/cv_base.yaml", False, over))

    print(f"launching {len(jobs)} folds on L4, in parallel")
    results = list(train_remote.starmap(jobs, order_outputs=True, return_exceptions=True))

    print(f"\n{'run':>22s}{'best_val_iou_debris':>22s}{'epochs':>9s}")
    for (_, _, over), r in zip(jobs, results):
        if isinstance(r, Exception):
            print(f"{over['name']:>22s}{'FAILED: ' + type(r).__name__:>22s}")
            continue
        s = r["summary"]
        print(f"{s['run']:>22s}{s['best_score']:>22.4f}{s['epochs_run']:>9d}")
    print("\nFetch every checkpoint with:\n  modal volume get syurell-runs / runs --force")


@app.local_entrypoint()
def main(
    config: str = "configs/train/combined_v2_segformer_b0_640.yaml",
    smoke: bool = False,
) -> None:
    out = train_remote.remote(config, smoke)
    print(json.dumps(out, indent=2, default=str))
    run = out["summary"]["run"]
    print(
        f"\nFetch the checkpoint with:\n"
        f"  modal volume get syurell-runs /{run}/best.pt runs/{run}/best.pt"
    )
