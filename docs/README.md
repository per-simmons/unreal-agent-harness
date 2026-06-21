# Docs Index

Start with **[00-GETTING-STARTED.md](00-GETTING-STARTED.md)**. Then jump to whatever you're building. Stuck → **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.

## 🚀 Setup
- [00-GETTING-STARTED.md](00-GETTING-STARTED.md) — install UE, enable the MCP, connect Claude Code, first build.
- [UNREAL-MCP-ENABLE.md](UNREAL-MCP-ENABLE.md) — exact config to enable the MCP + auto-start server in any project (the `.uproject` + `DefaultEngine.ini` edits).
- [ue58-python-api.md](ue58-python-api.md) — UE 5.8 Python API notes (for `ProgrammaticToolset` / remote exec).
- [programmatic-toolset-capabilities.md](programmatic-toolset-capabilities.md) — batching many tool calls in one sandboxed script.

## 🗽 Real-world cities (Cesium)
- [cesium-for-unreal.md](cesium-for-unreal.md) — stream Google Photorealistic 3D Tiles (real NYC, anywhere).
- [cesium-rebase-solution.md](cesium-rebase-solution.md) — the georeference/origin-rebase so tiles render at the origin.
- [cesium-splat-subsystem-disable.md](cesium-splat-subsystem-disable.md) — disabling the crashing gaussian-splat tick subsystem.
- [khr-gaussian-splatting.md](khr-gaussian-splatting.md) — gaussian-splat tile format notes (see also `../splat/`).

## ✈️ Aircraft + chase camera
- [plane-chase-pawn.md](plane-chase-pawn.md) — import a plane, rig a third-person chase cam.
- [chase-cam-correct.md](chase-cam-correct.md) — the *correct* chase-cam setup (the pawn's own camera, not a spring arm) + the "shadow but no plane" fixes (owner-no-see, scale, near-clip).
- [flight-pawn-setup.md](flight-pawn-setup.md) — the flying pawn + controls.
- [plane-life.md](plane-life.md) — "make it feel like flying" touches (cruise attitude, contrails caveats, camera lag).
- [pie-qa-capture.md](pie-qa-capture.md) — QA-capturing Play-In-Editor (and why CaptureViewport grabs the *editor* viewport, not the possessed cam).

## 🏙️ Procedural city (PCG)
- [PCG-GUIDE.md](PCG-GUIDE.md) — **the living guide**: the pipeline (shape → districts → blocks → buildings → roads), the MCP PCG tools, presentation tips, learnings log.
- [pcg-city-plan.md](pcg-city-plan.md) — the detailed node-by-node MCP recipe.
- [pcg-city-research.md](pcg-city-research.md) — how the demo is actually done + free assets (PCGEx, kits).

## 🎮 Make it a playable game
- [CITY-SAMPLE-PLAYABLE.md](CITY-SAMPLE-PLAYABLE.md) — Epic's City Sample: it ships playable (walk/drive/fly); Mac perf settings; add your own character; the MCP launch recipe.
- [UE-PLAYABLE-CHARACTER.md](UE-PLAYABLE-CHARACTER.md) — drop a third-person character into ANY level (Third Person template, GameMode, Enhanced Input, common "won't move / falls through" fixes).

## 🎨 Lighting & materials (recipes)
- [golden-hour-lighting-plan.md](golden-hour-lighting-plan.md) — directional sun + sky + fog + exposure for a time-of-day look.
- [lighting-safety-review.md](lighting-safety-review.md) — avoiding blown-out / Lumen-clipping lighting.
- [futuristic-look.md](futuristic-look.md) — windowed-glass skyscraper material (emissive window grid) + dusk lighting, built via MaterialTools nodes.

## 🧱 Asset pipeline
- See the [main README](../README.md) "Repo layout" + `../blender_jobs.py` / `../towers_jobs.py` (headless Blender), `../splat/` (gaussian splats), `../ue_remote/` (Python remote exec). Asset *sourcing* (CC0 kits, generation, image-to-3D) is covered in [AGENTIC-GAMEDEV-GUIDE.md](../AGENTIC-GAMEDEV-GUIDE.md) §5–6.

## 🔧 When things break
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — the consolidated gotchas (connection, camera, crashes, version compat, perf).
