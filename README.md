# Unreal Agent Harness

**Drive Unreal Engine 5.8 with an AI agent (Claude) — build real 3D scenes, generate cities, and play them — through the official Unreal MCP plugin.**

This is the harness behind the video: the agent gets *hands* (drive the editor), *eyes* (capture + decode the viewport), *knowledge* (the docs here), and a *QA loop* (see → act → check → fix). You point Claude Code at Unreal and it builds.

> ⚠️ **The experimental AI tooling is real but raw — budget time for plumbing.** Read [`docs/00-GETTING-STARTED.md`](docs/00-GETTING-STARTED.md) first. It's the difference between "this is magic" and "why won't it connect."

---

## What you can build with it (what's in the video)
- 🗽 **Photoreal real-world cities** — stream actual NYC (or anywhere) via Cesium Google 3D Tiles, flythrough-ready. → [`docs/cesium-for-unreal.md`](docs/cesium-for-unreal.md)
- ✈️ **A chase-cam aircraft over the city** — import a real plane mesh, rig a third-person follow cam, fly it. → [`docs/plane-chase-pawn.md`](docs/plane-chase-pawn.md)
- 🏙️ **A procedural city that builds itself, live** — PCG: shape → districts → blocks → buildings rise → roads, driven stage-by-stage on camera. → [`docs/PCG-GUIDE.md`](docs/PCG-GUIDE.md)
- 🎮 **Turn it into a game** — drop a playable third-person character into a city (incl. Epic's City Sample) and roam/drive it. → [`docs/CITY-SAMPLE-PLAYABLE.md`](docs/CITY-SAMPLE-PLAYABLE.md) · [`docs/UE-PLAYABLE-CHARACTER.md`](docs/UE-PLAYABLE-CHARACTER.md)

---

## Quickstart (≈15 min once UE is installed)
1. **Install + set up** — UE 5.8, the Metal toolchain, enable the MCP plugin + auto-start server, connect Claude Code. Full steps: [`docs/00-GETTING-STARTED.md`](docs/00-GETTING-STARTED.md).
2. **Verify the connection** — in Claude Code: `SceneTools.get_current_level` should return your level (not "Unable to connect").
3. **First build** — ask the agent to place a cube and capture it:
   - drive: `mcp__unreal__call_tool` → `SceneTools.add_to_scene_from_asset`
   - see: `EditorAppToolset.CaptureViewport` → then `python3 ue_qa.py decode`
4. **Run the loop** (below). Reach for the [recipes](docs/README.md) for lighting, materials, PCG, characters.

---

## How the agent sees and builds — the loop
`CaptureViewport` returns a multi-MB base64 PNG that floods agent context (raw HTTP to the MCP server also returns empty for big results — they stream on an async SSE channel). So the agent triggers captures through its **own MCP tool layer** (the runtime auto-saves big results to `tool-results/*.txt`, out of context), and **`ue_qa.py`** turns that blob into a small PNG + compact JSON the agent can cheaply read.

1. **Act** — build via `mcp__unreal__call_tool` (e.g. `SceneTools.add_to_scene_from_asset`).
2. **Capture** — `EditorAppToolset.CaptureViewport` `{ captureTransform, annotations, bShowUI:false }`. `captureTransform` shoots from a pose without moving the user's camera; `annotations` overlays a coordinate grid + actor labels.
3. **Decode** — `python3 ue_qa.py decode --name NAME` → `/tmp/ue_qa/NAME.png` + `NAME.json` (camera pose + labeled actors w/ positions).
4. **Read** — Read the PNG; `cat` the JSON for spatial reasoning.
5. **Correct** — fix and repeat.

**3-angle QA sweep per build step:** top-down (layout/overlap) · eye-level (aesthetic) · player-eye (gameplay feel). Also: read errors via `LogsToolset`; check overlaps via `SceneTools.find_actors(bounds)` / `trace_world`.

```
python3 ue_qa.py decode [--name NAME] [--file PATH]   # newest (or given) capture -> PNG + JSON
python3 ue_qa.py latest                               # path of newest saved capture
python3 ue_qa.py refdiff REF.png SHOT.png [--name N]  # side-by-side intent-vs-result (needs imagemagick)
```

**Two hard constraints:**
- Always go through the agent's MCP tool layer for captures (raw HTTP returns empty — async SSE).
- **One editor, one game thread → serialize every scene mutation.** No concurrent builders. Read-only inspection can overlap, but never two `ExecuteGraphInstance`/mutations at once.

---

## Documentation
Start at the **[docs index](docs/README.md)** — everything is grouped there (Setup · MCP+QA loop · Scene/Lighting/Material recipes · PCG city · Playable character & City Sample · Asset pipeline · Troubleshooting).

Stuck? → **[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)** (camera won't move, editor crashes, "Unable to connect", version mismatch, the boot hang…).

The build narrative / "how we got here, with opinions" → [`AGENTIC-GAMEDEV-GUIDE.md`](AGENTIC-GAMEDEV-GUIDE.md). The running session log → [`BUILD-LOG.md`](BUILD-LOG.md).

---

## Repo layout
```
README.md                  ← you are here (front door + the loop)
AGENTIC-GAMEDEV-GUIDE.md   ← teaching narrative + opinions
BUILD-LOG.md               ← chronological session log
ue_qa.py                   ← capture decoder (blob → PNG + JSON), refdiff
blender_jobs.py            ← headless Blender modeling jobs (bpy)
towers_jobs.py             ← procedural skyscraper generator (bpy)
ue_launch.sh / ue_crashlog.sh  ← launch UE + pull crash logs
ue_remote/                 ← Python remote-exec helpers (Cesium rebase, etc.)
splat/                     ← Gaussian-splat tile tooling
docs/                      ← all guides + recipes (see docs/README.md)
assets/                    ← (git-ignored) CC0 + generated + downloaded meshes/textures
```

## Prerequisites (short version)
macOS (Apple Silicon, M2+ for Nanite) or Windows · **UE 5.8** · Claude Code · Python 3 (+ `imagemagick` for refdiff) · Blender (only for the modeling jobs). Full list + install order in [`docs/00-GETTING-STARTED.md`](docs/00-GETTING-STARTED.md).
