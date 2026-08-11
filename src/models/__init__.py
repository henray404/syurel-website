"""Segmentation model zoo behind one interface.

    from models import build_model, registered
    net = build_model("lraspp_mnv3", n_classes=4)

Task 4 adds smp / SegFormer / YOLO files; each is one module plus one import
line in registry.build_model's lazy-import block.
"""

from .registry import build_model, register, registered

__all__ = ["build_model", "register", "registered"]
