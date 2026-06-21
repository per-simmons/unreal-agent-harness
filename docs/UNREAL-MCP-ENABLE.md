# Enabling the Unreal MCP in a NEW project (so Claude can drive it)

> The Unreal MCP plugin is **engine-level** (`/Users/Shared/Epic Games/UE_5.8/Engine/Plugins/
> Experimental/ModelContextProtocol`), so it's available to every 5.8 project — but each project
> must **enable it + turn on the auto-start server**. A fresh project (e.g. a Fab "Create
> project" like City Sample) does NOT have it on by default. This is the exact recipe.
> First applied 2026-06-20 to `futuristiccitysample` (the City Sample project on the T7 SSD).

## What "connected" requires
1. Plugins enabled in the project's `.uproject`: **ModelContextProtocol**, **AllToolsets**,
   **PythonScriptPlugin** (Python is usually already on).
2. The MCP HTTP server set to auto-start on **port 8123**, path **`/mcp`**.
3. `bRemoteExecution=False` (a True value makes a multicast listener hang macOS editor boot —
   learned the hard way; keep it False).
4. Editor restarted so it loads the plugins + reads the config, then Claude Code `/mcp` reconnect.

## Edit 1 — `<Project>/<Project>.uproject` → add to the `"Plugins"` array
```json
{ "Name": "ModelContextProtocol", "Enabled": true },
{ "Name": "AllToolsets", "Enabled": true },
{ "Name": "PythonScriptPlugin", "Enabled": true }
```

## Edit 2 — `<Project>/Config/DefaultEngine.ini` → append
> Put it in DefaultEngine.ini (project source config), NOT Saved/Config/.../
> EditorPerProjectUserSettings.ini — the editor rewrites the Saved user config on exit and
> would clobber it. DefaultEngine.ini is read at startup and not rewritten on quit.
```ini
[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
ServerUrlPath=/mcp
ServerPortNumber=8123
bAutoStartServer=True

[/Script/PythonScriptPlugin.PythonScriptPluginSettings]
bRemoteExecution=False
RemoteExecutionMulticastTtl=0
```

## Then (the human steps the MCP can't do)
1. **Fully quit** the Unreal editor for that project (so it picks up the new plugins + config).
2. **Reopen** the project. A C++ sample (like City Sample) may prompt **"missing modules — rebuild?"**
   → click **Yes** (that's the project's own code compiling, unrelated to these plugin edits).
   First open also recompiles shaders — let it finish.
3. In Claude Code, run **`/mcp`** to reconnect. Verify with a read-only call, e.g.
   `SceneTools.get_current_level`. "Unable to connect" = server not up → confirm the plugin is
   enabled (Edit → Plugins → "Model Context Protocol") + the editor was fully restarted.

## Gotchas
- Only ONE editor can bind port 8123. Switching projects kills the previous project's MCP
  server; you reconnect to whichever project is now open.
- The plugins are prebuilt engine plugins → enabling them does NOT force a project rebuild;
  any rebuild prompt is the project's own C++ modules.
- If `get_current_level` returns the wrong project, you're connected to a different editor
  instance — quit the stray one.
