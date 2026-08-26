"""Let the web page switch camera without the web server running processes.

THE RULE THIS EXISTS TO KEEP: an HTTP handler must never spawn the inference
process. Doing so would hand a network endpoint the power to start programs, and
it orphans children every time the dev server reloads on a file change. Instead
the running loop owns its own lifecycle and only *reads* a request file that the
web writes. The worst a bad request can do is name a camera that does not open,
which the loop reports and then ignores.

TWO FILES, ONE DIRECTION EACH:

    control.json   web writes, inference reads   {"source": "0"}
    status.json    inference writes, web reads   what is actually running

Keeping them separate means a stale request can never be mistaken for a live
status, and neither side has to lock anything.

Both writes are atomic (temp file + os.replace) for the same reason the JPEGs
are: the reader polls while the writer rewrites, and a half-written JSON file
raises a parse error rather than returning old data.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import cv2

from .preview import replace_with_retry

CONTROL_NAME = "control.json"
STATUS_NAME = "status.json"
POLYGONS_NAME = "polygons.json"

# Fewer than 3 points is not a polygon. The upper bound is arbitrary but real:
# the editor places points by clicking, and a runaway caller posting thousands
# would build a mask that takes visible time to rasterise on every frame.
MIN_POINTS = 3
MAX_POINTS = 64
# Smallest area worth keeping, as a fraction of the frame. Collinear points pass
# every other check and still rasterise to an empty mask -- and an empty
# structure polygon disables blockage alerts with no error at all.
MIN_AREA = 0.0001


def _write_atomic(path: Path, payload: dict[str, Any]) -> bool:
    """Same retry as the JPEGs: the web reads status.json while this rewrites it.

    On Windows a reader holding the destination open makes os.replace raise
    PermissionError, which would otherwise kill the inference process over a
    status file nobody depends on for measurement.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return replace_with_retry(tmp, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Missing, or caught mid-write on a filesystem that does not honour
        # os.replace. Either way the caller keeps what it already had.
        return None


def read_request(live_dir: Path | str) -> str | None:
    """The source the web is asking for, or None if it has not asked."""
    data = _read_json(Path(live_dir) / CONTROL_NAME)
    if data is None:
        return None
    source = data.get("source")
    return str(source) if source is not None else None


def write_request(live_dir: Path | str, source: str) -> None:
    _write_atomic(Path(live_dir) / CONTROL_NAME, {"source": str(source)})


def write_status(
    live_dir: Path | str,
    *,
    active: str,
    devices: list[dict[str, Any]],
    error: str | None = None,
) -> None:
    _write_atomic(
        Path(live_dir) / STATUS_NAME,
        {"active": str(active), "devices": devices, "error": error, "ts_epoch": time.time()},
    )


def valid_polygon(points: Any) -> list[list[float]] | None:
    """A polygon in NORMALISED coordinates, or None if it is not one.

    WHY NORMALISED (0..1) AND NOT PIXELS. Three things resize the picture
    between the camera and the click that places a point: preview.py downscales
    to max_width, the browser fits the <img> to its column, and switching camera
    changes the capture resolution outright. Pixel coordinates are wrong after
    any of the three. A fraction of the frame survives all of them.

    Rejects rather than clamps. A point outside the frame means the two sides
    disagree about the coordinate system, and silently pulling it to the edge
    would hide exactly the bug this format exists to prevent.
    """
    if not isinstance(points, list) or not (MIN_POINTS <= len(points) <= MAX_POINTS):
        return None

    out: list[list[float]] = []
    for pt in points:
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            return None
        x, y = pt
        if isinstance(x, bool) or isinstance(y, bool):
            return None
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        if not (0.0 <= float(x) <= 1.0) or not (0.0 <= float(y) <= 1.0):
            return None
        out.append([float(x), float(y)])

    if polygon_area(out) < MIN_AREA:
        return None
    return out


def polygon_area(points: list[list[float]]) -> float:
    """Shoelace area. Mirrors polygonArea in web/lib/polygons.ts."""
    total = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def read_polygons(live_dir: Path | str) -> dict[str, list[list[float]]] | None:
    """The operator-drawn ROI and structure, or None if none are saved.

    None means "use the config file" -- not "use an empty polygon". An empty
    structure polygon disables blockage alerts entirely, so the two must never
    be confused.
    """
    data = _read_json(Path(live_dir) / POLYGONS_NAME)
    if data is None:
        return None

    roi = valid_polygon(data.get("roi"))
    structure = valid_polygon(data.get("structure"))
    if roi is None or structure is None:
        return None
    return {"roi": roi, "structure": structure}


def write_polygons(
    live_dir: Path | str,
    roi: list[list[float]],
    structure: list[list[float]],
) -> bool:
    if valid_polygon(roi) is None or valid_polygon(structure) is None:
        raise ValueError("polygons must be 3-64 points with x,y in 0..1")
    return _write_atomic(
        Path(live_dir) / POLYGONS_NAME,
        {"roi": roi, "structure": structure, "normalized": True},
    )


def probe_cameras(max_index: int = 4) -> list[dict[str, Any]]:
    """Which camera indices actually open, with the frame size each gives.

    Called once at startup, BEFORE the main capture is opened -- a device can
    usually only be held by one reader, so probing while running would report
    the camera in use as unavailable.

    CAP_DSHOW rather than the default MSMF: on this machine MSMF takes seconds
    per failed index and reports a bogus CAP_PROP_POS_MSEC (see is_live_source
    in run.py), while DirectShow fails fast and enumerates the same devices.
    """
    found: list[dict[str, Any]] = []
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        try:
            if not cap.isOpened():
                continue
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            h, w = frame.shape[:2]
            found.append({"index": idx, "width": int(w), "height": int(h)})
        finally:
            cap.release()
    return found


def demo() -> None:
    """Self-check: python -m inference.control"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        live = Path(td)

        assert read_request(live) is None, "no file must read as no request"

        write_request(live, "2")
        assert read_request(live) == "2"

        # An int must come back as the string the capture layer expects.
        write_request(live, 0)  # type: ignore[arg-type]
        assert read_request(live) == "0"

        write_status(live, active="0", devices=[{"index": 0, "width": 640, "height": 480}])
        status = _read_json(live / STATUS_NAME)
        assert status is not None and status["active"] == "0"
        assert status["error"] is None
        assert not list(live.glob(".*.tmp")), "no temp file may survive a write"

        (live / CONTROL_NAME).write_text("{ broken", encoding="utf-8")
        assert read_request(live) is None, "corrupt request must read as no request"

    print("control ok")


if __name__ == "__main__":
    demo()
