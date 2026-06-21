# Making the piloted 787 "feel like it's truly flying" — crash-safe MCP-only spec

> Investigation only — **no editor was modified** while writing this. Grounded in the LIVE MCP
> (`list_toolsets` / `describe_toolset` / `AssetTools.find_assets`, 2026-06-19) and the verified
> setup docs in this folder: `chase-cam-correct.md`, `cesium-splat-subsystem-disable.md`,
> `pie-qa-capture.md`, `flight-pawn-setup.md`.
>
> Constraint honored: MCP can only **set properties / add components / call registered tools** — no
> Blueprint authoring, no UFUNCTION, no graph logic. Everything below is property/component/tool
> calls. `ObjectTools.set_properties` `values` is always a **JSON STRING** (escaped), per the schema.

---

## TL;DR — recommended package, in priority order

1. **Contrails = two `NiagaraComponent`s on the pawn, system `/Niagara/DefaultAssets/Templates/Systems/FountainLightweight`**, one per engine, set via `NiagaraToolset_Component.SetSystem` (NOT by poking the `Asset` property). Biggest "jet in flight" cue, camera-safe, crash-safe. (Why not the ribbon system — see §1.)
2. **Camera lag = LEAVE the working pawn `Camera` as-is (no lag).** A bare `UCameraComponent` has no lag fields; getting lag means switching to the `ChaseBoom` SpringArm, which *re-frames* the shot and reintroduces the failure modes `chase-cam-correct.md` was written to kill. Only switch if Pat explicitly wants lag — exact, framing-matched SpringArm values are in §2(b) as the fallback.
3. **Cruise attitude = nose-up ~2.5° on `PlaneMesh`**: with the mesh at Yaw 180, the value that lifts the nose is **`RelativeRotation.Pitch = -2.5`** (negative, because Yaw 180 flips the sign of local pitch — confirm by capture, §3).

Do them in this order; QA after each with the PIE-capture method (§4). Steps 1 and 3 are independent and safe; step 2(b) is the only one that can change the verified framing, so it's last and optional.

---

## Asset investigation — what actually exists (verified via find_assets)

I searched the **whole project + all plugins/engine** (`folder_path:""`) for `smoke`, `trail`,
`vapor`, `contrail`, `exhaust`, `ribbon`, `fog`, `steam`, `jet`, and listed `/Game/Planes` and the
Niagara template folders. Findings:

- **The plane pack has NO particle FX.** `/Game/Planes/*` is entirely StaticMesh + Materials.
  `/Game/Planes/Exhaust_Cone` sounds promising but `get_asset_class` → **`Material`** (it's the
  engine-nozzle surface shader on the mesh, not a system). Nothing in `/Game/Planes` is usable as a trail.
- **No project-authored smoke/trail/vapor/contrail system exists anywhere.** Those name searches
  returned `[]` across the whole project.
- **The only ready-to-drop trail/smoke `NiagaraSystem`s are the Niagara plugin templates:**
  | Path | Class | Look |
  |---|---|---|
  | `/Niagara/DefaultAssets/Templates/Systems/FountainLightweight` | NiagaraSystem | continuous sprite stream — reads as a **vapor puff stream** trailing a moving emitter ✅ **recommended** |
  | `/Niagara/DefaultAssets/Templates/Systems/AttributeReaderTrails` | NiagaraSystem | ribbon trail — the *textbook* contrail shape, but it's a **behavior example** that reads particle attributes and assumes a specific authored setup; higher risk it renders nothing or odd without its companion emitter wiring |
  | `/Niagara/DefaultAssets/Templates/Systems/{RadialBurst,SimpleExplosion,DirectionalBurst,DirectionalBurstLightweight,MinimalLightweight}` | NiagaraSystem | one-shot bursts / minimal — not a continuous trail |
  | `/Niagara/DefaultAssets/Templates/CascadeConversion/CompletelyEmpty` | NiagaraSystem | empty stub, useless here |

**Decision:** use **`FountainLightweight`**. It is self-contained (spawns sprites continuously with
no dependency on attribute wiring), so dropped on a moving pawn it leaves a visible particle stream =
a credible contrail. `AttributeReaderTrails` *looks* more like a real contrail but is an example
asset; treat it as the **upgrade to try second** only if the fountain reads too "puffy" — swap the
`system` refPath in the same `SetSystem` call and re-QA. If neither reads well, the honest fallback
is in §1(C).

> Note: `FountainLightweight` emits its particles **upward in its own local frame** by default. On a
> fast-moving pawn the world motion drags the stream behind the plane, so it still trails — but if it
> looks like it's puffing *up* instead of *back*, rotate the **NiagaraComponent** (not the system) so
> its local "up" points along the plane's −X (tail) direction: `RelativeRotation.Pitch = -90` makes
> local +Z point along world... see §1 step 4 for the exact tweak + how to confirm by capture.

---

## 1. Contrails / vapor trails (the biggest cue) — exact MCP calls

### Crash-safety first (the one thing to verify before adding any Niagara)

The crash we patched (`cesium-splat-subsystem-disable.md`) was **specifically**
`UCesiumGaussianSplatSubsystem::Tick` spawning *its own internal* Niagara system + grabbing a data
interface on a stale/GC'd component across PIE teardown. The fix set
`GetTickableTickType() → ETickableTickType::Never`, so that subsystem **never ticks and never spawns
anything**. A **user-placed generic `UNiagaraComponent`** runs through the normal `FNiagaraWorldManager`
tick path and has **zero** relationship to `UCesiumGaussianSplatSubsystem`. Adding one does NOT
re-arm the splat subsystem (that path is dead at the tickable-registration level, not gated on
component count). **Conclusion: generic Niagara contrails are crash-safe with the current patched
plugin.** The only residual risk is the generic UE one — a Niagara component left ticking across a
PIE start/stop edit — which we avoid by editing on the **editor-world** pawn with PIE stopped (same
rule as every other edit here).

**Pre-flight verification (do this once, read-only):** confirm the patch is live and Niagara is sane
before adding components:
```jsonc
// a) confirm the splat subsystem is NOT spawning its actor (patch is live):
{ "toolset_name": "editor_toolset.toolsets.scene.SceneTools", "tool_name": "<list/find actors>",
  "comment": "scan the level outliner for 'CesiumGaussianSplatSystemActor' — it MUST be absent. If present, the patch isn't loaded; STOP, do not add Niagara, see cesium-splat-subsystem-disable.md." }
// b) confirm the chosen system asset loads:
{ "toolset_name": "editor_toolset.toolsets.asset.AssetTools", "tool_name": "load_asset",
  "arguments": { "asset_path": "/Niagara/DefaultAssets/Templates/Systems/FountainLightweight" } }
```
**Risk / QA:** if (a) finds the splat actor → abort (patch regressed). If (b) errors → the template
isn't cooked; fall back to `AttributeReaderTrails` or §1(C). Both are read-only, can't break the scene.

### Geometry — where the two emitters go (pawn-local frame)

The plane is `RelativeScale3D 0.01` (~60 m) with mesh `RelativeRotation Yaw 180` (nose = pawn **+X**).
So in the **pawn-local** frame the *visible* plane is mirrored by that Yaw 180, but **component
offsets we add to the pawn are in the raw pawn frame** (pawn +X = nose, +Y = right, +Z = up — the
camera at X −9000 sits behind the nose, confirming +X = nose). Engine/wing positions, pawn-local:

- 787 wingspan ≈ 60 m → wingtips ≈ ±30 m; **engines hang ~⅓ out on each wing ≈ ±10–11 m = ±1000–1100 cm** on the wingspan axis (pawn **Y**).
- Engines sit **forward of the wing root and below the wing**: ~ **+300 cm X** (toward nose) and ~ **−250 cm Z** (below centerline) is a good first guess for a centered-pivot mesh.
- **These assume the mesh pivot is centered.** Many Fab FBX pivot at the nose/wingtip. **Before trusting the numbers, read `StaticMeshTools.get_bounds` (or `ActorTools.get_actor_bounds`) on the plane** and offset from the real origin. If the pivot is at the nose, the engines are ~ −2700…−3000 cm X from pivot, not +300.

Left engine ≈ `{X: 300, Y: -1050, Z: -250}`, right engine ≈ `{X: 300, Y: 1050, Z: -250}` (pawn-local cm).
(Y sign: pawn +Y = pawn-local right. The Yaw-180 mesh flips visual left/right, so if the trails come
out the wrong wing in capture, swap the two Y signs — cosmetic, confirm by §4 capture.)

### The calls (per engine — do twice, `_L` then `_R`)

First get the pawn refPath (you already operate on `...DynamicPawn_C....`); call it `<PAWN>`.

**Step 1 — add the NiagaraComponent to the pawn:**
```jsonc
{ "toolset_name": "editor_toolset.toolsets.actor.ActorTools",
  "tool_name": "add_component",
  "arguments": {
    "owner": { "refPath": "<PAWN>" },
    "component_type": { "refPath": "/Script/Niagara.NiagaraComponent" },
    "name": "Contrail_L" } }
// returns the new component → <CONTRAIL_L>. Repeat with name "Contrail_R" → <CONTRAIL_R>.
```
**Risk:** low. add_component on an instance is the same path used for the plane mesh + boom already
on this pawn. QA: `ActorTools.get_components(<PAWN>, /Script/Niagara.NiagaraComponent)` returns 2.

**Step 2 — assign the system via the Niagara toolset (NOT via the `Asset` property):**
```jsonc
{ "toolset_name": "NiagaraToolsets.NiagaraToolset_Component",
  "tool_name": "SetSystem",
  "arguments": {
    "niagaraComponent": { "refPath": "<CONTRAIL_L>" },
    "system": { "refPath": "/Niagara/DefaultAssets/Templates/Systems/FountainLightweight" },
    "bResetExistingOverrideParameters": true } }
// repeat for <CONTRAIL_R>.
```
> The toolset doc explicitly says: *"Use this instead of setting the Asset property directly to
> ensure proper initialization."* Poking `Asset` via `set_properties` can leave the component
> uninitialized (renders nothing). Use `SetSystem`.

**Risk:** low. QA: `NiagaraToolset_Component.GetUserVariables(<CONTRAIL_L>)` returns the system's
user params (proves it bound).

**Step 3 — position each emitter at its engine (pawn-local), confirm it's attached to the pawn root:**
```jsonc
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "set_properties",
  "arguments": {
    "instance": { "refPath": "<CONTRAIL_L>" },
    "values": "{ \"RelativeLocation\": { \"X\": 300.0, \"Y\": -1050.0, \"Z\": -250.0 }, \"bAutoActivate\": true }" } }
// right engine: same but Y: 1050.0
```
> `add_component` attaches new scene components under the actor's root by default. If
> `ActorTools.get_parent_component(<CONTRAIL_L>)` returns null (i.e. it became a second root),
> `ActorTools.set_parent_component(<CONTRAIL_L>, <PAWN_ROOT>)` first so it rides the pawn.
> Run `ObjectTools.list_properties(<CONTRAIL_L>)` ONCE before set to confirm the exact names
> (`RelativeLocation`, `bAutoActivate` are canonical on USceneComponent/UFXSystemComponent).

**Risk:** medium-low (offsets may need a nudge from `get_bounds`). QA: capture (§4) — two streams
should originate at the two engine nacelles and trail back.

**Step 4 — if the stream puffs UP instead of trailing BACK, rotate the component (not the system):**
```jsonc
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "set_properties",
  "arguments": {
    "instance": { "refPath": "<CONTRAIL_L>" },
    "values": "{ \"RelativeRotation\": { \"Pitch\": 90.0, \"Yaw\": 0.0, \"Roll\": 0.0 } }" } }
```
This tips the fountain's local +Z toward the plane's tail so emission points backward. **Confirm the
exact sign by capture** — if it now fires forward (toward nose), use Pitch −90. Cosmetic; iterate via
§4. (Optionally widen/lengthen the trail with `SetVariable` once `GetUserVariables` reveals the
template's spawn-rate / lifetime / velocity params — names vary per template, so read them first.)

**Step 5 — make the contrails follow even when origin-rebases:** nothing to do. They're children of
the pawn (relative transform), so `CesiumOriginShiftComponent` rebases them rigidly with the pawn,
exactly like the camera (see `chase-cam-correct.md` §4). Do **not** give them world locations.

### (C) Honest fallback if no Niagara trail reads well

If both `FountainLightweight` and `AttributeReaderTrails` look wrong and you don't want to tune
template params, the simplest non-Niagara "vapor" cue MCP can place is a **translucent ribbon/quad
mesh** (a long thin StaticMesh with the engine `/InterchangeAssets/Substrate/MX_VolumetricFogCloud`
material or a faint translucent material) added via `ActorTools.add_component`
(`/Script/Engine.StaticMeshComponent`) trailing each engine and stretched on X with `RelativeScale3D`.
It won't animate, but at chase distance + speed it reads as a static vapor smear and is 100%
crash-free (no ticking FX at all). This is a last resort — the fountain is better.

---

## 2. Camera lag for a dynamic chase feel

### (a) RECOMMENDED — keep the working pawn `Camera`, accept NO lag

The confirmed-working view is the pawn's own `Camera` (a bare `UCameraComponent`) at
`RelativeLocation (-9000,0,2800)`, `RelativeRotation pitch -6`, `bUsePawnControlRotation FALSE`,
`bAutoActivate true`. **A `UCameraComponent` has no `bEnableCameraLag` / `CameraLagSpeed` fields at
all** — those live on `USpringArmComponent`. So "add lag to the current camera" is impossible without
switching the view to the SpringArm. The current setup is the one `chase-cam-correct.md` proved
deterministic and free of the belly-view / two-camera / spring-collision failure modes.
**Recommendation: do nothing here.** The sense of speed comes far more from the contrails (§1) + the
3D-tile city streaming past than from camera lag. Lag is a nice-to-have, not a "feel like flying" driver.

### (b) FALLBACK — switch the view to `ChaseBoom` SpringArm to GET lag (only if Pat asks)

The pawn already has an unused `ChaseBoom` (SpringArm) + `ChaseCam`. SpringArm supports lag. To use
it AND reproduce the verified framing, you must reproduce the **total** offset (−9000 back, +2800 up,
pitch −6) as `SpringArm(RelativeLocation + RelativeRotation + TargetArmLength)` and then make
`ChaseCam` the only active camera. Exact calls:

**Step 1 — deactivate the pawn's own working Camera so two cameras don't fight** (the two-active-cameras
bug, `chase-cam-correct.md` §5.5):
```jsonc
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools", "tool_name": "set_properties",
  "arguments": { "instance": { "refPath": "<PAWN_CAMERA>" },
    "values": "{ \"bAutoActivate\": false }" } }
```
**Step 2 — configure the SpringArm to the verified pose + gentle lag, collision OFF** (so it can't
snap against the 3D tiles):
```jsonc
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools", "tool_name": "set_properties",
  "arguments": { "instance": { "refPath": "<CHASE_BOOM>" },
    "values": "{ \"TargetArmLength\": 9486.0, \"SocketOffset\": { \"X\": 0.0, \"Y\": 0.0, \"Z\": 0.0 }, \"TargetOffset\": { \"X\": 0.0, \"Y\": 0.0, \"Z\": 0.0 }, \"RelativeLocation\": { \"X\": 0.0, \"Y\": 0.0, \"Z\": 0.0 }, \"RelativeRotation\": { \"Pitch\": -163.0, \"Yaw\": 0.0, \"Roll\": 0.0 }, \"bDoCollisionTest\": false, \"bEnableCameraLag\": true, \"bEnableCameraRotationLag\": true, \"CameraLagSpeed\": 4.0, \"CameraRotationLagSpeed\": 4.0, \"bUsePawnControlRotation\": false, \"bInheritPitch\": false, \"bInheritYaw\": true, \"bInheritRoll\": false }" } }
```
> The arm geometry: a SpringArm places the camera at `arm-end = boom_origin + Rotation·(−X·TargetArmLength)`.
> To land the camera at pawn-local (−9000, 0, +2800) — i.e. 9000 behind, 2800 up — the boom must point
> **down-and-back**: arm length = hypot(9000, 2800) ≈ **9486**, and the boom RelativeRotation pitch is
> the angle whose back/up ratio gives that endpoint, ≈ **−163°** (pointing back+up so the −X arm tip
> lands behind+above). **These are computed, not verified** — they almost certainly need one capture-
> and-nudge pass. Easier, robust alternative: leave `TargetArmLength` small/0 and put the whole
> (−9000,0,2800) on the SpringArm's `RelativeLocation`, then put the camera framing pitch (−6) on
> `ChaseCam.RelativeRotation` with the boom not inheriting rotation — but then the boom's lag only
> lags *translation*, which is actually the nicer "trailing weight" feel anyway:
> ```jsonc
> // simpler arm: lag the position only, keep the exact verified pose
> { "instance": { "refPath": "<CHASE_BOOM>" },
>   "values": "{ \"TargetArmLength\": 0.0, \"RelativeLocation\": { \"X\": -9000.0, \"Y\": 0.0, \"Z\": 2800.0 }, \"RelativeRotation\": { \"Pitch\": -6.0, \"Yaw\": 0.0, \"Roll\": 0.0 }, \"bDoCollisionTest\": false, \"bEnableCameraLag\": true, \"CameraLagSpeed\": 4.0, \"bEnableCameraRotationLag\": true, \"CameraRotationLagSpeed\": 4.0, \"bUsePawnControlRotation\": false }" }
> // then ChaseCam at identity relative to the boom tip:
> { "instance": { "refPath": "<CHASE_CAM>" },
>   "values": "{ \"RelativeLocation\": { \"X\": 0.0, \"Y\": 0.0, \"Z\": 0.0 }, \"RelativeRotation\": { \"Pitch\": 0.0, \"Yaw\": 0.0, \"Roll\": 0.0 }, \"bUsePawnControlRotation\": false, \"bAutoActivate\": true, \"FieldOfView\": 90.0 }" }
> ```
> **Use the simpler arm (TargetArmLength 0 + RelativeLocation) — it reproduces the verified pose
> exactly and the lag is on translation, which reads as the plane "pulling ahead" of the camera on
> acceleration. The TargetArmLength-9486 form is mathematically equivalent only after a nudge pass.**

**Step 3 — make sure `ChaseCam` is active and the pawn cam is not:** set `ChaseCam.bAutoActivate=true`
(above) and `<PAWN_CAMERA>.bAutoActivate=false` (Step 1). `CalcCamera` picks the first **active**
camera (`chase-cam-correct.md` §1), so exactly one must be active.

**Risk (this is the only step that can change the verified framing):** the camera pose moves from the
proven Camera component to the SpringArm tip; if the boom math is off you'll get a different angle or
the belly view. **QA: capture BEFORE (current working cam) and AFTER (boom), compare framing** (§4).
If framing drifted, nudge `RelativeLocation`/`RelativeRotation` on the boom, not the cam. **If it
looks worse, revert instantly:** re-activate the pawn cam (`<PAWN_CAMERA>.bAutoActivate=true`) and
deactivate `ChaseCam` — you're back to the verified view with one property set. Because of that clean
revert, 2(b) is safe to *try*, but keep it last.

---

## 3. Subtle cruise attitude (nose-up) on `PlaneMesh`

Goal: lift the nose ~2.5° so the jet sits in a believable cruise attitude rather than dead-level.

The mesh is currently `RelativeRotation Yaw 180`. **Pitch composes in the mesh's local frame, and
Yaw 180 flips the sign of how local pitch reads in world**: a positive local pitch after a 180° yaw
rotates the nose **down**, so to lift the nose UP you apply a **negative** pitch. Set:
```jsonc
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools", "tool_name": "set_properties",
  "arguments": { "instance": { "refPath": "<PLANE_MESH>" },
    "values": "{ \"RelativeRotation\": { \"Pitch\": -2.5, \"Yaw\": 180.0, \"Roll\": 0.0 } }" } }
```
Keep `Yaw 180` and `Roll 0` in the same call (set_properties replaces the whole `RelativeRotation`
struct; omitting Yaw would reset it to 0 and send the nose sideways).

**Risk:** low and fully reversible (`RelativeRotation.Pitch` back to 0). **QA: capture (§4) and look
at the nose vs. the horizon.** If the nose dropped instead of lifted, the sign is flipped for this
mesh's pivot/yaw → use **`Pitch: +2.5`** instead. (The sign depends on the FBX's modeled forward;
the Yaw-180 makes −2.5 the most likely "up", but a single capture settles it.) Don't exceed ~3–4° or
it looks like a climb, not cruise.

---

## 4. QA — how to verify each step (your editor-capture method)

Per `pie-qa-capture.md`, edit on the **editor-world** pawn with **PIE stopped**, then verify:

- **Primary:** `EditorAppToolset` → `StartPIE` with **`warmupSeconds: 0`**, then `CaptureViewport`
  immediately. In-viewport PIE renders the **possessed chase cam** into the captured framebuffer, so
  you see the real flight view (contrails trailing, nose attitude, lag on accel).
- **Fallback if PIE tears down before capture:** `bSimulate: true`, read the pawn's runtime world
  transform with `ActorTools.get_actor_transform`, compute `pawn_world × chase_offset`, and pass that
  as `CaptureViewport`'s `CaptureTransform` to reconstruct the chase pose (deterministic, crash-light).
- **Per-step checks:**
  - Contrails: two streams originate at the engine nacelles and trail toward the tail. Wrong wing →
    swap Y signs. Puffing up → §1 step 4 rotation. None visible → confirm `SetSystem` bound
    (`GetUserVariables`) and `bAutoActivate=true`.
  - Cruise attitude: nose above the horizon by a hair. Nose dropped → flip pitch sign (§3).
  - Camera lag (only if 2(b) used): capture during an accel/turn; the plane should momentarily lead
    the frame, then re-center. Framing changed from the verified shot → nudge the boom, or revert
    (re-activate `<PAWN_CAMERA>`).
- **Crash watch:** after adding Niagara, run `~/coding/unreal-agent-harness/ue_crashlog.sh` once. A
  clean log (no `UObjectArray.h:1083`, no `FMetalDynamicRHI::RHILockBuffer`) confirms the generic
  Niagara path didn't disturb the patched splat subsystem.

---

## Ordered execution checklist (copy/run top-to-bottom)

1. Read-only pre-flight: confirm no `CesiumGaussianSplatSystemActor` in the outliner; `load_asset` the fountain system; `get_actor_bounds`/`StaticMeshTools.get_bounds` on the plane to get the real pivot. (§1)
2. `ActorTools.add_component` × 2 → `Contrail_L`, `Contrail_R` (`/Script/Niagara.NiagaraComponent`). (§1.1)
3. `NiagaraToolset_Component.SetSystem` × 2 → `FountainLightweight`. (§1.2)
4. `ObjectTools.set_properties` × 2 → engine RelativeLocation + `bAutoActivate`. (§1.3)
5. **QA capture** (§4). If puffing up → §1.4 component rotation; if wrong wing → swap Y signs. Run `ue_crashlog.sh`.
6. `ObjectTools.set_properties` → `PlaneMesh` RelativeRotation `{Pitch:-2.5, Yaw:180, Roll:0}`. (§3)
7. **QA capture** (§4). Nose dropped → flip to `+2.5`.
8. (OPTIONAL, only if Pat wants lag) 2(b): deactivate pawn cam → configure `ChaseBoom` (simpler arm form) + lag → activate `ChaseCam`. **QA capture, compare to the verified framing; revert in one set if worse.** (§2)

All steps are property/component/registered-tool calls only — no Blueprint authoring. Steps 2–7 are
safe + reversible; step 8 is the only one touching the verified camera and has a one-call revert.
