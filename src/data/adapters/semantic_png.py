"""Pre-rendered semantic mask PNGs -> our source-slot mask.

Covers LaRS (panoptic semantic layer) and USVInland (water segmentation subset),
and anything else shipping "image dir + mask dir". The decoding rule lives in the
dataset YAML, either:

    id_to_label:      { 0: water, 1: sky, 2: static_obstacle }
    # or, for colour-coded masks:
    color_to_label:   { "0,0,255": water, "255,0,0": static_obstacle }

NOTE: the directory layouts are configured, not hardcoded, because the on-disk
structure of LaRS and USVInland was not verified during the Phase 1 survey
(see docs/datasets.md). Point `paths.images` / `paths.masks` at whatever the
download actually contains; if the layout is nested, set `recursive: true`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..base import Adapter, Sample, register

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp")


def _parse_color(key: str) -> tuple[int, int, int]:
    parts = [int(x) for x in str(key).replace(" ", "").split(",")]
    if len(parts) != 3:
        raise ValueError(f"color key {key!r} must be 'R,G,B'")
    return parts[0], parts[1], parts[2]


@register("semantic_png")
class SemanticPngAdapter(Adapter):
    kind = "mask"

    def __init__(self, cfg: dict[str, Any], raw_root: Path) -> None:
        super().__init__(cfg, raw_root)
        self.image_root = self._resolve("images")
        self.mask_root = self._resolve("masks")
        self.recursive = bool(cfg.get("recursive", False))
        self.mask_suffix = str(cfg.get("mask_suffix", ".png"))
        self.group_from = str(cfg.get("group_from", "parent"))

        id_to_label = cfg.get("id_to_label")
        color_to_label = cfg.get("color_to_label")
        if bool(id_to_label) == bool(color_to_label):
            raise ValueError(
                f"{self.dataset}: set exactly one of id_to_label / color_to_label in the dataset YAML"
            )

        if id_to_label:
            self._mode = "id"
            self.labels = sorted({str(v) for v in id_to_label.values()})
            slot_of = {name: i + 1 for i, name in enumerate(self.labels)}
            # 256-entry LUT: source pixel id -> our slot. Unlisted ids -> 0 (unlabelled).
            self._lut = np.zeros(256, dtype=np.uint8)
            for src_id, label in id_to_label.items():
                self._lut[int(src_id)] = slot_of[str(label)]
        else:
            self._mode = "color"
            self.labels = sorted({str(v) for v in color_to_label.values()})
            slot_of = {name: i + 1 for i, name in enumerate(self.labels)}
            self._colors = [(_parse_color(k), slot_of[str(v)]) for k, v in color_to_label.items()]

        self._pairs = self._index()

    def _index(self) -> list[tuple[Path, Path]]:
        globber = self.image_root.rglob if self.recursive else self.image_root.glob
        pairs: list[tuple[Path, Path]] = []
        for img in sorted(globber("*")):
            if img.suffix.lower() not in IMAGE_EXTS:
                continue
            rel = img.relative_to(self.image_root)
            mask = self.mask_root / rel.with_suffix(self.mask_suffix)
            if mask.exists():
                pairs.append((img, mask))
        if not pairs:
            raise FileNotFoundError(
                f"{self.dataset}: no image/mask pairs under {self.image_root} + {self.mask_root}. "
                f"Check paths.images / paths.masks / mask_suffix / recursive in the dataset YAML."
            )
        return pairs

    def __len__(self) -> int:
        return len(self._pairs)

    def _group_key(self, img: Path) -> str:
        if self.group_from == "parent":
            rel = img.relative_to(self.image_root)
            return rel.parent.name or self.dataset
        if self.group_from == "stem_prefix":
            parts = img.stem.rsplit("_", 1)
            return parts[0] if len(parts) == 2 else img.stem
        if self.group_from == "flat":
            return self.dataset
        raise ValueError(f"{self.dataset}: unknown group_from {self.group_from!r}")

    def _decode(self, mask_path: Path) -> np.ndarray:
        raw = Image.open(mask_path)
        if self._mode == "id":
            arr = np.array(raw.convert("L"), dtype=np.uint8)
            return self._lut[arr]
        rgb = np.array(raw.convert("RGB"), dtype=np.uint8)
        out = np.zeros(rgb.shape[:2], dtype=np.uint8)
        for (r, g, b), slot in self._colors:
            out[(rgb[..., 0] == r) & (rgb[..., 1] == g) & (rgb[..., 2] == b)] = slot
        return out

    def samples(self) -> Iterator[Sample]:
        for img, mask_path in self._pairs:
            sid = img.relative_to(self.image_root).with_suffix("").as_posix().replace("/", "__")
            yield Sample(
                sample_id=sid,
                image_path=img,
                group=self._group_key(img),
                labels=self.labels,
                build_mask=lambda p=mask_path: self._decode(p),
            )
