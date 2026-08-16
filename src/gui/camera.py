"""Live UVC camera capture with real exposure control.

Why this module exists at all: Gradio's built-in webcam widget captures through
the BROWSER's getUserMedia, so the frame arrives already developed by the
browser's own auto-exposure. Nothing on the Python side can influence it, which
is why an Insta360 Link looks stable in its official app and blown out in a web
UI. Opening the device with OpenCV instead puts exposure, gain and white balance
back under our control.

Windows note: DirectShow (CAP_DSHOW) exposes far more UVC properties than the
default MSMF backend, so that is the default here.

Honesty rule for this module: a cv2 `set()` returning True does NOT mean the
driver applied anything -- several properties accept a write and silently keep
their old value. Every setter here reads the value back and reports what the
hardware actually holds, so the UI can show the truth rather than the request.
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass

import cv2
import numpy as np

# Property table. `lo`/`hi` are slider bounds, not driver limits -- the driver
# clamps to its own range and the readback shows where it landed.
CONTROLS: dict[str, dict] = {
    "exposure": {
        "prop": cv2.CAP_PROP_EXPOSURE,
        "lo": -13.0, "hi": 0.0, "step": 1.0,
        "label": "Exposure (log2 s; lower = darker)",
    },
    "brightness": {"prop": cv2.CAP_PROP_BRIGHTNESS, "lo": -64.0, "hi": 64.0, "step": 1.0,
                   "label": "Brightness"},
    "contrast": {"prop": cv2.CAP_PROP_CONTRAST, "lo": 0.0, "hi": 100.0, "step": 1.0,
                 "label": "Contrast"},
    "saturation": {"prop": cv2.CAP_PROP_SATURATION, "lo": 0.0, "hi": 128.0, "step": 1.0,
                   "label": "Saturation"},
    "gain": {"prop": cv2.CAP_PROP_GAIN, "lo": 0.0, "hi": 128.0, "step": 1.0, "label": "Gain"},
    "gamma": {"prop": cv2.CAP_PROP_GAMMA, "lo": 100.0, "hi": 500.0, "step": 10.0,
              "label": "Gamma"},
    "wb_temperature": {"prop": cv2.CAP_PROP_WB_TEMPERATURE, "lo": 2000.0, "hi": 8000.0,
                       "step": 100.0, "label": "White balance (K)"},
}

RESOLUTIONS = ["1920x1080", "1280x720", "640x480"]


def default_backend() -> int:
    return cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY


@dataclass
class Device:
    index: int
    max_w: int
    max_h: int

    @property
    def label(self) -> str:
        return f"{self.index}  (up to {self.max_w}x{self.max_h})"


def list_devices(limit: int = 6) -> list[Device]:
    """Indices that open AND deliver a frame.

    OpenCV cannot report device names on Windows, so these are bare indices --
    the preview is how you tell which camera is which.
    """
    out: list[Device] = []
    backend = default_backend()
    for idx in range(limit):
        cap = cv2.VideoCapture(idx, backend)
        try:
            if not cap.isOpened():
                continue
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 4096)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
            out.append(
                Device(idx,
                       int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                       int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            )
        finally:
            cap.release()
    return out


class Camera:
    """One open capture, shared between the preview loop and the control sliders.

    cv2.VideoCapture is not thread-safe and the preview generator runs on a
    different thread from the slider callbacks, so every touch goes through one
    lock. Without it, changing a slider mid-preview can hand back a torn frame
    or wedge the device.
    """

    def __init__(self) -> None:
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self.index: int | None = None

    # -- lifecycle ---------------------------------------------------------

    def open(self, index: int, resolution: str) -> str:
        self.close()
        w, h = (int(v) for v in resolution.split("x"))
        cap = cv2.VideoCapture(int(index), default_backend())
        if not cap.isOpened():
            cap.release()
            return f"Could not open camera {index}. Another app may be holding it."

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        ok, _ = cap.read()
        if not ok:
            cap.release()
            return f"Camera {index} opened but delivered no frame."

        with self._lock:
            self._cap = cap
            self.index = int(index)
        aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        note = "" if (aw, ah) == (w, h) else f"  (asked {w}x{h}, driver gave {aw}x{ah})"
        return f"Camera {index} open at {aw}x{ah}{note}"

    def close(self) -> str:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
                self.index = None
        return "Camera closed."

    @property
    def is_open(self) -> bool:
        return self._cap is not None

    # -- frames ------------------------------------------------------------

    def frame(self) -> np.ndarray | None:
        """One RGB frame, or None if the camera is closed or dropped it."""
        with self._lock:
            if self._cap is None:
                return None
            ok, bgr = self._cap.read()
        if not ok or bgr is None:
            return None
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # -- controls ----------------------------------------------------------

    def read_all(self) -> dict[str, float]:
        with self._lock:
            if self._cap is None:
                return {}
            return {k: float(self._cap.get(c["prop"])) for k, c in CONTROLS.items()}

    def set_control(self, name: str, value: float) -> float | None:
        """Set one property, return what the driver actually holds afterwards.

        The return value is the readback, not the request: a driver is free to
        clamp, round, or ignore the write entirely.
        """
        spec = CONTROLS.get(name)
        if spec is None:
            return None
        with self._lock:
            if self._cap is None:
                return None
            self._cap.set(spec["prop"], float(value))
            return float(self._cap.get(spec["prop"]))

    def set_auto_exposure(self, auto: bool) -> str:
        """Toggle auto-exposure, and say plainly whether the driver obeyed.

        DSHOW is unreliable here: it commonly reports -1 for CAP_PROP_AUTO_EXPOSURE
        and never moves. On most such drivers, writing CAP_PROP_EXPOSURE directly
        is what actually forces manual mode -- so the caller should follow this
        with a set_control("exposure", ...) rather than trusting the toggle.
        """
        with self._lock:
            if self._cap is None:
                return "Camera is closed."
            before = float(self._cap.get(cv2.CAP_PROP_AUTO_EXPOSURE))
            # 0.75 = auto, 0.25 = manual is the widely-used UVC convention.
            self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75 if auto else 0.25)
            after = float(self._cap.get(cv2.CAP_PROP_AUTO_EXPOSURE))

        if abs(after - before) < 1e-6:
            return (
                f"Auto-exposure flag did not move (still {after:g}). This driver ignores "
                "the toggle -- set the Exposure slider instead, which forces manual mode "
                "on most DirectShow cameras."
            )
        return f"Auto-exposure {'on' if auto else 'off'} (flag {before:g} -> {after:g})."

    def set_auto_wb(self, auto: bool) -> str:
        with self._lock:
            if self._cap is None:
                return "Camera is closed."
            before = float(self._cap.get(cv2.CAP_PROP_AUTO_WB))
            self._cap.set(cv2.CAP_PROP_AUTO_WB, 1.0 if auto else 0.0)
            after = float(self._cap.get(cv2.CAP_PROP_AUTO_WB))
        if abs(after - before) < 1e-6:
            return f"Auto white-balance flag did not move (still {after:g})."
        return f"Auto white-balance {'on' if auto else 'off'} ({before:g} -> {after:g})."


MID_GREY = 128.0


def exposure_sweep(cam: Camera, lo: float = -13.0, hi: float = 0.0) -> list[tuple[float, float]]:
    """(driver_exposure, mean_luminance) across the range, restoring the original.

    Reports the DRIVER's value, not the requested one -- this hardware clamps -10
    to -8, and recording the request would make the table a record of what we
    asked rather than what the camera did.
    """
    if not cam.is_open:
        return []
    rows: list[tuple[float, float]] = []
    original = cam.read_all().get("exposure")
    try:
        v = lo
        while v <= hi:
            got = cam.set_control("exposure", v)
            for _ in range(6):        # let the sensor settle before believing a frame
                cam.frame()
            # Median of several frames, not one. Measured on real hardware: this
            # camera intermittently returns a fully black frame right after a large
            # exposure change even once settled, and a single sample would record
            # that step as luminance 0 and drop the best exposure off the table.
            lums = [float(f.mean()) for f in (cam.frame() for _ in range(5)) if f is not None]
            if lums:
                lums.sort()
                rows.append((got if got is not None else v, lums[len(lums) // 2]))
            v += 1.0
    finally:
        if original is not None:
            cam.set_control("exposure", original)
    # The driver clamps, so several requests can land on one value. Keep the first.
    seen: dict[float, float] = {}
    for value, lum in rows:
        seen.setdefault(value, lum)
    return sorted(seen.items())


def best_exposure(cam: Camera) -> tuple[float, float] | None:
    """The swept exposure whose mean luminance sits nearest mid-grey."""
    rows = exposure_sweep(cam)
    if not rows:
        return None
    return min(rows, key=lambda r: abs(r[1] - MID_GREY))


def exposure_probe(cam: Camera) -> str:
    """Human-readable sweep: the whole table, so the choice can be second-guessed."""
    if not cam.is_open:
        return "Open the camera first."
    rows = exposure_sweep(cam)
    if not rows:
        return "No frames captured during the sweep."

    best = min(rows, key=lambda r: abs(r[1] - MID_GREY))
    table = "\n".join(
        f"| {v:g} | {m:.1f} |{' **<- suggested**' if v == best[0] else ''}" for v, m in rows
    )
    return (
        f"**Suggested exposure: {best[0]:g}** (mean luminance {best[1]:.1f}, "
        f"nearest mid-grey {MID_GREY:g})\n\n"
        f"| exposure | mean luminance |\n|---|---|\n{table}\n\n"
        "Values are what the driver actually held -- it clamps, so requests can collapse "
        "onto the same value. Mid-grey is a starting point, not a calibration: bright sky "
        "in frame pulls the mean up and biases this darker than you want. Judge by the "
        "preview, and prefer slightly dark over clipped, since clipped detail is gone for good."
    )
