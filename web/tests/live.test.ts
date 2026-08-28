import { mkdtemp, readFile, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { beforeAll, describe, expect, it } from "vitest";

// SYURELL_LIVE_DIR is read at module load, so it has to be set before the
// import. A static `import` would be hoisted above this and pick up the real
// out/ directory instead of a temp one.
let live: typeof import("../lib/live");
let dir: string;

beforeAll(async () => {
  dir = await mkdtemp(path.join(tmpdir(), "syurell-live-"));
  process.env.SYURELL_LIVE_DIR = dir;
  live = await import("../lib/live");
});

/** Minimal bytes that pass the JPEG sniff: SOI + APP0 marker. */
function jpeg(padding = 16): Uint8Array {
  return new Uint8Array([0xff, 0xd8, 0xff, 0xe0, ...new Array(padding).fill(0)]);
}

describe("previewPath", () => {
  it("maps the two known names", () => {
    expect(live.previewPath("frame")).toBe(path.join(dir, "frame.jpg"));
    expect(live.previewPath("mask")).toBe(path.join(dir, "mask.jpg"));
  });

  it("returns null for anything else, traversal included", () => {
    expect(live.previewPath("status")).toBeNull();
    expect(live.previewPath("../../../etc/passwd")).toBeNull();
    expect(live.previewPath("frame.jpg")).toBeNull();
  });
});

describe("savePreview", () => {
  it("writes the bytes under the mapped name", async () => {
    const res = await live.savePreview("frame", jpeg());
    expect(res).toEqual({ ok: true, bytes: 20 });
    expect(await readFile(path.join(dir, "frame.jpg"))).toEqual(Buffer.from(jpeg()));
  });

  it("leaves no temp file behind", async () => {
    await live.savePreview("mask", jpeg());
    // The atomic write is tmp-then-rename. A leftover .mask.jpg.upload.tmp would
    // mean the rename never happened, and a reader could be served half a frame.
    const left = (await readdir(dir)).filter((f) => f.includes(".tmp"));
    expect(left).toEqual([]);
  });

  it("refuses an unknown name without touching the disk", async () => {
    const res = await live.savePreview("../escape", jpeg());
    expect(res).toEqual({ ok: false, status: 404, error: "unknown preview: ../escape" });
  });

  it("refuses an empty body", async () => {
    const res = await live.savePreview("frame", new Uint8Array(0));
    expect(res).toMatchObject({ ok: false, status: 400 });
  });

  it("refuses bytes that are not a JPEG", async () => {
    // A truncated or mis-typed POST must never land as frame.jpg: the demo page
    // renders whatever is there, so junk would show as a broken image under a
    // live timestamp.
    const res = await live.savePreview("frame", new Uint8Array([0x89, 0x50, 0x4e, 0x47]));
    expect(res).toMatchObject({ ok: false, status: 415 });
  });

  it("refuses a body over the ceiling", async () => {
    const big = new Uint8Array(live.MAX_UPLOAD_BYTES + 1);
    big.set([0xff, 0xd8, 0xff, 0xe0]);
    const res = await live.savePreview("frame", big);
    expect(res).toMatchObject({ ok: false, status: 413 });
  });

  it("keeps the last good frame when a bad upload follows", async () => {
    await live.savePreview("frame", jpeg(32));
    const good = await readFile(path.join(dir, "frame.jpg"));
    await live.savePreview("frame", new Uint8Array([0x00, 0x01, 0x02, 0x03]));
    expect(await readFile(path.join(dir, "frame.jpg"))).toEqual(good);
  });
});
