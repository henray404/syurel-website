# Public Datasets for River Floating-Trash Segmentation

Phase 1 dataset survey. Target schema: semantic segmentation, 4 class indices —
`0=background, 1=water, 2=debris, 3=clump`.

> **Schema decision (2026-08-11).** Class 2 was originally `trash` (anthropogenic only).
> It is now **`debris` — anything floating that is not water**: plastic, sachets,
> styrofoam, bags, wood, and **floating vegetation including water hyacinth**. Origin is
> out of the schema. Rationale: for blockage warning a hyacinth raft blocks a rack exactly
> as well as a sachet raft, and separating origin adds an annotation judgement call that
> is hard to make consistently from a fixed camera. See [§9](#9-decisions-taken).
>
> **Data strategy decision (2026-08-11, revised).** Diversity **within the relevant
> domain** — river / inland water, debris floating on a water surface — not diversity for
> its own sake. Site footage from Phase 2 is what the model is ultimately fine-tuned on,
> so public data's job is breadth of appearance (perspective, water colour, lighting,
> debris type) across cases that are *plausibly the same problem*. A dataset that is a
> different problem wearing similar words is dropped, not down-weighted: it consumes
> conversion effort, drags the sampling budget, and in one case (ATLANTIS vegetation)
> teaches the model something actively wrong.
>
> Mixing is done with **per-dataset sampling weights**, so no single source dominates.
> See [§6](#6-conversion-order) for the kept set and [§8](#8-rejected--unverified) for
> what was dropped and why.

**Verification method.** Every URL below was fetched and returned a live response.
Status codes recorded on 2026-08-11 (`curl -L`, browser UA). Sites that block automated
clients on the HTML page (Zenodo, Roboflow) were re-checked with browser headers and/or
their public API; anything that could not be confirmed is listed in
[§8 Rejected / unverified](#8-rejected--unverified) with the reason, not in the main table.

---

## 1. Summary table

### Kept

| # | Dataset | Ann. type | Water labelled? | Imgs | Perspective | License | Role |
|---|---------|-----------|-----------------|------|-------------|---------|------|
| 1 | RIPTSeg / 4TU riverine trash+water | instance masks (COCO) | **yes** | 300 | fixed cam at barrier | CC BY 4.0 | **anchor + water ground truth** |
| 2 | RiSID v2 | instance masks (COCO) | no | 7,356 | bridge, nadir | CC BY 4.0 | **bulk debris masks** |
| 3 | IWHR_AI_Lable_Floater_V1 | bbox (VOC XML) | no | 3,000 | **shore-based fixed** | Apache 2.0 | closest camera geometry |
| 4 | LaRS | panoptic (stuff+thing) | **yes** | ~4,000 key / 40k | USV, incl. rivers+lakes | see repo | water diversity + hard negatives |
| 5 | USVInland | semantic (water subset) | **yes** | multi-sensor | USV inland | see repo | closest water appearance |
| 6 | Roboflow: Trash In River, River Trash final | bbox | no | 1,101 / ~1,800 | mixed river | varies | extra river variety |

### Dropped on relevance

| Dataset | Why |
|---|---|
| MaSTr1325 | Coastal Adriatic, clear blue sea, no debris class. Different water, different problem. |
| ATLANTIS | Arbitrary Flickr photos of dams/swamps/piers, no debris class, and its vegetation labelling **contradicts** our `debris` schema (§7). |
| FloW-Img | USV waterline, bbox, bottle-dominated, access-gated, mirror down. Cost ≫ value. |
| Roboflow: waste-in-water, floating-plastic-waste-river | 1,422 / 319 images, unaudited, redundant with the two kept Roboflow sets. |

Full reasoning for each is in [§8](#8-rejected--unverified). Satellite and underwater sets
were already out on medium grounds.

---

## 2. Tier 1 — datasets that carry the schema

### 2.1 Dataset of trash and water segmentations in riverine environments (RIPTSeg)

- **Link:** https://data.4tu.nl/datasets/90d13261-b0fe-444a-b408-c5a63db3d887 → HTTP 200
- **Direct file:** `paper_dataset.zip`, 289.7 MB → HTTP 206 on range request (download works)
- **DOI:** `10.4121/90d13261-b0fe-444a-b408-c5a63db3d887.v1`
- **Code:** https://github.com/TheOceanCleanup/RiverTrashSegmentation → HTTP 200
- **Paper:** "Foundation Model or Finetune? Evaluation of few-shot semantic segmentation
  for river pollution", Don, Pinson, Guillen Cebrian, Asano — GreenFOMO @ ECCV 2024,
  https://arxiv.org/abs/2409.03754
- **Size:** 300 images, 6 locations (`loc1`…`loc6`), ~50 per site. 4,387 masks total.
  Mixed 5 MP / 12 MP, e.g. 1944×2592.
- **Annotation:** COCO instance segmentation JSON + a train/test split mapping.
- **Classes:** `water`, `barrier`, `trash in-system`, `trash out-system`.
  In/out-system = trash inside vs outside The Ocean Cleanup Interceptor barrier.
- **Collection:** The Ocean Cleanup operational footage, 2020–2023, multiple countries.
- **License:** CC BY 4.0.
- **Perspective:** fixed camera looking at a trash-retention barrier. `[Medium]` — the
  4TU landing page describes overhead framing; exact mounting height/angle per site is
  not stated in the metadata and would need reading the zip.

**Verdict — the single most valuable dataset for this project.** It is the only public
dataset that labels *trash and water in the same image*, which is exactly what the
coverage metric needs, and the only one whose class list includes a **structure**
(`barrier`) — the direct analogue of the bridge-pier / trash-rack blockage case.

**Conversion work:** low. COCO polygons → rasterize with `pycocotools`.
Mapping: `water→1`, `trash in-system`+`trash out-system`→`2` (`debris`), `barrier→0`
(background; the structure is handled by the static polygon in inference, not by the
model — see §9 decision 2). Everything unlabelled → `0`. `clump` derived post-hoc by
connected-component area over threshold.

**Caveat:** 300 images is small. Treat this as the *schema reference and validation set*,
not the bulk of training data. It is also the natural set for sanity-checking the water
pseudo-labeller: it has ground-truth water, so pseudo-label quality can be measured
against it rather than eyeballed.

### 2.2 RiSID v2 — River Surface Image Dataset

- **Link:** https://doi.org/10.5281/zenodo.16927238 → resolves to
  https://zenodo.org/records/16927238 → HTTP 200 (v2, published 2025-08-22)
- **v1 record:** https://zenodo.org/records/15533743 → HTTP 200 (DOI `10.5281/zenodo.15533743`)
- **Data paper:** Kataoka, Yoshida, Yamamoto, *Data in Brief* vol. 63 (2025),
  https://www.sciencedirect.com/science/article/pii/S2352340925009102 ·
  open access mirror https://pmc.ncbi.nlm.nih.gov/articles/PMC12594929/
- **Files (v2):** `images.zip` 5.6 GB, `annotated.zip` 53.5 MB,
  `annotations_7cat.json` / `_5cat` / `_2cat` ~8.3 MB each, `quick_start.py`, `README.md`,
  `requirements.txt`
- **Size:** 7,356 images, 8,022 annotated debris objects. Standardised to 1,024×1,024;
  sources were HD (1280×720) and Full HD (1920×1080), 10–30 fps.
- **Annotation:** COCO polygon masks, three granularities — 7-class, 5-class, 2-class
  (plastics / non-plastics).
- **Classes (7):** drink bottles, other bottles, food containers, shopping bags,
  other bags, other plastics, non-plastics.
- **Perspective:** cameras "fixed to bridge rails or held by hand, with the river surface
  recorded in a perpendicular downward view." Focal lengths 2.7–706 mm, sensors 1/2.88″–1/6″.
- **Conditions:** primarily flood season / high-flow, 11 sites on 7 Japanese rivers
  (Arakawa, Danzu, Edo, Hikiji, others), collected 2010–2024.
- **License:** CC BY 4.0.

**Verdict — the bulk supplier of trash masks, with one serious caveat.** 7,356 images with
real pixel polygons is by far the largest mask source available. It is also the only large
set deliberately captured during **flood conditions**, which matches the blockage
use case.

**Conversion work:** medium.
1. Use `annotations_2cat.json`, collapse **both** plastics and non-plastics → `2`
   (`debris`). Under the `debris` schema this is now a plain 2→1 merge with no judgement
   call — RiSID's "non-plastics" is mostly wood and vegetation, which is in-class.
2. Water is **not** labelled → must be pseudo-labelled (SAM-assisted + manual review).
3. `clump` derived heuristically from component area.

The 7-class and 5-class annotation files are not needed for training, but keep them
around: they are the only public record of *composition* (bottle vs bag vs container),
which is useful for sanity-checking whether Indonesian debris mix differs the way §7
predicts.

**Perspective note.** RiSID is nadir (straight down from a bridge); a shore-mounted fixed
camera is oblique. Apparent shape, scale gradient and glare statistics differ, and pixel
coverage in an oblique view is a perspective-distorted quantity (which is why the
homography hook exists). Under the diversity-first decision this is a **feature, not a
disqualifier** — nadir data is the cheapest way to teach the model what debris texture
looks like free of horizon, sky and bank clutter. Do not expect zero-shot transfer to the
site; that is what Phase 2 fine-tuning is for.

Also note the paper's own finding that segmentation accuracy is strongly ground-sampling-
distance dependent (best at 1.0–1.5 mm/px) and that small objects are where it fails —
which is precisely your small-object concern, confirmed on real data.

---

## 3. Tier 2 — trash datasets needing bbox→mask conversion

### 3.1 IWHR_AI_Lable_Floater_V1

- **Link:** https://doi.org/10.6084/m9.figshare.27376851.v1 → resolves to figshare
  article 27376851 → HTTP 202 (figshare returns 202 to non-browser clients; contents
  confirmed via the public API, https://api.figshare.com/v2/articles/27376851)
- **Paper:** *Scientific Data* (2025), https://www.nature.com/articles/s41597-025-04594-9
  (paywall redirect for automated fetch; the figshare record is the authoritative source)
- **Size:** 3,000 images from real water scenarios.
- **Files:** `IWHR_AI_Lable_Floater_V1-package1.zip` (1.01 GB),
  `-package2.zip` (1.22 GB), plus baseline code (Faster R-CNN, YOLOv5/6/7) and
  `voc_label.py` / `split_train_val.py` — implying **Pascal VOC XML bounding boxes**.
- **Authors:** Guangchao Qiao, Mingxiang Yang, Hao Wang (IWHR — China Institute of Water
  Resources and Hydropower Research).
- **License:** **Apache 2.0** (unusually permissive for a dataset — no share-alike, no NC).
- **Perspective:** shore/bank-mounted surveillance cameras on Chinese inland waters.
- **Stated difficulty:** the authors report baseline detection accuracy remains low due to
  complex lighting and small object size.

**Verdict — usable, and the closest match to your camera geometry.** Shore-based fixed
cameras on inland water is exactly your deployment. Bounding boxes are the problem.

**Conversion work:** high but tractable. Feed each VOC box to **SAM as a box prompt** —
box-prompted SAM is far more reliable than unprompted segmentation, and this is the
standard trick for upgrading detection datasets to masks. Ship it through the same manual
review step as the water pseudo-labeller. Expect to discard a meaningful fraction.
Water still needs pseudo-labelling separately.

### 3.2 FloW-Img

- **Link:** https://github.com/ORCA-Uboat/FloW-Dataset → HTTP 200
- **Paper:** Cheng et al., ICCV 2021,
  https://openaccess.thecvf.com/content/ICCV2021/html/Cheng_FloW_A_Dataset_and_Benchmark_for_Floating_Waste_Detection_in_ICCV_2021_paper.html
- **Size:** ~2,000 images (FloW-Img) + ~4,000 radar frames (FloW-RI).
- **Annotation:** bounding boxes. Classes are essentially bottle-dominated.
- **Perspective:** USV, camera near the waterline — near-horizontal, strong glare.
- **Access:** **gated.** The GitHub repo is an information portal only; you must apply at
  http://www.orca-tech.cn/datasets (HTTP 200) under *Customer Support → Dataset → FloW*.
  The English mirror https://world.orca-tech.cn/ returned **HTTP 503** at check time.
- **License:** not stated publicly; effectively whatever the application grants.

**Verdict — DROPPED.** bbox-only, bottle-dominated so it adds no debris-type variety
beyond what RiSID already has, a USV waterline perspective that is the *least* like a
fixed shore camera, and an irrelevant radar modality. On top of that it is the only
kept-or-dropped candidate behind an access application, with its English mirror down.
Highest friction, lowest marginal value. Recorded here because it is the best-known name
in this field and you will keep seeing it cited — the citation is worth more than the data.

---

## 4. Water-class sources (no trash dataset labels water)

This is the gap your brief predicted, and it is real: of the trash datasets, **only
RIPTSeg labels water**. Options for sourcing the `water` class:

### 4.1 LaRS — Lakes, Rivers, Seas (ICCV 2023)

- **Link:** https://lojzezust.github.io/lars-dataset/ → HTTP 200
- **Paper:** https://arxiv.org/abs/2308.09618 · Žust, Perš, Kristan (Univ. of Ljubljana)
- **Size:** 4,000+ per-pixel labelled key frames, each with 9 preceding frames (~40k frames).
- **Annotation:** **panoptic.** Stuff: `water`, `sky`, `static obstacle` (shore, piers).
  Things (8): boat, row boat, paddle board, buoy, swimmer, animal, **float**, `other`.
  Plus 19 global scene attributes per frame.
- **Perspective:** USV / boat-level, but explicitly includes **rivers and lakes**, not just sea.
- **License:** `[Low]` — not confirmed; check the download page terms before use.

**Verdict — best water source, and doubles as a hard-negative mine.** The `static obstacle`
class gives structures. The scene attributes let you filter for glare/reflection/low-light
frames.

Conversion: `water→1`, everything else→`0`. The `float` and `other` thing classes need a
call under the `debris` schema — a moored buoy is man-made and floating but is permanent
infrastructure, not transported debris, so it belongs in `0` as a **hard negative**
(teaching the model "floating + man-made ≠ debris" is worth more than the handful of
pixels). `other` is open-world and genuinely ambiguous; drop those frames rather than
guess. Boats, swimmers and animals → `0`, which directly serves the annotation-guideline
rules in Task 6.

### 4.2 MaSTr1325

- **Link:** https://www.vicos.si/resources/mastr1325/ → HTTP 200
- **Size:** 1,325 images, per-pixel labelled, 3 classes: **sea / sky / environment**,
  synchronised with on-board IMU.
- **Perspective:** coastal USV, gulf of Koper, Slovenia, collected over 2 years.
- **License:** `[Low]` — research use stated on the page; verify before redistribution.

**Verdict — DROPPED on relevance.** Adriatic coastal sea: blue, clear, open horizon, wave
texture, no debris of any kind. Indonesian river water is brown, turbid, confined, and the
whole difficulty is low contrast between debris and silt. Training on clear blue sea
teaches a water boundary defined by colour separation that does not exist at the target
site, and the three-class scheme (`sea`/`sky`/`environment`) contributes nothing toward
`debris`. LaRS already covers the USV-perspective water case and actually includes rivers
and lakes. Cheap to convert is not a reason to convert.

### 4.3 ATLANTIS

- **Link:** https://github.com/smhassanerfani/atlantis → HTTP 200
- **Paper:** https://arxiv.org/abs/2111.11567 (iWERS lab, Univ. of South Carolina)
- **Size:** 5,195 pixel-annotated images — 3,364 train / 535 val / 1,296 test.
- **Classes:** 56 total — 17 artificial water bodies (dam, reservoir, canal, pier),
  18 natural (sea, lake, **river**, wetland, swamp, marsh), 21 general (person, car, road,
  building).
- **Source:** Flickr API, filtered by Creative Commons / US Government Work licenses.
- **Perspective:** mixed — these are web photographs, not fixed-camera footage.

**Verdict — DROPPED on relevance, and it is the one that would have done harm.**

Three reasons, in order of severity:

1. **Vegetation contradiction.** ATLANTIS labels `wetland`, `marsh` and `swamp` scenes
   with vegetation as scenery, not as objects on water. Our schema says *floating*
   vegetation is `debris`. The adapter cannot separate floating from rooted vegetation
   from ATLANTIS labels alone, so every hyacinth-like green mat would be taught as
   `background` — the exact opposite of what the Indonesian site needs (§7).
2. **No debris class at all.** It contributes only to `water`, and LaRS covers that with
   an actual water-surface perspective.
3. **Photographs, not monitoring footage.** Arbitrary Flickr framing, arbitrary
   distances, arbitrary lenses. Scenic photos of dams are not the trash-rack scene; the
   word "pier" appearing in a class list is not the same as a structure viewed by a fixed
   camera at a river surface.

Practical bonus: the README has **no direct dataset download link** (Google Drive weights
only), so obtainability was unconfirmed anyway. Dropping it removes the risk *and* the
open question.

### 4.4 USVInland

- **Link:** https://github.com/ORCA-Uboat/USVInland-Dataset → HTTP 200
- **Paper:** https://arxiv.org/abs/2103.05383
- Multi-sensor (lidar, stereo, mmWave radar, GPS/IMU) over 26 km of Chinese inland
  waterways, with a **water segmentation benchmark** among its tasks. Varied weather.

**Verdict — high value per image, high friction to obtain.** Inland, muddy, varied
weather — appearance-wise **the closest water to Indonesian rivers in this entire list**,
which under diversity-first makes it worth the trouble despite the USV perspective. The
friction is the download: the water-segmentation labels ship inside a large multi-sensor
bundle (lidar, stereo, radar, GPS/IMU) that is mostly irrelevant here. Pull it after the
Tier 1/2 sets are converted and the pipeline is proven, then extract the water subset only.

---

## 5. Roboflow Universe (Tier 3)

All four confirmed reachable (HTTP 200/206 with browser headers). Quality is
user-contributed and unaudited; treat as augmentation variety, not core training data.

| Dataset | Link | Size | Annotation | Status |
|---|---|---|---|---|
| Trash In River | https://universe.roboflow.com/try-uqrjj/trash-in-river | 1,101 | bbox | **kept** |
| River Trash final | https://universe.roboflow.com/trisha-lingat-m9vjl/river-trash-final-k9997 | ~1,800 | bbox, 10 classes | **kept** — has `clustered-trash` |
| waste in water | https://universe.roboflow.com/chinatele/waste-in-water | 1,422 | bbox | dropped — redundant |
| floating-plastic-waste-river | https://universe.roboflow.com/floatplasticwasteriver/floating-plastic-waste-river | 319 | bbox | dropped — too small to matter |

Two kept, two dropped. The kept pair earns its place on content, not volume:

*River Trash final* carries a **`clustered-trash`** class — someone else hit your `clump`
problem and drew a boundary. Read their examples before finalising the `clump` rule in
Task 6, even if you never train on the images. Its other classes (branch, oil-spill,
styrofoam) independently confirm styrofoam and floating branches as recognised failure
modes, which supports the `debris` decision.

*Trash In River* is the larger of the two generic river-trash sets and covers river
framings absent from RiSID's nadir view.

The two dropped ones add no class or perspective the kept pair lacks, and every Roboflow
image costs a SAM box-prompt conversion plus manual review — the most expensive
per-image path in the pipeline. Not worth it for redundancy.

**Caveats on all Roboflow data:** user-contributed and unaudited; expect label noise.
Roboflow can export polygons, but for bbox-only projects the export is still boxes.
Licenses are per-project and frequently unstated — check each before use.

**Catalog:** https://github.com/AgaMiko/waste-datasets-review → HTTP 200. Mined; the
water-relevant entries it lists are all covered above or rejected in §8.

---

## 6. Conversion order

Six datasets kept. Ordered by *what unblocks the next thing*.

**Wave 1 — proves the pipeline (COCO-polygon adapter)**

1. **RIPTSeg (4TU)**, 290 MB — convert first. It exercises the whole schema in one file
   (water + debris + structure) and it is the **only** set with ground-truth water, so it
   is the yardstick the SAM water pseudo-labeller gets scored against. Small enough to
   iterate on in a day.
2. **RiSID v2**, 5.6 GB — same adapter, so it costs almost nothing extra once (1) works.
   Supplies debris masks at a scale nothing else matches, under flood conditions.

**Wave 2 — water diversity (semantic/panoptic-PNG adapter)**

3. **LaRS** — water + hard negatives (glare, buoys, boats, reflections, swimmers), plus
   19 scene attributes per frame for filtering by condition. Now the *only* source of
   water-class variety besides RIPTSeg, so it carries more weight than before.
4. **USVInland** — water subset only. Turbid inland canal water, the closest appearance
   match to a tropical river in anything public. High download friction (multi-sensor
   bundle), so it comes after LaRS, but it is no longer optional: dropping MaSTr1325 and
   ATLANTIS makes this the water-appearance anchor.

**Wave 3 — bbox upgrade (VOC-bbox + SAM box-prompt adapter)**

5. **IWHR**, 2.2 GB, Apache 2.0 — shore-based fixed cameras on inland water, the closest
   camera geometry to your deployment in the entire survey. Worth the SAM conversion cost
   for that reason alone.
6. **Roboflow ×2** (Trash In River, River Trash final) — same adapter, cheap once (5)
   works. Read *River Trash final*'s `clustered-trash` examples before writing the Task 6
   `clump` rule.

**Three adapter shapes, six datasets.** COCO-polygon (1, 2), semantic/panoptic-PNG (3, 4),
VOC-bbox+SAM (5, 6). Each wave's first dataset pays the adapter cost; the rest of the wave
is a YAML class-map. That is the whole argument for the config-driven remap in Task 2.

**Stop-early rule.** If Wave 1 + Wave 2 already give acceptable trash IoU in the Task 4
comparison, Wave 3 is optional. SAM box-prompt conversion plus manual review is the most
expensive per-image work in this project; do not pay it out of completionism. IWHR earns
its place on camera geometry — if fine-tuning on Phase 2 site data makes that moot, it
was never needed.

### Sampling

Balanced sampling, not uniform pooling. Without it the mix is ~55% RiSID by image count
and the model overfits Japanese nadir footage.

- **Per-dataset sampling weight is a required config field.** Not a later addition.
- Default: **cap each dataset's per-epoch contribution** rather than weighting by size —
  e.g. sample `min(n_images, cap)` per dataset per epoch with a fixed seed. Boring,
  inspectable, and it makes "did dataset X help?" answerable by editing one number.
- **Record source dataset in every converted mask's metadata.** Without it, per-source
  validation metrics are impossible and you cannot tell whether a dataset is helping or
  fighting the others.
- Report **per-dataset validation IoU** alongside the pooled number in Task 3. A dataset
  whose own val IoU is fine while the pooled number drops is a dataset to down-weight or
  drop — this is how the kept set gets pruned further with evidence instead of judgement.

---

## 7. What public data cannot give you

Stated plainly, because this determines how much Phase 2 site annotation you actually need.

**Water appearance.** Every water-labelled dataset here is clear blue (MaSTr1325,
much of LaRS) or European/Japanese river water. Indonesian rivers run turbid brown with
high suspended sediment. Turbid brown water has *low contrast against brown organic
debris and cardboard*, which is the exact confusion that kills the debris class. No public
data contains this appearance in quantity. Colour augmentation can only stretch so far —
it changes hue statistics but not the underlying texture and specularity of silt-laden water.
USVInland (§4.4) is the closest available and is still Chinese canal water, not tropical
river water.

**Trash composition.** The public sets are bottle- and bag-dominated (RiSID's classes are
literally drink bottles / food containers / shopping bags). Indonesian rivers carry a very
different mix: **sachets** (small, thin, low-contrast, high count) and **styrofoam**
(white, bright, easily confused with foam and with sun glare). Sachets are close to the
worst case for a downscaled segmentation model — small, numerous, low-contrast. Styrofoam
is the worst case for the foam-vs-trash annotation rule.

**Water hyacinth (eceng gondok).** Absent from every dataset here as a labelled class.
It is a first-order feature of Indonesian rivers — seasonal blooms in the Citarum system
run to hundreds of hectares, and the vegetation mats co-occur with and physically entangle
plastic waste.

Under the `debris` schema hyacinth is **in-class**, which removes the labelling ambiguity
but not the appearance gap. In the kept set the nearest thing to a floating vegetation mat
is RiSID's `non-plastics` — Japanese wood and reed fragments, individual objects, not the
dense hectare-scale mats of the Citarum system.

ATLANTIS was the one dataset with vegetated-water imagery in quantity, and it labels that
vegetation as *scenery*, the opposite of our schema. Dropping it (§4.3) means the model
now learns nothing about hyacinth rather than learning something wrong — a strict
improvement, but it leaves the gap fully open. **Hyacinth is therefore the single
strongest argument for Phase 2 site annotation**: it is the one class where public data
is not merely insufficient but was actively contradictory.

**Camera geometry.** Across the six kept datasets: RiSID is nadir from a bridge; LaRS and
USVInland are at waterline from a moving boat; the Roboflow sets are mixed and
undocumented. Only **IWHR and RIPTSeg are fixed installations**, and neither publishes its
mounting height or angle. Your site will have one specific oblique angle with its own
scale gradient and its own occlusion pattern from the pier — the thing pixel-coverage
numbers are most sensitive to, and the thing no public dataset can supply.

**Structures.** Only RIPTSeg has a `barrier` class, and it is The Ocean Cleanup's
Interceptor, not a concrete bridge pier or a steel trash rack. Trash *piled against and
above the waterline on a rack* — your primary blockage signal — appears in essentially no
public dataset.

**Practical consequence.** Public data is enough to (a) build and debug the entire
pipeline before you visit the site, (b) pretrain a backbone that knows water-vs-not-water
and debris-vs-not-debris in general, and (c) run the model comparison in Task 4 on a real
benchmark. It is **not** enough to deploy. Budget the Phase 2 300–500 site frames as
mandatory, not optional, and expect fine-tuning on them to move debris IoU more than any
architecture choice in Task 4 will.

This is exactly why the diversity-first decision is the right one: since the model gets
fine-tuned on site data regardless, the public mix should optimise for **breadth of
invariance** — many perspectives, water colours, lighting conditions, debris types — so
the fine-tune starts from a backbone that has seen variation, rather than one overfitted
to a single foreign river that happens to look slightly more like yours.

---

## 8. Rejected / unverified

**Dropped on relevance** (2026-08-11 decision — reachable and real, but a different
problem; see the linked section for full reasoning):

| Item | Reason |
|---|---|
| MaSTr1325 (§4.2) | Clear blue Adriatic sea, no debris class. Wrong water, wrong difficulty. |
| ATLANTIS (§4.3) | No debris class; vegetation labelling contradicts the `debris` schema; scenic Flickr photos, not monitoring footage; download link unconfirmed. |
| FloW-Img (§3.2) | bbox, bottle-dominated, USV waterline, access-gated, mirror 503. Highest friction, lowest marginal value. |
| Roboflow `waste-in-water`, `floating-plastic-waste-river` (§5) | Redundant with the two kept Roboflow sets; 319 images is below the threshold where SAM conversion cost pays back. |

**Rejected on medium / sensor** — not the same imaging problem at all:

| Item | Reason |
|---|---|
| MARIDA — https://zenodo.org/records/5151941 (HTTP 200) | Sentinel-2 satellite, 10 m/px. Wrong scale by three orders of magnitude. |
| MADOS — https://zenodo.org/records/10664073 (HTTP 200) | Same — Sentinel-2 marine debris + oil spill. |
| TrashCan 1.0 | Underwater, and `conservancy.umn.edu` returned **HTTP 403** to every automated request — link not confirmed, so not recommended. |
| Trash-ICRA19 | Same host, same 403; underwater anyway. |
| DeepSeaWaste (Kaggle) | Classification labels only, underwater. |
| TACO | Land/street litter. Useful only as generic trash-appearance pretraining; not river. |
| Sentinel-2 Indonesian plastic-index work (Rancamanyar/Citarum) | Satellite indices, not imagery segmentation. Relevant as *context* for the domain gap, not as training data. |
| RivAIrSet (UAV river water segmentation, Data in Brief 2025) | Promising for the water class — UAV over rivers — but the ScienceDirect page dropped the connection on fetch and I could not confirm the repository DOI. **Worth re-checking manually**: https://www.sciencedirect.com/science/article/pii/S2352340925010704 |
| ATLANTIS download link | Repo confirmed, dataset download URL not present in README — obtainability unconfirmed. |
| LaRS / MaSTr1325 licenses | Pages live, license terms not machine-readable. Confirm before redistribution. |

---

## 9. Decisions taken

Resolved 2026-08-11. These are now binding on Task 2 and Task 3.

**1. Class 2 is `debris`, not `trash`.** Any floating matter that is not water: plastic,
sachets, styrofoam, bags, wood, floating vegetation, water hyacinth. Origin is out of the
schema.

Consequences:
- RiSID `non-plastics` → `2` (no longer a judgement call).
- The class list in the config becomes `background / water / debris / clump`. Rename
  everywhere; do not leave `trash` as an alias, it will cause a silent mismatch later.
- The Task 6 annotation guideline needs a *floating vs rooted* rule for vegetation
  instead of a *natural vs anthropogenic* rule. Floating hyacinth mat = `debris`;
  reeds rooted in the bank = `background`. Testable from a fixed camera: if it moves
  downstream between frames it is floating.
- Metrics reporting stays per-class, so if the composition question ever matters, it is
  recoverable in Phase 2 by adding a sub-label — not by changing this schema again.

**2. `barrier` / structure is a config polygon, not a model class.** Unanswered, so my
recommendation stands: a single fixed camera means the structure never moves, a hand-drawn
polygon cannot drift or be mispredicted, and it costs nothing to run. Map RIPTSeg
`barrier`→`0`. Revisit only if the camera is ever repositioned or a second site with a
different structure is added. *Say so if you disagree — it is cheap to change now and
annoying later.*

**3. Diversity within the relevant domain, and balanced sampling.** Six datasets kept,
three dropped on relevance plus two redundant Roboflow sets. Mixed with per-dataset
sampling weights so no single source dominates.

The rule applied: a dataset is kept if it is *plausibly the same problem* — debris or
water on an inland/river surface, viewed by a camera that could be a monitoring camera.
It is dropped if it is a different problem sharing vocabulary (open sea, scenic
photography, satellite, underwater), regardless of how easy it is to convert.

Consequences:
- No nadir-excluded ablation is planned. If debris IoU comes out low in Task 4,
  per-dataset validation metrics will show which source is fighting the others — cheaper
  and more informative than a pre-emptive ablation.
- Per-dataset **sampling weight** is a required config field (see §6), because
  "mix everything" without weights just means "train on RiSID".
- Converted-mask metadata must record source dataset per file, so per-source metrics are
  computable after the fact and further pruning is evidence-driven.
- Dropping ATLANTIS also **removes the hyacinth labelling contradiction** described in
  §7 — the schema no longer has a source that teaches floating vegetation as background.
  That gap now gets filled by Phase 2 site data only, which is the honest position.

---

*Compiled 2026-08-11. All HTTP status codes above reflect checks made on that date.*
