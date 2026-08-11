"""MobileSAM wrapper. Lazily imported so the base install stays torch-free.

Install:  uv sync --extra sam  &&  uv pip install git+https://github.com/ChaoningZhang/MobileSAM.git
Weights:  see `python scripts/download.py --dataset mobile_sam`  ->  data/checkpoints/mobile_sam.pt  (~40 MB)

Chosen over SAM ViT-B because it runs on CPU in ~1-2 s/image with no GPU, and its
output goes through manual review regardless (see review.py), so the small loss in
boundary precision costs less than a GPU requirement would.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

DEFAULT_CKPT = Path("data/checkpoints/mobile_sam.pt")

_INSTALL_HINT = (
    "MobileSAM is not installed. Run:\n"
    "  uv sync --extra sam\n"
    "  uv pip install git+https://github.com/ChaoningZhang/MobileSAM.git\n"
    "and download the checkpoint per `python scripts/download.py --dataset mobile_sam`."
)


class Sam:
    """Thin wrapper around MobileSAM's predictor. One image at a time."""

    def __init__(self, ckpt: Path | str = DEFAULT_CKPT, device: str = "cpu") -> None:
        try:
            from mobile_sam import SamPredictor, sam_model_registry  # type: ignore
        except ImportError as exc:
            raise RuntimeError(_INSTALL_HINT) from exc

        ckpt = Path(ckpt)
        if not ckpt.exists():
            raise FileNotFoundError(f"MobileSAM checkpoint not found at {ckpt}. {_INSTALL_HINT}")

        model = sam_model_registry["vit_t"](checkpoint=str(ckpt))
        model.to(device=device)
        model.eval()
        self._predictor = SamPredictor(model)
        self.device = device

    def set_image(self, rgb: np.ndarray) -> None:
        """rgb: HxWx3 uint8. Expensive (runs the encoder); call once per image."""
        if rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError(f"expected HxWx3 RGB, got {rgb.shape}")
        self._predictor.set_image(rgb)

    def mask_from_box(self, box: tuple[float, float, float, float]) -> np.ndarray:
        """Box-prompted mask. Returns HxW bool.

        Box prompts are far more reliable than unprompted segmentation, which is
        the whole reason bbox datasets are usable at all.
        """
        arr = np.asarray(box, dtype=np.float32)[None, :]
        masks, _scores, _ = self._predictor.predict(box=arr, multimask_output=False)
        return masks[0].astype(bool)

    def mask_from_points(
        self, points: np.ndarray, labels: np.ndarray, multimask: bool = True
    ) -> tuple[np.ndarray, float]:
        """Point-prompted mask. points: Nx2 (x, y); labels: N (1=fg, 0=bg).

        Returns (HxW bool, score). With multimask=True SAM proposes 3 candidates
        at different scales; for water we want the largest coherent region, so we
        take the highest-scoring one and let review.py catch the failures.
        """
        masks, scores, _ = self._predictor.predict(
            point_coords=np.asarray(points, dtype=np.float32),
            point_labels=np.asarray(labels, dtype=np.int32),
            multimask_output=multimask,
        )
        best = int(np.argmax(scores))
        return masks[best].astype(bool), float(scores[best])
