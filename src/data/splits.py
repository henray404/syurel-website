"""Deterministic, group-aware train/val/test splits written to disk.

    python -m data.splits
    python -m data.splits --dry-run

Two rules this enforces, both easy to get wrong and expensive to discover late:

1. NEVER split at runtime. The file lists on disk are the split. A split that is
   recomputed each run cannot be compared across experiments.

2. NEVER split within a group. Frames from one video or one site are
   near-duplicates; putting some in train and some in val leaks the answer and
   inflates every metric. Groups come from the adapter (see base.Sample.group).

Splitting is done per dataset, so every dataset appears in train, val AND test.
That is what makes the per-dataset validation IoU in docs/datasets.md section 6
computable -- which is how a dataset that is hurting the mix gets identified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from typing import Any

import yaml

from .convert import PROCESSED_ROOT
from .schema import REPO_ROOT

SPLITS_YAML = REPO_ROOT / "configs" / "splits.yaml"
SPLITS_DIR = REPO_ROOT / "data" / "splits"
SPLIT_NAMES = ("train", "val", "test")


def _hash_order(seed: int, dataset: str, group: str) -> str:
    """Stable pseudo-random sort key. Same inputs -> same key, forever, on any OS.

    Python's hash() is salted per process; md5 is not. This is not security, it is
    reproducibility.
    """
    return hashlib.md5(f"{seed}:{dataset}:{group}".encode()).hexdigest()


def _load_meta(dataset: str) -> list[dict[str, Any]]:
    path = PROCESSED_ROOT / dataset / "meta.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _load_excluded(dataset: str) -> set[str]:
    path = PROCESSED_ROOT / dataset / "excluded.txt"
    if not path.exists():
        return set()
    return {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()}


def _assign(
    by_group: dict[str, list[str]], groups: list[str], ratios: dict[str, float]
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Assign whole groups to splits, largest remaining deficit first.

    Not sequential quota-filling: with few groups that overshoots on the last
    group and leaves val/test empty (RIPTSeg has 6 groups, and 3 groups made it
    fail outright). Not hash-bucketing either: that gives wild ratios at this scale.

    Two passes:
      1. Seed one group into each split, so no split can come out empty whenever
         there are at least as many groups as splits. An empty val set is worse
         than an off-target ratio -- it means no early stopping and no metrics.
      2. Assign the rest to whichever split is furthest below its quota.

    Deterministic: `groups` arrives in a fixed hash order and ties break by the
    fixed SPLIT_NAMES order.
    """
    total = sum(len(v) for v in by_group.values())
    out: dict[str, list[str]] = {s: [] for s in SPLIT_NAMES}
    groups_of: dict[str, list[str]] = {s: [] for s in SPLIT_NAMES}
    quotas = {s: ratios[s] * total for s in SPLIT_NAMES}
    filled = {s: 0.0 for s in SPLIT_NAMES}

    def place(group: str, split: str) -> None:
        out[split].extend(sorted(by_group[group]))
        groups_of[split].append(group)
        filled[split] += len(by_group[group])

    remaining = list(groups)
    if len(remaining) >= len(SPLIT_NAMES):
        for split in SPLIT_NAMES:
            place(remaining.pop(0), split)

    for g in remaining:
        target = max(SPLIT_NAMES, key=lambda s: (quotas[s] - filled[s], -SPLIT_NAMES.index(s)))
        place(g, target)

    return out, groups_of


def split_dataset(
    dataset: str, ratios: dict[str, float], seed: int
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    records = _load_meta(dataset)
    excluded = _load_excluded(dataset)
    kept = [r for r in records if r["sample_id"] not in excluded]

    by_group: dict[str, list[str]] = defaultdict(list)
    for r in kept:
        by_group[r.get("group") or dataset].append(r["sample_id"])

    groups = sorted(by_group, key=lambda g: _hash_order(seed, dataset, g))
    raw, groups_of = _assign(by_group, groups, ratios)
    out = {s: [f"{dataset}/{sid}" for sid in raw[s]] for s in SPLIT_NAMES}

    stats: dict[str, Any] = {
        "dataset": dataset,
        "n_samples": len(kept),
        "n_excluded": len(records) - len(kept),
        "n_groups": len(groups),
        "counts": {s: len(out[s]) for s in SPLIT_NAMES},
        "groups": groups_of,
    }
    if any(not out[s] for s in SPLIT_NAMES):
        empty = [s for s in SPLIT_NAMES if not out[s]]
        stats["warning"] = (
            f"empty split(s) {empty}: only {len(groups)} group(s) available, "
            f"need at least {len(SPLIT_NAMES)}. Group-aware splitting cannot subdivide "
            f"a group without leaking. Use a finer group_from in the dataset YAML."
        )
    elif kept:
        achieved = {s: len(out[s]) / len(kept) for s in SPLIT_NAMES}
        worst = max(SPLIT_NAMES, key=lambda s: abs(achieved[s] - ratios[s]))
        if abs(achieved[worst] - ratios[worst]) > 0.15:
            stats["warning"] = (
                f"ratios are off target ({ {s: round(achieved[s], 2) for s in SPLIT_NAMES} } "
                f"vs {ratios}) because only {len(groups)} whole group(s) could be dealt out. "
                f"Expected at this scale, not a bug -- groups are indivisible."
            )
    return out, stats


def build(dry_run: bool = False) -> dict[str, Any]:
    cfg = yaml.safe_load(SPLITS_YAML.read_text(encoding="utf-8"))
    seed = int(cfg["seed"])
    ratios = {k: float(v) for k, v in cfg["ratios"].items()}
    if abs(sum(ratios.values()) - 1.0) > 1e-6:
        raise SystemExit(f"ratios must sum to 1.0, got {ratios} -> {sum(ratios.values())}")

    datasets = cfg.get("datasets") or sorted(
        p.name for p in PROCESSED_ROOT.glob("*") if (p / "meta.jsonl").exists()
    )
    if not datasets:
        raise SystemExit(
            f"no converted datasets under {PROCESSED_ROOT}. Run `python -m data.convert --all` first."
        )

    merged: dict[str, list[str]] = {s: [] for s in SPLIT_NAMES}
    per_dataset = []
    for ds in datasets:
        out, stats = split_dataset(ds, ratios, seed)
        for s in SPLIT_NAMES:
            merged[s].extend(out[s])
        per_dataset.append(stats)
        if "warning" in stats:
            print(f"[warn] {ds}: {stats['warning']}")

    summary = {
        "seed": seed,
        "ratios": ratios,
        "totals": {s: len(merged[s]) for s in SPLIT_NAMES},
        "per_dataset": per_dataset,
    }

    if dry_run:
        print(json.dumps(summary, indent=2))
        return summary

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    for s in SPLIT_NAMES:
        (SPLITS_DIR / f"{s}.txt").write_text("\n".join(sorted(merged[s])) + "\n", encoding="utf-8")
    (SPLITS_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary["totals"], indent=2))
    print(f"Wrote {SPLITS_DIR}/{{train,val,test}}.txt + summary.json")
    return summary


def demo() -> None:
    """Self-check: python -m data.splits --self-check"""
    ratios = {"train": 0.7, "val": 0.15, "test": 0.15}

    # Stable across runs and machines; sensitive to the seed.
    assert _hash_order(7, "ds", "loc1") == _hash_order(7, "ds", "loc1")
    assert _hash_order(7, "ds", "loc1") != _hash_order(8, "ds", "loc1")

    by_group = {f"g{i}": [f"s{i}_{j}" for j in range(10)] for i in range(10)}
    groups = sorted(by_group, key=lambda g: _hash_order(1, "d", g))
    out, groups_of = _assign(by_group, groups, ratios)

    # Every sample lands exactly once, and no group straddles two splits.
    assert sum(len(v) for v in out.values()) == 100
    placed = [g for s in SPLIT_NAMES for g in groups_of[s]]
    assert sorted(placed) == sorted(by_group), "a group was dropped or duplicated"
    assert all(out[s] for s in SPLIT_NAMES), out

    # Determinism: same call, same answer.
    out2, _ = _assign(by_group, groups, ratios)
    assert out == out2

    print("splits self-check OK")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args(argv)
    if args.self_check:
        demo()
        return 0
    build(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
