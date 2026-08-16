"""Interactive model tester.

    uv run python -m gui.app
    uv run python -m gui.app --share      # public link, expires in 72h

Four tabs:
  Segment   one image -> overlay + coverage, per model
  Compare   the same image through every trained checkpoint at once
  Video     a clip -> per-frame coverage time series + CSV
  Camera    live UVC capture with real exposure control, then segment a frame

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
from gui import camera
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

    cam = camera.Camera()

    def stream_preview():
        """Yield frames until the user presses Stop (Gradio cancels the generator).

        Capped at ~15 fps: the preview exists to judge exposure, and running it
        flat out competes with inference for the same device and CPU.
        """
        if not cam.is_open:
            yield None
            return
        while cam.is_open:
            f = cam.frame()
            if f is not None:
                yield f
            time.sleep(1 / 15)

    def run_camera(run, size, dev):
        if not cam.is_open:
            return None, "Open a camera first."
        frame = cam.frame()
        if frame is None:
            return None, "Camera delivered no frame."
        net, _ = load(run, runs[run], dev)
        mask, ms = predict(net, frame, int(size), dev)
        s = stats(mask)
        # Clipping check: an overexposed frame destroys the water/debris boundary
        # before the model ever sees it, and a coverage number off a blown-out
        # frame looks perfectly valid while meaning nothing.
        blown = float((frame >= 250).all(axis=2).mean())
        warn = ""
        if blown > 0.02:
            warn = (
                f"\n\n**{blown*100:.1f}% of this frame is pure white (clipped).** "
                "Detail there is gone -- no model can recover it. Lower Exposure or Gain "
                "and capture again before trusting this number."
            )
        return overlay(frame, mask), fmt(s, ms) + warn

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

        with gr.Tab("Camera"):
            gr.Markdown(
                "Live capture through **OpenCV**, not the browser's webcam widget -- that "
                "is the whole point of this tab. The browser develops its own frame with "
                "its own auto-exposure, which no Python setting can reach, which is why a "
                "camera that looks right in its official app can look blown out in a web "
                "page. Here exposure, gain and white balance are actually ours to set.\n\n"
                "Devices show as bare indices: OpenCV cannot read device names on Windows. "
                "Open one and look at the preview to tell which is which."
            )

            with gr.Row():
                with gr.Column(scale=1):
                    dev_list = gr.Dropdown(choices=[], value=None, label="Camera device")
                    scan_btn = gr.Button("Scan for cameras")
                    res_dd = gr.Dropdown(
                        camera.RESOLUTIONS, value=camera.RESOLUTIONS[0], label="Resolution"
                    )
                    with gr.Row():
                        open_btn = gr.Button("Open", variant="primary")
                        close_btn = gr.Button("Close")
                    cam_status = gr.Markdown("No camera open.")

                    gr.Markdown("### Exposure")
                    fix_btn = gr.Button("Fix overexposure", variant="secondary")
                    auto_exp = gr.Checkbox(value=False, label="Auto exposure")
                    probe_btn = gr.Button("Measure exposure sweep")

                    gr.Markdown("### Manual controls")
                    sliders = {}
                    for cname, spec in camera.CONTROLS.items():
                        sliders[cname] = gr.Slider(
                            spec["lo"], spec["hi"], step=spec["step"],
                            value=spec["lo"], label=spec["label"],
                        )
                    auto_wb = gr.Checkbox(value=True, label="Auto white balance")
                    readback_btn = gr.Button("Read values back from camera")

                with gr.Column(scale=2):
                    preview = gr.Image(label="Live preview", height=380)
                    with gr.Row():
                        stream_btn = gr.Button("Start preview", variant="primary")
                        stop_btn = gr.Button("Stop")
                    ctrl_md = gr.Markdown()

                    gr.Markdown("### Capture and segment")
                    with gr.Row():
                        crun = gr.Dropdown(names, value=default, label="Model run")
                        csize2 = gr.Dropdown([416, 512, 640, 768], value=640, label="Input size")
                        cdev2 = gr.Dropdown(devices, value=devices[0], label="Device")
                    grab_btn = gr.Button("Capture frame and segment", variant="primary")
                    cam_overlay = gr.Image(label="Overlay")
                    cam_md = gr.Markdown()

            ctrl_names = list(camera.CONTROLS)

            def do_scan():
                devs = camera.list_devices()
                if not devs:
                    return gr.update(choices=[], value=None), (
                        "No camera found. Check it is plugged in, in webcam mode, and not "
                        "held open by another app -- the official Insta360 app will hold it."
                    )
                labels = [d.label for d in devs]
                return gr.update(choices=labels, value=labels[0]), (
                    f"Found {len(devs)} camera(s). Open one to see which is which."
                )

            def do_open(label, res):
                if not label:
                    return "Pick a device first (press **Scan for cameras**)."
                return cam.open(int(str(label).split()[0]), res)

            def do_readback():
                vals = cam.read_all()
                if not vals:
                    return [gr.update() for _ in ctrl_names] + ["Camera is closed."]
                rows = "\n".join(f"| {n} | {vals[n]:g} |" for n in ctrl_names)
                return [gr.update(value=vals[n]) for n in ctrl_names] + [
                    f"Values now on the device:\n\n| control | value |\n|---|---|\n{rows}"
                ]

            def make_setter(cname: str):
                def _set(value):
                    got = cam.set_control(cname, value)
                    if got is None:
                        return "Camera is closed -- open it before changing controls."
                    if abs(got - float(value)) > 1e-6:
                        return (
                            f"`{cname}`: asked {float(value):g}, driver holds **{got:g}**. "
                            "It clamped or ignored the request; the readback is the real value."
                        )
                    return f"`{cname}` = {got:g}"
                return _set

            def do_fix_overexposure():
                """Lock exposure at a value MEASURED against the current scene.

                A fixed outdoor camera wants a LOCKED exposure. Auto-exposure chases
                clouds and glare, so the same debris changes brightness frame to frame --
                awkward to watch, worse for a model trained on stable exposure, and it
                makes coverage numbers incomparable over time.

                The value is measured rather than hardcoded on purpose. A fixed guess is
                worthless across scenes: on this hardware exposure -7 gives a mean
                luminance of 0.8 (effectively black) in one room and is reasonable
                outdoors. Only a sweep against the actual scene knows which.
                """
                if not cam.is_open:
                    return [gr.update() for _ in ctrl_names] + ["Open the camera first."]
                msgs = [cam.set_auto_exposure(False)]
                best = camera.best_exposure(cam)
                if best is None:
                    msgs.append("Exposure sweep captured no frames; nothing changed.")
                else:
                    value, lum = best
                    got = cam.set_control("exposure", value)
                    msgs.append(
                        f"Exposure locked at **{got:g}** (mean luminance {lum:.0f}, "
                        "closest to mid-grey of the values tried)."
                    )
                vals = cam.read_all()
                return [gr.update(value=vals[n]) for n in ctrl_names] + [
                    "\n\n".join(msgs)
                    + "\n\nStill not right? Nudge Exposure one step at a time -- mid-grey is "
                    "a starting point, not a calibration, and bright sky in frame biases it "
                    "dark. Locked and slightly off beats auto and hunting: consistent "
                    "exposure is what makes coverage comparable between frames."
                ]

            scan_btn.click(do_scan, None, [dev_list, cam_status])
            open_btn.click(do_open, [dev_list, res_dd], cam_status)
            close_btn.click(lambda: cam.close(), None, cam_status)

            for cname in ctrl_names:
                sliders[cname].release(make_setter(cname), sliders[cname], ctrl_md)

            auto_exp.change(lambda v: cam.set_auto_exposure(bool(v)), auto_exp, ctrl_md)
            auto_wb.change(lambda v: cam.set_auto_wb(bool(v)), auto_wb, ctrl_md)
            readback_btn.click(do_readback, None, [sliders[n] for n in ctrl_names] + [ctrl_md])
            fix_btn.click(do_fix_overexposure, None, [sliders[n] for n in ctrl_names] + [ctrl_md])
            probe_btn.click(lambda: camera.exposure_probe(cam), None, ctrl_md)

            ev = stream_btn.click(stream_preview, None, preview)
            stop_btn.click(None, None, None, cancels=[ev])

            grab_btn.click(run_camera, [crun, csize2, cdev2], [cam_overlay, cam_md])

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
