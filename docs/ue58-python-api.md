# UE 5.x Python API — Headless Scene Building Reference

Offline grep reference for the `unreal.` Python API used to spawn actors, import
assets, and place meshes from a headless / commandlet / Python-remote session.
Member names and signatures captured verbatim from the official Epic docs.

## Source URLs used

- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api (entry point)
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorActorSubsystem?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorAssetSubsystem?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AssetToolsHelpers?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AssetTools?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AssetImportTask?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/StaticMesh?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/StaticMeshComponent?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/StaticMeshActor?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorLevelLibrary?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SystemLibrary?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/GameplayStatics?application_version=5.5
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/Transform?application_version=5.5

NOTE: `docs.unrealengine.com/5.x/.../PythonAPI/` and the dev.epicgames.com pages
without the `?application_version=` query both return **403** to bare fetchers.
The version-pinned `dev.epicgames.com/.../python-api/class/<Class>?application_version=5.5`
form is the one that loads. The 5.5 API is identical for these classes through 5.6/5.8.

---

## unreal.EditorActorSubsystem

Primary subsystem for spawning/destroying/selecting actors in the editor world.
Get it with: `unreal.get_editor_subsystem(unreal.EditorActorSubsystem)`.

- `spawn_actor_from_class(actor_class, location, rotation=[0.0, 0.0, 0.0], transient=False) -> Actor`
  - Create an actor from a Blueprint or class, placing it in the current level.
- `spawn_actor_from_object(object_to_use, location, rotation=[0.0, 0.0, 0.0], transient=False) -> Actor`
  - Create an actor from a Factory, Archetype, Blueprint, Class, or Asset (e.g. a StaticMesh -> StaticMeshActor).
- `destroy_actor(actor_to_destroy) -> bool`
- `destroy_actors(actors_to_destroy) -> bool`
- `get_all_level_actors() -> Array[Actor]`
- `get_all_level_actors_components(...) -> Array[ActorComponent]`
- `set_actor_selection_state(actor, should_be_selected) -> None`
- `set_selected_level_actors(actors_to_select) -> None`
- `get_selected_level_actors() -> Array[Actor]`
- `clear_actor_selection_set() -> None`
- `select_nothing() -> None`
- `get_actor_reference(path_to_actor) -> Actor`
- `duplicate_actor(actor_to_duplicate, to_world=None, offset=[0.0, 0.0, 0.0]) -> Actor`
- `duplicate_actors(actors_to_duplicate, to_world=None, offset=[0.0, 0.0, 0.0]) -> Array[Actor]`
- `convert_actors(actors, actor_class, static_mesh_package_path) -> Array[Actor]`
- `set_actor_transform(actor, world_transform) -> bool`
- `set_component_transform(scene_component, world_transform) -> bool`

---

## unreal.EditorAssetSubsystem

Asset CRUD by content path (`/Game/...`).
Get it with: `unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)`.

- `load_asset(asset_path) -> Object`
- `save_asset(asset_to_save, only_if_is_dirty=True) -> bool`
- `save_loaded_asset(asset_to_save, only_if_is_dirty=True) -> bool`
- `save_loaded_assets(assets_to_save, only_if_is_dirty=True) -> bool`
- `save_directory(directory_path, only_if_is_dirty=True, recursive=True) -> bool`
- `does_asset_exist(asset_path) -> bool`
- `do_assets_exist(asset_paths) -> bool`
- `find_asset_data(asset_path) -> AssetData`
- `delete_asset(asset_path_to_delete) -> bool`
- `duplicate_asset(source_asset_path, destination_asset_path) -> Object`
- `rename_asset(source_asset_path, destination_asset_path) -> bool`
- `list_assets(directory_path, recursive=True, include_folder=False) -> Array[str]`

NOTE: importing files (FBX/OBJ/glTF) is NOT done here — use AssetTools +
AssetImportTask below. EditorAssetSubsystem operates on already-imported assets.

---

## unreal.AssetToolsHelpers  /  unreal.AssetTools

The import + asset-creation entry point. Standard flow:
`unreal.AssetToolsHelpers.get_asset_tools()` -> AssetTools -> `import_asset_tasks([...])`.

### unreal.AssetToolsHelpers
- `get_asset_tools() -> AssetTools`  (static — "Get Asset Tools")

### unreal.AssetTools
- `import_asset_tasks(import_tasks) -> None`
  - Imports assets using the AssetImportTask list (the headless import call).
- `import_assets_automated(import_data) -> Array[Object]`
  - Imports fully up front; never shows dialogs or modal errors.
- `create_asset(asset_name, package_path, asset_class, factory, calling_context='None') -> Object`
- `create_asset_with_dialog(asset_name, package_path, asset_class, factory, calling_context='None', call_configure_properties=True) -> Object`
- `duplicate_asset(asset_name, package_path, original_object) -> Object`

---

## unreal.AssetImportTask

Editor properties (set on the task object you hand to `import_asset_tasks`):

- `filename` (str) — file to be imported
- `destination_path` (str) — content path where the asset is imported
- `destination_name` (str) — custom asset name
- `automated` (bool) — avoid dialogs
- `save` (bool) — save after importing
- `replace_existing` (bool) — overwrite existing assets
- `replace_existing_settings` (bool) — replace existing settings when overwriting
- `options` (Object) — import options specific to the asset type (e.g. FbxImportUI / interchange pipeline)
- `factory` (Factory) — optional factory to use
- `async_` (bool) — async import where the format supports it
- `result` (Array[Object]) — DEPRECATED; use the get_objects function instead
- `imported_object_paths` (Array[str]) — paths to objects created/updated after import

Minimal headless import pattern:
```python
task = unreal.AssetImportTask()
task.filename = "/abs/path/mesh.glb"
task.destination_path = "/Game/Imported"
task.automated = True
task.save = True
task.replace_existing = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
```

---

## unreal.StaticMesh

- `get_bounding_box() -> Box` — local-space bounding box incl. bounds extensions
- `get_bounds() -> BoxSphereBounds`
- `get_num_lods() -> int32`
- `set_material(material_index, new_material) -> None`
- `static_materials` (Array[StaticMaterial]) — read/write
- `body_setup` (BodySetup) — physics setup, read/write

## unreal.StaticMeshComponent

- `set_static_mesh(new_mesh) -> bool` — change the StaticMesh used by this instance
- `static_mesh` (StaticMesh) — read-only property: the mesh this component renders
- `get_local_bounds() -> (min: Vector, max: Vector)`
- `set_forced_lod_model(forced_lod_model) -> None`
- `set_force_disable_nanite(...)`, `set_evaluate_world_position_offset(...)`,
  `set_reverse_culling(...)`, `set_distance_field_self_shadow_bias(...)`
- Materials/transform are inherited from `MeshComponent` / `PrimitiveComponent` /
  `SceneComponent` (e.g. `set_material(element_index, material)`,
  `set_world_location(...)`, `set_world_scale3d(...)`, `set_world_transform(...)`).

## unreal.StaticMeshActor

- `static_mesh_component` (StaticMeshComponent) — read-only; the actor's mesh component
- `static_mesh_physics_replication_mode`, `static_mesh_replicate_movement`
- `set_mobility(mobility)` — change mobility (Static / Stationary / Movable)
- Inherits Actor props: `root_component`, `tags`, `layers`, collision settings, etc.

Spawning a placed static mesh headlessly:
```python
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
mesh = unreal.load_asset("/Game/Imported/mesh")
actor = eas.spawn_actor_from_object(mesh, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
```

---

## unreal.EditorLevelLibrary  (DEPRECATED)

The **Editor Scripting Utilities Plugin is deprecated.** Do NOT use
`unreal.EditorLevelLibrary` in new code. Use these subsystems instead:

- **Editor Actor Utilities Subsystem** -> `unreal.EditorActorSubsystem` (actor selection/manipulation; replaces `get_all_level_actors`, `get_selected_level_actors`, `destroy_actor`, `clear_actor_selection_set`)
- **Level Editor Subsystem** -> `unreal.LevelEditorSubsystem` (level ops + viewport; replaces `save_current_level`, `load_level`, `new_level`, `editor_play_simulate`)
- **Unreal Editor Subsystem** -> `unreal.UnrealEditorSubsystem` (world access + camera info)
- **Static Mesh Editor Subsystem** -> `unreal.StaticMeshEditorSubsystem` (mesh ops)

Deprecated methods that moved: `clear_actor_selection_set()`, `get_all_level_actors()`,
`get_selected_level_actors()`, `destroy_actor()`, `save_current_level()`, `load_level()`.

---

## unreal.SystemLibrary  (Kismet System Library)

Static utility library; most methods take a `world_context_object` first arg.

- `get_game_time_in_seconds(world_context_object) -> float`
- `print_string(world_context_object, in_string="Hello", print_to_screen=True, print_to_log=True, text_color=..., duration=2.0, key='None') -> None`
- `line_trace_single(world_context_object, start, end, trace_channel, trace_complex, actors_to_ignore, draw_debug_type, ignore_self=True, ...) -> (bool, HitResult)`
- `box_trace_single(world_context_object, start, end, half_size, orientation, trace_channel, trace_complex, actors_to_ignore, draw_debug_type) -> (bool, HitResult)`
- `capsule_trace_single(world_context_object, start, end, radius, half_height, trace_channel, trace_complex, actors_to_ignore, draw_debug_type, ignore_self=True) -> (bool, HitResult)`
- `sphere_overlap_actors(world_context_object, sphere_pos, sphere_radius, object_types, actor_class_filter, actors_to_ignore) -> (bool, Array[Actor])`
- `draw_debug_line(world_context_object, line_start, line_end, line_color, duration=0.0, thickness=0.0) -> None`
- `execute_console_command(world_context_object, command, specific_player=None) -> None`
- `delay(world_context_object, duration=0.2, latent_info)` — latent
- `get_object_name(object) -> str`
- `collect_garbage() -> None`
- `quit_game(world_context_object, specific_player, quit_preference, ignore_platform_restrictions) -> None`

---

## unreal.GameplayStatics

Static runtime helper (game-world queries + spawning).

- `get_player_controller(world_context_object, player_index) -> PlayerController`
- `get_player_pawn(world_context_object, player_index) -> Pawn`
- `get_player_character(world_context_object, player_index) -> Character`
- `get_actor_of_class(world_context_object, actor_class) -> Actor` — first actor of class
- `get_all_actors_of_class(world_context_object, actor_class) -> Array[Actor]` (slow with many actors)
- `spawn_actor_from_class(world_context_object, actor_class, location, rotation, ...) -> Actor`
- `spawn_actor_from_object(world_context_object, object_to_use, location, rotation, ...) -> Actor`
- `begin_spawning_actor_from_class(...) -> Actor` / `finish_spawning_actor(actor, spawn_transform) -> Actor`
- `get_game_mode(world_context_object) -> GameModeBase`
- `get_world_delta_seconds(world_context_object) -> float`
- `set_global_time_dilation(world_context_object, time_dilation) -> None`

NOTE: GameplayStatics spawn requires a live world/PIE context; for editor scene
authoring prefer EditorActorSubsystem.

---

## unreal.Transform / unreal.Vector / unreal.Rotator

### unreal.Transform
Constructor: `unreal.Transform(location=Vector(), rotation=Rotator(), scale=Vector())`
Properties:
- `translation` (Vector) — translation as a vector
- `rotation` (Quat) — rotation as a quaternion
- `scale3d` (Vector) — 3D scale (local space)

### unreal.Vector
- Constructor: `unreal.Vector(x=0.0, y=0.0, z=0.0)`
- Properties: `x`, `y`, `z` (all float). Math ops supported (`+ - * /`, `.length()`, `.normal()`).
- Note: Unreal is **Z-up, left-handed**, units in **centimeters**.

### unreal.Rotator
- Constructor: `unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)`
- Properties: `roll`, `pitch`, `yaw` (degrees, all float)

---

## Known gaps / not captured

- `unreal.StaticMeshComponent` material/transform methods are inherited from
  `MeshComponent`/`PrimitiveComponent`/`SceneComponent` — the StaticMeshComponent page
  itself does not list them (names given above are the standard inherited ones, not
  re-confirmed verbatim from a child page).
- `unreal.Vector` / `unreal.Rotator` dedicated pages returned no member detail to the
  fetcher; `x/y/z` and `roll/pitch/yaw` are the well-established stable names.
- Bare `docs.unrealengine.com/PythonAPI/` and unversioned dev.epicgames.com URLs are
  **403-walled to fetchers** — always use the `?application_version=5.5` form.
