"""torchvision segmentation models, normalised to a plain logits tensor.

torchvision's segmentation heads return an OrderedDict with "out" (and "aux"),
which every downstream loss and metric would otherwise have to know about. The
wrapper unwraps it and guarantees the output is at input resolution.

Task 4 adds SegFormer / smp / YOLO in their own files behind the same interface.
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from .registry import register


class _TorchvisionSeg(nn.Module):
    """Unwrap the dict output and resize logits back to the input size."""

    def __init__(self, net: nn.Module) -> None:
        super().__init__()
        self.net = net

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        size = x.shape[-2:]
        out = self.net(x)
        logits = out["out"] if isinstance(out, dict) else out
        if logits.shape[-2:] != size:
            logits = F.interpolate(logits, size=size, mode="bilinear", align_corners=False)
        return logits


@register("lraspp_mnv3")
def lraspp_mobilenetv3(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    """LR-ASPP MobileNetV3-Large. ~3.2M params -- the Pi-first candidate."""
    from torchvision.models.segmentation import (
        LRASPP_MobileNet_V3_Large_Weights,
        lraspp_mobilenet_v3_large,
    )

    weights = LRASPP_MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
    net = lraspp_mobilenet_v3_large(weights=weights, num_classes=21 if pretrained else n_classes)
    if pretrained:
        # Re-head for our class count. The COCO-pretrained 21-class head is
        # useless to us; the pretrained backbone is the part worth keeping.
        net.classifier.low_classifier = nn.Conv2d(40, n_classes, kernel_size=1)
        net.classifier.high_classifier = nn.Conv2d(128, n_classes, kernel_size=1)
    return _TorchvisionSeg(net)


@register("deeplabv3_mnv3")
def deeplabv3_mobilenetv3(n_classes: int, pretrained: bool = True, **kw: Any) -> nn.Module:
    """DeepLabv3 with a MobileNetV3-Large backbone. Heavier than LR-ASPP."""
    from torchvision.models.segmentation import (
        DeepLabV3_MobileNet_V3_Large_Weights,
        deeplabv3_mobilenet_v3_large,
    )

    weights = DeepLabV3_MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
    net = deeplabv3_mobilenet_v3_large(
        weights=weights,
        num_classes=21 if pretrained else n_classes,
        aux_loss=True if pretrained else None,
    )
    if pretrained:
        net.classifier[-1] = nn.Conv2d(256, n_classes, kernel_size=1)
        if net.aux_classifier is not None:
            net.aux_classifier[-1] = nn.Conv2d(10, n_classes, kernel_size=1)
    return _TorchvisionSeg(net)
