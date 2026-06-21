# ProgrammaticToolset capabilities — can it call a UFUNCTION on an actor?

**Verdict: NO.** The official Unreal MCP plugin's `execute_tool_script` (ProgrammaticToolset)
**cannot** eval arbitrary `unreal` Python and **cannot** call a UFUNCTION/method on an actor.
It is a restricted orchestration sandbox that can only invoke other *registered* toolset tools,
none of which expose a generic "call method X on object Y" operation.

There is NO way through the stock plugin to trigger `set_origin_longitude_latitude_height(...)`
or `RefreshTileset()` on a live Cesium actor. (A separate C++/Blueprint extension path exists —
see "The one escape hatch" — but it requires authoring + compiling your own UFUNCTION library
plugin, not a runtime payload.)

---

## Source of truth

Engine: `UE_5.8`, official "Unreal MCP" = `ModelContextProtocol` plugin.

- Sandbox: `…/Experimental/Toolsets/EditorToolset/Content/Python/editor_toolset/toolsets/programmatic.py`
- Registered toolsets: `…/EditorToolset/Content/Python/editor_toolset/toolsets/__init__.py`
- C++ UFUNCTION tool path: `…/ModelContextProtocol/Source/ModelContextProtocolEngine/Private/ModelContextProtocolToolLibrary.cpp`

---

## Why it can't (the sandbox internals)

`execute_tool_script` runs the script via `exec()` with a **hand-built `__builtins__`**
(`programmatic.py` `__sandboxed_exec`, ~line 698). The globals given to the script are ONLY:

```python
globals_dict = {"__builtins__": {
    **_SAFE_BUILTINS,                 # builtins MINUS exec/eval/compile/input/breakpoint/help
    "execute_tool": self._tool_executor,   # the ONLY door to engine functionality
    "open": self._file_opener,        # read-only, project-dir-scoped
}}
```

Hard blocks:

1. **No `unreal` module.** It is never injected into the script globals. You cannot
   `import unreal`, `unreal.find_object(...)`, get an actor, or call any method on it.
2. **Import allowlist.** Only `json, math, datetime, copy, re, time` are importable
   (`_ALLOWED_MODULE_NAMES`). Enforced twice: AST walk at compile (`_validate_and_compile`,
   ~line 408) AND a `_safe_import` runtime `__import__` hook (~line 344). `unreal` is not on
   the list.
3. **No dynamic eval.** `exec`, `eval`, `compile` are stripped from `_SAFE_BUILTINS`
   (~line 372) — you can't bootstrap your way to the `unreal` module.
4. **`open()` is neutered** to read-only modes under the project dir (`_FileOpener`), so you
   can't write a `.py` and side-load it either.
5. The script must define `run() -> dict` and can only reach the engine through
   `execute_tool("<Toolset>.<Tool>", json_input)`.

So the script is a glue layer over **registered tools only**.

## And no registered tool calls a UFUNCTION

Registered toolsets (`__init__.py`): Actor, Asset, Blueprint, CurveTable, DataAsset,
DataTable, Material, MaterialInstance, **Object**, Primitive, Programmatic, Scene,
SkeletalMesh, StaticMesh, StringTable, Texture.

- `object.py` exposes only: `search_subclasses`, `get_class`, `list_properties`,
  `get_properties`, **`set_properties`**, `reset_properties`. Property get/set ONLY —
  no method invocation. (This is exactly the "plain property-set" surface we already have,
  and it does NOT trigger Cesium's georeference rebase, which fires inside a UFUNCTION.)
- A grep across every toolset for `call_method|call_function|invoke|console_command|exec|
  run_command` found NOTHING outside `programmatic.py`'s own internal `exec()` and the
  Blueprint-graph editor in `blueprint*.py` (which edits Blueprint node graphs, it does not
  invoke functions on a live actor at runtime).
- There is **no `EditorAppToolset`** in this registration. (The docstring example in
  `programmatic.py` references `EditorToolset.EditorAppToolset.GetSelectedActors`, but that
  toolset is not registered in this build — it's stale example text.) Even if present, it would
  not be a generic method-call tool; it would be its own fixed set of registered ops.
- **No console-command tool** is registered. The only `FAutoConsoleCommand`s in the plugin are
  operator-facing (`ModelContextProtocol.StartServer/StopServer/RefreshTools`,
  `GenerateClientConfig`) — not reachable from a script and not a `KismetSystemLibrary
  ExecuteConsoleCommand`-style tool.

---

## The one escape hatch (NOT a runtime payload)

`ModelContextProtocolToolLibrary.cpp` DOES call UFUNCTIONs via `ProcessEvent`
(line 308: `Library->ProcessEvent(Function, …)`). But this is the plugin's **extension point
for authoring your own tools**, not a generic dispatcher:

- You subclass `UModelContextProtocolToolLibrary` (a `UBlueprintFunctionLibrary`-style class)
  in C++ or Blueprint and mark UFUNCTIONs on it; `RegisterTools()` (line 68) iterates
  `TFieldIterator<UFunction>` over **your subclass** and registers each as an MCP tool
  (`bAutoRegisterTools`, line 27).
- `ProcessEvent` is then called on **that library CDO** with the function bound at registration
  time — it calls your specific pre-declared function, NOT an arbitrary method on an arbitrary
  actor chosen at call time.

To use it for Cesium you would have to **write + compile a plugin** with e.g.
`URefreshCesiumTool::RefreshTileset()` that internally finds the Cesium3DTileset and calls
`RefreshTileset()` on it, ship it, and restart the editor. That's a build-time C++ task, not an
`execute_tool_script` payload.

---

## Bottom line for the Cesium rebase

- `execute_tool_script` **cannot** be handed a payload that calls
  `set_origin_longitude_latitude_height(...)` or `RefreshTileset()`. There is no such payload —
  the sandbox has no `unreal` module and no registered method-call/console tool. (So the
  requested "exact payload (a)/(b)" does not exist.)
- `ObjectTools.set_properties` can set the georeference's Origin Longitude/Latitude/Height
  **properties**, but a property set does not run the UFUNCTION that performs Cesium's rebase —
  which is the whole reason this was being investigated.

### Practical alternatives (outside the stock ProgrammaticToolset)

1. **Author a tiny MCP tool plugin** via `UModelContextProtocolToolLibrary` (above): expose
   `SetGeoreferenceOrigin(lon, lat, height)` and `RefreshCesiumTileset()` UFUNCTIONs that do the
   real calls; they show up as native MCP tools (and become callable from `execute_tool` too).
   One-time C++ build + editor restart.
2. **Full Python remote-execution path** — UE's *separate* `PythonScriptPlugin` remote-execution
   endpoint (NOT this MCP sandbox) runs unrestricted `unreal` Python and can do
   `geo.set_origin_longitude_latitude_height(...)` / `tileset.refresh_tileset()` directly. If we
   can reach that endpoint, it's the fast route. (It is a different transport than the MCP server
   and is not gated by the ProgrammaticToolset allowlist.)
3. **Cesium's own georeference behavior** — setting the georeference origin through Cesium's
   intended API/actor usually triggers the rebase; the gap is specifically that an MCP
   *property-set* bypasses that. Options 1 or 2 close the gap.
