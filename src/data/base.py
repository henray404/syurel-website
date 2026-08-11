"""Adapter contract + registry.

An adapter's only job is to yield `Sample`s in the *source* dataset's own label
vocabulary. It never sees target class indices -- the mapping from source label
name to 0/1/2/3 lives in the dataset YAML, so collapsing or re-pointing classes
never requires touching adapter code.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# name -> adapter class
_REGISTRY: dict[str, type["Adapter"]] = {}


def register(name: str) -> Callable[[type["Adapter"]], type["Adapter"]]:
    def deco(cls: type[Adapter]) -> type[Adapter]:
        if name in _REGISTRY:
            raise ValueError(f"adapter {name!r} already registered by {_REGISTRY[name]}")
        _REGISTRY[name] = cls
        cls.adapter_name = name
        return cls

    return deco


def get_adapter(name: str) -> type["Adapter"]:
    # Import for side effects: each module registers itself on import.
    from . import adapters  # noqa: F401

    if name not in _REGISTRY:
        raise KeyError(f"no adapter {name!r}; registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def registered() -> list[str]:
    from . import adapters  # noqa: F401

    return sorted(_REGISTRY)


@dataclass
class Sample:
    """One image and its source-vocabulary annotation.

    Exactly one of `build_mask` / `boxes` must be set. `build_mask` is a callable
    rather than an array so a 7k-image dataset does not have to fit in RAM.
    """

    sample_id: str
    image_path: Path

    # Split grouping key. Frames from the same video or site are correlated;
    # splitting within a group leaks val/test into train and inflates every metric.
    group: str

    # Source label vocabulary. In the mask returned by build_mask, pixel value 0
    # means "unlabelled" and value i+1 means labels[i].
    labels: list[str] = field(default_factory=list)

    build_mask: Callable[[], np.ndarray] | None = None

    # (label_name, (x0, y0, x1, y1)) in pixel coords of the source image.
    boxes: list[tuple[str, tuple[float, float, float, float]]] | None = None

    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (self.build_mask is None) == (self.boxes is None):
            raise ValueError(
                f"{self.sample_id}: set exactly one of build_mask / boxes "
                f"(got build_mask={self.build_mask is not None}, boxes={self.boxes is not None})"
            )


class Adapter:
    """Base class. Subclass, decorate with @register('name'), implement samples()."""

    adapter_name: str = "<unregistered>"

    #: "mask" -> ships polygons or PNG masks; "bbox" -> needs SAM box-prompting.
    kind: str = "mask"

    def __init__(self, cfg: dict[str, Any], raw_root: Path) -> None:
        self.cfg = cfg
        self.raw_root = Path(raw_root)
        self.dataset = str(cfg["dataset"])

    def samples(self) -> Iterator[Sample]:
        raise NotImplementedError

    def __len__(self) -> int:
        """Optional: number of samples, for progress bars. -1 if unknown."""
        return -1

    def _resolve(self, key: str) -> Path:
        """Resolve a path from the dataset config, relative to data/raw/<dataset>/."""
        rel = self.cfg["paths"][key]
        p = self.raw_root / rel
        if not p.exists():
            raise FileNotFoundError(
                f"{self.dataset}: paths.{key} -> {p} does not exist. "
                f"Download it first (`python scripts/download.py --list`), "
                f"or fix the path in the dataset YAML."
            )
        return p
