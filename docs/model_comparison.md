# Model comparison

Generated 2026-08-15T05:13:40Z by `python -m bench.report`.

## 0. How to read this

- **Cost measured on:** AMD64 Family 25 Model 117 Stepping 2, AuthenticAMD (AMD64), torch 2.13.0+cpu, **1 thread(s)**, 15 runs after 4 warmup.
- **THESE LATENCY NUMBERS ARE A PROXY, NOT THE TARGET.** `is_target_device` is
  false in `configs/bench.yaml`. A Raspberry Pi 5 is roughly an order of
  magnitude slower than this host, with different SIMD width and far less
  memory bandwidth, so **the ordering can reorder**, particularly for the
  attention-based model. Copy the repo to the Pi, run `python -m bench.cost`,
  set `is_target_device: true`, and regenerate before committing to a model.
- Single-threaded by default: a deployed unit also decodes video and runs the
  inference loop, so it will not have every core free. Multi-threaded numbers on a
  many-core desktop flatter the heaviest models most.
- **Pixel accuracy appears nowhere.** Water is 85-95% of pixels; an all-water model
  scores ~0.9 and detects nothing. Judge on debris IoU and debris recall.

## 1. Cost

| model | params (M) | disk (MB) | GFLOPs@640 | GFLOPs@512 | GFLOPs@416 | ms@640 | ms@512 | ms@416 | licence |
|---|---|---|---|---|---|---|---|---|---|
| `lraspp_mnv3` | 3.22 | 13.084 | 6.1 | 3.9 | 2.6 | 189 | 164 | 74 | Apache-2.0 (torchvision) |
| `deeplabv3_mnv3` | 11.02 | 44.32 | 30.7 | 19.6 | 13.0 | 448 | 325 | 149 | Apache-2.0 (torchvision) |
| `unet_mnv3` | 6.69 | 26.986 | 38.6 | 24.7 | 16.3 | 636 | 553 | 268 | MIT (smp) |
| `unet_effnet_lite` | 5.2 | 21.092 | 36.4 | 23.3 | 15.4 | 642 | 541 | 288 | MIT (smp) |
| `deeplabv3plus_mnv3` | 4.71 | 19.088 | 14.5 | 9.3 | 6.1 | 422 | 312 | 167 | MIT (smp) |
| `segformer_b0` | 3.72 | 14.933 | 26.1 | 15.6 | 9.8 | 1013 | 945 | 282 | MIT (smp, native mit_b0) |
| `fast_scnn` | 1.14 | 4.726 | 2.6 | 1.7 | 1.1 | 84 | 61 | 33 | MIT (vendored, see src/models/fast_scnn.py) |

Latency tail (p90, ms) -- a frame budget is set by the tail, not the mean:

| model | p90@640 | p90@512 | p90@416 |
|---|---|---|---|
| `lraspp_mnv3` | 202 | 176 | 81 |
| `deeplabv3_mnv3` | 461 | 332 | 154 |
| `unet_mnv3` | 650 | 568 | 279 |
| `unet_effnet_lite` | 667 | 562 | 304 |
| `deeplabv3plus_mnv3` | 434 | 331 | 177 |
| `segformer_b0` | 1033 | 974 | 292 |
| `fast_scnn` | 89 | 63 | 36 |

## 2. Accuracy

Split: `test`. Device: cuda.

| model | res | mIoU | IoU background | IoU water | IoU debris | IoU clump | debris P | debris R |
|---|---|---|---|---|---|---|---|---|
| `lraspp_mnv3` | 640 | 0.7259 | 0.9666 | 0.7920 | 0.4191 | n/a | 0.4804 | 0.7666 |
| `lraspp_mnv3` | 512 | 0.7214 | 0.9662 | 0.7864 | 0.4117 | n/a | 0.4729 | 0.7607 |
| `lraspp_mnv3` | 416 | 0.7065 | 0.9621 | 0.7702 | 0.3872 | n/a | 0.4583 | 0.7138 |
| `unet_mnv3` | 640 | 0.7181 | 0.9792 | 0.7901 | 0.3851 | n/a | 0.4557 | 0.7133 |
| `unet_mnv3` | 512 | 0.7071 | 0.9771 | 0.7793 | 0.3650 | n/a | 0.4373 | 0.6883 |
| `unet_mnv3` | 416 | 0.6891 | 0.9751 | 0.7545 | 0.3376 | n/a | 0.4002 | 0.6835 |
| `segformer_b0` | 640 | 0.7473 | 0.9640 | 0.8034 | 0.4743 | n/a | 0.5327 | 0.8121 |
| `segformer_b0` | 512 | 0.7268 | 0.9500 | 0.7718 | 0.4586 | n/a | 0.5177 | 0.8006 |
| `segformer_b0` | 416 | 0.7010 | 0.9478 | 0.7389 | 0.4164 | n/a | 0.4643 | 0.8017 |
| `deeplabv3plus_mnv3` | 640 | 0.7091 | 0.9591 | 0.7551 | 0.4131 | n/a | 0.4563 | 0.8136 |
| `deeplabv3plus_mnv3` | 512 | 0.6907 | 0.9602 | 0.7213 | 0.3907 | n/a | 0.4189 | 0.8532 |
| `deeplabv3plus_mnv3` | 416 | 0.6772 | 0.9744 | 0.7042 | 0.3530 | n/a | 0.3744 | 0.8602 |

### Small-object trade-off

Debris IoU lost by downscaling, relative to the largest input. The mIoU column
sits next to it deliberately: when debris collapses and mIoU barely moves, the
aggregate metric is hiding the failure.

| model | res | debris IoU drop | mIoU drop |
|---|---|---|---|
| `lraspp_mnv3` | 416 | 7.6% | 2.7% |
| `lraspp_mnv3` | 512 | 1.8% | 0.6% |
| `lraspp_mnv3` | 640 | 0.0% | 0.0% |
| `unet_mnv3` | 416 | 12.3% | 4.0% |
| `unet_mnv3` | 512 | 5.2% | 1.5% |
| `unet_mnv3` | 640 | 0.0% | 0.0% |
| `segformer_b0` | 416 | 12.2% | 6.2% |
| `segformer_b0` | 512 | 3.3% | 2.7% |
| `segformer_b0` | 640 | 0.0% | 0.0% |
| `deeplabv3plus_mnv3` | 416 | 14.6% | 4.5% |
| `deeplabv3plus_mnv3` | 512 | 5.4% | 2.6% |
| `deeplabv3plus_mnv3` | 640 | 0.0% | 0.0% |

---

## 3. Reading the two tables together

Accuracy is now measured, not pending. Every model above was trained on the same
200 RIPTSeg images (loc2/3/5/6), validated on loc4 and tested on loc1, with
identical loss, optimiser, schedule and augmentation. Only the architecture
differs.

**The test split is an unseen location.** That is a much harder question than a
random split over 300 near-duplicate frames from six fixed cameras, which would
mostly measure memorisation. Expect these numbers to sit lower, and be more
honest, than published figures using random splits on the same dataset.

### The headline trade-off

| model | test mIoU@640 | test debris IoU@640 | ms@512 (CPU) | params |
|---|---|---|---|---|
| `segformer_b0` | **0.747** | **0.474** | 945 | 3.72 M |
| `lraspp_mnv3` | 0.726 | 0.419 | **164** | 3.22 M |
| `unet_mnv3` | 0.718 | 0.385 | 553 | 6.69 M |
| `deeplabv3plus_mnv3` | 0.709 | 0.413 | 312 | 4.71 M |

SegFormer-B0 wins on accuracy and loses on cost by a factor of six. It is
**13% better on debris IoU than LR-ASPP and 5.8x slower on CPU**. That is the
whole decision in one line, and it is exactly the tension the harness exists to
expose.

### The parameter count still lies

`unet_mnv3` has the most parameters (6.69 M), the second-worst latency, and the
**worst debris IoU of the four**. More capacity did not help; on 200 images it
hurt. Its validation curve peaked at **epoch 6** and degraded from there, while
LR-ASPP (half the parameters) peaked at epoch 32 and SegFormer at 49. That is
textbook overfitting, and it is the clearest argument in this document for why
the Phase 2 annotation budget matters more than the architecture choice.

### Small-object degradation, measured

Debris IoU lost by dropping from 640 to 416, against mIoU lost:

| model | debris IoU drop | mIoU drop | ratio |
|---|---|---|---|
| `lraspp_mnv3` | **7.6%** | 2.7% | 2.8x |
| `segformer_b0` | 12.2% | 6.2% | 2.0x |
| `unet_mnv3` | 12.3% | 4.0% | 3.1x |
| `deeplabv3plus_mnv3` | 14.6% | 4.5% | 3.2x |

**Debris degrades 2-3x faster than mIoU on every single model.** Choosing a
resolution on mIoU would understate the damage by roughly a factor of three. This
is the small-object trade-off the brief predicted, now quantified on real data.

`lraspp_mnv3` is also the most robust to downscaling in absolute terms (7.6%),
which matters more than it looks: on a Pi the affordable resolution is the binding
constraint, and LR-ASPP loses the least when forced down to 416.

---

## 4. What the cost numbers already told us, confirmed

All three pre-accuracy cost findings survive contact with the accuracy data:

1. **Parameter count mis-ranks latency.** SegFormer-B0 is the 3rd smallest model
   and the slowest, 5.8x slower than LR-ASPP at 512. It is now also the most
   accurate, so the mis-ranking cuts both ways.
2. **FLOPs mis-rank it too.** SegFormer does fewer GFLOPs than DeepLabv3-MNv3
   (15.6 vs 19.6) and takes 2.9x longer.
3. **SegFormer scales 3.4x from 416 to 512** where every CNN scales 1.9-2.2x,
   because attention is quadratic in token count.

Point 3 now has a sharper consequence. SegFormer's advantage is largest at 640
(+0.055 debris IoU over LR-ASPP) and shrinks at 416 (+0.029), which is the only
resolution where its CPU latency is remotely tolerable. **It wins where it cannot
run, and nearly ties where it can.**

---

## 5. Recommendation

### Pi 5, CPU only

**`lraspp_mnv3` at 512, or 416 if the frame budget demands it.**

It is 5.8x faster than the most accurate model for a 12% relative loss in debris
IoU, it degrades the least under downscaling, and it is the only candidate whose
projected Pi latency (0.8-2.5 s/frame at 512, 0.4-1.1 s at 416) fits the coverage
sampling rate. Coverage needs 0.5-1 fps, not 30.

Do not read the 512-vs-640 gap as free accuracy: it costs 1.8% of debris IoU for
40% more latency. At 416 the cost is 7.6%, which is the real decision point.

### Pi 5 + Hailo-8L

**`unet_effnet_lite` or `lraspp_mnv3`. Still not SegFormer.**

Unchanged by the accuracy data and reinforced by it: SegFormer's advantage is
concentrated at high resolution, which is where NPU memory limits bite hardest,
and transformer blocks frequently fail to map onto NPU toolchains at all.

`unet_effnet_lite` was not trained here -- only its cost was measured. Given
`unet_mnv3` came last on accuracy, **do not assume the EfficientNet-lite variant
will be competitive**; train it before committing to the Hailo path. The lite
encoder exists for quantisation friendliness, not accuracy.

INT8 quantisation remains unmeasured and can cost a 2-3% class disproportionately.

### Jetson Orin Nano

**`segformer_b0`.** Its CPU penalty is a CPU artifact -- attention parallelises
well on a GPU and 15.6 GFLOPs@512 is mid-pack. On a Jetson it is the most accurate
option at the resolution where it is most accurate, and resolution is the single
biggest lever on small-object performance. If the budget stretches to a Jetson,
that is where the accuracy ceiling actually moves.

### Not recommended

`unet_mnv3`: worst debris IoU, second-worst latency, most parameters, earliest
overfit. Dominated on every axis that matters here.

`yolo11n_seg`: AGPL-3.0 and structurally unable to produce coverage (no water
class). Unchanged.

---

## 6. Honest gaps

- **One dataset, 300 images, 4 training locations.** These numbers describe
  RIPTSeg, not Indonesian rivers. The domain gap in docs/datasets.md section 7 is
  entirely unaddressed by this experiment.
- **Test set is 50 images from one location.** Treat differences under ~0.03
  debris IoU as noise: the SegFormer-vs-LR-ASPP gap (0.055) is probably real, the
  LR-ASPP-vs-DeepLabv3+ gap (0.006) is not.
- **Single seed.** No run-to-run variance was measured. On 200 images that
  variance is plausibly comparable to the smaller gaps above.
- **Latency is still x86, not the target.** The Pi projections remain
  extrapolation. Re-run `python -m bench.cost` on the device.
- **No INT8 numbers**, and both edge deployment paths need them.
- **`clump` was collapsed into `debris` for every accuracy figure here.** The
  4-class run scored debris IoU 0.10-0.13 because the heuristic left `debris` as a
  thin residue. Any future reintroduction of `clump` needs real annotation, not
  the area heuristic.
- **`unet_effnet_lite` and `fast_scnn` have cost numbers but no accuracy**, so the
  Hailo recommendation rests on architectural reasoning rather than measurement.
