"""Inference: video/RTSP in, coverage + flux + blockage alerts out.

    python -m inference.run --config configs/inference/site_example.yaml --source river.mp4

Self-checks (no model, no video, no GPU needed):

    python -m inference.geometry
    python -m inference.velocity
    python -m inference.metrics
    python -m inference.sink

Everything is a pixel ratio until the homography is calibrated in Phase 2.
geometry.py refuses to fake a scale rather than emitting plausible-looking m^2.
"""
