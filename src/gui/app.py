"""Interactive model tester.

    uv run python -m gui.app
    uv run python -m gui.app --share      # public link, expires in 72h

Three tabs:
  Segment   one image -> overlay + coverage, per model
  Compare   the same image through every trained checkpoint at once
  Video     a clip -> per-frame coverage time series + CSV

Discovers checkpoints by scanning runs/ for best.pt, so a model appears here the
moment it finishes training. No config to keep in sync.

The number this shows is COVERAGE = (debris+clump)/(debris+clump+water), the same
definition src/inference/metrics.py uses. It is a ratio over water, not over the
frame, so it does not change when the framing does. It is NOT calibrated to m2 --
that needs the Phase 2 homography.
"""

from __future__ import annotations

import argparse
import csv
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml

from data.schema import BACKGROUND, CLUMP, DEBRIS, REPO_ROOT, WATER, load_schema
from models import build_model

RUNS = REPO_ROOT / "runs"
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# background, water, debris, clump
PALETTE = np.array([[0, 0, 0], [40, 90, 255], [255, 40, 40], [255, 220, 0]], dtype=np.uint8)

_CACHE: dict[str, torch.nn.Module] = {}


def discover_runs() -> dict[str, dict]:
    """run name -> {ckpt, model, classes, size}. Reads each run's own config.yaml."""
    found: dict[str, dict] = {}
    if not RUNS.exists():
        return found
    for d in sorted(RUNS.iterdir()):
        ckpt, cfg_p = d / "best.pt", d / "config.yaml"
        if not (ckpt.exists() and cfg_p.exists()):
            continue
        try:
            cfg = yaml.safe_load(cfg_p.read_text(encoding="utf-8"))
        except Exception:
            continue
        found[d.name] = {
            "ckpt": ckpt,
            "model": str((cfg.get("model") or {}).get("name", "?")),
            "classes": cfg.get("classes"),
            "size": int((cfg.get("data") or {}).get("size", 512)),
        }
    return found


def load(run: str, info: dict, device: str):
    schema = load_schema(REPO_ROOT / info["classes"]) if info.get("classes") else load_schema()
    key = f"{run}:{device}"
    if key not in _CACHE:
        state = torch.load(info["ckpt"], map_location=device, weights_only=False)
        net = build_model(info["model"], n_classes=len(schema.names), pretrained=False)
        net.load_state_dict(state["model"])
        _CACHE[key] = net.to(device).eval()
    return _CACHE[key], schema


@torch.no_grad()
def predict(net, rgb: np.ndarray, size: int, device: str) -> tuple[np.ndarray, float]:
    """RGB uint8 -> class-index mask at original resolution, plus latency in ms."""
    h, w = rgb.shape[:2]
    small = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)
    x = (small.astype(np.float32) / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
    t = torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0).to(device)

    if device == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    pred = net(t).argmax(1)[0].cpu().numpy().astype(np.uint8)
    if device == "cuda":
        torch.cuda.synchronize()
    ms = (time.perf_counter() - t0) * 1000

    # NEAREST: interpolating class indices invents classes never predicted.
    return cv2.resize(pred, (w, h), interpolation=cv2.INTER_NEAREST), ms


def overlay(rgb: np.ndarray, mask: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    tint = PALETTE[np.clip(mask, 0, len(PALETTE) - 1)]
    out = np.where(mask[..., None] == BACKGROUND, rgb, ((1 - alpha) * rgb + alpha * tint))
    return out.astype(np.uint8)


def stats(mask: np.ndarray) -> dict:
    debris = int(((mask == DEBRIS) | (mask == CLUMP)).sum())
    water = int((mask == WATER).sum())
    denom = debris + water
    return {
        # None, never 0.0: a frame with no water and no debris is unmeasurable,
        # and a silent zero reads as "clean river".
        "coverage": (debris / denom) if denom else None,
        "debris_px": debris,
        "water_px": water,
        "bg_px": int((mask == BACKGROUND).sum()),
    }


def fmt(s: dict, ms: float) -> str:
    cov = "n/a (no water or debris in frame)" if s["coverage"] is None else f"{s['coverage']:.4f}"
    return (
        f"| metric | value |\n|---|---|\n"
        f"| **coverage** | **{cov}** |\n"
        f"| debris+clump px | {s['debris_px']:,} |\n"
        f"| water px | {s['water_px']:,} |\n"
        f"| background px | {s['bg_px']:,} |\n"
        f"| latency | {ms:.0f} ms |\n\n"
        "coverage = (debris+clump) / (debris+clump+water), measured over water rather "
        "than frame area. Not calibrated to m2 -- that needs the Phase 2 homography."
    )


def build_ui():
    import gradio as gr

    runs = discover_runs()
    if not runs:
        raise SystemExit(f"no checkpoints under {RUNS}. Train a model first.")
    names = list(runs)
    default = next((n for n in names if "segformer" in n), names[0])
    devices = ["cuda", "cpu"] if torch.cuda.is_available() else ["cpu"]

    def run_one(img, run, size, dev):
        if img is None:
            return None, "Upload an image first."
        net, _ = load(run, runs[run], dev)
        mask, ms = predict(net, img, int(size), dev)
        return overlay(img, mask), fmt(stats(mask), ms)

    def run_all(img, size, dev):
        if img is None:
            return [], "Upload an image first."
        gallery, rows = [], []
        for name in names:
            net, _ = load(name, runs[name], dev)
            mask, ms = predict(net, img, int(size), dev)
            s = stats(mask)
            gallery.append((overlay(img, mask), name))
            cov = "n/a" if s["coverage"] is None else f"{s['coverage']:.4f}"
            rows.append(f"| `{name}` | {cov} | {s['debris_px']:,} | {s['water_px']:,} | {ms:.0f} |")
        table = (
            "| run | coverage | debris px | water px | ms |\n|---|---|---|---|---|\n"
            + "\n".join(rows)
            + "\n\nSame image, same resolution, every trained checkpoint. Disagreement "
            "between runs on one frame is the honest measure of how settled this is."
        )
        return gallery, table

    def run_video(path, run, size, dev, stride, progress=gr.Progress()):
        if not path:
            return None, None, "Upload a video first."
        net, _ = load(run, runs[run], dev)
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        rows, covs, idx, last = [], [], 0, None
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % int(stride) == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mask, ms = predict(net, rgb, int(size), dev)
                s = stats(mask)
                rows.append(
                    [idx, round(idx / fps, 3), s["coverage"], s["debris_px"],
                     s["water_px"], round(ms, 1)]
                )
                covs.append(s["coverage"] if s["coverage"] is not None else float("nan"))
                last = overlay(rgb, mask)
                if total:
                    progress(idx / total)
            idx += 1
        cap.release()

        if not rows:
            return None, None, "No frames decoded."

        out = Path(tempfile.gettempdir()) / "syurell_video_coverage.csv"
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["frame", "t_seconds", "coverage", "debris_px", "water_px", "latency_ms"])
            w.writerows(rows)

        arr = np.array([c for c in covs if c == c])
        summary = (
            f"**{len(rows)} frames sampled** (every {int(stride)}), {fps:.1f} fps source\n\n"
            f"| metric | value |\n|---|---|\n"
            f"| mean coverage | {arr.mean():.4f} |\n"
            f"| median coverage | {np.median(arr):.4f} |\n"
            f"| min / max | {arr.min():.4f} / {arr.max():.4f} |\n"
            f"| frames unmeasurable | {len(covs)-len(arr)} |\n\n"
            "Single-frame coverage is noisy; the deployed pipeline smooths it over a "
            "window (src/inference/metrics.py). Velocity and area flux are NOT computed "
            "here -- they need consecutive frames at camera rate."
        )
        return last, str(out), summary

    with gr.Blocks(title="Syurell - river debris segmentation") as demo:
        gr.Markdown(
            "# Syurell - river debris segmentation\n"
            "Blue = water, red = debris, yellow = clump. Models are discovered from "
            "`runs/*/best.pt`, so a newly trained one shows up without editing anything."
        )

        with gr.Tab("Segment"):
            with gr.Row():
                with gr.Column():
                    img = gr.Image(type="numpy", label="Image")
                    run_dd = gr.Dropdown(names, value=default, label="Model run")
                    size_dd = gr.Dropdown([416, 512, 640, 768], value=640, label="Input size")
                    dev_dd = gr.Dropdown(devices, value=devices[0], label="Device")
                    btn = gr.Button("Segment", variant="primary")
                with gr.Column():
                    out_img = gr.Image(label="Overlay")
                    out_md = gr.Markdown()
            btn.click(run_one, [img, run_dd, size_dd, dev_dd], [out_img, out_md])

        with gr.Tab("Compare all models"):
            with gr.Row():
                with gr.Column(scale=1):
                    cimg = gr.Image(type="numpy", label="Image")
                    csize = gr.Dropdown([416, 512, 640, 768], value=640, label="Input size")
                    cdev = gr.Dropdown(devices, value=devices[0], label="Device")
                    cbtn = gr.Button("Compare", variant="primary")
                with gr.Column(scale=2):
                    gal = gr.Gallery(label="Overlays", columns=3, height=420)
                    ctab = gr.Markdown()
            cbtn.click(run_all, [cimg, csize, cdev], [gal, ctab])

        with gr.Tab("Video"):
            with gr.Row():
                with gr.Column():
                    vid = gr.Video(label="Video")
                    vrun = gr.Dropdown(names, value=default, label="Model run")
                    vsize = gr.Dropdown([416, 512, 640], value=512, label="Input size")
                    vdev = gr.Dropdown(devices, value=devices[0], label="Device")
                    vstride = gr.Slider(1, 30, value=5, step=1, label="Process every Nth frame")
                    vbtn = gr.Button("Run", variant="primary")
                with gr.Column():
                    vlast = gr.Image(label="Last processed frame")
                    vcsv = gr.File(label="Coverage time series (CSV)")
                    vmd = gr.Markdown()
            vbtn.click(run_video, [vid, vrun, vsize, vdev, vstride], [vlast, vcsv, vmd])

    return demo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--share", action="store_true", help="public gradio link (72h)")
    ap.add_argument("--port", type=int, default=7860)
    args = ap.parse_args(argv)

    build_ui().launch(share=args.share, server_port=args.port, inbrowser=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
