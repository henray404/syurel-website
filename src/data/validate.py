"""Validate converted masks and splits, then write a report.

    python -m data.validate
    python -m data.validate --sample 200     # spot-check instead of full scan

Checks, in rough order of how badly each one bites:

  * orphan classes      -- pixel values outside the schema (silently poisons loss)
  * size mismatches     -- mask vs image vs recorded metadata
  * missing files       -- meta.jsonl referencing something that is not there
  * split integrity     -- overlap between splits, group straddling, dangling ids
  * class distribution  -- per dataset and overall
  * pseudo-label state  -- pseudo_pending datasets that never got reviewed

Report goes to docs/data_validation.md and data/processed/validation_report.json.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import numpy as np
from PIL import Image
from tqdm import tqdm

from .convert import PROCESSED_ROOT, load_dataset_cfg
from .schema import REPO_ROOT, Schema, class_pixel_counts, load_schema, read_mask
from .splits import SPLIT_NAMES, SPLITS_DIR

REPORT_MD = REPO_ROOT / "docs" / "data_validation.md"
REPORT_JSON = PROCESSED_ROOT / "validation_report.json"

#: Below this share of debris pixels a "converted" dataset is probably broken --
#: a label_map typo maps everything to background and the run still "succeeds".
DEBRIS_SHARE_FLOOR = 1e-5


def _iter_meta(dataset: str) -> list[dict[str, Any]]:
    path = PROCESSED_ROOT / dataset / "meta.jsonl"
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def check_dataset(dataset: str, schema: Schema, sample: int | None) -> dict[str, Any]:
    ds_dir = PROCESSED_ROOT / dataset
    records = _iter_meta(dataset)
    if sample is not None and len(records) > sample:
        step = max(1, len(records) // sample)
        records = records[::step][:sample]

    errors: list[str] = []
    warnings: list[str] = []
    totals = np.zeros(256, dtype=np.int64)
    orphans: Counter[int] = Counter()
    n_checked = 0
    n_clump_heuristic = 0
    groups: Counter[str] = Counter()

    valid = set(schema.ids) | {schema.ignore_index}

    for rec in tqdm(records, desc=f"validate {dataset}", leave=False):
        mask_path = ds_dir / rec["mask"]
        image_path = ds_dir / rec["image"]

        if not mask_path.exists():
            errors.append(f"{rec['sample_id']}: mask missing ({rec['mask']})")
            continue
        if not image_path.exists():
            errors.append(f"{rec['sample_id']}: image missing ({rec['image']})")
            continue

        mask = read_mask(mask_path)
        with Image.open(image_path) as im:
            iw, ih = im.size

        if (mask.shape[1], mask.shape[0]) != (iw, ih):
            errors.append(
                f"{rec['sample_id']}: mask {mask.shape[1]}x{mask.shape[0]} != image {iw}x{ih}"
            )
        if (mask.shape[1], mask.shape[0]) != (rec.get("width"), rec.get("height")):
            errors.append(
                f"{rec['sample_id']}: mask {mask.shape[1]}x{mask.shape[0]} != "
                f"meta {rec.get('width')}x{rec.get('height')}"
            )

        counts = class_pixel_counts(mask)
        for cid in np.nonzero(counts)[0]:
            if int(cid) not in valid:
                orphans[int(cid)] += int(counts[cid])
        totals += counts
        groups[rec.get("group", "?")] += 1
        n_clump_heuristic += int(bool(rec.get("clump_heuristic")))
        n_checked += 1

    total_px = max(1, int(totals.sum()))
    share = {schema.names[c]: float(totals[c]) / total_px for c in schema.ids}

    if orphans:
        listed = {int(k): int(v) for k, v in orphans.items()}
        errors.append(f"orphan class values present: {listed} -- valid ids are {sorted(valid)}")
    if share.get("debris", 0.0) < DEBRIS_SHARE_FLOOR:
        errors.append(
            f"debris is {share.get('debris', 0.0):.2e} of pixels -- effectively absent. "
            f"Check label_map in configs/datasets/{dataset}.yaml."
        )

    try:
        cfg = load_dataset_cfg(dataset)
    except FileNotFoundError:
        cfg = {}
    water_source = str(cfg.get("water_source", "?"))
    if water_source == "pseudo_pending":
        if not (ds_dir / "pseudolabel.jsonl").exists():
            warnings.append("water_source=pseudo_pending but water_pseudolabel.py has not run")
        elif not (ds_dir / "excluded.txt").exists():
            warnings.append(
                "pseudo-labels exist but review has not been applied "
                f"(`python -m data.review --dataset {dataset} --apply`) -- "
                "unreviewed water is in the training data"
            )
    if share.get("water", 0.0) < 1e-4 and water_source != "none":
        warnings.append(f"water is {share.get('water', 0.0):.2e} of pixels; expected far more")

    return {
        "dataset": dataset,
        "n_records": len(records),
        "n_checked": n_checked,
        "n_groups": len(groups),
        "n_clump_heuristic": n_clump_heuristic,
        "water_source": water_source,
        "class_share": {k: round(v, 6) for k, v in share.items()},
        "orphan_values": {int(k): int(v) for k, v in orphans.items()},
        "errors": errors,
        "warnings": warnings,
    }


def check_splits() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    lists: dict[str, set[str]] = {}
    for s in SPLIT_NAMES:
        p = SPLITS_DIR / f"{s}.txt"
        if not p.exists():
            warnings.append(f"{p} missing -- run `python -m data.splits`")
            lists[s] = set()
            continue
        lists[s] = {ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()}

    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        overlap = lists.get(a, set()) & lists.get(b, set())
        if overlap:
            errors.append(f"{a}/{b} overlap on {len(overlap)} ids, e.g. {sorted(overlap)[:3]}")

    # A group must live in exactly one split, else val leaks into train.
    group_split: dict[tuple[str, str], str] = {}
    straddling: set[str] = set()
    meta_cache: dict[str, dict[str, str]] = {}
    for s in SPLIT_NAMES:
        for entry in sorted(lists.get(s, set())):
            ds, _, sid = entry.partition("/")
            if ds not in meta_cache:
                try:
                    meta_cache[ds] = {r["sample_id"]: r.get("group", "?") for r in _iter_meta(ds)}
                except FileNotFoundError:
                    meta_cache[ds] = {}
            group = meta_cache[ds].get(sid)
            if group is None:
                errors.append(f"{s}: {entry} is not in {ds}/meta.jsonl")
                continue
            key = (ds, group)
            if key in group_split and group_split[key] != s:
                straddling.add(f"{ds}/{group}")
            group_split.setdefault(key, s)
    if straddling:
        errors.append(
            f"{len(straddling)} group(s) straddle splits (leakage): {sorted(straddling)[:5]}"
        )

    return {
        "counts": {s: len(lists.get(s, set())) for s in SPLIT_NAMES},
        "errors": errors,
        "warnings": warnings,
    }


def _md(report: dict[str, Any], schema: Schema) -> str:
    header = " | ".join(schema.names[c] for c in schema.ids)
    lines = [
        "# Data validation report",
        "",
        f"Generated {report['generated_at']} by `python -m data.validate`.",
        "",
        f"**{report['n_errors']} error(s), {report['n_warnings']} warning(s).**",
        "",
        "## Per dataset",
        "",
        f"| dataset | samples | groups | {header} | clump(heur) | water source | errors |",
        "|---|---|---|" + "---|" * len(schema.ids) + "---|---|---|",
    ]
    for d in report["datasets"]:
        shares = " | ".join(f"{d['class_share'].get(schema.names[c], 0.0):.4f}" for c in schema.ids)
        lines.append(
            f"| {d['dataset']} | {d['n_checked']} | {d['n_groups']} | {shares} | "
            f"{d['n_clump_heuristic']} | {d['water_source']} | {len(d['errors'])} |"
        )

    lines += ["", "## Splits", "", "| split | samples |", "|---|---|"]
    for s, n in report["splits"]["counts"].items():
        lines.append(f"| {s} | {n} |")

    if report["n_errors"]:
        lines += ["", "## Errors", ""]
        for d in report["datasets"]:
            lines += [f"- **{d['dataset']}**: {e}" for e in d["errors"]]
        lines += [f"- **splits**: {e}" for e in report["splits"]["errors"]]

    if report["n_warnings"]:
        lines += ["", "## Warnings", ""]
        for d in report["datasets"]:
            lines += [f"- **{d['dataset']}**: {w}" for w in d["warnings"]]
        lines += [f"- **splits**: {w}" for w in report["splits"]["warnings"]]

    lines += [
        "",
        "## Reading this",
        "",
        "- Class shares are pixel fractions. Water dominating at 0.85-0.95 is expected, and is",
        "  exactly why pixel accuracy is banned as a headline metric.",
        "- `clump(heur)` counts masks whose clump class came from the connected-component",
        "  heuristic rather than from annotation. Those labels are weaker than the rest.",
        "- Any orphan class value is a hard error: a mask carries a pixel value the schema does",
        "  not define, which silently corrupts the loss.",
        "",
    ]
    return "\n".join(lines)


def run(sample: int | None = None) -> dict[str, Any]:
    schema = load_schema()
    datasets = sorted(p.name for p in PROCESSED_ROOT.glob("*") if (p / "meta.jsonl").exists())
    if not datasets:
        raise SystemExit(f"nothing converted under {PROCESSED_ROOT}")

    results = [check_dataset(d, schema, sample) for d in datasets]
    splits = check_splits()

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datasets": results,
        "splits": splits,
        "n_errors": sum(len(d["errors"]) for d in results) + len(splits["errors"]),
        "n_warnings": sum(len(d["warnings"]) for d in results) + len(splits["warnings"]),
    }

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(_md(report, schema), encoding="utf-8")

    print(f"{report['n_errors']} error(s), {report['n_warnings']} warning(s)")
    print(f"Wrote {REPORT_MD} and {REPORT_JSON}")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--sample", type=int, default=None, help="check only ~N images per dataset")
    ap.add_argument("--strict", action="store_true", help="exit non-zero if any error was found")
    args = ap.parse_args(argv)
    report = run(sample=args.sample)
    return 1 if (args.strict and report["n_errors"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
