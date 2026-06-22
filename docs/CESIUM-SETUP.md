# Cesium for Unreal — setup (stream the real Earth into Unreal)

> Pull real-world cities (Google Photorealistic 3D Tiles) into Unreal, then let the **AI agent build the scene for you over the MCP**. You do two tiny one-time things; the agent does the rest.

> **On UE 5.8 (or any UE version with no Fab release), the Fab install below does NOT exist** — Fab shows *"You cannot install this plugin as there are no compatible engines installed."* Building from source is then the **only** path. Follow **[CESIUM-BUILD-FROM-SOURCE.md](CESIUM-BUILD-FROM-SOURCE.md)** (exact, agent-executable) and skip step 1 here; step 2 (the Google key) still applies. The rest of this doc assumes the plugin is installed (whether from Fab or from source).

## You do 2 things (≈5 min, once)
1. **Install Cesium for Unreal — one click from Fab** *(supported UE versions only; on 5.8 use the source build above)*. [fab.com](https://www.fab.com) (sign in with your Epic account) → search **"Cesium for Unreal"** (free) → **Add to Library** → **Install to Engine** → in the editor, **Edit → Plugins → enable "Cesium for Unreal" → restart**. Its UI then lives under **Window → Cesium**.
2. **Get a Google Maps API key** (the one credential only you can make). Google Cloud Console → enable the **Map Tiles API** → **Create credentials → API key**. You'll hand this to the agent.

That's the whole manual part. **You do NOT hand-place actors or hand-build the scene.**

## The agent does the rest — over the MCP
Point your agent at [`NYC-CESIUM-WALKTHROUGH.md`](NYC-CESIUM-WALKTHROUGH.md). With the MCP connected ([`UNREAL-MCP-ENABLE.md`](UNREAL-MCP-ENABLE.md)), it drives Unreal for you:
- adds a **CesiumGeoreference** (your city's lat/lon),
- adds a **Cesium3DTileset** → `FromUrl` = `https://tile.googleapis.com/v1/3dtiles/root.json?key=YOUR_KEY` (your key), linked to the georeference,
- adds sun/sky + a flying pawn, and **rebases** the tiles to the origin so they render at the world center.

You tell it the city + paste the key → it builds → you press Play and fly. Reuse for any city by changing the coordinates. Property reference: [`cesium-for-unreal.md`](cesium-for-unreal.md).

## Gotchas
- **Google ion's old free P3DT asset (`2275207`) is no longer free** — use the **direct Google key URL** above, not that ion asset.
- **Ray tracing off on Mac** for stability/perf (`r.RayTracing=0`).
- **Plugin UI is under `Window → Cesium`**, not the toolbar.

---

## No Fab release for your UE version? (UE 5.8 and any future bleeding-edge)
This is **not** a footnote on 5.8 — it's the only way in. Fab has no 5.8 Cesium build, so we
built **v2.27.0 from source** and installed it as a project plugin
(`<Project>/Plugins/CesiumForUnreal`), which is why on this machine it's *not* a Fab download.
The complete, exact, copy-pasteable recipe (deps → recursive clone → 8 UE-5.8 patches →
cesium-native CMake build → `Darwin-universal`→`arm64` symlinks → editor dylibs via UBT against
a throwaway C++ host → install → splat-tick patch) lives in
**[CESIUM-BUILD-FROM-SOURCE.md](CESIUM-BUILD-FROM-SOURCE.md)**. Build artifacts + the patch:
`~/coding/cesium-build/` (`cesium-5.8-patches.diff`). On a **supported** UE version, ignore all
of this and just install from Fab (step 1 above).
