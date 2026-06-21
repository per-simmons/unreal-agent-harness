# Cesium DynamicPawn chase-cam — the DEFINITIVE answer (UE 5.8, from source)

> Source-verified against the LOCAL Cesium clone
> `~/coding/cesium-build/cesium-unreal/Source/CesiumRuntime/{Public,Private}/GlobeAwareDefaultPawn.{h,cpp}`
> and the UE 5.8 engine source
> `/Users/Shared/Epic Games/UE_5.8/Engine/Source/Runtime/Engine/{Private/Actor.cpp, Private/DefaultPawn.cpp, Private/Pawn.cpp, Private/Camera/CameraComponent.cpp, Classes/Camera/CameraComponent.h}`.
> No editor was touched. This supersedes the uncertain "does it override CalcCamera?" passages in
> `plane-chase-pawn.md` (Step 5d). The answer is **NO, it does not override CalcCamera.**

This is the answer to the 5 questions, then the exact `set_properties` values.

---

## TL;DR — the one decision that fixes everything

**Do NOT use a SpringArm. Do NOT touch the camera's RelativeRotation while `bUsePawnControlRotation=true`.**
Either:

- **(A) FIXED chase, no mouse-look (RECOMMENDED, simplest, deterministic):** put the chase
  Camera component directly on the pawn root, set `bUsePawnControlRotation = FALSE`, and give the
  camera a hard `RelativeLocation` (behind+above) + `RelativeRotation` (pitched down). The view is
  then *exactly* `cameraRelativeTransform × pawnWorldTransform`. Numbers below frame a ~62 m plane.
- **(B) chase that still aims with mouse-look:** keep `bUsePawnControlRotation = TRUE` and pull the
  camera back with `RelativeLocation` only (its rotation is overwritten every frame by the pawn's
  globe-aware view rotation — so RelativeRotation is *ignored*; you steer with the mouse).

Your "shadow but no plane / belly view" symptom is almost certainly **(1)** the camera sitting at
the pawn origin *inside* the 62 m plane (near-clip eats it, you see only its shadow on the tiles),
and/or **(2)** you set the camera's RelativeRotation while `bUsePawnControlRotation` was still
`true`, so your rotation was silently overwritten by `GetViewRotation()` (which points wherever the
control rotation points — often down at the globe = belly view). Fix = move the camera back/up AND
make the rotation source unambiguous (pick A or B).

---

## 1. How does GlobeAwareDefaultPawn choose its view camera?

**It uses the first ACTIVE `UCameraComponent` it owns — via the inherited `AActor::CalcCamera`.
It does NOT override `CalcCamera`.**

- `AGlobeAwareDefaultPawn : public ADefaultPawn` (`GlobeAwareDefaultPawn.h:36`). It overrides only
  `MoveForward/MoveRight/MoveUp_World`, `GetViewRotation()`, `GetBaseAimRotation()`. **No
  `CalcCamera` override** anywhere in the class.
- `ADefaultPawn` does not override `CalcCamera` either, and `APawn` doesn't define one — so the
  call resolves to `AActor::CalcCamera` (`Actor.cpp:3688`):

  ```cpp
  void AActor::CalcCamera(float DeltaTime, FMinimalViewInfo& OutResult) {
    if (bFindCameraComponentWhenViewTarget) {            // default TRUE (Actor.cpp:320)
      TInlineComponentArray<UCameraComponent*> Cameras;
      GetComponents(Cameras);
      for (UCameraComponent* CameraComponent : Cameras) {
        if (CameraComponent->IsActive()) {
          CameraComponent->GetCameraView(DeltaTime, OutResult); // ← THE VIEW
          return;
        }
      }
    }
    GetActorEyesViewPoint(OutResult.Location, OutResult.Rotation); // fallback if no active cam
  }
  ```

  So **whatever active `UCameraComponent` exists on the pawn IS the view.** This is the single most
  important fact and it kills the old doc's fear (Step 5d #2) that a property-set camera "can't win"
  — it always wins as long as it's the only **active** camera. (If two cameras are active, the first
  one returned by `GetComponents` wins, which is order-dependent → deactivate the pawn's stock cam.)

- **Stock `ADefaultPawn` has NO CameraComponent.** Its constructor (`DefaultPawn.cpp:36–73`) creates
  only a `USphereComponent` (root, `CollisionComponentName`), a `UFloatingPawnMovement`, and an
  optional `UStaticMeshComponent` (the hidden engine sphere, `bOwnerNoSee=true`). **The `Camera`
  component you see at `...DynamicPawn_C....Camera` is added by Cesium's `DynamicPawn` Blueprint**,
  not by C++. That camera is what `CalcCamera` finds.
- **Does the pawn parent the camera to a boom?** No. There is no SpringArm in `ADefaultPawn` or in
  `AGlobeAwareDefaultPawn`. The `DynamicPawn` BP's `Camera` is attached directly to the root
  (`DefaultSceneRoot`/collision). **You do not need a SpringArm at all** — and a SpringArm adds the
  `bDoCollisionTest` failure mode against the 3D Tiles. Skip it.

---

## 2. What rotates the camera/pawn on mouse-look?

Trace, exactly:

1. Mouse → axis `DefaultPawn_Turn` (`MouseX`) and `DefaultPawn_LookUp` (`MouseY`, scale **−1**)
   (`DefaultPawn.cpp:135–146`). These call `AddControllerYawInput` / `AddControllerPitchInput`,
   which accumulate into the **PlayerController's control rotation** (NOT the pawn's actor
   rotation).
2. **Pawn body orientation:** `APawn::bUseControllerRotationPitch/Yaw/Roll` all default **FALSE**
   (`Pawn.cpp:98–100`). So on a stock DynamicPawn the *actor* does not rotate with the mouse — only
   the control rotation changes. (The plane mesh, attached to the root, therefore does NOT bank/turn
   from mouse on a stock pawn — flight movement turns it via `GetViewRotation()`-driven movement
   input, see `_moveAlongViewAxis`.)
3. **What the camera does with the control rotation depends ONLY on `CameraComponent.bUsePawnControlRotation`**
   (`CameraComponent.cpp` `GetCameraView`):

   ```cpp
   void UCameraComponent::GetCameraView(float DeltaTime, FMinimalViewInfo& DesiredView) {
     if (bUsePawnControlRotation) {
       const APawn* OwningPawn = Cast<APawn>(GetOwner());
       const AController* OwningController = OwningPawn ? OwningPawn->GetController() : nullptr;
       if (OwningController && OwningController->IsLocalPlayerController()) {
         const FRotator PawnViewRotation = OwningPawn->GetViewRotation(); // ← globe-aware override
         if (!PawnViewRotation.Equals(GetComponentRotation()))
           SetWorldRotation(PawnViewRotation);            // OVERWRITES camera world rotation EVERY frame
       }
     }
     ...
     DesiredView.Location = GetComponentLocation();        // camera world location (relative × pawn)
     DesiredView.Rotation = GetComponentRotation();        // camera world rotation (just set above, or relative)
   }
   ```

   - `bUsePawnControlRotation = TRUE`  → camera world rotation is force-set to
     `AGlobeAwareDefaultPawn::GetViewRotation()` every frame. **Your `RelativeRotation` is ignored**
     (overwritten). Mouse aims the camera. `GetViewRotation()` (`GlobeAwareDefaultPawn.cpp:98–135`)
     takes the controller's control rotation, interprets it as **East-South-Up (ESU)** and
     transforms it into the Unreal world frame, so "up" stays sane across the globe. Default for
     `UCameraComponent::bUsePawnControlRotation` is **FALSE** (`CameraComponent.cpp:94`); the
     `DynamicPawn` BP camera ships it **TRUE** (that's how first-person mouse-look works today).

   - `bUsePawnControlRotation = FALSE` → no force-set. `DesiredView.Rotation = GetComponentRotation()`
     = `RelativeRotation` composed onto the pawn's world rotation. **Mouse-look no longer aims the
     camera.** This is correct and intended for a *fixed* chase. It does NOT "break aiming" — it
     removes mouse aiming on purpose. If you want both a behind-the-plane chase AND mouse aim, that
     is option (B): leave it TRUE and offset only the location.

**So: setting `bUsePawnControlRotation = false` is exactly right for a fixed chase (A). It is wrong
if you wanted to keep steering the view with the mouse (then use B).** The two are mutually
exclusive on a single camera with no SpringArm — you cannot have a fixed *relative* rotation AND
mouse-driven rotation on the same component, because `GetCameraView` picks one source.

---

## 3. Exact camera offset for a behind+above chase of a ~62 m plane

### Pawn local axes (this is where belly/sideways views come from)

- UE actor local axes: **forward = +X, right = +Y, up = +Z.** A child component's
  `RelativeLocation` is in the **parent (pawn) local frame**, then composed onto the pawn's *world*
  rotation. So `RelativeLocation = {X:-2200}` means "2200 cm behind the pawn's local +X (its nose)."
- **The plane mesh must have its nose along the pawn's +X**, set via the *mesh component's*
  `RelativeRotation` (plane-chase-pawn.md Step 3c — Yaw 90 if nose modeled +Y, Yaw 180 if −X, etc.).
  Confirm with `StaticMeshTools.get_bounds`: the long axis (≈6200 cm for a 62 m jet) is nose↔tail,
  the wide axis is wingspan. Align the long axis to +X. **If the plane mesh nose is NOT on +X, the
  camera (which sits behind +X) will frame the plane side-on — that's the "belly/sideways" view, and
  it's a PLANE-mesh rotation bug, not a camera bug.**
- **Does setting the pawn actor's yaw change local-forward for the camera offset?** No, in the right
  way: the camera offset is *relative*, so it rotates *with* the pawn. If you yaw the pawn actor, +X
  rotates, the camera offset rotates with it, and the camera stays behind the plane. Good. (Note: on
  a stock DynamicPawn the actor yaw doesn't change from mouse because `bUseControllerRotationYaw=false`
  — the plane points where movement input sends it. That's fine for a flythrough.)

### Concrete numbers (≈62 m plane = ≈6200 cm long, attached nose +X at pawn origin)

Camera component **on the pawn root** (NOT on a SpringArm), `bUsePawnControlRotation = FALSE`:

| Property | Value | Why |
|---|---|---|
| `RelativeLocation.X` | **−2400.0** | 24 m behind the pawn origin. Plane spans ~−3100…+3100 on X if centered; this sits ~just behind the tail so the whole fuselage is in frame, not clipped. |
| `RelativeLocation.Y` | **0.0** | centered left/right. |
| `RelativeLocation.Z` | **+900.0** | 9 m above, looking down over the fuselage. |
| `RelativeRotation.Pitch` | **−8.0** | tilt the camera down ~8° so the plane sits in the lower-center and the skyline fills the top. |
| `RelativeRotation.Yaw` | **0.0** | look straight down the plane's +X (its nose). |
| `RelativeRotation.Roll` | **0.0** | level. |
| `FieldOfView` | **90.0** | a 62 m jet at 24–26 m back + 9 m up fits comfortably; widen to 95–100 for more skyline, narrow to 75 for a tighter "on the tail" look. |
| `bUsePawnControlRotation` | **false** | fixed chase; relative transform is the view (see Q2). |
| `bAutoActivate` | **true** | so `IsActive()` is true and `CalcCamera` selects it. |

**Geometry check:** camera at (−2400, 0, +900) relative to a plane centered at origin → it's 24 m
behind and 9 m up, look-down 8°. The plane's nose at +3100, tail at −3100; camera at −2400 is ~7 m
*ahead of the tail tip* and well outside the 62 m body, so it is **outside the near-clip** and the
plane renders fully (fixes "shadow but no plane"). Tune: pull `X` to −3000…−4000 for a wider/more
cinematic chase; raise `Z` to 1200 to look further down on it.

> If the plane mesh's pivot is NOT at its center (many Fab FBX pivot at the nose or a wingtip),
> recenter it with the *mesh component's* `RelativeLocation` first (Step 3c), or push the camera `X`
> further back to compensate. Read `get_bounds.origin` to know the pivot offset before trusting the
> numbers above.

### Option (B) — keep mouse aim (location-only pullback)

Same `RelativeLocation` as above, but `bUsePawnControlRotation = true` and **omit RelativeRotation**
(it's overwritten anyway). The mouse now aims; the camera stays the offset distance behind the
*aim* point. This gives a "look-around chase." It will pitch toward wherever you aim, so it can
point at the ground if you look down — that's expected with mouse aim, not a bug.

---

## 4. Does globe-anchor / origin-shift affect the camera's RELATIVE offset?

**No. The relative-offset approach is origin-shift-proof. Use relative offsets, never world
coordinates.**

- `RelativeLocation`/`RelativeRotation` are defined in the **parent (pawn) local frame** and
  composed onto the pawn's current world transform each frame. When `CesiumOriginShiftComponent`
  rebases the floating origin, it moves the *pawn's world transform*; the camera, being a child,
  moves rigidly with it. The relative numbers never change.
- `UCesiumGlobeAnchorComponent` precisely ties the pawn to the globe (ECEF), and `GetViewRotation()`
  uses the georeference's ESU→Unreal transform — but all of that feeds the *pawn's* world transform
  and (in option B) the camera's force-set world rotation. None of it touches a child's *relative*
  transform. So a behind+above relative offset stays behind+above through every rebase and anywhere
  on Earth.
- Corollary: **do not set the camera with a world `SetWorldLocation`-style absolute** — that would
  drift on the next origin shift. Relative only. (And do not re-set any `Origin*` georeference
  property here; that triggers a Cesium rebase — see `cesium-rebase-solution.md`.)

---

## 5. The "shadow but no plane" gotcha — root causes

In priority order, the things that produce "I see the plane's shadow on the tiles but not the
plane," or a belly/sideways view:

1. **Camera at the pawn origin, inside the 62 m plane.** Default camera `RelativeLocation` is
   `(0,0,0)`; the plane is also at the origin. The camera is *inside* the fuselage → the near-clip
   plane (default ~10 cm but the geometry surrounds the lens) renders nothing but you still see the
   plane's cast shadow on the ground. **Fix: the −2400/0/+900 offset above** (get the lens outside
   the mesh bounds).
2. **RelativeRotation set while `bUsePawnControlRotation` was still `true`.** Your rotation is
   silently overwritten by `GetViewRotation()` every frame (Q2). If the control rotation pitch was
   negative (looking down), you get a belly/ground view regardless of what RelativeRotation you set.
   **Fix: set `bUsePawnControlRotation = false` (option A) OR accept mouse aim (option B) — don't
   mix.**
3. **Plane mesh nose not on +X.** Camera sits behind +X; if the nose is on +Y/−X the plane is
   framed side-on (looks like a wing/belly). **Fix: plane *mesh component* RelativeRotation Yaw
   (Step 3c), confirmed via `get_bounds` long-axis.**
4. **`bOwnerNoSee` / wrong mesh visibility.** The stock DefaultPawn's hidden sphere has
   `bOwnerNoSee=true`. Make sure your *plane* StaticMeshComponent does NOT inherit a hidden/owner-no-see
   flag and that `StaticMesh` actually bound (Step 3c returned true; `get_bounds` is non-zero).
5. **Two active cameras.** If the DynamicPawn BP's stock `Camera` is still active, `CalcCamera`
   may pick it (order-dependent) instead of yours. **Deactivate the stock cam** (set its
   `bAutoActivate=false`) so yours is the only active one — though the *cleanest* path is to just
   reconfigure the **existing** DynamicPawn `Camera` component in place (it's already the active one
   and already the view), rather than adding a second camera. See "Recommended call" below.
6. **Components added during PIE.** Edits to a PIE-clone vanish on StopPIE. Build/edit on the
   **editor-world** pawn with PIE stopped, then StartPIE (plane-chase-pawn.md Step 7 note).

---

## Recommended call — reconfigure the EXISTING DynamicPawn `Camera` (no SpringArm, no 2nd camera)

The DynamicPawn already has an **active** `Camera` component that is already the view. The minimal,
deterministic fix is to (a) attach the plane mesh to the root, and (b) set this one camera's
offset + turn off pawn-control-rotation. `values` is a **JSON STRING** (escaped) — schema gotcha.

**Camera component — fixed chase (option A):**

```jsonc
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "set_properties",
  "arguments": {
    "instance": { "refPath": "<DYNPAWN_CAMERA_REFPATH>" },
    "values": "{ \"bUsePawnControlRotation\": false, \"bAutoActivate\": true, \"FieldOfView\": 90.0, \"RelativeLocation\": { \"X\": -2400.0, \"Y\": 0.0, \"Z\": 900.0 }, \"RelativeRotation\": { \"Pitch\": -8.0, \"Yaw\": 0.0, \"Roll\": 0.0 } }"
  } }
```

**Camera component — mouse-aim chase (option B), if you want look-around instead:**

```jsonc
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "set_properties",
  "arguments": {
    "instance": { "refPath": "<DYNPAWN_CAMERA_REFPATH>" },
    "values": "{ \"bUsePawnControlRotation\": true, \"bAutoActivate\": true, \"FieldOfView\": 90.0, \"RelativeLocation\": { \"X\": -2400.0, \"Y\": 0.0, \"Z\": 900.0 } }"
  } }
```

**Pawn flags — leave at DefaultPawn defaults; do NOT set them for a basic chase:**
`bUseControllerRotationPitch/Yaw/Roll` are all `false` by default (Pawn.cpp:98–100) and should stay
`false`. Setting them `true` would make the *plane body* (and thus the whole chase frame) spin with
the mouse, which is usually not what you want for a flythrough. Only set
`bUseControllerRotationYaw = true` if you specifically want the plane to yaw toward the mouse and the
camera to swing around the turn with it (option A + body-yaw). If you do, the call is:

```jsonc
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "set_properties",
  "arguments": {
    "instance": { "refPath": "<DYNPAWN_REFPATH>" },
    "values": "{ \"bUseControllerRotationYaw\": true, \"bUseControllerRotationPitch\": false, \"bUseControllerRotationRoll\": false }"
  } }
```

**Plane mesh component (attached to pawn root) — nose to +X, centered, real-world scale.** Read
`StaticMeshTools.get_bounds` FIRST; set `RelativeRotation.Yaw` to land the long axis on +X (90 if
nose was +Y, 180 if −X). `RelativeScale3D` from measured bounds (1.0 if already ~62 m):

```jsonc
{ "toolset_name": "editor_toolset.toolsets.object.ObjectTools",
  "tool_name": "set_properties",
  "arguments": {
    "instance": { "refPath": "<PLANE_COMP>" },
    "values": "{ \"StaticMesh\": { \"refPath\": \"<PLANE_SM_REFPATH>\" }, \"RelativeLocation\": { \"X\": 0.0, \"Y\": 0.0, \"Z\": 0.0 }, \"RelativeRotation\": { \"Pitch\": 0.0, \"Yaw\": 90.0, \"Roll\": 0.0 }, \"RelativeScale3D\": { \"X\": 1.0, \"Y\": 1.0, \"Z\": 1.0 } }"
  } }
```

> Before any of these: `ObjectTools.list_properties` (or `get_properties`) on `<DYNPAWN_CAMERA_REFPATH>`
> to confirm the exact names `bUsePawnControlRotation`, `bAutoActivate`, `FieldOfView`,
> `RelativeLocation`, `RelativeRotation` (they are canonical on UCameraComponent/USceneComponent).
> Make all edits with **PIE stopped** on the editor-world pawn, then StartPIE + CaptureViewport to
> verify (plane-chase-pawn.md Step 7). If the plane is framed side-on → fix `<PLANE_COMP>`
> RelativeRotation Yaw, not the camera. If you see only shadow → the camera offset didn't apply or
> a second camera is active.

---

## Why this differs from `plane-chase-pawn.md`

That doc built a **SpringArm + a second ChaseCam** and was *uncertain* whether GlobeAwareDefaultPawn
overrides `CalcCamera` (Step 5d #2 hedged with a Blueprint fallback). Source proves it does **not**
override CalcCamera, so:
- The SpringArm is unnecessary (and risks `bDoCollisionTest` snapping against 3D Tiles).
- A second camera is unnecessary and risks the two-active-cameras ordering bug.
- Reconfiguring the **existing** active DynamicPawn `Camera` in place is the minimal, correct fix.

Keep the SpringArm path only if you later want collision-free camera lag/smoothing
(`bEnableCameraLag`/`bEnableCameraRotationLag`) — those live on USpringArmComponent, not on a bare
CameraComponent. For a stable framed chase, the bare camera offset above is enough and has fewer
failure modes.
