"""High-end candidates: accuracy first, edge cost ignored.

These are NOT for the Raspberry Pi. They exist to answer "how well can this
problem actually be solved", which is the ceiling every lightweight model gets
measured against -- and, later, the teacher if distillation is ever wanted.

VRAM measured on an RTX 5050 Laptop (8 GB), batch 8 at 512, AMP on. Anything
whose peak exceeds ~7.2 GB spills into Windows shared memory: it still runs, but
several times slower, and "it worked" is then misleading. Per-model notes record
what was measured, not what was assumed.

Encoder weights are ImageNet unless `pretrained: false`.
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


@register("segformer_b2")
def segformer_b2(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    """SegFormer-B2, ~24.7M params. The natural scale-up of segformer_b0, which
    was the most accurate model in the Pi comparison, so this is the first place
    to look for headroom."""
    return _build("segformer", "mit_b2", n_classes, pretrained, **kw)


@register("segformer_b3")
def segformer_b3(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    """SegFormer-B3, ~44.6M params. Measured at 8.8 GB peak at batch 8 / 512,
    i.e. OVER an 8 GB card -- drop the batch size or expect it to spill."""
    return _build("segformer", "mit_b3", n_classes, pretrained, **kw)


@register("unet_effnet_b4")
def unet_effnet_b4(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    """U-Net with an EfficientNet-B4 encoder, ~19.4M params.

    The U-Net decoder keeps full-resolution skip connections, the structure that
    should help most on small objects -- and 83% of RiSID's annotations are
    COCO-small. Worth testing despite unet_mnv3 coming last in the Pi comparison:
    that result was capacity overfitting 200 images, not a verdict on the
    decoder."""
    return _build("unet", "tu-efficientnet_b4", n_classes, pretrained, **kw)


@register("deeplabv3plus_r101")
def deeplabv3plus_r101(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    """DeepLabv3+ with ResNet-101, ~45.7M params.

    Measured the FASTEST of the high-end set and the lightest on VRAM (4.6 GB),
    despite the second-highest parameter count -- another instance of parameter
    count failing to predict cost."""
    return _build("deeplabv3plus", "tu-resnet101", n_classes, pretrained, **kw)


@register("upernet_convnext_s")
def upernet_convnext_s(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    """UPerNet + ConvNeXt-Small, ~58.7M params.

    Included for completeness; measured extremely slow per step in the first
    probe. Train it only if the others plateau."""
    return _build("upernet", "tu-convnext_small", n_classes, pretrained, **kw)
