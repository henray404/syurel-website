# EDA — RiSID annotations

Run 2026-08-15 on `annotations_7cat.json` and `annotations_2cat.json`
(7.9 MB each, from Zenodo record 16927238). **Images were not downloaded** — the
annotations are 8 MB against 5.6 GB of pixels, and every question that decides
whether this dataset is usable is answerable from the annotations alone.

---

## 1. Scale

| | |
|---|---|
| images | 7,356 |
| annotations | 8,022 |
| annotations per image | **1.09** |
| resolution | 1024×1024, uniform |
| images with ≥1 annotation | 7,356 (100%) |
| objects per image | median **1**, max 12 |

---

## 2. Object size — the decisive number

| percentile | mask area (px) | equivalent side (px) |
|---|---|---|
| p5 | 87 | 9.3 |
| p25 | 179 | 13.4 |
| **median** | **320** | **17.9** |
| p75 | 599 | 24.5 |
| p95 | 3,438 | 58.6 |
| max | 401,628 | 634 |

Median object is **0.03% of the frame**.

By COCO convention, at native 1024×1024:

| size class | count | share |
|---|---|---|
| small (<32²) | 6,678 | **83.2%** |
| medium (<96²) | 1,254 | 15.6% |
| large (≥96²) | 90 | 1.1% |

**RiSID is overwhelmingly a small-object dataset** — the condition Task 4 measured
as most fragile under downscaling.

### What survives downscaling

| target | median side | <3 px | <2 px | <1 px |
|---|---|---|---|---|
| 640 | 11.2 px | 0.2% | 0.1% | 0.1% |
| 512 | 9.0 px | 0.5% | 0.2% | 0.1% |
| 416 | 7.3 px | **1.5%** | 0.3% | 0.1% |

**Better than feared.** Even at 416 the median object is ~7 px across and only
1.5% fall below 3 px. Downscaling to 416 does not annihilate this dataset — the
long tail is thin. That supports 416 remaining viable on a Pi, and is consistent
with the measured 7.6% debris-IoU loss for LR-ASPP at 416.

---

## 3. Class balance

7-category split:

| class | count | share | median area |
|---|---|---|---|
| `o_pla` (other plastics) | 4,542 | **56.6%** | 229 px |
| `o_bag` | 1,151 | 14.3% | 361 px |
| `bottle` | 1,112 | 13.9% | 684 px |
| `bag` | 429 | 5.3% | 825 px |
| `food_pack` | 334 | 4.2% | 789 px |
| `non_pla` | 255 | 3.2% | 436 px |
| `o_bottle` | 199 | 2.5% | 256 px |

2-category split: **plastics 96.8%, non-plastics 3.2%.**

Two things follow. The dominant class is a catch-all "other plastics", so the
7-category detail is thinner than it looks — using the 2-category file loses
almost nothing. And **`non_pla` is only 3.2%**, which sharply reduces the weight
of the §9.1 schema decision in `datasets.md`: whether non-plastics map to
`debris` or `background` moves 3% of objects, not a third of the dataset.

---

## 4. The incompatibility with RIPTSeg

This is the finding that changes plans.

| | RIPTSeg | RiSID |
|---|---|---|
| foreground coverage | **18.5%** | **0.10%** |
| objects per image | dense mats | 1.09 |
| median object | large aggregations | 320 px (0.03% of frame) |
| view | oblique, at a barrier | nadir, from a bridge |
| what it depicts | trash accumulating against a structure | isolated items drifting past |

**A ~180× difference in foreground coverage.** These datasets do not describe the
same visual problem. RIPTSeg is dense mats against an interceptor; RiSID is one
bottle drifting under a bridge.

Consequences:

1. **Do not naively pool them.** A model trained on the union sees two
   incompatible worlds. The per-dataset sampling weights already in the configs
   are necessary, not optional — and per-dataset validation IoU (already logged
   by `train.py`) is the check that says whether one is poisoning the other.
2. **The `clump` heuristic behaves in opposite ways.** On RIPTSeg it promoted
   14.9% of labelled pixels to `clump`; on RiSID, with a 320 px median object
   against a 0.5%-of-frame threshold, it will promote **almost nothing**. The same
   config yields a different effective schema per dataset — an argument for the
   collapsed 3-class schema across the board.
3. **RiSID is the better proxy for "trash flux past a point"** (the rainfall
   correlation use case); RIPTSeg is the better proxy for "accumulation against a
   structure" (the blockage alert). They serve the two different use cases in the
   brief, and that is the honest way to use them.

---

## 5. Two bugs this EDA caught

Both were in code already written and tested, and neither was catchable without
the real annotations.

### 5.1 Group-aware splitting was a no-op on RiSID

`configs/datasets/risid.yaml` had `group_from: stem_prefix`. Filenames look like:

```
20221007124922_d.flv20221007124922_d_001255_6_0.png
```

Stripping the last `_`-token left **7,332 groups for 7,356 images** — one group
per image, so grouping did nothing. Meanwhile **90.5% of adjacent frame pairs
within a video are under 10 frames apart**. Those near-duplicates would have been
dealt into train and val at the same time, inflating every reported metric.

Fixed with a `regex` group mode capturing everything before the frame counter:
**279 real video groups, mean 26 images each.**

### 5.2 `.stem` cut filenames at an embedded dot

`samples()` passes a path with the extension already removed; `_group_key` then
called `Path.stem` again. Python treats the last dot as a suffix boundary, and
RiSID filenames embed `.flv` mid-name, so the key collapsed to
`20221007124922_d`.

On RiSID this *accidentally* produced roughly correct video grouping — worse than
an outright failure, because it looks right while being one filename convention
away from silently regrouping.

---

## 6. Verdict on RiSID

**Keep it, with eyes open.**

- 7,356 images with real polygon masks is still the largest mask source available,
  and object sizes survive downscaling better than expected.
- The 2-category annotation file is sufficient; the 7-category detail is dominated
  by a catch-all class.
- **It must not be pooled naively with RIPTSeg** — 180× coverage difference.
- Water is still unlabelled here, so the SAM pseudo-labelling step remains
  required, and RIPTSeg remains the only source of ground-truth water to score it
  against.
- The 5.6 GB image download is the remaining cost; on this connection that needs
  the chunked downloader.

---

## 7. Reproducing

```bash
curl -L -o data/raw/risid/annotations_7cat.json \
  "https://zenodo.org/records/16927238/files/annotations_7cat.json?download=1"
curl -L -o data/raw/risid/annotations_2cat.json \
  "https://zenodo.org/records/16927238/files/annotations_2cat.json?download=1"
```

Do not use `curl -C -` on a partially written file from a concurrent download:
that appends onto corrupt bytes and yields invalid JSON while still exiting 0.
