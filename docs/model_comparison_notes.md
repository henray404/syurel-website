## 3. What the cost numbers already tell us

Accuracy is not measured yet, so nothing below is a final pick. But three findings
are already solid, because they are properties of the architectures rather than of
the training data.

Run-to-run variance on this host is roughly 5-10%; every gap discussed below is far
larger than that.

### 3.1 The parameter count lies. Badly.

| model | params | rank by params | ms@512 | rank by latency |
|---|---|---|---|---|
| `fast_scnn` | 1.14 M | 1 | 61 | 1 |
| `lraspp_mnv3` | 3.22 M | 2 | 164 | 2 |
| `segformer_b0` | 3.72 M | 3 | **945** | **7 (last)** |
| `deeplabv3plus_mnv3` | 4.71 M | 4 | 312 | 3 |
| `unet_effnet_lite` | 5.20 M | 5 | 541 | 5 |
| `unet_mnv3` | 6.69 M | 6 | 553 | 6 |
| `deeplabv3_mnv3` | 11.02 M | 7 | 325 | 4 |

SegFormer-B0 is the third *smallest* model and the *slowest* by a wide margin --
**5.8x slower than LR-ASPP** at 512 while having only 16% more parameters.
DeepLabv3-MNv3 is the largest model, 3.4x the parameters of SegFormer, and runs
**2.9x faster**. If you had picked on "lightweight = few parameters", you would
have picked one of the two worst options for CPU deployment.

### 3.2 FLOPs lie too, just less

| model | GFLOPs@512 | ms@512 | ms per GFLOP |
|---|---|---|---|
| `deeplabv3_mnv3` | 19.6 | 325 | 16.6 |
| `unet_mnv3` | 24.7 | 553 | 22.4 |
| `deeplabv3plus_mnv3` | 9.3 | 312 | 33.5 |
| `fast_scnn` | 1.7 | 61 | 35.9 |
| `lraspp_mnv3` | 3.9 | 164 | 42.0 |
| `segformer_b0` | **15.6** | **945** | **60.6** |

SegFormer-B0 does *fewer* FLOPs than DeepLabv3-MNv3 (15.6 vs 19.6) and takes
**2.9x longer**. FLOPs count arithmetic; they do not count memory traffic,
attention's irregular access pattern, or how well an op maps onto the CPU's vector
units. Report FLOPs because the literature does, but never rank on them.

### 3.3 SegFormer falls off a cliff between 416 and 512

| model | ms@416 | ms@512 | ratio | ms@640 | ratio vs 416 |
|---|---|---|---|---|---|
| `fast_scnn` | 33 | 61 | 1.9x | 84 | 2.5x |
| `deeplabv3plus_mnv3` | 167 | 312 | 1.9x | 422 | 2.5x |
| `lraspp_mnv3` | 74 | 164 | 2.2x | 189 | 2.6x |
| `segformer_b0` | 282 | **945** | **3.4x** | 1013 | **3.6x** |

Pixel count only grows 1.51x from 416 to 512, and every convolutional model tracks
roughly that (1.9-2.2x, the excess being cache effects). SegFormer jumps **3.4x**,
because self-attention is quadratic in token count and the token grid grows with
the square of the input side.

The practical consequence is sharp: **SegFormer-B0 is borderline usable at 416 and
unusable at 512+ on CPU.** If it wins on accuracy, it wins only at 416 -- which is
also the resolution where a small-object problem hurts most. That tension is
exactly what section 2's resolution sweep has to resolve, and it cannot be resolved
from the cost table alone.

---

## 4. The number that should worry you

Everything above was measured on a **Ryzen 9 270, single-threaded**. A Raspberry
Pi 5 is not a Ryzen. Single-core comparisons put a Cortex-A76 at 2.4 GHz somewhere
in the region of **5-15x slower** than a modern desktop Zen core on this kind of
workload `[Low confidence -- not measured, and the spread is wide]`.

Applying that range to the fastest *pretrained* model:

| | ms measured | Pi 5 estimate (5-15x) |
|---|---|---|
| `lraspp_mnv3` @ 416 | 74 | **0.4 - 1.1 s/frame** |
| `lraspp_mnv3` @ 512 | 164 | **0.8 - 2.5 s/frame** |
| `segformer_b0` @ 512 | 945 | 4.7 - 14 s/frame |

**This is fine for coverage and fatal for velocity.** The two metrics have
completely different timing requirements:

- **Coverage / blockage alert** -- trash accumulates over minutes. Sampling at
  0.5-1 fps is ample, and Task 5's decoupled sampling already assumes you do not
  run everything every frame. LR-ASPP on a Pi 5 clears this comfortably.
- **Surface velocity via optical flow** -- needs *consecutive* frames close enough
  in time that the same debris is trackable between them. At 1-2 s/frame, a patch
  of trash moving 0.5 m/s has travelled 0.5-1 m and may have left the ROI
  entirely. Optical flow on segmentation output at that cadence will not work.

The fix is not a faster model. It is to decouple velocity from segmentation: run
optical flow on **raw frames** at native camera rate (it is cheap, and it does not
need the network), and use the segmentation mask only to decide *which* flow
vectors count as debris. Flagged now because it changes the Task 5 design, and it
would otherwise be discovered late and expensively.

---

## 5. Recommendation

**Provisional, cost-only. Do not commit to a model until section 2 is filled in.**
The cheapest model that cannot see a sachet is worth nothing, and debris IoU is the
column that decides.

### Pi 5, CPU only

**`lraspp_mnv3` at 416.** It is the fastest model with pretrained weights, by more
than 2x over the next pretrained candidate, and 416 keeps it near ~1 s/frame even
on a pessimistic Pi estimate.

`fast_scnn` is genuinely faster (61 ms vs 164 at 512, and a 4.7 MB checkpoint) but
it has **no pretrained weights** -- it trains from scratch on a few thousand images
while everything else starts from ImageNet or COCO. Expect it to lose on accuracy
for reasons that have nothing to do with its architecture. Revisit it only if
LR-ASPP misses the latency budget on real hardware; then a from-scratch Fast-SCNN
plus heavier augmentation is the escape hatch.

### Pi 5 + Hailo-8L

**`unet_effnet_lite`, or `lraspp_mnv3` if it quantizes cleanly. Not SegFormer.**

The Hailo path is not about latency, it is about what the compiler can map. Two
concrete constraints drive this:

1. **Attention frequently will not map.** NPU toolchains target convolutional
   graphs; transformer blocks either fall back to CPU (destroying the benefit) or
   fail to compile. SegFormer-B0 is a bad bet here regardless of its accuracy.
2. **EfficientNet-lite exists precisely for this.** The "lite" variants drop
   squeeze-excitation blocks and replace swish with ReLU6 -- both chosen because SE
   and swish are poorly supported by edge NPU toolchains. That is why
   `unet_effnet_lite` is in the candidate set at all, despite being mid-pack on CPU
   latency: on a Hailo it may well beat models that beat it here.

Hailo also requires INT8 quantization, which is its own accuracy loss and is not
measured anywhere in this document. **If Hailo is a serious option, budget a
separate quantization-accuracy experiment** -- post-training INT8 can cost a small
class like debris disproportionately, and that risk is invisible in FP32 numbers.
`[Medium confidence on the mapping constraints; nothing here has been compiled for
that device.]`

### Jetson Orin Nano

**Re-run the benchmark before deciding -- this table does not apply.**

Orin Nano has a real CUDA GPU, so the CPU latency ranking above is close to
irrelevant. SegFormer's penalty is largely a CPU artifact: attention parallelises
well on a GPU, and its 15.6 GFLOPs@512 is mid-pack. Under TensorRT, SegFormer-B0
and `deeplabv3plus_mnv3` both become plausible, and the resolution ceiling lifts --
which matters more here than anywhere else, because **resolution is the single
biggest lever on small-object accuracy** and the Jetson is the only target that can
afford it.

If the Jetson is affordable for the deployment, the honest engineering answer is
that it removes the constraint doing the most damage to this project's accuracy
ceiling.

### Excluded regardless of score

**`yolo11n_seg`** -- AGPL-3.0, and structurally unable to produce the metric. It
has no water class, so it cannot compute coverage = debris/(debris+water) on its
own; it would always need a second model for the denominator. It stays as a
reference number for "how good is debris masking alone", nothing more. See
`src/models/yolo_seg.py`.

---

## 6. Honest gaps in this document

- **No accuracy at all yet.** Every recommendation above is provisional on cost.
- **Wrong CPU.** Measured on x86-64 Windows; the target is aarch64 Linux. Re-run
  `python -m bench.cost` on the Pi and set `is_target_device: true`.
- **The Pi estimates are extrapolation**, not measurement, and the 5-15x range is
  wide enough to change the conclusion at 512.
- **No INT8 / quantized numbers.** Both the Hailo and the Jetson-TensorRT paths run
  quantized in practice, and quantization can hurt a 1-3% class more than the
  aggregate metrics suggest.
- **`fast_scnn` is not accuracy-comparable** to anything here until someone
  pretrains it, and nobody publishes those weights.
- **Batch size 1, no competing load.** A deployed loop decoding video and holding a
  cached water mask will see worse numbers than an idle benchmark.
- **Latency varies 5-10% run to run.** Re-running `bench.cost` will move the third
  digit; it will not move any ranking discussed here.
