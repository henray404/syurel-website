"""COCO instance-segmentation polygons -> semantic mask.

Covers RIPTSeg (4TU) and RiSID v2. Both ship polygon `segmentation` lists, so
this rasterises with PIL and avoids a pycocotools dependency entirely
(pycocotools is a recurring build headache on Windows). RLE segmentations fall
back to pycocotools only if actually encountered.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from ..base import Adapter, Sample, register


def _rasterise(
    ann_groups: list[tuple[int, Any]],
    size: tuple[int, int],
    paint_order: list[int],
) -> np.ndarray:
    """Paint polygons into a HxW uint8 mask of source label slots (1-based).

    `ann_groups` is [(label_slot, segmentation), ...]. Painting follows
    `paint_order` so that e.g. debris drawn after water wins on overlap, which is
    what we want: a bottle sitting on water is debris, not water.
    """
    width, height = size
    canvas = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(canvas)

    by_slot: dict[int, list[Any]] = defaultdict(list)
    for slot, seg in ann_groups:
        by_slot[slot].append(seg)

    for slot in paint_order:
        for seg in by_slot.get(slot, []):
            if isinstance(seg, dict):  # RLE
                binary = _decode_rle(seg, height, width).astype(bool)
                arr = np.array(canvas, dtype=np.uint8)
                arr[binary] = slot
                canvas = Image.fromarray(arr, mode="L")
                draw = ImageDraw.Draw(canvas)
                continue
            for poly in seg:
                if len(poly) < 6:  # need >= 3 points
                    continue
                pts = [(float(poly[i]), float(poly[i + 1])) for i in range(0, len(poly) - 1, 2)]
                draw.polygon(pts, fill=slot)

    return np.array(canvas, dtype=np.uint8)


def _decode_rle(seg: dict[str, Any], height: int, width: int) -> np.ndarray:
    try:
        from pycocotools import mask as mask_utils  # type: ignore
    except ImportError as exc:  # pragma: no cover - only hit on RLE datasets
        raise RuntimeError(
            "This COCO file contains RLE segmentations, which need pycocotools. "
            "Install it with `uv add pycocotools` and re-run. "
            "(Neither RIPTSeg nor RiSID needed it at survey time.)"
        ) from exc
    # Two RLE shapes reach us, and frPyObjects only handles one of them.
    # `counts` as a list of ints is uncompressed RLE, which frPyObjects converts.
    # `counts` as a string is ALREADY compressed RLE -- Roboflow's brush/SAM
    # labels export that way -- and frPyObjects then runs int() over the encoded
    # bytes and raises `invalid literal for int() with base 10`. Compressed RLE
    # goes straight to decode; it only needs its counts as bytes.
    counts = seg.get("counts")
    if isinstance(counts, str):
        rle = {"counts": counts.encode("ascii"), "size": seg["size"]}
    elif isinstance(counts, bytes):
        rle = seg
    else:
        rle = mask_utils.frPyObjects(seg, height, width)
    return mask_utils.decode(rle).astype(np.uint8)


@register("coco_polygon")
class CocoPolygonAdapter(Adapter):
    kind = "mask"

    def __init__(self, cfg: dict[str, Any], raw_root: Path) -> None:
        super().__init__(cfg, raw_root)
        ann_path = self._resolve("annotations")
        self.image_root = self._resolve("images")
        coco = json.loads(ann_path.read_text(encoding="utf-8"))

        cat_name: dict[int, str] = {int(c["id"]): str(c["name"]) for c in coco["categories"]}

        # Source label vocabulary, in a stable order. Slot = index + 1.
        self.labels: list[str] = sorted(set(cat_name.values()))
        slot_of = {name: i + 1 for i, name in enumerate(self.labels)}
        slot_of_cat = {cid: slot_of[name] for cid, name in cat_name.items()}

        # Painting order: later wins. Config lists source label names; anything
        # unlisted is painted first (lowest priority).
        order_names: list[str] = list(cfg.get("paint_order") or [])
        unknown = set(order_names) - set(self.labels)
        if unknown:
            raise ValueError(
                f"{self.dataset}: paint_order names not in the COCO categories: {sorted(unknown)}. "
                f"Available: {self.labels}"
            )
        rest = [n for n in self.labels if n not in order_names]
        self.paint_order = [slot_of[n] for n in rest + order_names]

        self._images = {int(im["id"]): im for im in coco["images"]}
        self._anns: dict[int, list[tuple[int, Any]]] = defaultdict(list)
        for ann in coco["annotations"]:
            seg = ann.get("segmentation")
            if not seg:
                continue
            self._anns[int(ann["image_id"])].append((slot_of_cat[int(ann["category_id"])], seg))

        # Frames from the same source video are near-duplicates. Group by a path
        # component so splits cannot straddle them; configurable because RIPTSeg
        # groups by loc1..loc6 directory and RiSID by filename stem prefix.
        self.group_from = str(cfg.get("group_from", "parent"))
        self._group_re = re.compile(str(cfg["group_regex"])) if cfg.get("group_regex") else None
        if self.group_from == "regex" and self._group_re is None:
            raise ValueError(f"{self.dataset}: group_from: regex requires a `group_regex`")

        # RIPTSeg stores a bare basename in file_name while the images sit in
        # loc1/..loc6/ subdirectories, so `image_root / file_name` resolves to
        # nothing and every sample would be skipped in silence. Build a
        # basename -> path index and fall back to it. Refuses on ambiguity rather
        # than picking an arbitrary match.
        self._by_name: dict[str, Path] = {}
        if bool(cfg.get("recursive_images", False)):
            dupes = []
            for p in self.image_root.rglob("*"):
                if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                    if p.name in self._by_name:
                        dupes.append(p.name)
                    self._by_name[p.name] = p
            if dupes:
                raise ValueError(
                    f"{self.dataset}: recursive_images needs unique basenames, but "
                    f"{len(dupes)} collide (e.g. {sorted(set(dupes))[:3]}). "
                    f"Resolving by basename would silently pick the wrong file."
                )
        self._unresolved = 0

    def __len__(self) -> int:
        return len(self._images)

    def _resolve_image(self, file_name: str) -> Path | None:
        direct = self.image_root / file_name
        if direct.exists():
            return direct
        return self._by_name.get(Path(file_name).name)

    def _group_key(self, rel: str) -> str:
        p = Path(rel)
        # `rel` arrives with the extension ALREADY removed, so use .name, never
        # .stem: RiSID filenames embed a dot mid-name
        # ("20221007124922_d.flv20221007124922_d_001255_6_0"), and .stem would
        # treat everything after that dot as a suffix and cut the name to
        # "20221007124922_d".
        stem = p.name
        if self.group_from == "parent":
            return p.parent.name or self.dataset
        if self.group_from == "stem_prefix":
            # "arakawa_20210715_000123.jpg" -> "arakawa_20210715"
            parts = stem.rsplit("_", 1)
            return parts[0] if len(parts) == 2 else stem
        if self.group_from == "regex":
            # For datasets whose grouping needs more than a suffix strip. RiSID
            # names frames "<video>_<frame>_<n>.png", and stem_prefix left 7332
            # groups for 7356 images -- i.e. no grouping at all, while 90% of
            # adjacent frames sit under 10 frames apart. Group 1 of the match is
            # the key; a non-match falls back to the stem (its own group), which
            # is the conservative direction.
            m = self._group_re.search(stem) if self._group_re else None
            return m.group(1) if m else stem
        if self.group_from == "flat":
            return self.dataset
        raise ValueError(f"{self.dataset}: unknown group_from {self.group_from!r}")

    def samples(self) -> Iterator[Sample]:
        skip_empty = bool(self.cfg.get("skip_unannotated", False))

        for image_id, im in self._images.items():
            anns = self._anns.get(image_id, [])
            if skip_empty and not anns:
                continue

            file_name = str(im["file_name"])
            image_path = self._resolve_image(file_name)
            if image_path is None:
                # Counted, not silent: an adapter that quietly yields nothing is
                # indistinguishable from an empty dataset.
                self._unresolved += 1
                continue

            # COCO width/height are sometimes wrong or absent; trust the file.
            width, height = int(im.get("width", 0)), int(im.get("height", 0))
            if width <= 0 or height <= 0:
                with Image.open(image_path) as img:
                    width, height = img.size

            def build(anns: list[tuple[int, Any]] = anns, size: tuple[int, int] = (width, height)) -> np.ndarray:
                return _rasterise(anns, size, self.paint_order)

            # Derive id and group from the RESOLVED path, not from file_name.
            # file_name may be a bare basename (RIPTSeg), in which case it carries
            # no directory to group on; the resolved path always does. Using the
            # stem alone would also collide across loc1..loc6.
            rel = image_path.relative_to(self.image_root).with_suffix("").as_posix().strip("/")
            yield Sample(
                sample_id=rel.replace("/", "__"),
                image_path=image_path,
                group=self._group_key(rel),
                labels=self.labels,
                build_mask=build,
                extra={"n_instances": len(anns)},
            )

        if self._unresolved:
            print(
                f"[{self.dataset}] WARNING: {self._unresolved} annotated image(s) not found "
                f"under {self.image_root}. Set `recursive_images: true` if the images are "
                f"in subdirectories."
            )
