# Enabling the Unreal MCP in a project (so Claude can drive it)

> The MCP server is **per-project** — it is not a global Unreal setting. Every project you open
> must enable the plugin once and start its server. A fresh project (e.g. a Fab "Create project"
> like City Sample) does NOT have it on by default.
> Source: Epic's official docs — https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor

---

## ✅ The official way (do this — it's what your audience should follow)

### 1. Enable the plugin (one-time per project, needs a restart)
1. **Edit → Plugins**
2. Search **"Unreal MCP"** → check **Enabled** (this auto-enables the dependent **Toolset Registry** plugin)
3. Restart the editor when prompted.

> For the full *building* toolset palette (SceneTools, StaticMeshTools, MaterialTools, PCGToolset, …),
> also enable **AllToolsets** + **PythonScriptPlugin** in Plugins. Without AllToolsets you only get a
> minimal toolset and can't actually build.

> **A note on the port (read this first).** The default MCP port is **8000**. **Most people can
> leave it at 8000.** Change it only if something else already uses 8000 — which is common (other
> Unreal projects, dictation apps like WhisperFlow, etc.). On this machine 8000 was taken, so we
> use **8123** everywhere below. If 8000 is free for you, keep the default and ignore the 8123s.

### 2. Start the server
**Manual (instant, no restart) — also the cleanest thing to show on camera:**
1. Press the **backtick** key `` ` `` to open the editor **console** (bottom of the editor).
2. Run:
   ```
   ModelContextProtocol.StartServer 8123
   ```
   (Omit the number to use the default port 8000. We use **8123** because 8000 is often taken,
   e.g. by dictation apps.)

**Auto-start (every launch) — the real location:**
- **Edit → Editor Preferences → General → Model Context Protocol → enable "Auto Start Server"**
  (and set the **Port** to 8123 + URL path `/mcp` here).
- This is a **per-user Editor Preference** (written to `Saved/Config/<Platform>Editor/
  EditorPerProjectUserSettings.ini`), NOT `DefaultEngine.ini`. Editing DefaultEngine.ini does
  nothing for auto-start — use this panel (or edit that user .ini while the editor is closed).

### 3. Connect your AI client
In the editor console:
```
ModelContextProtocol.GenerateClientConfig ClaudeCode
```
(supported: `ClaudeCode`, `Cursor`, `VSCode`, `Gemini`, `Codex`, `All`). This writes a `.mcp.json`
to the **project root**. Launch your agent CLI from that root. In Claude Code, `/mcp` connects to
`http://127.0.0.1:8123/mcp`.

**Verify:** `mcp__unreal__call_tool → SceneTools.get_current_level` returns your level.
`"Unable to connect"` = the server isn't started → re-run `ModelContextProtocol.StartServer 8123`.

---

## Quick reference — console commands
```
ModelContextProtocol.StartServer 8123          # start the server now (no restart)
ModelContextProtocol.StopServer                # stop it
ModelContextProtocol.GenerateClientConfig ClaudeCode   # write .mcp.json to project root
```

---

## Optional — pre-bake it via config files (for automation/scripting)
If you're provisioning a project without clicking through the UI, you can set it on disk. Note the
**scope split** (this is the gotcha that bit us):

- **`<Project>/<Project>.uproject`** → enable the plugins (this part IS project config):
  ```json
  { "Name": "ModelContextProtocol", "Enabled": true },
  { "Name": "AllToolsets", "Enabled": true },
  { "Name": "PythonScriptPlugin", "Enabled": true }
  ```
- **Auto-start lives in the per-user file**, not DefaultEngine.ini — edit it **with the editor closed**
  (the editor rewrites it on quit): `<Project>/Saved/Config/<Platform>Editor/EditorPerProjectUserSettings.ini`
  ```ini
  [/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
  ServerUrlPath=/mcp
  ServerPortNumber=8123
  bAutoStartServer=True
  ```
- Keep remote execution off (a True value can hang the editor on macOS boot) — in DefaultEngine.ini:
  ```ini
  [/Script/PythonScriptPlugin.PythonScriptPluginSettings]
  bRemoteExecution=False
  ```

> **Easiest path remains the UI above.** The console `StartServer` command needs no restart and is
> the most reliable thing to demo.

## Gotchas
- **Per-project, every time.** Switching projects kills the previous project's server; only one
  editor can bind the port. Start the server in whichever project is now open.
- **"Unable to connect"** almost always = server not started in the current project → run
  `ModelContextProtocol.StartServer 8123`.
- **Only a minimal toolset shows** → enable **AllToolsets**.
- The plugins are prebuilt engine plugins → enabling them doesn't force a project rebuild; any
  "rebuild modules?" prompt is the project's own C++.
