# Cesium for Unreal — setup (stream the real Earth into Unreal)

> Pull real-world cities (Google Photorealistic 3D Tiles) into Unreal, then let the **AI agent build the scene for you over the MCP**. You do two tiny one-time things; the agent does the rest.

## You do 2 things (≈5 min, once)
1. **Install Cesium for Unreal — one click from Fab.** [fab.com](https://www.fab.com) (sign in with your Epic account) → search **"Cesium for Unreal"** (free) → **Add to Library** → **Install to Engine** → in the editor, **Edit → Plugins → enable "Cesium for Unreal" → restart**. Its UI then lives under **Window → Cesium**.
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

## Footnote — bleeding-edge UE with no Fab release (rare; what we hit on 5.8)
Skip this unless Fab has **no** Cesium build for your exact UE version. We were on **UE 5.8** the week it dropped, before Cesium shipped a 5.8 release, so we built **v2.27 from source** and dropped it in as a project plugin (`<Project>/Plugins/CesiumForUnreal`) — which is why on that machine it's *not* a Fab download. If you're ever in that spot: `brew install nasm pkg-config cmake` → `git clone --recursive https://github.com/CesiumGS/cesium-unreal` → build `cesium-native` (CMake) → apply the UE-version compile fixes → build the plugin dylibs via UBT against a throwaway C++ host → copy into `<Project>/Plugins/`. Our build + the 5.8 patch live in `~/coding/cesium-build/` (`cesium-5.8-patches.diff`). **Most people will never need this — just install from Fab.**
