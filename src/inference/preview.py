"""Write the newest frame and its segmentation overlay to disk for the web UI.

WHY THIS EXISTS INSTEAD OF STREAMING THE WEBCAM TO THE BROWSER. The browser can
open a webcam itself (`getUserMedia`), but that gives a viewfinder and nothing
else: the mask lives in this process, and the browser never sees it. Worse,
`getUserMedia` is refused on an insecure origin, so a page opened over the LAN --
which is how the ESP32 and any phone reach this server -- gets no camera at all.
Two JPEGs on disk work from every device and carry the model's output with them.

ATOMICITY IS THE WHOLE TRICK. The web server polls these files while this loop
rewrites them. Writing in place hands the reader a half-flushed JPEG, which
renders as a grey band or a broken image. Every write here lands on a temporary
name and is moved into place with os.replace, which is atomic on Windows and
POSIX alike, so a reader sees either the previous frame or the next one.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from data.schema import DEBRIS, WATER

# BGR, because OpenCV. Debris is the alarm colour; water is calm.
DEBRIS_BGR = (60, 60, 235)
WATER_BGR = (235, 150, 60)
ROI_BGR = (255, 255, 255)
STRUCTURE_BGR = (60, 215, 245)


def replace_with_retry(tmp: Path, final: Path, attempts: int = 5, delay: float = 0.02) -> bool:
    """os.replace, but survives a reader holding the destination open.

    MEASURED FAILURE, not a hypothetical. On Windows os.replace raises
    PermissionError (WinError 5) when the destination is open in another
    process. The web server reads frame.jpg on every poll, so at ten writes a
    second the two collide regularly -- and an uncaught raise here killed the
    inference process outright, ending measurement because a screenshot failed.

    The reader's hold lasts milliseconds, so a few short retries clear it.
    Returns False if they do not, and the caller carries on: a missed preview
    frame costs nothing, and the next one is 100 ms away.
    """
    for attempt in range(attempts):
        try:
            os.replace(tmp, final)
            return True
        except PermissionError:
            if attempt == attempts - 1:
                break
            time.sleep(delay)
    # Do not leave the temp file behind; the next write would find it and the
    # directory would slowly fill with dot-files nobody reads.
    tmp.unlink(missing_ok=True)
    return False


@dataclass
class PreviewParams:
    enabled: bool = False
    # Writing a JPEG pair costs a few ms; at camera rate that is wasted work
    # nobody sees, since the page refreshes on its own schedule.
    interval_s: float = 1.0
    # Downscale before encoding. A 4K site camera would otherwise write ~2 MB
    # per frame to disk continuously.
    max_width: int = 960
    jpeg_quality: int = 80
    # Draw the ROI and structure polygons over the overlay. On by default: the
    # polygons in a fresh site config are placeholders, and seeing them
    # misaligned is the fastest way to find that out.
    draw_polygons: bool = True


def overlay(
    frame: np.ndarray,
    combined: np.ndarray,
    roi: np.ndarray | None = None,
    structure: np.ndarray | None = None,
    params: PreviewParams | None = None,
) -> np.ndarray:
    """Tint debris and water over a copy of the frame."""
    p = params or PreviewParams()
    out = frame.copy()

    tint = np.zeros_like(frame)
    tint[combined == WATER] = WATER_BGR
    tint[combined == DEBRIS] = DEBRIS_BGR
    painted = (combined == WATER) | (combined == DEBRIS)
    # Blend only where something was detected, so untouched pixels stay exactly
    # as the camera saw them -- a uniform blend washes out the whole image and
    # makes it hard to judge whether the mask is right.
    out[painted] = cv2.addWeighted(frame, 0.45, tint, 0.55, 0)[painted]

    if p.draw_polygons:
        for mask, colour in ((roi, ROI_BGR), (structure, STRUCTURE_BGR)):
            if mask is None or not mask.any():
                continue
            contours, _ = cv2.findContours(
                mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            cv2.drawContours(out, contours, -1, colour, 2)

    return out


class LivePreview:
    """Throttled, atomic writer for `live/frame.jpg` and `live/mask.jpg`."""

    def __init__(self, out_dir: Path | str, params: PreviewParams | None = None) -> None:
        self.params = params or PreviewParams()
        self.dir = Path(out_dir) / "live"
        self._last = -1e18
        self.failures = 0
        if self.params.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _write(self, name: str, image: np.ndarray) -> bool:
        p = self.params
        h, w = image.shape[:2]
        if w > p.max_width:
            scale = p.max_width / w
            image = cv2.resize(image, (p.max_width, max(1, int(h * scale))))

        ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, p.jpeg_quality])
        if not ok:
            return False

        final = self.dir / name
        # Same directory as the target: os.replace is only atomic within one
        # filesystem, and a temp dir may sit on another drive.
        tmp = self.dir / f".{name}.tmp"
        tmp.write_bytes(buf.tobytes())
        return replace_with_retry(tmp, final)

    def update(
        self,
        frame: np.ndarray,
        combined: np.ndarray,
        now: float,
        roi: np.ndarray | None = None,
        structure: np.ndarray | None = None,
    ) -> bool:
        """Returns True when this call actually wrote files."""
        if not self.params.enabled:
            return False
        if (now - self._last) < self.params.interval_s:
            return False
        self._last = now

        # THE PREVIEW MUST NEVER TAKE DOWN THE MEASUREMENT LOOP. This writes
        # pictures for a dashboard; the rows in SQLite are the actual product.
        # A full disk, a locked file or a codec failure is a reason to skip a
        # frame, never a reason to stop watching the river.
        try:
            wrote = self._write("frame.jpg", frame)
            wrote = self._write("mask.jpg", overlay(frame, combined, roi, structure, self.params))
        except OSError as err:
            self.failures += 1
            # Report the first one and then stay quiet: at ten frames a second a
            # persistent fault would otherwise bury the alert lines in the log.
            if self.failures == 1:
                print(f"[preview] write failed ({err}); measurement continues")
            return False

        return wrote

    def close(self) -> None:
        """Remove any temp file a crash mid-write left behind."""
        if not self.params.enabled or not self.dir.exists():
            return
        for stale in self.dir.glob(".*.tmp"):
            stale.unlink(missing_ok=True)


def demo() -> None:
    """Self-check: python -m inference.preview"""
    import tempfile

    frame = np.full((40, 60, 3), 120, dtype=np.uint8)
    combined = np.zeros((40, 60), dtype=np.uint8)
    combined[0:10, 0:10] = DEBRIS
    combined[20:30, 20:30] = WATER

    painted = overlay(frame, combined)
    assert not np.array_equal(painted[0, 0], frame[0, 0]), "debris pixels must be tinted"
    assert np.array_equal(painted[39, 59], frame[39, 59]), "untouched pixels must stay exact"

    with tempfile.TemporaryDirectory() as td:
        pv = LivePreview(td, PreviewParams(enabled=True, interval_s=10.0))
        assert pv.update(frame, combined, now=100.0), "first call must write"
        assert not pv.update(frame, combined, now=101.0), "must throttle inside the interval"
        assert pv.update(frame, combined, now=200.0), "must write again after the interval"
        assert (Path(td) / "live" / "frame.jpg").exists()
        assert (Path(td) / "live" / "mask.jpg").exists()
        assert not list((Path(td) / "live").glob(".*.tmp")), "no temp file may survive a write"

    print("preview ok")


if __name__ == "__main__":
    demo()
