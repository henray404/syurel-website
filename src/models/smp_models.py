"""segmentation_models_pytorch candidates.

One dependency covers three of the brief's candidates, because smp 0.5.0 ships a
native Segformer decoder and mit_b0 encoder -- so `transformers` is not needed:

    unet_mnv3           U-Net + MobileNetV3 encoder
    unet_effnet_lite    U-Net + EfficientNet-lite0 encoder
    deeplabv3plus_mnv3  DeepLabv3+ + MobileNetV3 encoder
    segformer_b0        SegFormer-B0 (mit_b0)

Install:  uv sync --extra bench

smp returns logits at input resolution already, so no wrapper is needed. Encoder
weights are ImageNet unless `pretrained: false`.
"""

from __future__ import annotations

from typing import Any

import torch.nn as nn

from .registry import register

_INSTALL_HINT = "segmentation_models_pytorch is not installed. Run: uv sync --extra bench"


def _build(arch: str, encoder: str, n_classes: int, pretrained: bool, **kw: Any) -> nn.Module:
    try:
        import segmentation_models_pytorch as smp
    except ImportError as exc:
        raise RuntimeError(_INSTALL_HINT) from exc

    return smp.create_model(
        arch=arch,
        encoder_name=encoder,
        encoder_weights="imagenet" if pretrained else None,
        in_channels=3,
        classes=n_classes,
        **kw,
    )


@register("unet_mnv3")
def unet_mobilenetv3(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    # `tu-` routes to timm; the bare `timm-` names are deprecated in smp and
    # slated for removal.
    return _build("unet", "tu-mobilenetv3_large_100", n_classes, pretrained, **kw)


@register("unet_effnet_lite")
def unet_efficientnet_lite(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    """EfficientNet-lite0: no SE blocks, ReLU6 instead of swish. That is the
    whole point -- both are poorly supported by edge NPU toolchains."""
    return _build("unet", "tu-efficientnet_lite0", n_classes, pretrained, **kw)


@register("deeplabv3plus_mnv3")
def deeplabv3plus_mobilenetv3(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    return _build("deeplabv3plus", "tu-mobilenetv3_large_100", n_classes, pretrained, **kw)


@register("segformer_b0")
def segformer_b0(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    """SegFormer-B0. Attention-based, so expect the worst CPU latency here even
    though the parameter count looks competitive -- that gap is exactly the kind
    of finding this comparison exists to surface."""
    return _build("segformer", "mit_b0", n_classes, pretrained, **kw)
