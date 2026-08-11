"""Importing this package registers every adapter.

Adding a dataset that fits an existing shape (COCO polygons, semantic PNGs, VOC
boxes) needs only a YAML in configs/datasets/ -- no code at all. Adding a genuinely
new *shape* means one new module here plus one line below.
"""

from . import coco_polygon, semantic_png, voc_bbox  # noqa: F401

__all__ = ["coco_polygon", "semantic_png", "voc_bbox"]
