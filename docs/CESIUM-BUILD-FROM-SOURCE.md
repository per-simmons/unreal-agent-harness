# Building Cesium for Unreal from source — UE 5.8, macOS (Apple Silicon)

> **When you need this:** Cesium for Unreal has **no UE 5.8 build on Fab** ("You cannot
> install this plugin as there are no compatible engines installed"). On any UE version
> with no matching Fab release, building from source is the **only** path. For supported
> versions (≤5.7 today), use the one-click Fab install in [CESIUM-SETUP.md](CESIUM-SETUP.md)
> instead — this whole document is unnecessary.

This is an **exact, copy-pasteable** recipe reconstructed from the real build at
`~/coding/cesium-build/` (logs in `~/coding/cesium-build/logs/`). It builds **Cesium for
Unreal v2.27.0** against **UE 5.8** and installs it as a project plugin. An agent can run
this top to bottom. Every command is the real one that was run; paths and flags are literal.

Total wall-clock on an M4 Max / 64 GB: ~25–35 min (cesium-native + vcpkg deps dominate).

---

## 0. Prerequisites (verify before starting)

```bash
# UE 5.8 installed here (the engine root every command references):
ls "/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh"

# Xcode command-line toolchain present (build used Apple clang 17 / Xcode clang 19.1.5):
xcode-select -p
clang++ --version
```

Install the three native-build deps:

```bash
brew install nasm pkg-config cmake
```

- `nasm` — assembler some vcpkg ports need.
- `pkg-config` — dependency discovery during the cesium-native CMake build.
- `cmake` — drives the cesium-native build (the build used the `Unix Makefiles` generator).

> The build does **not** use a system vcpkg. cesium-unreal vendors its own via **ezvcpkg**,
> which clones microsoft/vcpkg into `~/.ezvcpkg/<commit>/` automatically during configure.
> Expect `~/.ezvcpkg/` to fill with ~40 built packages (abseil, draco, openssl, ktx, spz, …).

---

## 1. Clone the source (recursive, pinned to the v2.27.0 tag)

```bash
mkdir -p ~/coding/cesium-build
cd ~/coding/cesium-build
git clone --recursive https://github.com/CesiumGS/cesium-unreal
cd cesium-unreal
git checkout v2.27.0          # commit c1214cbe, .uplugin VersionName 2.27.0
git submodule update --init --recursive
```

**Produces:** `~/coding/cesium-build/cesium-unreal/` with `extern/cesium-native/` (the C++
library) and `extern/vcpkg-overlays/` populated.
**Verify:** `git -C ~/coding/cesium-build/cesium-unreal describe --tags` prints `v2.27.0`.

> The `.uplugin` ships `"EngineVersion": "5.5.0"` — that is fine; we bump it to `5.8.0` at
> install time in step 7. The source-level v2.27.0 code is what we patch for 5.8.

---

## 2. Apply the UE-5.8 compile patches

The v2.27.0 source does **not** compile against UE 5.8 unmodified. Apply the saved patch
set (8 fixes across 6 files):

```bash
cd ~/coding/cesium-build/cesium-unreal
git apply ~/coding/cesium-build/cesium-5.8-patches.diff
git status        # should show 6 modified files, no rejects
```

If `cesium-5.8-patches.diff` is not present (fresh machine), the patch reproduces these
fixes — apply them by hand if `git apply` fails:

| # | File | UE-5.8 break | Fix |
|---|------|--------------|-----|
| 1 | `Source/CesiumRuntime/CesiumRuntime.Build.cs` | UE 5.8 promotes `-Wunreachable-code-break` / `-Wunreachable-code-loop-increment` to errors via `-Werror`; they fire on harmless `return X; break;` switch cases. | Add a `#if UE_5_8_OR_LATER` block setting `CppCompileWarningSettings.UnreachableCodeWarningLevel = WarningLevel.Off;`. **(Without this, the very first editor build also fails with "HostProjEditor modifies the values of properties … has build products in common with UnrealEditor" — see Gotcha A.)** |
| 2 | `Source/CesiumRuntime/Private/CesiumTextureResource.cpp` | UE 5.8 **removed `FRHIResourceCreateInfo`**. | Drop the struct; pass the debug name directly: `const TCHAR* createDebugName = *debugName;` and feed it to `FRHITextureCreateDesc::Create2D/Create3D(createDebugName)`. |
| 3 | `Source/CesiumRuntime/Private/CesiumViewExtension.h` | UE 5.8 **moved the full `FSceneViewState` definition** out of `ScenePrivate.h`. | `#include "SceneViewState.h"`. |
| 4–8 | `CesiumFeaturesMetadataViewer.cpp`, `CesiumVoxelShaderBuilder.cpp`, `Cesium3DTileset.cpp`, `CesiumGltfComponent.cpp` | UE 5.8's **format-string sanitizer** (`FormatStringSanErrors.inl`) hard-errors on `UE_LOG`/`TEXT("… {} …")` braces and on arg-count mismatches: `static assertion failed … missing format specifier`. | Replace `{}` with the right specifier (`%s`/`%d`), add the missing trailing args (`UTF8_TO_TCHAR(...)`), and remove an extra arg in the `Cesium3DTileset` "World Bounds Checks" log that had no specifier. |

> These format-string fixes were found **iteratively** — the editor build failed three
> times in a row (`editor-build2/3/4.log`) on successive `FormatStringSan` assertions
> before all sites were patched. The committed diff already contains every one.

**Verify:** `git diff --stat` lists exactly these 6 files.

---

## 3. Build cesium-native (the C++ library) with CMake

cesium-unreal's `extern/CMakeLists.txt` is the driver. It requires `UNREAL_ENGINE_ROOT`,
hard-codes the install prefix to `../Source/ThirdParty`, and lays libs into
`lib/<System>-<Processor>-Release` = `Darwin-arm64-Release`.

```bash
cd ~/coding/cesium-build/cesium-unreal/extern
export UNREAL_ENGINE_ROOT="/Users/Shared/Epic Games/UE_5.8"

# Configure (generator: Unix Makefiles). This runs ezvcpkg, which clones vcpkg into
# ~/.ezvcpkg and builds ~40 packages — slow on first run (~3 min configure + deps).
cmake -B build -S . -G "Unix Makefiles" -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  2>&1 | tee ~/coding/cesium-build/logs/configure.log

# Build + install the static libs into ../Source/ThirdParty
cmake --build build --config Release --target install \
  2>&1 | tee ~/coding/cesium-build/logs/native-build.log
```

> **Do NOT use `extern/build-helper.sh` or `extern/CMakeSettings.json`** — those are the
> repo's stock **Windows** files (Visual Studio 2019 generator / Ninja+msvc). On macOS use
> the `Unix Makefiles` invocation above. The real build's `CMakeCache.txt` confirms
> `CMAKE_GENERATOR:INTERNAL=Unix Makefiles`, `CMAKE_BUILD_TYPE=RelWithDebInfo`, install
> prefix resolving to `…/cesium-unreal/Source/ThirdParty`.

**Produces:**
`~/coding/cesium-build/cesium-unreal/Source/ThirdParty/lib/Darwin-arm64-Release/` — ~140
`.a` files (`libCesiumUtility.a`, `libCesium3DTiles.a`, `libCesiumGltfReader.a`, …) plus
`Source/ThirdParty/include/` and `Source/ThirdParty/share/`.

**Verify:**
```bash
ls ~/coding/cesium-build/cesium-unreal/Source/ThirdParty/lib/Darwin-arm64-Release/ | wc -l   # ~140
```

> **macOS-version linker warnings are expected and harmless:** the libs are built for
> macOS 26.0 but linked against the 14.0 deployment target — `ld: warning: object file …
> was built for newer 'macOS' version (26.0) than being linked (14.0)`. The final build
> succeeds anyway.

---

## 4. Add the `Darwin-universal` → `arm64` symlinks (Apple Silicon)

UBT's plugin build (UE 5.8 on Apple Silicon) looks for `Darwin-universal-Release` /
`Darwin-universal-Debug` lib dirs, but the CMake install produced only
`Darwin-arm64-Release`. Symlink the expected names at it:

```bash
cd ~/coding/cesium-build/cesium-unreal/Source/ThirdParty/lib
ln -s ./Darwin-arm64-Release Darwin-universal-Release
ln -s ./Darwin-arm64-Release Darwin-universal-Debug
```

> **Direction matters — this is the opposite of how it's sometimes described.** You create
> `Darwin-universal-*` pointing **at** the real `Darwin-arm64-Release` output (not the
> reverse). And both `-Release` **and** `-Debug` map to the single `arm64-Release` build
> (we only built Release).

**Verify:**
```bash
ls -la ~/coding/cesium-build/cesium-unreal/Source/ThirdParty/lib/
# Darwin-universal-Release -> ./Darwin-arm64-Release
# Darwin-universal-Debug   -> ./Darwin-arm64-Release
```

---

## 5. Create the throwaway C++ host project

The plugin's **editor dylibs** are built by running **UBT against a real C++ host
project** whose `Plugins/CesiumForUnreal` is a symlink back to the source clone. (The
official `RunUAT BuildPlugin -NoHostPlatform` path was tried and **failed** — see Gotcha
B.) Recreate the host project exactly:

```bash
mkdir -p ~/coding/cesium-build/hostproj/Source/HostProj
mkdir -p ~/coding/cesium-build/hostproj/Plugins

# Symlink the plugin source INTO the host project's Plugins/
ln -s ~/coding/cesium-build/cesium-unreal \
      ~/coding/cesium-build/hostproj/Plugins/CesiumForUnreal
```

Write the four scaffold files **exactly** as below.

**`~/coding/cesium-build/hostproj/HostProj.uproject`**
```json
{
	"FileVersion": 3,
	"EngineAssociation": "5.8",
	"Category": "",
	"Description": "",
	"Modules": [
		{ "Name": "HostProj", "Type": "Runtime", "LoadingPhase": "Default" }
	],
	"Plugins": [
		{ "Name": "CesiumForUnreal", "Enabled": true }
	]
}
```

**`~/coding/cesium-build/hostproj/Source/HostProj.Target.cs`**
```csharp
using UnrealBuildTool;
public class HostProjTarget : TargetRules {
	public HostProjTarget(TargetInfo Target) : base(Target) {
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("HostProj");
	}
}
```

**`~/coding/cesium-build/hostproj/Source/HostProjEditor.Target.cs`**
```csharp
using UnrealBuildTool;
public class HostProjEditorTarget : TargetRules {
	public HostProjEditorTarget(TargetInfo Target) : base(Target) {
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("HostProj");
	}
}
```

**`~/coding/cesium-build/hostproj/Source/HostProj/HostProj.Build.cs`**
```csharp
using UnrealBuildTool;
public class HostProj : ModuleRules {
	public HostProj(ReadOnlyTargetRules Target) : base(Target) {
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
	}
}
```

**`~/coding/cesium-build/hostproj/Source/HostProj/HostProj.cpp`**
```cpp
#include "Modules/ModuleManager.h"
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, HostProj, "HostProj");
```

**Verify:**
```bash
ls -la ~/coding/cesium-build/hostproj/Plugins/CesiumForUnreal   # -> …/cesium-unreal
```

---

## 6. Build the editor plugin dylibs via UBT

Build the host project's **Editor** target. Because `CesiumForUnreal` is enabled and
symlinked in, UBT compiles the plugin's `CesiumRuntime` + `CesiumEditor` modules and emits
their editor dylibs into the (symlinked) source tree's `Binaries/Mac/`.

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" \
  HostProjEditor Mac Development \
  -Project="/Users/patsimmons/coding/cesium-build/hostproj/HostProj.uproject" \
  2>&1 | tee ~/coding/cesium-build/logs/editor-build.log
```

Wait for `Result: Succeeded`. (In the original build, runs 2–4 failed on the
`FormatStringSan` errors until step 2's patches were complete; run 5 succeeded in ~22 s
once cesium-native was already built.)

**Produces** (in the symlinked source tree, which IS the plugin):
`~/coding/cesium-build/cesium-unreal/Binaries/Mac/`
- `libUnrealEditor-CesiumRuntime.dylib` (~33 MB)
- `libUnrealEditor-CesiumEditor.dylib` (~15 MB)
- `UnrealEditor.modules`

**Verify:**
```bash
ls -la ~/coding/cesium-build/cesium-unreal/Binaries/Mac/
grep -c "^Result: Succeeded" ~/coding/cesium-build/logs/editor-build.log   # 1
```

---

## 7. Install into the target project + enable it

Copy the **whole plugin folder** (source + `Content/` + `Config/` + the built
`Binaries/Mac/` + `Source/ThirdParty/`) into the real project's `Plugins/`, bump the
plugin's declared engine version to 5.8 so the editor will load it, then enable it in the
`.uproject`. Installing the full copy (not a symlink) means the project owns its own
`Source/` — which is what lets you later hot-rebuild a single module (see step 8).

```bash
TARGET="/Users/patsimmons/Documents/Unreal Projects/MyProject"   # <- your project
mkdir -p "$TARGET/Plugins"

# Copy the built plugin in (resolve the symlink to copy real files).
cp -R ~/coding/cesium-build/cesium-unreal/ "$TARGET/Plugins/CesiumForUnreal"

# Bump the plugin's EngineVersion 5.5.0 -> 5.8.0 so UE 5.8 accepts it.
cd "$TARGET/Plugins/CesiumForUnreal"
cp CesiumForUnreal.uplugin CesiumForUnreal.uplugin.bak
sed -i '' 's/"EngineVersion": "5.5.0"/"EngineVersion": "5.8.0"/' CesiumForUnreal.uplugin
```

Then enable it in `<TargetProject>/MyProject.uproject` — add to the `"Plugins"` array:

```json
{ "Name": "CesiumForUnreal", "Enabled": true }
```

**Verify:**
```bash
ls "$TARGET/Plugins/CesiumForUnreal/Binaries/Mac/"        # the two dylibs present
grep EngineVersion "$TARGET/Plugins/CesiumForUnreal/CesiumForUnreal.uplugin"   # 5.8.0
```

Launch the editor (`~/coding/unreal-agent-harness/ue_launch.sh`). Cesium's UI appears
under **Window → Cesium**. From here the agent builds scenes over the MCP — see
[NYC-CESIUM-WALKTHROUGH.md](NYC-CESIUM-WALKTHROUGH.md).

---

## 8. Post-build: kill the Gaussian-splat subsystem tick crash

A from-source Cesium hard-crashes on PIE start/stop with
`Assertion failed: Index >= 0 [UObjectArray.h:1083]` inside
`UCesiumGaussianSplatSubsystem::Tick`. There is **no cvar/config flag** for it. Two-line
source patch + rebuild **only** `CesiumRuntime`:

In `…/Plugins/CesiumForUnreal/Source/CesiumRuntime/Private/CesiumGaussianSplatSubsystem.cpp`,
make `GetTickableTickType()` return `ETickableTickType::Never` (and optionally `return;` at
the top of `Tick`). Then rebuild via the project's editor target:

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" \
  MyProjectEditor Mac Development \
  -Project="/Users/patsimmons/Documents/Unreal Projects/MyProject/MyProject.uproject"
```

(If `MyProject` has no C++ target, rebuild `HostProjEditor` as in step 6 and copy the
fresh `libUnrealEditor-CesiumRuntime-*.dylib` into the project plugin's `Binaries/Mac/`.)

Full detail + verification: [cesium-splat-subsystem-disable.md](cesium-splat-subsystem-disable.md).

---

## Gotchas (the ones that actually bit us)

**A. First editor build fails: "HostProjEditor modifies the values of properties … has
build products in common with UnrealEditor."**
Root cause: UE 5.8 defaults several warning levels to `Error`
(`UnreachableCodeWarningLevel`, `UndefinedIdentifierWarningLevel`, `ReturnTypeWarningLevel`,
`DanglingWarningLevel`). The unpatched `CesiumRuntime.Build.cs` turns one **off**, which
mutates the *shared* build environment — UBT refuses because the Editor target shares build
products with `UnrealEditor`. **Fix = patch #1 in step 2** (gate the warning override behind
`#if UE_5_8_OR_LATER` so it's applied cleanly). Do **not** "fix" this by setting
`BuildEnvironment = TargetBuildEnvironment.Unique` — the final working targets do **not**
use `Unique`; the patch is the correct fix.

**B. `RunUAT BuildPlugin -NoHostPlatform` does NOT work on 5.8.** The official packaging
path
(`dotnet AutomationTool.dll BuildPlugin -Plugin=…/CesiumForUnreal.uplugin -Package=… -TargetPlatforms=Mac -NoHostPlatform`)
was tried (`logs/buildplugin*.log`) and **failed with ExitCode 6** — it tries to build
`arm64+x64` (`-architecture=arm64+x64`, "Compile [Intel] …") and chokes on the 5.8 source
errors / deprecated RHI APIs. Use the **host-project UBT** path in steps 5–6 instead (Mac
arm64 editor only).

**C. cesium-native install dir naming.** CMake installs to `Source/ThirdParty/lib/Darwin-arm64-Release`,
but UBT expects `Darwin-universal-Release`. Step 4's symlinks bridge it. Skip them and the
plugin link step fails to find the static libs.

**D. Use `Unix Makefiles`, not the repo's stock Windows CMake files.** `build-helper.sh`
(`Visual Studio 16 2019`) and `CMakeSettings.json` (Ninja + msvc) are Windows-only. Drive
the macOS build with the explicit `cmake -B build -S . -G "Unix Makefiles"` in step 3.

**E. macOS 26 vs 14 linker warnings are noise.** `ld: warning: object file … built for
newer 'macOS' version (26.0) than being linked (14.0)` appears throughout — the build
still succeeds.

---

## File map (the real artifacts this was reconstructed from)

- `~/coding/cesium-build/cesium-unreal/` — v2.27.0 source clone (patched).
- `~/coding/cesium-build/cesium-5.8-patches.diff` — the 8-fix UE-5.8 patch.
- `~/coding/cesium-build/hostproj/` — throwaway C++ host project (Plugins/CesiumForUnreal → source).
- `~/coding/cesium-build/logs/` — `configure.log`, `native-build.log`, `buildplugin*.log`
  (the failed `-NoHostPlatform` attempts), `editor-build*.log` (build 5 = success).
- `~/Documents/Unreal Projects/MyProject/Plugins/CesiumForUnreal/` — the installed plugin
  (full copy, `.uplugin` EngineVersion bumped to 5.8.0, splat patch applied).
