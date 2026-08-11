"""Manual review loop for pseudo-labelled water.

    python -m data.review --dataset risid           # 1. write the verdict CSV
    #    ... open review/risid/ , flip through overlays, edit the CSV ...
    python -m data.review --dataset risid --apply   # 2. exclude what you rejected

The CSV is deliberately dumb: three columns, edit in Excel or any text editor.
Rows are sorted worst-first (auto-flagged, then lowest SAM score) so the review
budget goes where it pays. Auto-flagged rows are left BLANK, not pre-filled with
"ok" -- a blank verdict counts as unreviewed and is excluded, so skipping the
review cannot silently promote junk into the training set.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .convert import PROCESSED_ROOT
from .water_pseudolabel import REVIEW_ROOT

VALID = {"ok", "reject", ""}


def _load_pseudo(dataset: str) -> list[dict[str, Any]]:
    path = PROCESSED_ROOT / dataset / "pseudolabel.jsonl"
    if not path.exists():
        raise SystemExit(
            f"{dataset}: no {path}. Run `python -m data.water_pseudolabel --dataset {dataset}` first."
        )
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def verdict_path(dataset: str) -> Path:
    return REVIEW_ROOT / f"{dataset}_verdict.csv"


def write_template(dataset: str, *, overwrite: bool = False) -> Path:
    out = verdict_path(dataset)
    if out.exists() and not overwrite:
        raise SystemExit(
            f"{out} already exists -- refusing to overwrite your review work. "
            f"Pass --overwrite if you really mean it."
        )

    rows = _load_pseudo(dataset)
    # Worst first: flagged before clean, then ascending SAM score.
    rows.sort(key=lambda r: (r.get("auto_flag", "") == "", float(r.get("sam_score", 0.0))))

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "verdict", "note"])
        for r in rows:
            flag = r.get("auto_flag", "")
            note = (
                f"auto:{flag} water_frac={r.get('water_frac')} score={r.get('sam_score')}"
                if flag
                else ""
            )
            # Blank verdict on flagged rows forces a human to look at them.
            w.writerow([r["sample_id"], "" if flag else "ok", note])

    n_flagged = sum(1 for r in rows if r.get("auto_flag"))
    print(
        f"Wrote {out} ({len(rows)} rows, {n_flagged} auto-flagged and left blank).\n"
        f"Overlays: {REVIEW_ROOT / dataset}\n"
        f"Set verdict to 'ok' or 'reject' for every blank row, then run:\n"
        f"  python -m data.review --dataset {dataset} --apply"
    )
    return out


def apply(dataset: str) -> dict[str, Any]:
    path = verdict_path(dataset)
    if not path.exists():
        raise SystemExit(f"{path} not found. Run without --apply first to generate it.")

    excluded: list[str] = []
    counts = {"ok": 0, "reject": 0, "unreviewed": 0}
    with path.open(encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=2):
            v = (row.get("verdict") or "").strip().lower()
            if v not in VALID:
                raise SystemExit(f"{path}:{i}: verdict must be ok/reject/blank, got {v!r}")
            sample_id = (row.get("file") or "").strip()
            if not sample_id:
                continue
            if v == "ok":
                counts["ok"] += 1
            else:
                counts["reject" if v == "reject" else "unreviewed"] += 1
                excluded.append(sample_id)

    out = PROCESSED_ROOT / dataset / "excluded.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(sorted(excluded)) + ("\n" if excluded else ""), encoding="utf-8")

    print(json.dumps({"dataset": dataset, **counts, "excluded_file": str(out)}, indent=2))
    if counts["unreviewed"]:
        print(
            f"\nNOTE: {counts['unreviewed']} rows are still blank and are being EXCLUDED. "
            f"That is the safe default, not an error -- but if you meant to keep them, "
            f"fill in 'ok' and re-run --apply."
        )
    return {"dataset": dataset, **counts}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--apply", action="store_true", help="read the CSV and write excluded.txt")
    ap.add_argument("--overwrite", action="store_true", help="regenerate the CSV from scratch")
    args = ap.parse_args(argv)

    if args.apply:
        apply(args.dataset)
    else:
        write_template(args.dataset, overwrite=args.overwrite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
