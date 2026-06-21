# 00 · Getting Started — from zero to "the agent is driving Unreal"

> The single onboarding path. Do these in order. The AI tooling is real but raw — most of the pain is plumbing, and it's all here.

## 0. Prerequisites
| Need | Notes |
|---|---|
| **Machine** | macOS Apple Silicon (**M2 or newer** for Nanite) or Windows/DX12. 32 GB+ RAM; heavy scenes want 64 GB. |
| **Disk** | Fast SSD. Real projects are big (City Sample ≈ 90 GB installed). An external **NVMe SSD** (e.g. Samsung T7 Shield) works well. |
| **Unreal Engine 5.8** | via the Epic Games Launcher. (Launcher ≠ Engine ≠ Editor — three separate things.) |
| **Claude Code** | the agent that drives it. |
| **Python 3** | for `ue_qa.py`. `imagemagick` for `refdiff`. **Blender** only if you run the modeling jobs. |

## 1. Install Unreal Engine 5.8
Epic Games Launcher → Unreal Engine → Library → install **5.8**.

**macOS gotcha — Metal Toolchain error on first launch.** Xcode 26 ships the Metal compiler separately:
```bash
xcodebuild -downloadComponent MetalToolchain
```

## 2. Get a project
Either your own blank project, or a sample (e.g. Fab → "Create project" → City Sample — note it's ~90 GB and a *Complete Project*, not a level you add). The agent drives whatever project is **currently open**.

## 3. Enable the Unreal MCP (so Claude can connect)
The MCP server is **per-project** — every project must enable the plugin once and start its own server. A fresh project does NOT have it on. Full recipe (Epic's official method): [`UNREAL-MCP-ENABLE.md`](UNREAL-MCP-ENABLE.md). In short:

1. **Edit → Plugins** → search **"Unreal MCP"** → **Enabled** (auto-enables Toolset Registry) → restart. Also enable **AllToolsets** + **PythonScriptPlugin** for the full building palette (without AllToolsets you get a minimal, useless toolset).
2. **Start the server** — easiest, no restart: open the console (**backtick** `` ` ``) and run:
   ```
   ModelContextProtocol.StartServer 8123
   ```
   For every-launch auto-start: **Edit → Editor Preferences → General → Model Context Protocol → Auto Start Server** (set Port 8123). This is an Editor *Preference* (per-user config), NOT `DefaultEngine.ini`.
3. **Generate the client config** (console): `ModelContextProtocol.GenerateClientConfig ClaudeCode` → writes `.mcp.json` to the project root; launch Claude Code from there.

## 4. Connect Claude Code
With the project open and the server running, in Claude Code run `/mcp` to connect to `http://127.0.0.1:8123/mcp`.

**Verify:**
```
mcp__unreal__call_tool  →  SceneTools.get_current_level
```
Returns your level path = connected. `"Unable to connect"` = server not up → re-check the plugin is enabled + the editor was *fully* restarted ([Troubleshooting](TROUBLESHOOTING.md)).

## 5. Clone the harness + Python deps
```bash
git clone <this repo> unreal-agent-harness && cd unreal-agent-harness
python3 -c "import sys; print(sys.version)"   # 3.x
brew install imagemagick                       # for ue_qa.py refdiff (optional)
```

## 6. First build (smoke test the loop)
Ask the agent to:
1. `SceneTools.add_to_scene_from_asset` a cube,
2. `EditorAppToolset.CaptureViewport`,
3. `python3 ue_qa.py decode --name smoke` → Read `/tmp/ue_qa/smoke.png`.

If you see the cube, the loop works. Now go to the [docs index](README.md) for recipes (lighting, materials, PCG, characters) or the [main README](../README.md) for the full loop.

## Discovering what the agent can do
```
mcp__unreal__list_toolsets                     # all ~28 toolsets
mcp__unreal__describe_toolset <toolset_name>   # exact tools + params for one
```
Key toolsets: `SceneTools` (place/find/trace actors, load levels, camera), `StaticMeshTools` (incl. `import_file`), `MaterialTools`, `ObjectTools` (get/set/list_properties — **always confirm property names with `list_properties` first**), `ActorTools`, `EditorAppToolset` (camera + `CaptureViewport` + PIE), `LogsToolset`, `PCGToolset`, `ProgrammaticToolset` (batch many calls in one sandboxed script).
