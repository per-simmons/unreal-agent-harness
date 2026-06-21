# Disabling the Cesium Gaussian-Splat Subsystem (UE 5.8, from-source build)

## TL;DR

There is **no console variable and no config flag** that disables
`UCesiumGaussianSplatSubsystem` or its `Tick`. The subsystem has zero cvars in the
entire `CesiumRuntime` module. The cleanest reliable fix is a **2-line source patch**
that early-outs `Tick()` and refuses to register the tickable, then **rebuild only the
`CesiumRuntime` module** (no full plugin repackage). Patch is applied directly in the
plugin copy the project actually loads:
`~/Documents/Unreal Projects/MyProject/Plugins/CesiumForUnreal/` (it is a full copy with
its own `Source/`, not a symlink).

---

## 1. Is there a cvar / config flag? — No.

Source: `cesium-unreal/Source/CesiumRuntime/Private/CesiumGaussianSplatSubsystem.{h,cpp}`

- `UCesiumGaussianSplatSubsystem` is a `UEngineSubsystem` + `FTickableGameObject`.
  Engine subsystems are auto-created at engine startup; there is **no
  `ShouldCreateSubsystem()` override**, so it always exists.
- Tick gating is `IsTickable()` → returns `_isTickEnabled`, and
  `GetTickableTickType()` → `ETickableTickType::Always`.
- `_isTickEnabled` is set `true` in `Initialize()` (used purely as a "this is the real
  singleton, not the CDO" marker) and only set `false` in `Deinitialize()`. Nothing
  reads any cvar or setting.
- `grep -rE "TAutoConsoleVariable|ConsoleVariable"` across the whole `CesiumRuntime`
  module returns **0 hits**. The splat files (`CesiumGaussianSplat*`,
  `CesiumGltfGaussianSplat*`) define no cvar.

So a `DefaultEngine.ini [SystemSettings]` / `[ConsoleVariables]` line cannot turn it off.
There is nothing to set.

## 2. What gates the Tick? What makes it early-out?

`Tick(float)` (CesiumGaussianSplatSubsystem.cpp:226) early-returns only when:
- `_isTickEnabled` is false (i.e. the CDO, or post-Deinitialize), OR
- `GetPrimaryWorld()` is invalid (then it also destroys the actor + resets), OR
- `!FApp::CanEverRender()` or the world is a dedicated server.

Crucially it does **NOT** gate on "are there any splat tilesets?". Even with **zero**
registered splat components it runs every frame, calls `GetPrimaryWorld()`, and in
`initializeForWorld()` (line 149) it **spawns `CesiumGaussianSplatSystemActor`** and a
Niagara system into the primary world. That is why you see the actor in every level even
though you only use Google Photorealistic 3D Tiles.

## 3. The UObjectArray.h:1083 crash

`Assertion failed: Index >= 0 [UObjectArray.h:1083]` inside
`UCesiumGaussianSplatSubsystem::Tick` is a stale `UObject` index — the subsystem is
dereferencing/indexing an object whose `InternalIndex` is `-1` (already destroyed /
unhashed). The most likely sources inside this Tick path:

- `GetPrimaryWorld()` / `_pLastCreatedWorld`: on PIE start/stop and editor-world
  swaps the primary world changes and the previously-spawned `_pNiagaraActor` /
  `_pNiagaraComponent` become stale; the code re-enters `initializeForWorld` /
  touches the Niagara component.
- `getDataInterface()` → `UNiagaraFunctionLibrary::GetDataInterface(...)` on a
  Niagara component that was GC'd, or the Niagara `GaussianSplatSystem` asset failing
  to load (the build is from source; the cooked/loaded Niagara content for the splat
  system may be missing or version-mismatched against UE 5.8), leaving the path
  operating on partially-constructed/destroyed objects.

It is **not** specific to using a splat tileset (we use none) — it fires from the
unconditional per-frame initialization the Tick does, and is aggravated by
PIE/editor-world teardown. The reliable conclusion: the subsystem should not be doing
any of this when we never use splats. Disable the Tick entirely.

## 4. The fix — minimal source patch + rebuild CesiumRuntime only

No cvar exists, so a patch is required. Two complementary one-liners make the subsystem
inert and stop it registering as a tickable:

### Patch (file: `Source/CesiumRuntime/Private/CesiumGaussianSplatSubsystem.cpp`)

**a. Never register as a tickable** — change `GetTickableTickType()`:

```cpp
ETickableTickType UCesiumGaussianSplatSubsystem::GetTickableTickType() const {
  // DISABLED: we only use Google Photorealistic 3D Tiles, never Gaussian splats.
  // Returning Never keeps this subsystem from registering with the tickable
  // manager, so Tick() is never called (was crashing at UObjectArray.h:1083).
  return ETickableTickType::Never;
}
```

**b. Belt-and-suspenders early-out** — first line of `Tick()`:

```cpp
void UCesiumGaussianSplatSubsystem::Tick(float DeltaTime) {
  return; // DISABLED: Gaussian splats unused; avoids stale-UObject crash on tick.
  if (!this->_isTickEnabled) {
    ...
```

(a) alone is sufficient and is the clean fix — `ETickableTickType::Never` means the
tickable manager never adds it, so `Tick` is never invoked and no
`CesiumGaussianSplatSystemActor` / Niagara system is ever spawned. (b) is cheap
insurance. Leave `IsTickable()` / the rest untouched so the class still compiles and
`RegisterSplat`/`UnregisterSplat` remain valid no-ops in practice.

Apply the edit in the **project's** plugin copy (the one UE loads), which currently is
byte-identical to the build source:
`~/Documents/Unreal Projects/MyProject/Plugins/CesiumForUnreal/Source/CesiumRuntime/Private/CesiumGaussianSplatSubsystem.cpp`
(Optionally mirror the same edit in
`~/coding/cesium-build/cesium-unreal/Source/...` so a future repackage keeps it.)

### Rebuild — just the editor module, the way this build was already done

This Cesium was built from source. The editor dylibs (e.g.
`libUnrealEditor-CesiumRuntime-0003.dylib`) were produced by running **UBT against a
throwaway C++ host project** (`cesium-build/hostproj/`, whose `Plugins/CesiumForUnreal`
is a symlink to `cesium-build/cesium-unreal`). The recorded editor-build command was:

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" \
  HostProjEditor Mac Development \
  -Project="/Users/patsimmons/coding/cesium-build/hostproj/HostProj.uproject"
```

So the two reliable rebuild options:

**Option A (recommended, simplest): rebuild via the real project.**
Because `MyProject/Plugins/CesiumForUnreal` has full `Source/`, just edit the source
there and let UBT recompile the project's plugin module:

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" \
  MyProjectEditor Mac Development \
  -Project="/Users/patsimmons/Documents/Unreal Projects/MyProject/MyProject.uproject"
```

If `MyProject` has no C++ source/target, generate one (add an empty C++ class once in
the editor, or add a minimal `Source/` + `.Target.cs`) OR use Option B and copy the
resulting dylib in.

**Option B: rebuild in the cesium-build host project, then copy the dylib.**
Edit `cesium-build/cesium-unreal/Source/.../CesiumGaussianSplatSubsystem.cpp`, then:

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" \
  HostProjEditor Mac Development \
  -Project="/Users/patsimmons/coding/cesium-build/hostproj/HostProj.uproject"
# then copy the rebuilt CesiumRuntime editor dylib into the project plugin:
cp "/Users/patsimmons/coding/cesium-build/hostproj/Plugins/CesiumForUnreal/Binaries/Mac/"libUnrealEditor-CesiumRuntime-*.dylib \
   "/Users/patsimmons/Documents/Unreal Projects/MyProject/Plugins/CesiumForUnreal/Binaries/Mac/"
```

Either way you are rebuilding **only `CesiumRuntime`** (one `.cpp` changed) — not the
full `RunUAT BuildPlugin` repackage and not cesium-native. Quit the editor before
rebuilding; relaunch with `~/coding/unreal-agent-harness/ue_launch.sh`.

### Verify the fix
After rebuild + relaunch:
- No `CesiumGaussianSplatSystemActor` appears in the level (it was spawned from
  `initializeForWorld`, which now never runs).
- No more `UObjectArray.h:1083` crash from `UCesiumGaussianSplatSubsystem::Tick` —
  check with `~/coding/unreal-agent-harness/ue_crashlog.sh`.
- Google Photorealistic 3D Tiles (`Cesium3DTileset`) are unaffected — the splat
  subsystem is independent of regular tileset rendering.

---

## File references
- `cesium-unreal/Source/CesiumRuntime/Private/CesiumGaussianSplatSubsystem.cpp:226` — `Tick`
- `…CesiumGaussianSplatSubsystem.cpp:273` — `GetTickableTickType` (the patch point)
- `…CesiumGaussianSplatSubsystem.cpp:149` — `initializeForWorld` (spawns the actor)
- `…CesiumGaussianSplatSubsystem.cpp:289` — `IsTickable`
- Project plugin (loaded by UE): `~/Documents/Unreal Projects/MyProject/Plugins/CesiumForUnreal/`
- Build source: `~/coding/cesium-build/cesium-unreal/`
- Host project for source rebuild: `~/coding/cesium-build/hostproj/HostProj.uproject`
