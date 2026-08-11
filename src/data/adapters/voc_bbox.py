"""Pascal VOC XML bounding boxes -> Sample(boxes=...).

Covers IWHR_AI_Lable_Floater_V1 (ships VOC XML plus voc_label.py) and Roboflow
Universe exports set to "Pascal VOC".

This adapter emits boxes only. Turning boxes into masks is SAM's job and happens
in convert.py, so the expensive, reviewable step stays in one place instead of
being duplicated per dataset.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..base import Adapter, Sample, register

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp")

Box = tuple[str, tuple[float, float, float, float]]


def _parse_voc(xml_path: Path) -> tuple[str | None, list[Box]]:
    root = ET.parse(xml_path).getroot()
    filename_el = root.find("filename")
    filename = filename_el.text.strip() if filename_el is not None and filename_el.text else None

    boxes: list[Box] = []
    for obj in root.findall("object"):
        name_el = obj.find("name")
        bb = obj.find("bndbox")
        if name_el is None or name_el.text is None or bb is None:
            continue

        def _f(tag: str, bb: ET.Element = bb) -> float | None:
            el = bb.find(tag)
            return float(el.text) if el is not None and el.text else None

        x0, y0, x1, y1 = _f("xmin"), _f("ymin"), _f("xmax"), _f("ymax")
        if x0 is None or y0 is None or x1 is None or y1 is None:
            continue
        if x1 <= x0 or y1 <= y0:  # degenerate box, seen in user-contributed sets
            continue
        boxes.append((name_el.text.strip(), (x0, y0, x1, y1)))
    return filename, boxes


@register("voc_bbox")
class VocBboxAdapter(Adapter):
    kind = "bbox"

    def __init__(self, cfg: dict[str, Any], raw_root: Path) -> None:
        super().__init__(cfg, raw_root)
        self.image_root = self._resolve("images")
        self.ann_root = self._resolve("annotations")
        self.recursive = bool(cfg.get("recursive", False))
        self.group_from = str(cfg.get("group_from", "flat"))
        self.skip_empty = bool(cfg.get("skip_unannotated", True))

        globber = self.ann_root.rglob if self.recursive else self.ann_root.glob
        self._xmls = sorted(globber("*.xml"))
        if not self._xmls:
            raise FileNotFoundError(
                f"{self.dataset}: no .xml under {self.ann_root}. "
                f"For Roboflow, export the dataset as 'Pascal VOC' rather than YOLO."
            )

        # Grows as XMLs are read; the dataset YAML's label_map is what actually
        # validates the vocabulary, in convert.py.
        self.labels: list[str] = list(cfg.get("labels") or [])

    def __len__(self) -> int:
        return len(self._xmls)

    def _find_image(self, xml_path: Path, declared: str | None) -> Path | None:
        rel_parent = xml_path.parent.relative_to(self.ann_root)
        candidates: list[Path] = []
        if declared:
            candidates.append(self.image_root / rel_parent / declared)
        candidates += [self.image_root / rel_parent / (xml_path.stem + ext) for ext in IMAGE_EXTS]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _group_key(self, img: Path) -> str:
        if self.group_from == "parent":
            return img.parent.name or self.dataset
        if self.group_from == "stem_prefix":
            parts = img.stem.rsplit("_", 1)
            return parts[0] if len(parts) == 2 else img.stem
        if self.group_from == "flat":
            return self.dataset
        raise ValueError(f"{self.dataset}: unknown group_from {self.group_from!r}")

    def samples(self) -> Iterator[Sample]:
        for xml_path in self._xmls:
            declared, boxes = _parse_voc(xml_path)
            if self.skip_empty and not boxes:
                continue
            image_path = self._find_image(xml_path, declared)
            if image_path is None:
                continue  # counted and reported in aggregate by convert.py

            for name, _ in boxes:
                if name not in self.labels:
                    self.labels.append(name)

            # Relative-path id, not bare stem: nested VOC exports reuse filenames
            # across subdirectories and a stem-based id would silently collide.
            rel = xml_path.relative_to(self.ann_root).with_suffix("").as_posix()
            yield Sample(
                sample_id=rel.replace("/", "__"),
                image_path=image_path,
                group=self._group_key(image_path),
                labels=self.labels,
                boxes=boxes,
                extra={"n_boxes": len(boxes)},
            )
