"""Fast-SCNN, vendored.

WHY VENDORED: the brief asks for BiSeNetV2 / Fast-SCNN / PP-LiteSeg. As of
2026-08-11 none of the three has a maintained pip package -- only GitHub repos,
and PP-LiteSeg is natively PaddlePaddle. Rather than take an unmaintained
dependency, the lightest of the three is reimplemented here in one file with no
new requirements.

    Poudel, Liwicki, Cipolla. "Fast-SCNN: Fast Semantic Segmentation Network."
    BMVC 2019. https://arxiv.org/abs/1902.04502

READ THIS BEFORE COMPARING ITS ACCURACY TO ANYTHING ELSE: there are no
pretrained weights for this architecture, so it trains from scratch while every
other candidate starts from ImageNet or COCO. On a few thousand images that
handicap is large and has nothing to do with the architecture's merit. Its
honest use here is the COST columns -- params, FLOPs, latency -- where it should
be the cheapest model in the set. docs/model_comparison.md flags this in-table.
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from .registry import register


def _conv_bn(inp: int, out: int, k: int = 3, s: int = 1, p: int = 1) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(inp, out, k, s, p, bias=False), nn.BatchNorm2d(out), nn.ReLU(inplace=True)
    )


class _DSConv(nn.Module):
    """Depthwise separable conv."""

    def __init__(self, inp: int, out: int, stride: int = 1) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(inp, inp, 3, stride, 1, groups=inp, bias=False),
            nn.BatchNorm2d(inp),
            nn.ReLU(inplace=True),
            nn.Conv2d(inp, out, 1, bias=False),
            nn.BatchNorm2d(out),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class _Bottleneck(nn.Module):
    """Inverted residual, as in MobileNetV2."""

    def __init__(self, inp: int, out: int, stride: int, expand: int = 6) -> None:
        super().__init__()
        hidden = inp * expand
        self.use_res = stride == 1 and inp == out
        self.block = nn.Sequential(
            nn.Conv2d(inp, hidden, 1, bias=False),
            nn.BatchNorm2d(hidden),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, hidden, 3, stride, 1, groups=hidden, bias=False),
            nn.BatchNorm2d(hidden),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, out, 1, bias=False),
            nn.BatchNorm2d(out),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.block(x) if self.use_res else self.block(x)


class _PPM(nn.Module):
    """Pyramid pooling module."""

    def __init__(self, inp: int, out: int, bins: tuple[int, ...] = (1, 2, 3, 6)) -> None:
        super().__init__()
        inter = inp // 4
        self.stages = nn.ModuleList(
            [nn.Sequential(nn.AdaptiveAvgPool2d(b), _conv_bn(inp, inter, 1, 1, 0)) for b in bins]
        )
        self.project = _conv_bn(inp + inter * len(bins), out, 1, 1, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        size = x.shape[-2:]
        feats = [x] + [
            F.interpolate(s(x), size=size, mode="bilinear", align_corners=False)
            for s in self.stages
        ]
        return self.project(torch.cat(feats, dim=1))


class _FeatureFusion(nn.Module):
    def __init__(self, low_ch: int, high_ch: int, out_ch: int, scale: int = 4) -> None:
        super().__init__()
        self.dwconv = nn.Sequential(
            nn.Conv2d(
                high_ch, out_ch, 3, 1, scale, dilation=scale, groups=high_ch, bias=False
            ),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 1, bias=False),
            nn.BatchNorm2d(out_ch),
        )
        self.low = nn.Sequential(nn.Conv2d(low_ch, out_ch, 1, bias=False), nn.BatchNorm2d(out_ch))
        self.relu = nn.ReLU(inplace=True)

    def forward(self, low: torch.Tensor, high: torch.Tensor) -> torch.Tensor:
        high = F.interpolate(high, size=low.shape[-2:], mode="bilinear", align_corners=False)
        return self.relu(self.low(low) + self.dwconv(high))


class FastSCNN(nn.Module):
    def __init__(self, n_classes: int) -> None:
        super().__init__()
        # Learning to downsample: full resolution -> 1/8, cheaply.
        self.down = nn.Sequential(_conv_bn(3, 32, 3, 2, 1), _DSConv(32, 48, 2), _DSConv(48, 64, 2))

        # Global feature extractor, 1/8 -> 1/32.
        self.gfe = nn.Sequential(
            _Bottleneck(64, 64, 2),
            _Bottleneck(64, 64, 1),
            _Bottleneck(64, 64, 1),
            _Bottleneck(64, 96, 2),
            _Bottleneck(96, 96, 1),
            _Bottleneck(96, 96, 1),
            _Bottleneck(96, 128, 1),
            _Bottleneck(128, 128, 1),
            _Bottleneck(128, 128, 1),
            _PPM(128, 128),
        )

        self.fusion = _FeatureFusion(low_ch=64, high_ch=128, out_ch=128)
        self.classifier = nn.Sequential(
            _DSConv(128, 128), _DSConv(128, 128), nn.Dropout(0.1), nn.Conv2d(128, n_classes, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        size = x.shape[-2:]
        low = self.down(x)
        high = self.gfe(low)
        fused = self.fusion(low, high)
        out = self.classifier(fused)
        # Interface contract: logits at input resolution (see registry.py).
        return F.interpolate(out, size=size, mode="bilinear", align_corners=False)


@register("fast_scnn")
def fast_scnn(n_classes: int, pretrained: bool = False, **kw: Any) -> nn.Module:
    if pretrained:
        raise ValueError(
            "fast_scnn has no pretrained weights -- no maintained source publishes them. "
            "Pass pretrained: false, and note in the comparison that it trains from scratch."
        )
    return FastSCNN(n_classes=n_classes)


def demo() -> None:
    """Self-check: python -m models.fast_scnn"""
    net = FastSCNN(n_classes=4).eval()
    for size in (416, 512, 640):
        with torch.no_grad():
            out = net(torch.randn(1, 3, size, size))
        assert out.shape == (1, 4, size, size), out.shape

    n_params = sum(p.numel() for p in net.parameters())
    # The paper reports ~1.11M parameters; a wildly different number means the
    # channel widths above drifted from the architecture.
    assert 0.8e6 < n_params < 1.8e6, n_params
    print(f"fast_scnn self-check OK ({n_params / 1e6:.2f}M params)")


if __name__ == "__main__":
    demo()
