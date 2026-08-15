# Phase 1 results — trained models and measured accuracy

Run on 2026-08-15. Everything below is measured on this machine, not estimated.
Hardware: RTX 5050 Laptop (8 GB, sm_120), Ryzen 9 270, torch 2.12.0.dev+cu128.

---

## 1. What was actually run

```
download RIPTSeg (276 MB)  ->  convert 300 imgs  ->  splits 200/50/50
   ->  train 5 runs  ->  evaluate on held-out location  ->  inference demo
```

**Data.** RIPTSeg only. 300 images, 6 locations, 4387 COCO polygons.
Split **by location**: train loc2/3/5/6, val loc4, **test loc1**. Val and test are
locations the model never saw. This is deliberately harder than a random split,
which over 300 near-duplicate frames from fixed cameras would mostly measure
memorisation.

**Class balance after conversion** (share of labelled pixels):
water 75.9%, clump 14.9%, background 6.8%, debris 2.4%. Dataset coverage
(debris/(debris+water)) = 18.5%.

---

## 2. The headline result

**Best model: SegFormer-B0.** Test set = loc1, never seen in training.

| metric | value |
|---|---|
| mIoU | **0.747** |
| debris IoU | **0.474** |
| debris precision | 0.533 |
| debris recall | 0.812 |
| water IoU | 0.803 |

**Best model for a Raspberry Pi: LR-ASPP MobileNetV3** — mIoU 0.726, debris IoU
0.419, and **5.8x faster on CPU** (164 ms vs 945 ms at 512).

Full four-way comparison, cost and accuracy, is in
[docs/model_comparison.md](model_comparison.md).

---

## 3. The finding that mattered most

The 4-class schema produced a **useless debris class**, and fixing it moved the
headline number by 4x.

| schema | test mIoU | test debris IoU |
|---|---|---|
| 4-class (debris + clump separate) | 0.584 | **0.103** |
| 3-class (clump folded into debris) | 0.726 | **0.419** |

`clump` is not annotation — it is the connected-component heuristic in
`src/data/clump.py`. On RIPTSeg, which is footage of dense trash mats piled
against an interceptor barrier, that heuristic promoted almost all foreground to
`clump` (14.9% of labelled pixels) and left `debris` as a thin 2.4% residue. Its
IoU measured the area threshold, not the model.

The model was always detecting trash well; in the 4-class run it scored clump IoU
0.417 while debris sat at 0.103. Collapsing the two recovers the metric the
project actually needs — what fraction of the water surface is covered.

**This is the documented fallback in
[docs/annotation_guideline.md](annotation_guideline.md) §4, now taken on evidence.**
It is a load-time LUT, so the PNGs on disk are untouched and it is reversible.

---

## 4. The small-object trade-off, quantified

Debris IoU lost by dropping 640 → 416, versus mIoU lost:

| model | debris IoU drop | mIoU drop | ratio |
|---|---|---|---|
| `lraspp_mnv3` | 7.6% | 2.7% | 2.8x |
| `segformer_b0` | 12.2% | 6.2% | 2.0x |
| `unet_mnv3` | 12.3% | 4.0% | 3.1x |
| `deeplabv3plus_mnv3` | 14.6% | 4.5% | 3.2x |

**Debris degrades 2–3x faster than mIoU on every model.** Picking a resolution on
mIoU would understate the damage threefold. Confirmed on real data, as the brief
predicted.

Also confirmed: `pixel_acc` was **0.93** on the 4-class run while debris IoU was
0.10. That single pair is why pixel accuracy is structurally banned from the
headline metrics.

---

## 5. Inference pipeline, end to end

Ran the trained model over the 50 held-out loc1 frames:

```
python -m inference.run --config configs/inference/riptseg_loc1.yaml --source loc1_test.mp4
```

- 50 frames processed, 51-row time series written to CSV + SQLite
- **smoothed coverage = 0.316**, UTC timestamps ready for a rainfall join
- velocity empty and area_flux `n/a` — correct: the source is time-lapse stills
  minutes apart, so there is no frame-to-frame correspondence for optical flow
- `is_metric = 0`, flux labelled `relative_index` — homography is uncalibrated, so
  nothing pretends to be m²/s

The loop works. Coverage is a real ratio; flux is not a physical rate yet.

---

## 6. Bugs this run exposed

Four, all of which failed silently and none of which the synthetic smoke tests
could catch. Each now has a regression test.

1. **Bare-basename image paths.** RIPTSeg's COCO stores `frame.jpg` while images
   live in `loc1/`…`loc6/`, so path resolution returned nothing and **all 300
   images were skipped while the converter reported success**.
2. **Unlabelled ≠ background.** Only ~20.6% of each frame is annotated. Mapping
   the other 80% to `background` made water look like 15% of pixels and would have
   taught the model that river water is background. Now `unlabelled: ignore`.
3. **Absent structure polygon meant "whole frame".** A blockage alert fired on
   frame 14 of the demo despite no structure being configured — in production that
   is a false alarm that dispatches a cleanup crew.
4. **Dataloader workers spawned with the wrong interpreter**, so training hung at
   epoch 0 with the GPU at 2%. Orphaned workers then survived and starved later
   runs, which made it look like a model problem.

---

## 7. What these numbers do not say

- **They describe RIPTSeg, not an Indonesian river.** The domain gap in
  [docs/datasets.md](datasets.md) §7 is completely unaddressed: no turbid brown
  water, no sachets, no water hyacinth.
- **Test set is 50 images from one location.** Treat gaps under ~0.03 debris IoU
  as noise. SegFormer-vs-LR-ASPP (0.055) is probably real; LR-ASPP-vs-DeepLabv3+
  (0.006) is not.
- **Single seed, no variance measured.**
- **Latency is x86, not a Pi.** Pi figures remain extrapolation.
- **U-Net peaked at epoch 6** and degraded — 200 images is not enough data for
  6.7 M parameters. The Phase 2 annotation budget will move accuracy more than any
  architecture choice here.

---

## 8. Reproducing

```bash
python scripts/download.py --dataset riptseg
# unzip to data/raw/riptseg/unz/
python -m data.convert --dataset riptseg
python -m data.splits
python -m data.validate

python -m train.train --config configs/train/riptseg_lraspp_collapsed.yaml
python -m train.train --config configs/train/riptseg_segformer_b0_collapsed.yaml
python -m train.train --config configs/train/riptseg_unet_mnv3_collapsed.yaml
python -m train.train --config configs/train/riptseg_deeplabv3plus_mnv3_collapsed.yaml

python -m bench.accuracy --config configs/bench_riptseg_all.yaml --split test
python -m bench.report
```
