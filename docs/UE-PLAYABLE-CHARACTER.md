# Adding a playable third-person character to ANY UE 5.8 level

> Goal: take any open level and make it a "game you can walk around in" — drop in a
> player-controlled humanoid, press Play, roam with WASD + mouse + jump. This is the
> **transferable engine workflow** (Third Person template → GameMode → Enhanced Input →
> PlayerStart → PIE), independent of any specific level (City Sample, Cesium, our PCG city, etc.).
>
> Companion to the level-specific guides. Here we cover the fundamentals every "turn this into a
> game" task reuses.
>
> Engine: **UE 5.8**. UE-5.8-vs-older-tutorial differences are flagged inline with **[5.8]**.
> Every claim is sourced; URLs at the bottom.

---

## The 4 pieces you always need

To possess and walk a character in a level, UE needs exactly four things wired together:

1. **A Character class** — a `Pawn` with a capsule + skeletal mesh + `CharacterMovementComponent`
   (gravity, walking, jumping). The Third Person template's `BP_ThirdPersonCharacter` is this.
2. **A GameMode** that names which Pawn to spawn (`DefaultPawnClass`) and which
   `PlayerController` to use. The template's `BP_ThirdPersonGameMode` does this.
3. **A spawn point** — a `PlayerStart` actor in the level. On Play, the GameMode spawns the
   DefaultPawn here and possesses it with player 0.
4. **Input** — an **Enhanced Input** Mapping Context (IMC) + Input Actions (move/look/jump),
   *added to the player on BeginPlay*. Without this the character spawns but won't move.

The template ships all four. Your job on an arbitrary level is: (a) make the template content
exist in the project, (b) point the level's GameMode at it, (c) place a PlayerStart, (d) Play.

---

## 1. The Third Person template — what it is and how to ADD it to an existing project

### What the template content contains
Source: Epic's "Third Person Template in Unreal Engine" docs.

| Asset | Path | Role |
|-------|------|------|
| `BP_ThirdPersonCharacter` | `Content/ThirdPerson/Blueprints/` | the playable character (capsule, mesh, camera boom, input logic) |
| `BP_ThirdPersonGameMode` | `Content/ThirdPerson/Blueprints/` | GameMode; `DefaultPawnClass = BP_ThirdPersonCharacter` |
| **Quinn** (default) + **Manny** skeletal meshes | `Content/Characters/Mannequins/Meshes/` | the two stock mannequins |
| Animation set + Anim Blueprints | `Content/Characters/Mannequins/Animations/` | locomotion; **uses the IK Rig system** (`CR_Mannequin_BasicFootIK`, `CR_Mannequin_Body` in `Content/Characters/Mannequins/Rigs/`) |
| Enhanced Input assets | `Content/ThirdPerson/Input/` (IMC + `Content/ThirdPerson/Input/Actions/`) | `IMC_Default`, `IA_Move`, `IA_Look`, `IA_Jump` (see §3) |
| Prototype level + geometry | `Content/LevelPrototyping/` | ramps, platforms, physics cubes (you can ignore these and use your own level) |

**[5.8]** Naming has been stable across 5.x: character `BP_ThirdPersonCharacter`, GameMode
`BP_ThirdPersonGameMode`, meshes Quinn/Manny, animations on the **IK Rig** system. Older
(UE4) tutorials reference `ThirdPersonCharacter` (no `BP_` prefix), the old "Mannequin" (UE4
grey mannequin, not Quinn/Manny), and **legacy Input** (`Project Settings → Input → Action/Axis
Mappings`) instead of Enhanced Input — if a tutorial shows Axis Mappings, it predates 5.x.

### How to add it via "Add Feature or Content Pack" — exact path **[5.8]**
The reliable way to inject the template into a project that was created from a *different* template
(blank, First Person, our Cesium/PCG project, etc.):

1. In the editor, **Tools → Add Feature or Content Pack…** (older / alt path: the **+ Add**
   button in the Content Browser → *Add Feature or Content Pack*). Both open the same
   "Add Content to the Project" dialog.
2. Select the **Blueprint** tab (vs C++).
3. Under **Game** templates, pick **Third Person**.
4. Click **Add to Project**.
5. The folders (`ThirdPerson/`, `Characters/Mannequins/`, `LevelPrototyping/`) populate in the
   Content Browser.

> **[5.8] caveat — Enhanced Input plugin must be on.** Enhanced Input is the engine default in
> 5.x and is enabled in template-created projects automatically. If you add Third Person to a
> *very* stripped project, confirm `Edit → Plugins → Enhanced Input` is enabled (it is on by
> default in 5.8) and that `Project Settings → Engine → Input → Default Classes` point at
> `EnhancedInputComponent` / `EnhancedPlayerInput`. Template-born projects already have this.

> This is content-only and **must be done in the editor by hand** — it is not exposed over the
> Unreal MCP (see §4). Everything *after* the content exists can be MCP-driven.

---

## 2. GameMode wiring — what to set and where it lives

The GameMode is the contract "which pawn + controller does this level use." Two ways to apply it;
for "any level" you almost always want the **per-level override**.

### The GameMode's own properties (on `BP_ThirdPersonGameMode`)
Open the GameMode Blueprint → **Class Defaults**. The load-bearing properties:

| Property | Value (template default) |
|----------|--------------------------|
| **Default Pawn Class** | `BP_ThirdPersonCharacter` |
| **Player Controller Class** | `PlayerController` (stock) |
| **HUD / GameState / PlayerState** | stock defaults (fine to leave) |

You normally don't edit these — the template ships them correct. You only edit `Default Pawn
Class` if you want a *different* character.

### Assigning the GameMode to a level — **World Settings → GameMode Override**
This is the per-level switch and the one that matters for "make THIS level playable":

1. **Window → World Settings** (the World Settings panel; in template projects it's docked by
   the Details panel).
2. Under **Game Mode → GameMode Override**, set it to **`BP_ThirdPersonGameMode`**.
3. (Optional, visible once an override is set) confirm **Default Pawn Class** reads
   `BP_ThirdPersonCharacter`.

**[5.8]** The property is `AWorldSettings.DefaultGameMode` internally but is labeled **GameMode
Override** in the UI — unchanged across 5.x. (Project-wide default lives at *Project Settings →
Maps & Modes → Default GameMode*, but per-level override wins and is cleaner for one level.)

### Place a PlayerStart
1. In the **Place Actors** panel (or **Quickly Add → Basic**), search **Player Start**, drag it
   into the level.
2. Position it **slightly above the floor** and on solid ground (see §5 — most "falls through /
   spawns in air" bugs are a mis-placed PlayerStart).

On Play, `BP_ThirdPersonGameMode` spawns `BP_ThirdPersonCharacter` at the PlayerStart and
possesses it with player 0. That's the whole spawn chain.

---

## 3. Enhanced Input (the 5.x default) — and the #1 "won't move" failure

**[5.8]** UE 5.x defaults to **Enhanced Input**, replacing the legacy Action/Axis mapping system.
This is the single biggest divergence from UE4 tutorials.

### What the template sets up
- **Input Mapping Context (IMC):** `IMC_Default` — maps physical keys/sticks to Input Actions
  (e.g. W/A/S/D + left stick → `IA_Move`; mouse/right stick → `IA_Look`; Space/gamepad-A →
  `IA_Jump`).
- **Input Actions (IA):** `IA_Move` (Axis2D / Vector2D), `IA_Look` (Axis2D), `IA_Jump` (Digital
  bool). Stored under `Content/ThirdPerson/Input/Actions/`.
- **Binding:** in `BP_ThirdPersonCharacter`, the IA events (`EnhancedInputAction IA_Move`, etc.)
  drive `Add Movement Input` / `Add Controller Yaw/Pitch Input` / `Jump`. In the C++ template the
  same happens in `SetupPlayerInputComponent` via
  `EnhancedInputComponent->BindAction(MoveAction, ETriggerEvent::Triggered, …)`.
- **The critical glue — adding the IMC on BeginPlay.** In `BP_ThirdPersonCharacter`'s
  **Event BeginPlay**: Get the `PlayerController` → `Get Enhanced Input Local Player Subsystem`
  → **Add Mapping Context** (`IMC_Default`, Priority 0). The template wires this for you.

### If the character spawns but won't move — diagnose in this order
This is almost always an input wiring problem, not a movement problem:

1. **IMC never added to the player.** The most common failure when porting the character into a
   custom GameMode/level. The `Add Mapping Context` node on BeginPlay must run with a valid
   `EnhancedInputLocalPlayerSubsystem`. If you re-created the character or copied logic, verify
   BeginPlay still gets the subsystem **from the PlayerController** (not from the pawn) and that
   `IMC_Default` is the context passed. No IMC = no input events fire = character is inert.
2. **Wrong PlayerController is possessing.** If the level's GameMode override isn't
   `BP_ThirdPersonGameMode`, a different controller/pawn may possess and BeginPlay input setup
   never runs for *this* character.
3. **Input Actions not bound** (C++ path): missing `BindAction` in `SetupPlayerInputComponent`,
   or the `UInputAction*` / `UInputMappingContext*` UPROPERTYs are unset in the BP defaults.
4. **Enhanced Input plugin/default classes off** (stripped project) — see §1 caveat.
5. **Viewport focus** — in PIE you must **click once inside the play viewport** or keyboard input
   goes to the editor, not the game. (Mimics the same focus rule as the flight-pawn doc.)

---

## 4. Can the Unreal MCP do this? (SceneTools / ObjectTools / BlueprintTools / EditorAppToolset)

Mixed — and the split is the whole point of this section. Our MCP is the official Unreal MCP
plugin; its `execute_tool_script` is a **restricted orchestration sandbox** that can only call
*registered* toolset tools — no `import unreal`, no arbitrary method calls, no console commands
(see `docs/programmatic-toolset-capabilities.md`). So:

### MUST be done by hand (not MCP-automatable)
- **Adding the Third Person template content** (§1). "Add Feature or Content Pack" is an editor
  UI flow; there is no registered toolset tool that injects a content/feature pack. Until the
  assets (`BP_ThirdPersonCharacter`, `BP_ThirdPersonGameMode`, IMC/IA, mannequins) exist in the
  project, none of the steps below have anything to point at.
- **Authoring the BeginPlay Add-Mapping-Context graph from scratch.** `BlueprintTools` can edit
  Blueprint node graphs, but you do not need to — the template's `BP_ThirdPersonCharacter`
  already has it. Recreating it node-by-node over MCP is fragile; lean on the shipped asset.

### MCP-automatable (once the content exists)
Same call form as the flight-pawn doc: `mcp__unreal__call_tool` with
`{ "tool": "<Toolset.Tool>", "arguments": { … } }`.

| Step | Toolset.Tool | Notes |
|------|--------------|-------|
| Find WorldSettings + PlayerStart refPaths | `SceneTools` get-all-level-actors (or `EditorAppToolset.GetVisibleActors`) | get **real** refPaths; don't fabricate |
| Set the level's GameMode override | `ObjectTools.set_properties` on WorldSettings → `GameModeOverride` = `BP_ThirdPersonGameMode`'s **GeneratedClass** (`…_C`) refPath | class-valued property → pass the `_C` class, e.g. `/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C` |
| Verify the class resolves | `ObjectTools.get_class` / `AssetTools` load of `/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode` | confirm before relying on it |
| Place / move the PlayerStart | `ActorTools` spawn-actor (class `/Script/Engine.PlayerStart`) **or** `ActorTools.set_actor_transform` on an existing one | put it just above the floor (§5) |
| (Optional) set AutoPossessPlayer | `ObjectTools.set_properties` on the pawn CDO → `AutoPossessPlayer = Player0` | usually unnecessary — GameMode possesses via PlayerStart |
| Start Play | `EditorAppToolset.StartPIE` with `playMode: PlayMode_InViewPort`, `bSimulate: false` (+ optional `startTransform` to override spawn pose) | full PIE, pawn possessed, input live |
| Confirm + screenshot | `EditorAppToolset.IsPIERunning` (expect true) → `EditorAppToolset.CaptureViewport` | |
| Stop | `EditorAppToolset.StopPIE` | |

> `StartPIE`'s **`startTransform`** override spawns + possesses the DefaultPawn at an exact pose
> *without* needing a PlayerStart — handy on a level with no spawn point yet. (Same mechanism the
> flight-pawn doc uses.) But `bSimulate:false` + `PlayMode_InViewPort` is required for a *possessed,
> input-driven* character (Simulate gives you no possessed pawn / no player input).

> **Pre-flight, like the flight doc:** `EditorAppToolset.IsPIERunning {}` must be **false** before
> `StartPIE`. If true, stop and ask.

---

## 5. "Character falls through the floor / spawns in the air / can't move" — fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Falls straight through the floor on Play | Floor mesh has **no collision** (or set to *No Collision* / *Query Only*) | Give the floor **Block All** collision (Static Mesh → Collision → simple/complex; for landscape it's automatic) |
| Falls through, or pushed up violently | PlayerStart capsule **embedded in / below** the floor — engine resolves penetration by ejecting | Raise the PlayerStart so its capsule sits **just above** the surface. Common trick: spawn point at floor **Z + a few cm**; some place the floor at `Z = -5` so the capsule rests cleanly above 0 |
| Spawns high up then falls | PlayerStart is floating in the air; character free-falls until it hits geometry | Move PlayerStart down onto solid ground; the blue capsule gizmo should rest on the floor |
| Spawns at world origin / camera, **not** at PlayerStart | No PlayerStart in the level, or GameMode isn't possessing (wrong/empty GameMode override) | Add a PlayerStart **and** set World Settings → GameMode Override to `BP_ThirdPersonGameMode`. With no PlayerStart, GameMode spawns at origin (0,0,0) — often mid-air |
| Spawns fine but **won't move** | Enhanced Input IMC not added on BeginPlay (or wrong controller possessing, or no viewport focus) | See §3 diagnosis order — start by confirming the `Add Mapping Context (IMC_Default)` runs on the possessed character, then click inside the PIE viewport |
| Red **"PlayerStart is in floor"** / blocked icon | PlayerStart capsule overlaps geometry | Nudge it up/over until the icon clears; same as the embedded-capsule fix |

Rule of thumb: a valid spawn = a **PlayerStart whose capsule rests just above collidable floor**,
in a level whose **GameMode override possesses a character with a CharacterMovementComponent**.

---

## 6. Camera — the template's spring-arm third-person rig

`BP_ThirdPersonCharacter`'s component tree (the standard third-person rig):

- **`CameraBoom`** — a **Spring Arm Component**. Holds the camera at a fixed distance behind the
  character and **collides with the world** so the camera pulls in near walls.
- **`FollowCamera`** — a **Camera Component** attached to the spring arm's socket end.

Key Spring Arm properties to tweak (in the BP, select `CameraBoom` → Details):

| Property | Default | Effect |
|----------|---------|--------|
| **Target Arm Length** | `400` (cm) | distance behind the character — raise to ~600–800 for a wider/further chase cam, lower to ~250 for over-the-shoulder |
| **Socket Offset** (esp. Z) | small | raise **Z** to lift the camera higher above the character's head; raise **Y** for an over-the-shoulder offset |
| **Do Collision Test** | true | leave on so the camera doesn't clip through walls |
| **Use Pawn Control Rotation** (on spring arm) | true | spring arm rotates with mouse/look input |

The character also uses **Orient Rotation to Movement** (on `CharacterMovementComponent`) so the
mannequin faces its travel direction while the camera orbits independently — the classic
third-person feel. To make the character turn *with* the camera instead, turn that off and enable
`Use Controller Rotation Yaw` on the character.

**[5.8]** Spring-arm/camera setup is unchanged from earlier 5.x; `Target Arm Length 400` is the
long-standing template default. Over MCP you can edit these via `ObjectTools.set_properties` on
the `CameraBoom` component, but it's usually a quick manual tweak in the BP.

---

## Minimal path: from "Third Person content present + a level open" → "press Play, roam"

**The one manual step the user must do first (not MCP-automatable):**
> **Tools → Add Feature or Content Pack → Blueprint → Third Person → Add to Project** (§1), so
> `BP_ThirdPersonCharacter` + `BP_ThirdPersonGameMode` + the Enhanced Input assets exist. Do this
> once per project.

**Then the MCP-driven steps** (all `mcp__unreal__call_tool`, content already exists):

1. **Pre-flight:** `EditorAppToolset.IsPIERunning {}` → must be `false`.
2. **Find refPaths:** `SceneTools` get-all-level-actors (or `EditorAppToolset.GetVisibleActors`)
   → grab the **WorldSettings** refPath (and a **PlayerStart** refPath if one exists).
3. **Set GameMode override:** `ObjectTools.set_properties` on WorldSettings →
   `GameModeOverride = /Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C`
   (verify the class first with `ObjectTools.get_class`).
4. **Ensure a spawn point** (pick one):
   - **a.** Place a PlayerStart on solid ground — `ActorTools` spawn `/Script/Engine.PlayerStart`,
     then `ActorTools.set_actor_transform` to sit it just above the floor; **or**
   - **b.** Skip the PlayerStart and pass a **`startTransform`** to `StartPIE` (step 5) — spawns +
     possesses the character at that exact pose (a few cm above the floor).
5. **Play:** `EditorAppToolset.StartPIE` with
   `{ "options": { "bSimulate": false, "playMode": "PlayMode_InViewPort"[, "startTransform": {…}] } }`.
6. **Verify:** `EditorAppToolset.IsPIERunning {}` (expect `true`) →
   `EditorAppToolset.CaptureViewport { "bShowUI": true }`.
7. **Hand off:** tell the user to **click once inside the play viewport** for keyboard focus, then
   roam — **WASD** move, **mouse** look, **Space** jump. **F8** ejects, **Esc** (or
   `EditorAppToolset.StopPIE`) exits.

Net: the user does **one** editor click-through (add the template content); the agent does
everything else (GameMode override, PlayerStart/spawn pose, Play, verify) over MCP.

---

## Sources

- [Third Person Template in Unreal Engine — UE 5.8 docs (Epic)](https://dev.epicgames.com/documentation/unreal-engine/third-person-template-in-unreal-engine)
- [Third Person Template in Unreal Engine — UE 5.7 docs (Epic, identical structure)](https://dev.epicgames.com/documentation/en-us/unreal-engine/third-person-template-in-unreal-engine)
- [World of Level Design — Add additional game templates into existing UE5 projects (Add Feature or Content Pack)](https://www.worldofleveldesign.com/categories/ue5/additional-game-templates-in-existing-projects.php)
- [Epic Forums — How to add 3rd person starter content to a first person project](https://forums.unrealengine.com/t/how-to-add-3rd-person-starter-content-to-my-first-person-project/2022307)
- [Enhanced Input System complete guide (Input Action + Mapping Context setup)](https://uhiyama-lab.com/en/notes/ue/enhanced-input-system-complete-guide/)
- [How Third Person Movement Works in UE5 (BeginPlay Add Mapping Context, IMC_Default, IA_Move/Look/Jump)](https://wirepair.org/2023/09/22/how-third-person-movement-works-in-ue5/)
- [GameDev.tv — Character doesn't move in UE5 (Enhanced Input / IMC not added)](https://community.gamedev.tv/t/how-to-use-ue5s-enhanced-input-system/246269)
- [Add Sprinting to the UE5 Third Person Character in C++ — SetupPlayerInputComponent / BindAction, IMC_Default](https://gdtactics.com/add-sprinting-to-the-ue5-third-person-character-in-cpp)
- [Epic Forums — Third Person Character stuck through floor / falling on spawn](https://forums.unrealengine.com/t/third-person-character-is-stuck-through-floor-and-then-falling-on-spawn/483319)
- [Epic Forums — Character spawns not at Player Start & falls through map](https://forums.unrealengine.com/t/character-spawns-not-at-player-start-falls-through-map/2565259)
- [Epic Forums — Why does my actor fall through the floor on Play (collision / Z offset)](https://forums.unrealengine.com/t/why-does-my-actor-fall-through-the-floor-on-play/278641)
- Internal: `docs/programmatic-toolset-capabilities.md` (MCP sandbox limits — no `import unreal`, registered tools only), `docs/flight-pawn-setup.md` (the GameModeOverride / StartPIE / startTransform MCP call patterns reused here)
</content>
</invoke>
