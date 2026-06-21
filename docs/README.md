# Docs Index

Start with **[00-GETTING-STARTED.md](00-GETTING-STARTED.md)**. For the big picture of every world we built + the method, read **[ENVIRONMENTS.md](ENVIRONMENTS.md)**. Then jump to whatever you're building. Stuck → **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.

## 🌍 The environments (overview)
- [ENVIRONMENTS.md](ENVIRONMENTS.md) — **the worlds library + the method**: City Sample base + PCG grammar generator + custom Blender facade kits → futuristic glass city, car showcase, Paris (Beaux-Arts), Art-Deco, sci-fi interior, real NYC. The "what can this make + how" overview.
- [REALISM-GUIDE.md](REALISM-GUIDE.md) — **how to make ANY generated scene look real, not "bland 3D"** (style-agnostic: variety, PBR + normal maps, decals, ornament geometry, roofs, street life, the QA loop), illustrated with the Paris block.
- [BLENDER-DETAIL.md](BLENDER-DETAIL.md) — **the real source of architectural detail** (the honest method): scanned assets/materials > geometry method (Geometry Nodes, trim sheets) > lighting > decals. Why hand-bpy boxes + gen textures look bland, and what to do instead.
- [scifi-interior-plan.md](scifi-interior-plan.md) — free CC0 sci-fi interior kit + build plan.

## 🚀 Setup
- [00-GETTING-STARTED.md](00-GETTING-STARTED.md) — install UE, enable the MCP, connect Claude Code, first build.
- [UNREAL-MCP-ENABLE.md](UNREAL-MCP-ENABLE.md) — exact config to enable the MCP + auto-start server in any project (the `.uproject` + `DefaultEngine.ini` edits).
- [ue58-python-api.md](ue58-python-api.md) — UE 5.8 Python API notes (for `ProgrammaticToolset` / remote exec).
- [programmatic-toolset-capabilities.md](programmatic-toolset-capabilities.md) — batching many tool calls in one sandboxed script.

## 🗽 Real-world cities (Cesium)
- [NYC-CESIUM-WALKTHROUGH.md](NYC-CESIUM-WALKTHROUGH.md) — **the step-by-step demo**: stream real NYC start to finish (plugin → Google 3D Tiles key → georeference → rebase → sun/sky → fly). Works for any city.
- [cesium-for-unreal.md](cesium-for-unreal.md) — Cesium actor/property/function *reference*.
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
