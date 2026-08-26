"""Run a trained model over a video or RTSP stream and emit the metrics.

    python -m inference.run --config configs/inference/site_example.yaml --source river.mp4
    python -m inference.run --config configs/inference/site_example.yaml --source rtsp://...

THREE CLOCKS, and keeping them separate is the whole design:

    camera rate    every frame is decoded and fed to optical flow. Flow needs
                   consecutive frames ~33 ms apart; it is cheap and never touches
                   the network.
    trash rate     segmentation for debris. Default every 1.0 s.
    water rate     water mask refresh. Default every 30 s, cached in between,
                   because water level moves over minutes.

HONEST NOTE ON THE WATER OPTIMISATION. With a single 4-class model, one forward
pass yields water and debris together, so caching the water mask saves NOTHING --
the model still has to run for debris. The saving only becomes real when water
comes from a separate, cheaper source. Both paths are supported:

    models.trash    required
    models.water    optional. If set, the trash model runs at the trash rate and
                    the water model at the water rate, and the saving is real. If
                    null, water is taken from the trash model's own output and
                    `water_interval_s` only controls how stale the cached water
                    mask may be -- which still matters, because it stabilises the
                    coverage denominator against frame-to-frame water flicker.

The startup banner prints which mode is active, so this is never silently assumed.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import yaml

from data.schema import BACKGROUND, CLUMP, DEBRIS, WATER, load_schema
from models import build_model

from .geometry import build_geometry, build_masks, denormalize
from .metrics import (
    BlockageMonitor,
    BlockageParams,
    Smoother,
    SmoothingParams,
    area_flux,
    frame_metrics,
)
from .control import probe_cameras, read_polygons, read_request, write_request, write_status
from .preview import LivePreview, PreviewParams
from .sink import TimeSeriesSink
from .velocity import VelocityEstimator, VelocityParams

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def load_model(spec: dict[str, Any], n_classes: int, device: str) -> torch.nn.Module:
    ckpt = Path(spec["checkpoint"])
    if not ckpt.exists():
        raise SystemExit(f"checkpoint not found: {ckpt}")
    state = torch.load(ckpt, map_location=device, weights_only=False)

    args = dict(spec.get("args") or {})
    args["pretrained"] = False  # weights come from the checkpoint
    model = build_model(str(spec["name"]), n_classes=n_classes, **args).to(device)
    model.load_state_dict(state["model"])
    model.eval()
    return model


@torch.no_grad()
def infer(model: torch.nn.Module, frame_bgr: np.ndarray, size: int, device: str) -> np.ndarray:
    """BGR frame -> class-index mask at the ORIGINAL frame resolution."""
    h, w = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    small = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)

    x = (small.astype(np.float32) / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
    tensor = torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0).to(device)

    pred = model(tensor).argmax(1)[0].cpu().numpy().astype(np.uint8)
    # NEAREST: any smooth interpolation of class indices invents classes.
    return cv2.resize(pred, (w, h), interpolation=cv2.INTER_NEAREST)


def is_live_source(source: str) -> bool:
    """True for a camera index or a network stream, False for a file on disk.

    THIS DECIDES WHICH CLOCK THE ROWS ARE STAMPED WITH, and it must be decided
    from the source, not from what the capture reports.

    The earlier version trusted CAP_PROP_POS_MSEC whenever it was positive. On
    Windows the default MSMF backend answers that with the device's uptime --
    measured here as 78717938 ms, about 22 hours -- rather than time elapsed
    since the camera opened. Every row then landed ~22 h in the future, which
    made the ESP/camera join (60 s tolerance) impossible to satisfy and quietly
    disabled the pairing of the two sources.

    A file is the opposite case: its POS_MSEC is meaningful and must be used, so
    replaying the same recording twice yields identical timestamps.
    """
    s = str(source)
    return s.isdigit() or "://" in s


def open_source(source: str) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not cap.isOpened():
        raise SystemExit(f"cannot open source: {source}")
    return cap


def run(config_path: Path, source: str, max_frames: int | None = None) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    schema = load_schema()
    n_classes = len(schema.names)

    device = str(cfg.get("device") or ("cuda" if torch.cuda.is_available() else "cpu"))
    size = int(cfg.get("input_size", 512))
    site = str(cfg.get("site", "site"))

    trash_spec = cfg["models"]["trash"]
    water_spec = cfg["models"].get("water")
    trash_model = load_model(trash_spec, n_classes, device)
    water_model = load_model(water_spec, n_classes, device) if water_spec else None

    sampling = cfg.get("sampling") or {}
    trash_interval = float(sampling.get("trash_interval_s", 1.0))
    water_interval = float(sampling.get("water_interval_s", 30.0))

    # Kept so they can be rebuilt on a camera switch: a median window carried
    # across two different scenes blends measurements that share nothing.
    smoothing_params = SmoothingParams(**(cfg.get("smoothing") or {}))
    blockage_params = BlockageParams(**(cfg.get("blockage") or {}))
    velocity_params = VelocityParams(**(cfg.get("velocity") or {}))

    smoother = Smoother(smoothing_params)
    monitor = BlockageMonitor(blockage_params)
    velocity = VelocityEstimator(velocity_params)
    geometry = build_geometry(cfg)
    cross_section_width = float(cfg.get("cross_section_width", 1.0))

    # Probe BEFORE opening our own capture: a device can only be held by one
    # reader, so the camera we are about to take would look unavailable.
    devices = probe_cameras() if is_live_source(source) else []

    cap = open_source(source)
    live = is_live_source(source)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    dt_nominal = 1.0 / fps if fps > 0 else 1.0 / 30.0

    out_dir = Path(cfg.get("output_dir", "out")) / site
    sink = TimeSeriesSink(
        out_dir,
        site=site,
        csv_enabled=bool((cfg.get("output") or {}).get("csv", True)),
        sqlite_enabled=bool((cfg.get("output") or {}).get("sqlite", True)),
    )
    preview = LivePreview(out_dir, PreviewParams(**(cfg.get("preview") or {})))
    live_dir = preview.dir
    # Publish what is running before the first frame, so the web dropdown is
    # populated even if the model is still warming up.
    if preview.params.enabled:
        live_dir.mkdir(parents=True, exist_ok=True)
        write_status(live_dir, active=str(source), devices=devices)
        # Sync the control file to what we actually opened. Without this, a
        # control.json left over from an earlier session wins over the --source
        # the user just typed: the first pass of the loop below reads the stale
        # value, sees it differs from active_source, and switches away from the
        # camera that was explicitly asked for. The command line is the more
        # recent statement of intent, so it is the one that survives.
        write_request(live_dir, str(source))

    mode = (
        "two-model (real compute saving)"
        if water_model
        else "single-model (cache only, no compute saved)"
    )
    print(
        f"site={site} device={device} size={size} fps={fps or 'unknown'}\n"
        f"water mode: {mode}\n"
        f"intervals: trash={trash_interval}s water={water_interval}s\n"
        f"clock: {'wall (live source)' if live else 'frame-derived (file)'}\n"
        f"geometry: {'metric' if geometry.is_metric else 'PIXEL RATIO (relative index)'}"
    )

    masks = None
    water_mask: np.ndarray | None = None
    debris_mask: np.ndarray | None = None
    last_trash = last_water = -1e18
    frame_idx = 0
    t_start = time.time()
    prev_ts: float | None = None

    active_source = str(source)
    last_control_check = 0.0
    last_flush = time.time()
    # A request that failed to open stays failed until the web asks for
    # something else. Without this the loop retries every 0.5 s, and each failed
    # VideoCapture open costs about a second on Windows -- the frame rate would
    # collapse because someone picked an unplugged camera once.
    refused_source: str | None = None
    # None means "no drawing saved, use the config polygons". Never {} -- an
    # empty structure polygon silently disables blockage alerts.
    active_polygons = read_polygons(live_dir) if preview.params.enabled else None
    if active_polygons is not None:
        print("[polygons] using operator-drawn polygons from polygons.json")

    try:
        while True:
            # --- camera switch requested by the web page ----------------------
            # Polled, not pushed: this loop must not depend on the web server
            # being up, and a missing or corrupt file simply means no request.
            if preview.params.enabled and (time.time() - last_control_check) >= 0.5:
                last_control_check = time.time()
                # Redrawn polygons: rebuild the masks, but do NOT reset the
                # series. The scene is the same one; only the region being
                # counted moved, so the history stays comparable in a way it
                # does not across a camera switch.
                drawn = read_polygons(live_dir)
                if drawn != active_polygons:
                    active_polygons = drawn
                    masks = None
                    print("[polygons] reloaded")

                wanted = read_request(live_dir)
                if wanted is not None and wanted != active_source and wanted != refused_source:
                    new_cap = cv2.VideoCapture(int(wanted) if wanted.isdigit() else wanted)
                    if new_cap.isOpened():
                        cap.release()
                        cap = new_cap
                        active_source = wanted
                        refused_source = None
                        live = is_live_source(wanted)
                        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
                        dt_nominal = 1.0 / fps if fps > 0 else 1.0 / 30.0
                        # The new camera may have a different resolution, so the
                        # polygons must be re-rasterised, and every accumulated
                        # measurement now describes a scene that is gone.
                        masks = None
                        water_mask = debris_mask = None
                        last_trash = last_water = -1e18
                        prev_ts = None
                        smoother = Smoother(smoothing_params)
                        monitor = BlockageMonitor(blockage_params)
                        velocity = VelocityEstimator(velocity_params)
                        write_status(live_dir, active=active_source, devices=devices)
                        print(f"[switch] source -> {active_source}")
                    else:
                        new_cap.release()
                        refused_source = wanted
                        # Keep running on the old camera. Reporting the failure
                        # and carrying on beats going dark because someone
                        # picked a device that is unplugged or already in use.
                        write_status(
                            live_dir,
                            active=active_source,
                            devices=devices,
                            error=f"tidak bisa membuka sumber {wanted!r}",
                        )
                        print(f"[switch] FAILED to open {wanted!r}, staying on {active_source}")

            ok, frame = cap.read()
            if not ok:
                break

            # Wall clock for a live stream; frame-derived for a file, so replaying
            # a recording produces the same timestamps every time. See
            # is_live_source() for why this cannot be decided from POS_MSEC.
            if live:
                now = time.time()
            else:
                pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                offset = pos_ms / 1000.0 if pos_ms and pos_ms > 0 else frame_idx * dt_nominal
                now = t_start + offset

            if masks is None:
                shape = frame.shape[:2]
                if active_polygons is None:
                    mask_cfg = cfg
                else:
                    # Operator-drawn polygons win over the config file. They are
                    # normalised, so they survive the camera switch that just
                    # changed this frame's resolution -- which is the whole
                    # reason they are stored as fractions.
                    mask_cfg = {
                        **cfg,
                        "roi": denormalize(active_polygons["roi"], shape),
                        "structure": denormalize(active_polygons["structure"], shape),
                    }
                masks = build_masks(mask_cfg, shape)
                if masks.structure_pixels == 0:
                    print("[warn] structure polygon is empty -- blockage alerts cannot fire")

            # --- camera rate: optical flow on RAW frames ----------------------
            dt = dt_nominal if prev_ts is None else max(1e-6, now - prev_ts)
            prev_ts = now
            vel = velocity.update(frame, debris_mask, dt)

            water_due = (now - last_water) >= water_interval or water_mask is None

            # --- water rate ---------------------------------------------------
            if water_due and water_model is not None:
                water_mask = infer(water_model, frame, size, device) == WATER
                last_water = now

            # --- trash rate ---------------------------------------------------
            if (now - last_trash) >= trash_interval or debris_mask is None:
                pred = infer(trash_model, frame, size, device)
                debris_mask = (pred == DEBRIS) | (pred == CLUMP)
                last_trash = now
                # Single-model mode: water comes free from the same pass, but is
                # only refreshed on the slower water clock so the coverage
                # denominator does not flicker frame to frame.
                if water_model is None and water_due:
                    water_mask = pred == WATER
                    last_water = now

            if water_mask is None or debris_mask is None:
                frame_idx += 1
                continue

            # Recombine the two cached masks into one class-index mask. Debris
            # wins on overlap: a bottle floating on water is debris.
            combined = np.full(frame.shape[:2], BACKGROUND, dtype=np.uint8)
            combined[water_mask] = WATER
            combined[debris_mask] = DEBRIS

            m = frame_metrics(combined, masks, geometry)
            smoothed = smoother.update(m["coverage"])
            block = monitor.update(m["accumulation_frac"], now)
            flux = area_flux(smoothed, vel["velocity_px_s"], cross_section_width, geometry)

            sink.write(
                {
                    "ts_epoch": now,
                    "frame_idx": frame_idx,
                    "coverage": m["coverage"],
                    "coverage_smoothed": smoothed,
                    "debris_px": m["debris_px"],
                    "water_px": m["water_px"],
                    "roi_px": m["roi_px"],
                    "accumulation_px": m["accumulation_px"],
                    "accumulation_frac": round(m["accumulation_frac"], 6),
                    "velocity_px_s": vel["velocity_px_s"],
                    "n_flow_vectors": vel["n_vectors"],
                    "area_flux": flux["area_flux"],
                    "flux_units": flux["flux_units"],
                    "is_metric": m["is_metric"],
                    "growth_per_min": block["growth_per_min"],
                    "alert": block["alert"],
                    "alert_reason": block["alert_reason"],
                    "water_mask_age_s": round(now - last_water, 2),
                }
            )

            # After the metrics, so a frame the web shows is one that produced a
            # row: an overlay with no matching number is impossible to debug.
            preview.update(frame, combined, now, masks.roi, masks.structure)

            if block["alert"] and block["streak"] == monitor.params.consecutive:
                print(f"[ALERT] frame {frame_idx}: {block['alert_reason']}")

            frame_idx += 1
            # Commit on a CLOCK, not a frame count.
            #
            # This used to flush every 100 frames. At the webcam config's 25
            # rows/s that is a write transaction held open for four seconds, and
            # SQLite allows one writer at a time -- so the web server's ingest
            # POST hit "database is locked", returned 503, and the ESP32 retried
            # the same batch forever with no reading ever stored.
            #
            # Frame count was never the right unit anyway: the same 100 frames
            # is 4 s on a webcam and 50 minutes at the barrage's 30 s sampling.
            if (time.time() - last_flush) >= 0.5:
                sink.flush()
                last_flush = time.time()
            if max_frames is not None and frame_idx >= max_frames:
                break
    finally:
        cap.release()
        sink.close()
        preview.close()

    summary = {
        "site": site,
        "frames": frame_idx,
        "coverage_smoothed": smoother.value,
        "output_dir": str(out_dir),
        "is_metric": geometry.is_metric,
    }
    print(summary)
    if not geometry.is_metric:
        print(
            "REMINDER: coverage is a ratio and is valid as-is, but area_flux is a "
            "RELATIVE INDEX, not m^2/s. Calibrate the homography before treating it "
            "as a physical rate."
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--source", required=True, help="video path, RTSP url, or camera index")
    ap.add_argument("--max-frames", type=int, default=None)
    args = ap.parse_args(argv)
    run(args.config, args.source, args.max_frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
