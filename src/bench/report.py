"""Merge cost.json + accuracy.json into docs/model_comparison.md.

    python -m bench.cost && python -m bench.report

The tables and PENDING markers are machine-written. The narrative (recommendation,
reasoning, deployment targets) is hand-written and lives in
docs/model_comparison_notes.md, which this file appends verbatim -- so
regenerating the numbers never silently overwrites the analysis.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data.schema import REPO_ROOT, load_schema

from .cost import BENCH_DIR

OUT_MD = REPO_ROOT / "docs" / "model_comparison.md"
NOTES_MD = REPO_ROOT / "docs" / "model_comparison_notes.md"


def _load(name: str) -> dict[str, Any] | None:
    p = BENCH_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _fmt(v: Any, spec: str = ".4f") -> str:
    if v is None:
        return "-"
    if isinstance(v, float) and v != v:  # NaN
        return "n/a"
    if isinstance(v, (int, float)):
        return format(v, spec)
    return str(v)


def build(cost: dict[str, Any] | None, acc: dict[str, Any] | None) -> str:
    schema = load_schema()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    L: list[str] = ["# Model comparison", ""]

    if cost is None:
        L += ["No `bench/cost.json`. Run `python -m bench.cost` first.", ""]
        return "\n".join(L)

    host = cost["host"]
    resolutions = [str(r) for r in cost["resolutions"]]
    proxy = not cost.get("is_target_device", False)

    L += [
        f"Generated {now} by `python -m bench.report`.",
        "",
        "## 0. How to read this",
        "",
        f"- **Cost measured on:** {host['cpu']} ({host['machine']}), "
        f"torch {host['torch']}, **{cost['threads']} thread(s)**, "
        f"{cost['runs']} runs after {cost['warmup']} warmup.",
    ]

    if proxy:
        L += [
            "- **THESE LATENCY NUMBERS ARE A PROXY, NOT THE TARGET.** `is_target_device` is",
            "  false in `configs/bench.yaml`. A Raspberry Pi 5 is roughly an order of",
            "  magnitude slower than this host, with different SIMD width and far less",
            "  memory bandwidth, so **the ordering can reorder**, particularly for the",
            "  attention-based model. Copy the repo to the Pi, run `python -m bench.cost`,",
            "  set `is_target_device: true`, and regenerate before committing to a model.",
        ]
    else:
        L += ["- Latency measured **on the target device**. These numbers decide."]

    L += [
        "- Single-threaded by default: a deployed unit also decodes video and runs the",
        "  inference loop, so it will not have every core free. Multi-threaded numbers on a",
        "  many-core desktop flatter the heaviest models most.",
        "- **Pixel accuracy appears nowhere.** Water is 85-95% of pixels; an all-water model",
        "  scores ~0.9 and detects nothing. Judge on debris IoU and debris recall.",
        "",
        "## 1. Cost",
        "",
        "| model | params (M) | disk (MB) | "
        + " | ".join(f"GFLOPs@{r}" for r in resolutions)
        + " | "
        + " | ".join(f"ms@{r}" for r in resolutions)
        + " | licence |",
        "|---|---|---|" + "---|" * (2 * len(resolutions)) + "---|",
    ]

    for m in cost["models"]:
        gf = " | ".join(_fmt(m["gflops"].get(r), ".1f") for r in resolutions)
        ms = " | ".join(_fmt(m["latency"].get(r, {}).get("mean_ms"), ".0f") for r in resolutions)
        L.append(
            f"| `{m['name']}` | {m['params_m']} | {m['disk_mb']} | {gf} | {ms} | {m['license']} |"
        )

    L += ["", "Latency tail (p90, ms) -- a frame budget is set by the tail, not the mean:", ""]
    L += ["| model | " + " | ".join(f"p90@{r}" for r in resolutions) + " |"]
    L += ["|---|" + "---|" * len(resolutions)]
    for m in cost["models"]:
        p90 = " | ".join(_fmt(m["latency"].get(r, {}).get("p90_ms"), ".0f") for r in resolutions)
        L.append(f"| `{m['name']}` | {p90} |")

    if cost.get("failures"):
        L += ["", "**Not measured:**", ""]
        L += [f"- `{k}`: {v}" for k, v in cost["failures"].items()]

    # --- accuracy -----------------------------------------------------------
    L += ["", "## 2. Accuracy", ""]

    if acc is None:
        L += [
            "**PENDING.** No `bench/accuracy.json` yet.",
            "",
            "Accuracy needs trained checkpoints, which need the datasets downloaded and",
            "converted. Nothing in this section can be filled in before that. Sequence:",
            "",
            "```",
            "python scripts/download.py --dataset riptseg",
            "python -m data.convert --dataset riptseg",
            "python -m data.splits",
            "python -m train.train --config configs/train/baseline.yaml",
            "python -m bench.accuracy",
            "python -m bench.report",
            "```",
            "",
            "**Do not pick a model from the cost table alone.** The cheapest model that",
            "cannot see a sachet is worthless, and that is exactly the trade-off the",
            "resolution sweep exists to expose.",
        ]
    else:
        names = [f"iou_{schema.names[c]}" for c in schema.ids]
        L += [
            f"Split: `{acc['split']}`. Device: {acc['device']}.",
            "",
            "| model | res | mIoU | "
            + " | ".join(n.replace("iou_", "IoU ") for n in names)
            + " | debris P | debris R |",
            "|---|---|---|" + "---|" * len(names) + "---|---|",
        ]
        for m in acc["models"]:
            if m.get("status") != "OK":
                L.append(
                    f"| `{m['name']}` | - | {m.get('status', '?')} | "
                    + " | ".join("-" for _ in names)
                    + " | - | - |"
                )
                continue
            for res, mm in m["by_resolution"].items():
                per = " | ".join(_fmt(mm.get(n)) for n in names)
                L.append(
                    f"| `{m['name']}` | {res} | {_fmt(mm.get('miou'))} | {per} | "
                    f"{_fmt(mm.get('precision_debris'))} | {_fmt(mm.get('recall_debris'))} |"
                )

        L += [
            "",
            "### Small-object trade-off",
            "",
            "Debris IoU lost by downscaling, relative to the largest input. The mIoU column",
            "sits next to it deliberately: when debris collapses and mIoU barely moves, the",
            "aggregate metric is hiding the failure.",
            "",
            "| model | res | debris IoU drop | mIoU drop |",
            "|---|---|---|---|",
        ]
        for m in acc["models"]:
            for res, d in (m.get("debris_iou_drop_pct") or {}).items():
                md = (m.get("miou_drop_pct") or {}).get(res)
                L.append(f"| `{m['name']}` | {res} | {_fmt(d, '.1f')}% | {_fmt(md, '.1f')}% |")

        for m in acc["models"]:
            if m.get("status") in ("PENDING", "NOT_EVALUATED"):
                L += ["", f"- `{m['name']}`: {m.get('status')} -- {m.get('reason', '')}"]

    # --- hand-written narrative --------------------------------------------
    L += ["", "---", ""]
    if NOTES_MD.exists():
        L.append(NOTES_MD.read_text(encoding="utf-8").strip())
    else:
        L += [
            "## 3. Recommendation",
            "",
            f"_No `{NOTES_MD.name}` found. Write the analysis there; this file appends it_",
            "_verbatim so regenerating the numbers never overwrites the reasoning._",
        ]
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, default=OUT_MD)
    args = ap.parse_args(argv)

    md = build(_load("cost.json"), _load("accuracy.json"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
