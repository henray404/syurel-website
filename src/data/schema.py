"""Target class schema and mask I/O.

Everything that touches class indices goes through here so there is exactly one
place where 0/1/2/3 is defined.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

# Repo root = three levels up from this file (src/data/schema.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLASSES_YAML = REPO_ROOT / "configs" / "classes.yaml"

BACKGROUND = 0
WATER = 1
DEBRIS = 2
CLUMP = 3

# Foreground for the coverage metric: coverage = (debris+clump)/(debris+clump+water)
FOREGROUND = (DEBRIS, CLUMP)


@dataclass(frozen=True)
class Schema:
    names: dict[int, str]
    ignore_index: int
    collapse: dict[str, str]

    @property
    def ids(self) -> list[int]:
        return sorted(self.names)

    def id_of(self, name: str) -> int:
        for i, n in self.names.items():
            if n == name:
                return i
        raise KeyError(f"unknown class name {name!r}; known: {sorted(self.names.values())}")

    def collapse_lut(self) -> np.ndarray:
        """256-entry LUT applying `collapse` from the config.

        Applied at load time, never baked into the PNGs, so collapsing clump into
        debris is a config edit and not a re-conversion.
        """
        lut = np.arange(256, dtype=np.uint8)
        for src_name, dst_name in self.collapse.items():
            lut[self.id_of(src_name)] = self.id_of(dst_name)
        return lut


def load_schema(path: Path | str = DEFAULT_CLASSES_YAML) -> Schema:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    names = {int(c["id"]): str(c["name"]) for c in cfg["classes"]}
    ignore = int(cfg.get("ignore_index", 255))
    if ignore in names:
        raise ValueError(f"ignore_index {ignore} collides with class id")
    return Schema(names=names, ignore_index=ignore, collapse=dict(cfg.get("collapse") or {}))


def write_mask(path: Path, mask: np.ndarray) -> None:
    """Write a HxW uint8 class-index mask as a single-channel PNG.

    Explicitly mode 'L', not a palette image: palette PNGs silently round-trip
    through some tools as RGB and the class indices turn into colours.
    """
    if mask.ndim != 2:
        raise ValueError(f"mask must be HxW, got shape {mask.shape}")
    if mask.dtype != np.uint8:
        raise ValueError(f"mask must be uint8, got {mask.dtype}")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask, mode="L").save(path, optimize=True)


def read_mask(path: Path) -> np.ndarray:
    arr = np.array(Image.open(path))
    if arr.ndim != 2:
        raise ValueError(f"{path} is not a single-channel mask (shape {arr.shape})")
    return arr.astype(np.uint8)


def class_pixel_counts(mask: np.ndarray, n_ids: int = 256) -> np.ndarray:
    """Histogram of class indices. Returns a length-n_ids int64 array."""
    return np.bincount(mask.ravel(), minlength=n_ids).astype(np.int64)
