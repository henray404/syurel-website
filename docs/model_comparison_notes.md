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
