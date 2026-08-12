# Annotation guideline — Phase 2 site data

This document matters more than the class list. Inconsistent labels are the main
way this project fails, and they fail it invisibly: the model trains, the loss
falls, the metrics look plausible, and the numbers are wrong in a way no
validation split can detect — because the validation labels carry the same
inconsistency.

Every rule below is written to be **testable**: two people applying it to the same
frame should produce the same mask. Where a rule cannot be made testable, that is
said outright, along with the fallback.

---

## 1. The classes

| id | name | what it is |
|---|---|---|
| 0 | `background` | everything that is not the water surface or floating on it: bank, road, sky, vegetation rooted on land, the structure itself when clean |
| 1 | `water` | visible river surface |
| 2 | `debris` | **anything floating that is not water** |
| 3 | `clump` | an aggregated mat where individual items cannot be separated — see §4 |

**Class 2 is `debris`, not `trash`.** Origin is deliberately out of the schema:
plastic, sachets, styrofoam, bags, wood, leaves, and water hyacinth are all
`debris`. This is a decision, not an oversight — see
[docs/datasets.md §9](datasets.md) for the reasoning. In one line: a hyacinth mat
blocks a trash rack exactly as well as a sachet mat, and asking an annotator to
judge "is this anthropogenic?" from a fixed camera at 20 m produces coin flips.

**Only annotate what is inside the ROI polygon.** Outside it, label nothing.

---

## 2. The ambiguous cases

These are the ones that actually cost you consistency. Each has a rule and a
reason. When the rule and your instinct disagree, follow the rule — consistency is
worth more than any individual mask being perfect.

### 2.1 Partially submerged debris

**Rule: label only the visible portion. Do not extrapolate the submerged part.**

A bottle floating with 30% above water is 30% debris pixels, not 100%. Draw the
boundary where the object visually disappears into the water.

*Why:* the metric is surface coverage, and the model can only ever see the
surface. Guessing at the submerged volume adds annotator-specific noise to the one
number the project produces — and different annotators guess differently, which is
worse than everyone being consistently conservative.

*Edge case:* an object visible only as a dark shape *under* the surface is
`water`, not `debris`. If you cannot tell where the waterline crosses it, label
the clearly-above-water part and stop.

### 2.2 Reflections and sun glare

**Rule: never `debris`. Label as `water`.**

A bright specular patch, a sun glint track, or the mirrored image of a bridge on
the surface is all `water`.

*Test:* does it move with the water surface, or stay put as the water flows under
it? Reflections and glare are **fixed to the geometry** of sun, camera, and object
— they do not drift downstream. Real debris drifts. Check two frames a few seconds
apart if you are unsure.

*Why this one gets its own rule:* this is the single most common false positive
for a bright class like styrofoam, and if glare is labelled `debris` even
occasionally, you are actively training the model to fire on sunshine.

### 2.3 White foam versus fragmented styrofoam

The genuinely hard one. Both are white, both float, both fragment.

| | natural foam | styrofoam |
|---|---|---|
| edges | soft, diffuse, no defined boundary | sharp, defined, geometric |
| shape | forms streaks and lines along flow | discrete lumps, irregular but bounded |
| behaviour | forms and dissipates; changes shape between frames | persists; rigid, same shape frame to frame |
| location | downstream of turbulence, piers, weirs | anywhere |
| texture | uniform | often shows facets or broken-cell texture |

**Rule: `debris` only if it has a defined edge you could trace. Diffuse foam with
no traceable boundary is `water`.**

**Rule: when genuinely uncertain after checking two frames, label `water`.**

*Why bias toward `water`:* foam appears constantly and styrofoam appears in
bursts. A false `debris` on foam pollutes a large number of frames with a
persistent, systematic error; a missed styrofoam fragment costs one object in one
frame. The asymmetry is large, so the tie-break is not symmetric either.

*If this proves unworkable at your site* — some rivers foam heavily enough that
the distinction is genuinely impossible — say so early. The fallback is a
site-specific decision to label all persistent white as `debris` and accept the
bias, recorded in the dataset metadata. Do not let individual annotators make that
call frame by frame.

### 2.4 Shadows on water

**Rule: `water`. Always.**

Bridge shadows, pier shadows, cloud shadows, vegetation shadows. Dark water is
still water.

*Corollary that is easy to get wrong:* debris **inside** a shadow is still
`debris`. Do not skip a shadowed region because it is hard to see — that teaches
the model that dark regions contain nothing, which is precisely wrong at dawn,
dusk, and under the bridge you are monitoring. If you cannot resolve a shadowed
region at all, mark the frame for review rather than labelling it as empty water.

### 2.5 Boats, people, animals

**Rule: `background`. Not `debris`, not `water`.**

Boats, canoes, people wading or swimming, buffalo, birds on the surface, fishing
gear in active use.

*Why `background` and not `debris`:* they float, so a literal reading of "anything
floating that is not water" would include them. But they are not transported by
the river and they are not a blockage risk — counting them would put a spike in
the coverage time series every time a boat passes, and that spike would correlate
with human activity, not rainfall. The rainfall correlation is half the point of
the project.

*Test: is it self-propelled, moored, or carried by the current?* Carried by the
current → `debris`. Self-propelled or moored → `background`.

### 2.6 Floating vegetation, including water hyacinth

**Rule: `debris` if it is floating and moving with the current. `background` if it
is rooted.**

*Test — and this is the whole reason the rule is stated this way:* does it move
downstream between frames? Floating hyacinth mats drift. Reeds and grasses rooted
in the bank or the shallows stay put, even when the current bends them.

*Why:* water hyacinth is a first-order feature of Indonesian rivers, it physically
entangles plastic waste, and it blocks a trash rack. Excluding it would make the
blockage alert blind to one of the most common real blockage causes. This is also
the one class where public training data actively taught the wrong thing (see
[docs/datasets.md §7](datasets.md)), so your site labels are the only source of
truth the model will ever get.

*Hard case:* a hyacinth mat pinned against the structure is not moving, but it is
not rooted either. Rule: **pinned against the structure counts as `debris`** — see
§2.7, which is the same rule.

### 2.7 Debris caught on the rack, above the waterline

**Rule: `debris`. Explicitly counted. This one is not optional.**

Trash piled against a bridge pier or trash rack, sitting above the waterline, dry,
no longer floating — label it `debris`.

*Why, stated bluntly:* this is the blockage signal. It is the thing that raises
the upstream water level, and detecting it is the first of the two use cases this
system exists for. A guideline that only counted floating items would make the
model blind at exactly the moment it matters most, because in a real blockage the
mat stops floating and starts piling.

*Boundary:* label up to where the pile visually ends. The clean structure itself
is `background`; the material on it is `debris`. If the pile extends above the
frame or out of the ROI, label to the edge and stop.

*Note for the inference side:* this is why `configs/inference/site_example.yaml`
tells you to draw the structure polygon generously enough to include the region
above the waterline.

### 2.8 Quick reference

| what you see | class |
|---|---|
| bottle, bag, sachet, cup, styrofoam lump | `debris` |
| wood, branch, leaf raft | `debris` |
| floating hyacinth mat (drifting) | `debris` |
| trash piled on the rack, above water | `debris` |
| submerged part of a floating object | `water` |
| sun glare, specular highlight | `water` |
| reflection of bridge/sky/trees | `water` |
| shadow on water | `water` |
| diffuse foam with no traceable edge | `water` |
| debris inside a shadow | `debris` |
| boat, person, animal | `background` |
| rooted reeds, bank vegetation | `background` |
| clean pier / rack surface | `background` |
| anything outside the ROI | *leave unlabelled* |

---

## 3. Before you annotate anything

Do this once; it saves more time than it costs:

1. Draw the ROI polygon on a representative frame. Everything outside it is out of
   scope forever.
2. Draw the structure polygon (pier / rack), generous enough to include the pile
   region above the waterline.
3. **Annotate 10 frames, then stop.** Have a second person annotate the same 10
   independently. Compare. If you disagree on more than ~10% of foreground pixels,
   the disagreement is in a rule above and not in your skill — find which rule,
   write down the site-specific clarification, and only then continue.

That 20-frame exercise is the highest-value hour in Phase 2. Skipping it is how
you discover the inconsistency after 400 frames are done.

---

## 4. `debris` versus `clump` — the hardest rule

### The proposed rule

> A region is `clump` when **individual item boundaries cannot be visually
> determined** — you cannot trace where one object ends and the next begins.
> Otherwise it is `debris`.

### Making it testable

The rule above is still subjective. Two operational tests, either sufficient:

1. **The tracing test.** Could you, in under ~5 seconds, draw the outline of one
   individual item inside the region? If yes → `debris`. If you would be guessing
   at the boundary → `clump`.
2. **The count test.** Could two annotators agree on how many items are in the
   region, ±1? If yes → `debris`. If their counts would differ wildly → `clump`.

**A single large object is never `clump`.** A whole tree branch is `debris`, no
matter how big. `clump` is about *aggregation*, not size.

**A clump is contiguous.** Two separate mats with clear water between them are two
clump regions, not one.

### Sanity floor

If a region is smaller than roughly **1% of the ROI area**, do not call it `clump`
regardless — small regions are almost always separable, and the heuristic in
`src/data/clump.py` uses a comparable area threshold. Keeping the human rule and
the automatic rule roughly aligned means the two label sources do not fight.

### Prior art worth 10 minutes

The Roboflow dataset *River Trash final* has a `clustered-trash` class — someone
hit this exact problem and drew a boundary. Look at their examples before
finalising your own interpretation:
<https://universe.roboflow.com/trisha-lingat-m9vjl/river-trash-final-k9997>

### The fallback, and when to take it

**If `clump` proves inconsistent in practice, merge it into `debris` and derive
clumps post-hoc from connected-component area.** This is fully supported and costs
nothing:

- annotation: label everything `debris`, stop thinking about clump
- config: uncomment the collapse rule in `configs/classes.yaml`

  ```yaml
  collapse:
    clump: debris
  ```

- the collapse is applied at load time, not baked into the PNGs, so it is
  reversible without re-converting anything
- clumps are then derived automatically by `src/data/clump.py`

**Decide this on evidence, not vibes.** In the 20-frame calibration exercise in
§3, measure agreement on `clump` specifically. **If two annotators disagree on
more than ~20% of clump-labelled pixels, take the fallback immediately.** A class
that cannot be labelled consistently is worse than no class: it injects noise into
`debris` as well, because every clump disagreement is also a debris disagreement.

Honest assessment: `clump` is the most likely part of this schema to be abandoned,
and that is fine. It was designed with an escape hatch for that reason.

---

## 5. Frame sampling — diversity beats volume

**Target: 300–500 annotated frames.** More than that has sharply diminishing
returns for a fixed camera, because consecutive frames from one viewpoint are
enormously redundant.

### The one hard rule

**Never annotate consecutive frames.** Two frames one second apart are nearly the
same image. They cost two annotations and give you slightly more than one frame's
worth of information — and worse, if they land in different splits they leak
validation data into training and inflate every metric you report.

Minimum spacing: **5 minutes** between sampled frames. Prefer different days.

### What to spread across

Aim for coverage of each axis rather than a fixed count per cell — but if a cell
is empty, the model will be blind in that condition.

| axis | must include |
|---|---|
| time of day | dawn, morning, midday (harshest glare), afternoon, dusk, night if the camera has IR |
| weather | clear, overcast, light rain, heavy rain |
| water level | low, normal, high, **flood** |
| debris density | empty water, sparse items, moderate, dense mat, rack blockage |
| water appearance | clear-ish, turbid brown, post-rain sediment surge |
| surface state | calm, rippled, glare-heavy |

**Flood frames are the most valuable and the hardest to get.** They are the
condition the blockage alert exists for, and they occur only a few times a season.
Set up recording *before* the rainy season and archive aggressively — you cannot
retroactively capture a flood.

**Deliberately include boring frames.** Empty water with no debris is a real and
common state; if every annotated frame contains debris, the model learns that
debris is always present and will hallucinate it on clean water. Roughly 15–20% of
the set should be genuinely empty.

**Deliberately include the failure modes.** Frames with heavy glare, rain on the
lens, a boat passing, a hyacinth mat. These are worth more than another frame of
ordinary conditions.

### Active learning loop

Do not annotate all 400 frames up front.

1. **Annotate ~100 frames**, spread across the axes above as best you can.
2. **Train** on them (`python -m train.train --config ...`) — it does not need to
   be a good model, it needs to be an opinionated one.
3. **Run it over the unannotated pool.**
4. **Rank by uncertainty** and annotate the least-confident ~100 next.
5. **Repeat** until validation debris IoU stops improving.

A usable uncertainty score, cheapest first:

- **mean top-2 softmax margin** per frame — a small margin means the model is torn
  between two classes. Simple and effective.
- **predicted debris area near zero but nonzero** — the model half-sees something.
- **disagreement between two resolutions** (416 vs 640) — a cheap proxy for
  instability, and it directly surfaces the small-object failures Task 4 warns
  about.

*Why this ordering pays:* the model learns nothing from a frame it already gets
right, and clean water frames are the majority of any pool. Uncertainty sampling
spends your annotation hours on the frames that change the model, which in
practice is glare, dense mats, and low light.

**Keep the axis coverage from above even while doing this.** Pure uncertainty
sampling over-selects weird frames and can leave you with no ordinary examples at
all. Rule of thumb: **~70% uncertainty-selected, ~30% deliberately sampled for
diversity.**

---

## 6. Practical notes

- **Tooling:** anything that exports polygons or masks. The converter already
  reads COCO polygons (`src/data/adapters/coco_polygon.py`), so a COCO export
  needs no new code — one dataset YAML and you are done.
- **Splits are group-aware.** Frames are grouped and never split within a group
  (`src/data/splits.py`). Record which recording session each frame came from;
  that becomes the group key, and it is what stops leakage.
- **Label the whole ROI in every annotated frame.** Partial annotation means
  unlabelled water gets learned as `background`, which quietly corrupts the
  coverage denominator. If a frame is too hard to complete, discard it rather than
  half-labelling it.
- **When you break a rule deliberately, write it down.** A short note per site
  beats a rule everyone remembers differently.
- **Re-read §2 after your first 50 frames.** Drift is real, and it is easiest to
  correct early.
