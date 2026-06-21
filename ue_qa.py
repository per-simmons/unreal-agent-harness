#!/usr/bin/env python3
"""
Unreal MCP QA/vision harness.

The agent triggers a capture through its MCP tool layer
(mcp__unreal__call_tool -> EditorToolset.EditorAppToolset.CaptureViewport).
That result is multi-MB base64 and the runtime auto-saves it to a tool-results
file instead of flooding context. THIS script turns that saved blob into a small,
downscaled PNG the agent can cheaply Read, plus a compact JSON sidecar (camera
pose + labeled actors with world XYZ in meters) for spatial reasoning.

Workflow per QA shot:
  1. agent: call_tool CaptureViewport { captureTransform, annotations, bShowUI }
  2. agent: python3 ue_qa.py decode --name top
  3. agent: Read /tmp/ue_qa/top.png   (and optionally cat /tmp/ue_qa/top.json)

3-angle QA sweep (recommended each build step):
  - top-down  : captureTransform above the area, pitch -90  -> layout/overlap
  - eye-level : ~170cm height, level pitch                 -> aesthetic
  - player-eye: street level, slight up-tilt               -> gameplay feel

Commands:
  python3 ue_qa.py decode [--name NAME] [--file PATH]
        Decode newest (or given) saved capture -> /tmp/ue_qa/NAME.png + NAME.json
  python3 ue_qa.py latest
        Print path of the newest saved tool-result capture file
  python3 ue_qa.py refdiff REF.png SHOT.png [--name NAME]
        Compose reference + capture side-by-side -> /tmp/ue_qa/NAME_diff.png
        (Critic Reads one frame to compare intent vs result.)
"""
import sys, os, base64, re, glob, json, subprocess

OUT = "/tmp/ue_qa"
MAXDIM = 1600
PROJECTS = os.path.expanduser("~/.claude/projects")
os.makedirs(OUT, exist_ok=True)


def newest_capture():
    pats = glob.glob(os.path.join(PROJECTS, "**", "tool-results", "mcp-unreal-call_tool-*.txt"), recursive=True)
    return max(pats, key=os.path.getmtime) if pats else None


def _num(raw, key):
    m = re.search(r'"%s"\s*:\s*(-?[0-9.]+)' % key, raw)
    return float(m.group(1)) if m else None


def decode(path, name):
    raw = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r'"data"\s*:\s*"([A-Za-z0-9+/=]{500,})"', raw)
    if not m:
        print("No base64 image found in", path); sys.exit(1)
    png = os.path.join(OUT, name + ".png")
    with open(png, "wb") as f:
        f.write(base64.b64decode(m.group(1)))
    subprocess.run(["sips", "-Z", str(MAXDIM), png], capture_output=True)

    # Build a compact spatial sidecar: camera pose + labeled actors (world XYZ, meters).
    sidecar = {"png": png, "source": os.path.basename(path), "camera": {}, "actors": []}
    cl = re.search(r'"cameraLocation"\s*:\s*\{[^}]*"x"\s*:\s*(-?[0-9.]+)[^}]*"y"\s*:\s*(-?[0-9.]+)[^}]*"z"\s*:\s*(-?[0-9.]+)', raw)
    if cl:
        sidecar["camera"]["location_cm"] = [float(cl.group(1)), float(cl.group(2)), float(cl.group(3))]
    fov = _num(raw, "cameraFOV")
    if fov:
        sidecar["camera"]["fov"] = fov
    # labeledActors: the "label" field already embeds name + position in meters,
    # e.g. "MCP_TestCube @(0,0,2)". Robust against nested screenPosition/class objects.
    seen = set()
    for lm in re.finditer(r'"label"\s*:\s*"([^"]+)"', raw):
        lbl = lm.group(1)
        if lbl not in seen:
            seen.add(lbl)
            sidecar["actors"].append({"label": lbl})
    js = os.path.join(OUT, name + ".json")
    json.dump(sidecar, open(js, "w"), indent=2)

    kb = os.path.getsize(png) // 1024
    print(f"PNG: {png}  ({kb} KB)   JSON: {js}   [from {os.path.basename(path)}]")
    if sidecar["actors"]:
        print(f"Labeled actors ({len(sidecar['actors'])}):")
        for a in sidecar["actors"][:60]:
            print(f"  - {a['label']}")


def refdiff(ref, shot, name):
    out = os.path.join(OUT, name + "_diff.png")
    # Prefer ImageMagick montage if present; else sips-based fallback.
    if subprocess.run(["which", "montage"], capture_output=True).returncode == 0:
        subprocess.run(["montage", ref, shot, "-tile", "2x1", "-geometry", "+8+8",
                        "-background", "black", "-title", f"REF  |  {os.path.basename(shot)}", out],
                       capture_output=True)
    elif subprocess.run(["which", "magick"], capture_output=True).returncode == 0:
        subprocess.run(["magick", "montage", ref, shot, "-tile", "2x1", "-geometry", "+8+8", out], capture_output=True)
    else:
        # last-resort: just copy the shot and note both paths
        subprocess.run(["cp", shot, out], capture_output=True)
        print("(no montage/magick — install imagemagick for true side-by-side)")
    print(f"DIFF: {out}   (left=reference {os.path.basename(ref)}, right=capture {os.path.basename(shot)})")


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd, args = sys.argv[1], sys.argv[2:]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    if cmd == "latest":
        print(newest_capture() or "no capture files found")
    elif cmd == "decode":
        path = opt("--file") or newest_capture()
        if not path:
            print("no capture files found — trigger a CaptureViewport first"); sys.exit(1)
        decode(path, opt("--name", "view"))
    elif cmd == "refdiff":
        pos = [a for a in args if not a.startswith("--")]
        if len(pos) < 2:
            print("usage: refdiff REF.png SHOT.png [--name NAME]"); sys.exit(1)
        refdiff(pos[0], pos[1], opt("--name", "ref"))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
