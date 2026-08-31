"""Write leave-one-location-out split files for RIPTSeg.

    python scripts/make_folds.py

WHY. The project's single split puts 50 images from loc4 in val and 50 from loc1
in test. Two numbers from two cameras cannot carry a conclusion: adjacent epochs of
one run swing val iou_debris by +-0.1, and loc1 turned out to be a harbour scene
(sky, horizon, ships, breakwater) resembling no other location and no deployment
site. A recipe comparison decided on it is decided on one draw.

RIPTSeg has exactly 6 locations of 50 images each, which is the natural grouping:

    fold i:  test  = loc i           (50 images, never seen)
             val   = loc i+1 wrap    (50 images, early stopping only)
             train = the other 4 locations (200) + the pseudo-labelled datasets

val is a DIFFERENT held-out location from test, so the checkpoint is selected
without ever touching that fold's test images.

Two training lists per fold, so the two recipes run over the same folds and can be
compared as a paired difference:

    train_lama  riptseg(4 loc) + iwhr           -- pseudo-labels as converted
    train_v3    riptseg(4 loc) + iwhr + risid   -- paired with data.relabel in the
                                                  config, which sends iwhr.water
                                                  and risid.background to ignore

Nothing here touches data/splits/{train,val,test}.txt, so runs already trained
stay reproducible.
"""

from __future__ import annotations

from pathlib import Path

SPLITS = Path("data/splits")
PROCESSED = Path("data/processed")
LOCS = [f"loc{i}" for i in range(1, 7)]


def main() -> None:
    everything = []
    for name in ("train", "val", "test"):
        everything += [
            line.strip()
            for line in (SPLITS / f"{name}.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    riptseg: dict[str, list[str]] = {loc: [] for loc in LOCS}
    iwhr: list[str] = []
    for sid in everything:
        ds, _, rest = sid.partition("/")
        if ds == "riptseg":
            riptseg[rest.split("__", 1)[0]].append(sid)
        elif ds == "iwhr":
            iwhr.append(sid)

    # RiSID was converted but never entered a split file, so it is absent from the
    # three lists above and has to be read off disk.
    risid = sorted(
        f"risid/{p.stem}"
        for p in (PROCESSED / "risid" / "masks").glob("*.png")
        if (PROCESSED / "risid" / "images" / f"{p.stem}.jpg").exists()
    )

    for loc, ids in riptseg.items():
        assert len(ids) == 50, f"{loc} has {len(ids)} images, expected 50"
    print(f"riptseg 6x50, iwhr {len(iwhr)}, risid {len(risid)}")

    for i, test_loc in enumerate(LOCS):
        val_loc = LOCS[(i + 1) % len(LOCS)]
        train_locs = [loc for loc in LOCS if loc not in (test_loc, val_loc)]
        train_riptseg = [sid for loc in train_locs for sid in riptseg[loc]]

        fold = f"fold{i + 1}"
        write = {
            f"{fold}_test": riptseg[test_loc],
            f"{fold}_val": riptseg[val_loc],
            f"{fold}_train_lama": train_riptseg + iwhr,
            f"{fold}_train_v3": train_riptseg + iwhr + risid,
            # The ablation nobody ran: is the pseudo-labelled data net positive at
            # all? Every config in the repo assumes IWHR helps, on the strength of
            # one LR-ASPP pair (0.6304 -> 0.6601 val, single split). 200 images of
            # real annotation against 2510 of SAM output is a big bet to leave
            # unmeasured.
            f"{fold}_train_riptonly": train_riptseg,
        }
        held = set(riptseg[test_loc]) | set(riptseg[val_loc])
        for name, ids in write.items():
            if name.startswith(f"{fold}_train"):
                # The entire point of the fold. Cheap to assert; silent and fatal if wrong.
                assert not held & set(ids), f"{name} leaks {test_loc}/{val_loc}"
            assert len(ids) == len(set(ids)), f"{name} has duplicates"
            (SPLITS / f"{name}.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")

        print(
            f"{fold}: test={test_loc} val={val_loc} train={','.join(train_locs)}"
            f"  lama={len(write[f'{fold}_train_lama'])} v3={len(write[f'{fold}_train_v3'])}"
        )


if __name__ == "__main__":
    main()
