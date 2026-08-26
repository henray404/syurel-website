"""Resumable chunked downloader for the archives that are too big to restart.

    python scripts/download_resumable.py --dataset risid
    python scripts/download_resumable.py --dataset risid --assemble

Why this exists alongside scripts/download.py: that script uses
`urllib.request.urlretrieve`, which restarts from byte zero on every failure. Fine
for a 300 MB archive, useless for RiSID's 5.6 GB one on a connection that drops --
which is what happened, leaving 810 MB of orphaned parts behind.

Chunks land in `<dest>/<name>.parts/NNNNN.part`, 32 MB each. Re-running the command
picks up where the last one stopped, so an interrupted download costs only the chunk
that was in flight. Once every byte is present the parts are concatenated into the
real archive and the parts directory is removed.

The server must honour HTTP Range requests. Zenodo does; this script probes for it
and says so plainly rather than silently re-downloading the whole file.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "data" / "raw"

CHUNK = 32 * 1024 * 1024  # bytes per part file
READ_BLOCK = 1024 * 1024  # bytes per socket read
RETRIES = 20

# name -> (destination dir, filename, url)
SOURCES: dict[str, tuple[Path, str, str]] = {
    "risid": (
        RAW_ROOT / "risid",
        "images.zip",
        "https://zenodo.org/records/16927238/files/images.zip?download=1",
    ),
}


def _total_size(url: str) -> int | None:
    """Content-Length via a range probe, which also proves the server resumes."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.status != 206:
                return None
            rng = r.headers.get("Content-Range", "")  # "bytes 0-0/5871234567"
            if "/" in rng:
                return int(rng.rsplit("/", 1)[1])
    except Exception:
        return None
    return None


def _have_bytes(parts_dir: Path) -> int:
    """Bytes already on disk, counting only WHOLE parts.

    A part shorter than CHUNK is the one that was in flight when the connection
    dropped. It is discarded rather than appended to: resuming mid-part risks
    duplicating or losing bytes around the seam, and re-fetching 32 MB is cheap
    insurance against a corrupt 5.6 GB archive that only fails at unzip time.
    """
    if not parts_dir.exists():
        return 0
    total = 0
    for p in sorted(parts_dir.glob("*.part")):
        size = p.stat().st_size
        if size == CHUNK:
            total += size
        else:
            p.unlink()  # partial tail, re-fetch it
    return total


def fetch(name: str) -> int:
    dest, filename, url = SOURCES[name]
    dest.mkdir(parents=True, exist_ok=True)
    final = dest / filename
    if final.exists():
        print(f"{filename} already assembled ({final.stat().st_size / 1e9:.2f} GB)")
        return 0

    parts_dir = dest / f"{filename}.parts"
    parts_dir.mkdir(exist_ok=True)

    total = _total_size(url)
    if total is None:
        print(
            "server did not answer a Range request with 206; cannot resume.\n"
            f"Fall back to: python scripts/download.py --dataset {name}",
            file=sys.stderr,
        )
        return 1

    have = _have_bytes(parts_dir)
    print(f"{name}: {have / 1e9:.2f} / {total / 1e9:.2f} GB already on disk")

    while have < total:
        index = have // CHUNK
        start = index * CHUNK
        end = min(start + CHUNK, total) - 1
        out = parts_dir / f"{index:05d}.part"

        for attempt in range(1, RETRIES + 1):
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(req, timeout=120) as r, out.open("wb") as fh:
                    got = 0
                    while chunk := r.read(READ_BLOCK):
                        fh.write(chunk)
                        got += len(chunk)
                        pct = (start + got) * 100.0 / total
                        print(
                            f"\r  {pct:5.1f}%  ({(start + got) / 1e9:.2f}/{total / 1e9:.2f} GB)",
                            end="",
                            flush=True,
                        )
                expected = end - start + 1
                if out.stat().st_size != expected:
                    raise OSError(f"short read: {out.stat().st_size} != {expected}")
                break
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                if out.exists():
                    out.unlink()
                if attempt == RETRIES:
                    print(f"\n  part {index} failed after {RETRIES} tries: {exc}", file=sys.stderr)
                    return 1
                print(f"\n  part {index} attempt {attempt} failed ({exc}); retrying")

        have = start + (end - start + 1)

    print(f"\n{name}: all {total / 1e9:.2f} GB downloaded")
    return assemble(name)


def assemble(name: str) -> int:
    dest, filename, url = SOURCES[name]
    parts_dir = dest / f"{filename}.parts"
    final = dest / filename

    total = _total_size(url)
    parts = sorted(parts_dir.glob("*.part"))
    have = sum(p.stat().st_size for p in parts)
    if total is not None and have != total:
        print(
            f"refusing to assemble: {have} bytes on disk, {total} expected. "
            "Re-run without --assemble to fetch the rest.",
            file=sys.stderr,
        )
        return 1

    print(f"assembling {len(parts)} parts -> {final}")
    with final.open("wb") as out:
        for p in parts:
            with p.open("rb") as fh:
                shutil.copyfileobj(fh, out, READ_BLOCK)
    shutil.rmtree(parts_dir)
    print(f"done: {final} ({final.stat().st_size / 1e9:.2f} GB)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dataset", required=True, choices=sorted(SOURCES))
    ap.add_argument(
        "--assemble",
        action="store_true",
        help="concatenate existing parts without downloading (only if already complete)",
    )
    args = ap.parse_args(argv)
    return assemble(args.dataset) if args.assemble else fetch(args.dataset)


if __name__ == "__main__":
    raise SystemExit(main())
