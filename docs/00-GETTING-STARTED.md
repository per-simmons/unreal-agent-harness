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
The MCP plugin is **engine-level** in 5.8 (`…/UE_5.8/Engine/Plugins/Experimental/ModelContextProtocol`), but **every project must turn it on + start the server.** A fresh project does NOT have it on. Full, copy-pasteable recipe: [`UNREAL-MCP-ENABLE.md`](UNREAL-MCP-ENABLE.md). In short:

1. In the project's **`.uproject`**, enable plugins: `ModelContextProtocol`, `AllToolsets`, `PythonScriptPlugin`.
   - `AllToolsets` is the aggregator that registers the full ~28-toolset palette. Without it you only get a useless `AgentSkillToolset`.
2. In **`Config/DefaultEngine.ini`** append:
   ```ini
   [/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
   ServerUrlPath=/mcp
   ServerPortNumber=8123
   bAutoStartServer=True

   [/Script/PythonScriptPlugin.PythonScriptPluginSettings]
   bRemoteExecution=False
   ```
   - `bAutoStartServer` defaults **false** — enabling the plugin alone never starts the server.
   - Port **8000** is often taken (WhisperFlow dictation, etc.) → we use **8123**.
   - `bRemoteExecution=False` — a `True` value makes a multicast listener **hang the editor on boot** (macOS). Keep it False.
3. **Fully quit + reopen** the editor (it reads this at startup; quitting also stops it clobbering Saved config). A C++ sample may prompt **"missing modules — rebuild?"** → **Yes** (that's the project's code, not the plugin).

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
