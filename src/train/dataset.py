"""Dataset, augmentation, and the balanced sampler.

Augmentation targets the documented failure modes rather than generic ImageNet
jitter (docs/datasets.md s7):

  turbid brown water        -> HueSaturationValue + RandomBrightnessContrast, wide
  low debris/water contrast -> CLAHE, RandomGamma
  sun glare, specular       -> RandomSunFlare, RandomToneCurve
  rain                      -> RandomRain, RandomFog
  low light                 -> RandomBrightnessContrast biased negative

Geometry is kept mild on purpose: a fixed shore camera never rotates 45 degrees,
and training invariance you will never need spends capacity a 3M-parameter model
does not have.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml
from PIL import Image
from torch.utils.data import Dataset, Sampler

from data.convert import CONFIG_DIR, PROCESSED_ROOT
from data.schema import Schema, load_schema
from data.splits import SPLITS_DIR

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass
class Item:
    dataset: str
    sample_id: str
    image: Path
    mask: Path


def _read_split(split: str) -> list[Item]:
    path = SPLITS_DIR / f"{split}.txt"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing. Run `python -m data.splits` first.")
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        ds, _, sid = line.partition("/")
        items.append(
            Item(
                dataset=ds,
                sample_id=sid,
                image=PROCESSED_ROOT / ds / "images" / f"{sid}.jpg",
                mask=PROCESSED_ROOT / ds / "masks" / f"{sid}.png",
            )
        )
    if not items:
        raise ValueError(f"{path} is empty")
    return items


def dataset_weights() -> dict[str, float]:
    """sampling_weight from each configs/datasets/*.yaml. Missing -> 1.0."""
    out: dict[str, float] = {}
    for p in CONFIG_DIR.glob("*.yaml"):
        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        out[str(cfg.get("dataset", p.stem))] = float(cfg.get("sampling_weight", 1.0))
    return out


def build_transform(cfg: dict[str, Any] | None, size: int, train: bool):
    import albumentations as A

    if not train:
        # Val/test: resize only. Any randomness here makes runs incomparable.
        return A.Compose(
            [
                A.LongestMaxSize(max_size=size),
                A.PadIfNeeded(size, size, border_mode=0),
                A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ]
        )

    a = cfg or {}

    def p(key: str, default: float) -> float:
        return float(a.get(key, default))

    return A.Compose(
        [
            A.LongestMaxSize(max_size=size),
            A.PadIfNeeded(size, size, border_mode=0),
            A.HorizontalFlip(p=0.5),
            # Mild geometry only: a fixed camera does not tumble.
            A.Affine(
                scale=(0.85, 1.2),
                translate_percent=(-0.05, 0.05),
                rotate=(-10, 10),
                p=p("affine", 0.5),
            ),
            # Turbid brown water + low contrast. Deliberately wide.
            A.RandomBrightnessContrast(
                brightness_limit=0.4, contrast_limit=0.4, p=p("brightness_contrast", 0.8)
            ),
            A.HueSaturationValue(
                hue_shift_limit=25, sat_shift_limit=40, val_shift_limit=25, p=p("hsv", 0.8)
            ),
            A.RandomGamma(gamma_limit=(60, 160), p=p("gamma", 0.4)),
            A.CLAHE(clip_limit=3.0, p=p("clahe", 0.2)),
            # Sun glare and specular reflection -- the classic false positive.
            A.RandomSunFlare(flare_roi=(0, 0, 1, 0.6), p=p("sun_flare", 0.20)),
            A.RandomToneCurve(scale=0.3, p=p("tone_curve", 0.2)),
            # Weather.
            A.RandomRain(blur_value=3, brightness_coefficient=0.9, p=p("rain", 0.12)),
            A.RandomFog(p=p("fog", 0.12)),
            # Low light. Separate from the symmetric jitter above so it actually
            # biases dark instead of cancelling out.
            A.RandomBrightnessContrast(
                brightness_limit=(-0.5, -0.1), contrast_limit=(-0.3, 0.0), p=p("low_light", 0.15)
            ),
            A.MotionBlur(blur_limit=5, p=p("motion_blur", 0.1)),
            A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


class SegDataset(Dataset):
    def __init__(
        self,
        split: str,
        size: int = 512,
        aug_cfg: dict[str, Any] | None = None,
        schema: Schema | None = None,
        train: bool | None = None,
    ) -> None:
        self.items = _read_split(split)
        self.schema = schema or load_schema()
        self.split = split
        self.train = (split == "train") if train is None else train
        self.tf = build_transform(aug_cfg, size, self.train)
        # Collapse is applied here, at load time, so configs/classes.yaml can merge
        # clump into debris without re-running conversion.
        self.collapse = self.schema.collapse_lut()

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> dict[str, Any]:
        it = self.items[i]
        image = np.array(Image.open(it.image).convert("RGB"))
        mask = np.array(Image.open(it.mask))

        out = self.tf(image=image, mask=mask)
        image, mask = out["image"], out["mask"]

        image_t = torch.from_numpy(np.ascontiguousarray(image.transpose(2, 0, 1))).float()
        mask_t = torch.from_numpy(self.collapse[mask]).long()
        return {"image": image_t, "mask": mask_t, "dataset": it.dataset, "sample_id": it.sample_id}


class BalancedEpochSampler(Sampler[int]):
    """Cap each dataset's per-epoch contribution instead of weighting by size.

    Uniform pooling makes the mix ~55% RiSID and the model overfits Japanese nadir
    footage (docs/datasets.md s6). Capping is the boring fix: per epoch each
    dataset contributes at most `cap * sampling_weight` samples, drawn without
    replacement, reshuffled each epoch from a seed+epoch stream so runs stay
    reproducible.
    """

    def __init__(
        self, items: list[Item], cap: int, weights: dict[str, float] | None = None, seed: int = 0
    ) -> None:
        self.cap = cap
        self.weights = weights or {}
        self.seed = seed
        self.epoch = 0
        self.by_dataset: dict[str, list[int]] = {}
        for i, it in enumerate(items):
            self.by_dataset.setdefault(it.dataset, []).append(i)

    def set_epoch(self, epoch: int) -> None:
        self.epoch = epoch

    def _quota(self, ds: str, n: int) -> int:
        return max(1, min(n, int(round(self.cap * self.weights.get(ds, 1.0)))))

    def __len__(self) -> int:
        return sum(self._quota(ds, len(idx)) for ds, idx in self.by_dataset.items())

    def __iter__(self):
        rng = np.random.default_rng(self.seed + self.epoch)
        chosen: list[int] = []
        for ds in sorted(self.by_dataset):
            idx = self.by_dataset[ds]
            chosen.extend(rng.choice(idx, size=self._quota(ds, len(idx)), replace=False).tolist())
        rng.shuffle(chosen)
        return iter(chosen)


def build_dataloaders(cfg: dict[str, Any], schema: Schema):
    from torch.utils.data import DataLoader

    size = int(cfg["data"].get("size", 512))
    batch = int(cfg["data"].get("batch_size", 8))
    workers = int(cfg["data"].get("num_workers", 4))
    seed = int(cfg.get("seed", 0))

    train_ds = SegDataset("train", size, cfg.get("aug"), schema)
    val_ds = SegDataset("val", size, None, schema, train=False)

    cap = int(cfg["data"].get("per_dataset_cap", 0))
    sampler = None
    if cap > 0:
        sampler = BalancedEpochSampler(train_ds.items, cap, dataset_weights(), seed)

    train_dl = DataLoader(
        train_ds,
        batch_size=batch,
        sampler=sampler,
        shuffle=sampler is None,
        num_workers=workers,
        pin_memory=True,
        drop_last=True,
        persistent_workers=workers > 0,
    )
    val_dl = DataLoader(
        val_ds,
        batch_size=batch,
        shuffle=False,
        num_workers=workers,
        pin_memory=True,
        persistent_workers=workers > 0,
    )
    return train_dl, val_dl, sampler
