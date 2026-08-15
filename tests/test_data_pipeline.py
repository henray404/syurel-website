"""Checks for the parts of the conversion pipeline that can silently corrupt data.

Deliberately small. Each test guards one failure mode that would otherwise show up
as "the model just doesn't learn" three weeks later.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from data.adapters.coco_polygon import _rasterise
from data.clump import ClumpParams, derive_clump
from data.convert import build_slot_lut, resize_long_side
from data.schema import BACKGROUND, CLUMP, DEBRIS, WATER, Schema, load_schema, read_mask, write_mask
from data.splits import _assign, _hash_order


@pytest.fixture
def schema() -> Schema:
    return load_schema()


def test_schema_ids_are_what_the_docs_claim(schema: Schema) -> None:
    assert schema.names[0] == "background"
    assert schema.names[1] == "water"
    assert schema.names[2] == "debris"
    assert schema.names[3] == "clump"
    assert schema.ignore_index not in schema.names


def test_collapse_is_reversible_and_load_time_only(schema: Schema) -> None:
    """Collapsing clump into debris must be a config edit, never a re-conversion."""
    collapsed = Schema(names=schema.names, ignore_index=255, collapse={"clump": "debris"})
    lut = collapsed.collapse_lut()
    mask = np.array([[BACKGROUND, WATER], [DEBRIS, CLUMP]], dtype=np.uint8)
    assert lut[mask].tolist() == [[0, 1], [2, 2]]
    # The default config collapses nothing.
    assert (schema.collapse_lut() == np.arange(256, dtype=np.uint8)).all()


def test_unmapped_label_is_an_error_not_a_silent_background(schema: Schema) -> None:
    """A dataset that gains a category must break the build, not vanish into class 0."""
    cfg = {"dataset": "x", "label_map": {"water": "water"}}
    with pytest.raises(ValueError, match="not in label_map"):
        build_slot_lut(["water", "mystery_new_class"], cfg, schema)

    lut = build_slot_lut(["water", "mystery_new_class"], dict(cfg, unmapped="background"), schema)
    assert lut[1] == WATER
    assert lut[2] == BACKGROUND
    assert lut[0] == BACKGROUND  # slot 0 is "unlabelled"


def test_paint_order_puts_debris_on_top_of_water() -> None:
    """A bottle on water is debris. If water paints last, every overlap is lost."""
    water_poly = [[0, 0, 100, 0, 100, 100, 0, 100]]
    debris_poly = [[10, 10, 40, 10, 40, 40, 10, 40]]
    anns = [(1, water_poly), (2, debris_poly)]

    good = _rasterise(anns, (100, 100), paint_order=[1, 2])
    assert good[25, 25] == 2, "debris must survive being drawn over water"
    assert good[80, 80] == 1

    bad = _rasterise(anns, (100, 100), paint_order=[2, 1])
    assert bad[25, 25] == 1, "sanity: reversed order really does bury the debris"


def test_mask_resize_never_invents_a_class() -> None:
    """Any interpolation other than NEAREST creates class ids that do not exist."""
    mask = np.zeros((200, 100), dtype=np.uint8)
    mask[:, :50] = WATER
    mask[:, 50:] = CLUMP  # ids 1 and 3 -- bilinear would produce a 2 at the seam
    img = Image.new("RGB", (100, 200))

    _, small = resize_long_side(img, mask, max_size=64)
    assert set(np.unique(small)).issubset({WATER, CLUMP})
    assert max(small.shape) == 64


def test_resize_keeps_image_and_mask_the_same_size() -> None:
    img = Image.new("RGB", (1600, 900))
    mask = np.zeros((900, 1600), dtype=np.uint8)
    img_r, mask_r = resize_long_side(img, mask, max_size=1024)
    assert img_r.size == (mask_r.shape[1], mask_r.shape[0])
    assert max(img_r.size) == 1024


def test_resize_is_a_noop_when_already_small_enough() -> None:
    img = Image.new("RGB", (640, 480))
    mask = np.zeros((480, 640), dtype=np.uint8)
    img_r, mask_r = resize_long_side(img, mask, max_size=1024)
    assert img_r.size == (640, 480)
    assert mask_r.shape == (480, 640)


def test_clump_never_invents_foreground_area() -> None:
    """Coverage is the whole product. Morphological closing must not add pixels."""
    m = np.ones((100, 100), dtype=np.uint8)  # all water
    m[40:60, 10:50] = DEBRIS
    m[40:60, 52:90] = DEBRIS
    before_fg = int(((m == DEBRIS) | (m == CLUMP)).sum())

    out, n = derive_clump(m, ClumpParams(min_area_frac=0.01, close_kernel=3))
    after_fg = int(((out == DEBRIS) | (out == CLUMP)).sum())

    assert n == 1
    assert after_fg == before_fg, "closing leaked clump onto water pixels"
    assert (out[40:60, 50:52] == WATER).all()


def test_clump_ignores_specks() -> None:
    m = np.ones((100, 100), dtype=np.uint8)
    m[0:2, 0:2] = DEBRIS
    out, n = derive_clump(m, ClumpParams(min_area_frac=0.01))
    assert n == 0
    assert (out == m).all()


def test_mask_png_roundtrip_preserves_exact_indices(tmp_path) -> None:
    """Palette PNGs silently turn class indices into colours. Mode 'L' must not."""
    mask = np.array([[0, 1, 2, 3], [3, 2, 1, 0]], dtype=np.uint8)
    p = tmp_path / "m.png"
    write_mask(p, mask)
    assert (read_mask(p) == mask).all()


def test_write_mask_rejects_wrong_dtype(tmp_path) -> None:
    with pytest.raises(ValueError):
        write_mask(tmp_path / "a.png", np.zeros((4, 4), dtype=np.int32))
    with pytest.raises(ValueError):
        write_mask(tmp_path / "b.png", np.zeros((4, 4, 3), dtype=np.uint8))


def test_split_hash_is_stable_and_seed_sensitive() -> None:
    """Python's hash() is salted per process; splits must not be."""
    assert _hash_order(1, "ds", "g") == _hash_order(1, "ds", "g")
    assert _hash_order(1, "ds", "g") != _hash_order(2, "ds", "g")
    assert _hash_order(1, "ds", "g") != _hash_order(1, "other", "g")


def test_no_group_straddles_two_splits() -> None:
    """Frames from one video in both train and val leaks the answer."""
    ratios = {"train": 0.7, "val": 0.15, "test": 0.15}
    by_group = {f"g{i}": [f"s{i}_{j}" for j in range(10)] for i in range(10)}
    groups = sorted(by_group, key=lambda g: _hash_order(20260811, "d", g))

    out, groups_of = _assign(by_group, groups, ratios)

    placed = [g for s in out for g in groups_of[s]]
    assert sorted(placed) == sorted(by_group), "a group was dropped or duplicated"
    assert len(set(placed)) == len(placed), "a group landed in more than one split"
    assert sum(len(v) for v in out.values()) == 100
    assert all(out[s] for s in ("train", "val", "test"))


def test_split_is_deterministic() -> None:
    ratios = {"train": 0.7, "val": 0.15, "test": 0.15}
    by_group = {f"g{i}": [f"s{i}"] for i in range(20)}
    groups = sorted(by_group, key=lambda g: _hash_order(20260811, "d", g))
    assert _assign(by_group, groups, ratios)[0] == _assign(by_group, groups, ratios)[0]


# --- regressions ------------------------------------------------------------


def test_no_split_is_empty_when_there_are_enough_groups() -> None:
    """Regression: sequential quota-filling overshot on the last group and left
    val and test empty. An empty val set means no early stopping and no metrics --
    worse than an off-target ratio, and it looked like success in the summary."""
    ratios = {"train": 0.7, "val": 0.15, "test": 0.15}
    for n_groups in (3, 4, 6, 7):
        by_group = {f"g{i}": [f"s{i}_{j}" for j in range(4)] for i in range(n_groups)}
        groups = sorted(by_group, key=lambda g: _hash_order(20260811, "d", g))
        out, _ = _assign(by_group, groups, ratios)
        assert all(out[s] for s in ("train", "val", "test")), (n_groups, out)


def test_split_ratios_converge_when_groups_are_plentiful() -> None:
    ratios = {"train": 0.7, "val": 0.15, "test": 0.15}
    by_group = {f"g{i}": [f"s{i}_{j}" for j in range(5)] for i in range(60)}
    groups = sorted(by_group, key=lambda g: _hash_order(20260811, "d", g))
    out, _ = _assign(by_group, groups, ratios)
    total = sum(len(v) for v in out.values())
    for s, want in ratios.items():
        assert abs(len(out[s]) / total - want) < 0.05, (s, len(out[s]) / total)


def _write_coco(tmp_path, file_names, subdirs, categories=("t",)):
    """Synthetic COCO where file_name is a BARE BASENAME, as RIPTSeg ships it."""
    import json

    images, anns = [], []
    for i, (fn, sub) in enumerate(zip(file_names, subdirs), start=1):
        p = tmp_path / "images" / sub / fn
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 24)).save(p)
        images.append({"id": i, "file_name": fn, "width": 32, "height": 24})
        anns.append(
            {"id": i, "image_id": i, "category_id": 1, "segmentation": [[0, 0, 8, 0, 8, 8]]}
        )

    ann_dir = tmp_path / "annotations"
    ann_dir.mkdir(parents=True, exist_ok=True)
    (ann_dir / "i.json").write_text(
        json.dumps(
            {
                "images": images,
                "annotations": anns,
                "categories": [{"id": 1, "name": categories[0]}],
            }
        ),
        encoding="utf-8",
    )
    return {
        "dataset": "t",
        "adapter": "coco_polygon",
        "paths": {"images": "images", "annotations": "annotations/i.json"},
    }


def test_bare_basename_resolves_into_subdirectories(tmp_path) -> None:
    """Regression: RIPTSeg's file_name carries no directory while images live in
    loc1..loc6, so `image_root / file_name` resolved to nothing and ALL 300 images
    were skipped in silence."""
    from data.adapters.coco_polygon import CocoPolygonAdapter

    cfg = _write_coco(tmp_path, ["a.jpg", "b.jpg", "c.jpg"], ["loc1", "loc2", "loc3"])

    without = list(CocoPolygonAdapter(cfg, tmp_path).samples())
    assert without == [], "sanity: without recursive_images nothing resolves"

    cfg["recursive_images"] = True
    got = list(CocoPolygonAdapter(cfg, tmp_path).samples())
    assert len(got) == 3, got
    # Group must come from the RESOLVED path, since file_name has no directory.
    assert {s.group for s in got} == {"loc1", "loc2", "loc3"}
    assert {s.sample_id for s in got} == {"loc1__a", "loc2__b", "loc3__c"}


def test_recursive_lookup_refuses_ambiguous_basenames(tmp_path) -> None:
    """Resolving by basename is only safe while basenames are unique."""
    from data.adapters.coco_polygon import CocoPolygonAdapter

    cfg = _write_coco(tmp_path, ["dup.jpg", "dup.jpg"], ["loc1", "loc2"])
    cfg["recursive_images"] = True
    with pytest.raises(ValueError, match="unique basenames"):
        CocoPolygonAdapter(cfg, tmp_path)


def test_unlabelled_can_be_ignored_instead_of_background(schema: Schema) -> None:
    """Regression: RIPTSeg annotates only ~20% of each frame. Mapping the rest to
    background taught the model that real river water is background."""
    cfg = {"dataset": "x", "label_map": {"water": "water"}}

    lut_bg = build_slot_lut(["water"], cfg, schema)
    assert lut_bg[0] == BACKGROUND, "default must stay background"

    lut_ig = build_slot_lut(["water"], dict(cfg, unlabelled="ignore"), schema)
    assert lut_ig[0] == schema.ignore_index
    assert lut_ig[1] == WATER, "mapped labels are unaffected"

    with pytest.raises(ValueError, match="unlabelled must be"):
        build_slot_lut(["water"], dict(cfg, unlabelled="nonsense"), schema)


def test_coco_sample_ids_do_not_collide_across_directories(tmp_path) -> None:
    """Regression: sample_id came from the filename stem, so RIPTSeg's
    loc1/frame_000.jpg .. loc6/frame_000.jpg all collapsed onto one id and 5/6 of
    the dataset was silently skipped as 'already converted'."""
    from data.adapters.coco_polygon import CocoPolygonAdapter

    images, anns = [], []
    for loc in (1, 2, 3):
        rel = f"loc{loc}/frame_000.jpg"
        p = tmp_path / "images" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 24)).save(p)
        images.append({"id": loc, "file_name": rel, "width": 32, "height": 24})
        anns.append(
            {"id": loc, "image_id": loc, "category_id": 1, "segmentation": [[0, 0, 8, 0, 8, 8]]}
        )

    ann_dir = tmp_path / "annotations"
    ann_dir.mkdir(parents=True, exist_ok=True)
    import json

    (ann_dir / "i.json").write_text(
        json.dumps({"images": images, "annotations": anns, "categories": [{"id": 1, "name": "t"}]}),
        encoding="utf-8",
    )

    cfg = {
        "dataset": "t",
        "adapter": "coco_polygon",
        "paths": {"images": "images", "annotations": "annotations/i.json"},
    }
    ids = [s.sample_id for s in CocoPolygonAdapter(cfg, tmp_path).samples()]
    assert len(ids) == len(set(ids)) == 3, ids
    groups = {s.group for s in CocoPolygonAdapter(cfg, tmp_path).samples()}
    assert groups == {"loc1", "loc2", "loc3"}
