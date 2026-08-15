"""Model registry. One decorator, one factory.

Every model is a plain `nn.Module` whose forward returns a logits tensor of shape
(B, n_classes, H, W) at the INPUT resolution. Architectures that natively output
at a lower stride must upsample inside their own wrapper -- the training loop does
not special-case anyone.

Adding a model is one file in this package plus one import line in __init__.py.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import torch.nn as nn


class ModelBuilder(Protocol):
    def __call__(self, n_classes: int, **kwargs: Any) -> nn.Module: ...


_REGISTRY: dict[str, ModelBuilder] = {}


def register(name: str) -> Callable[[ModelBuilder], ModelBuilder]:
    def deco(fn: ModelBuilder) -> ModelBuilder:
        if name in _REGISTRY:
            raise ValueError(f"model {name!r} already registered")
        _REGISTRY[name] = fn
        return fn

    return deco


def _load_all() -> None:
    """Import every model module for its registration side effect.

    Imported here rather than at package import so a missing optional dependency
    only bites when that model is actually asked for. smp_models raises its
    install hint at build time, not at import time, so this stays safe.
    """
    from . import fast_scnn, highend, smp_models, torchvision_models  # noqa: F401


def build_model(name: str, n_classes: int, **kwargs: Any) -> nn.Module:
    _load_all()

    if name not in _REGISTRY:
        raise KeyError(f"no model {name!r}; registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name](n_classes=n_classes, **kwargs)


def registered() -> list[str]:
    _load_all()
    return sorted(_REGISTRY)
