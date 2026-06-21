# Cesium rebase via Unreal MCP `ObjectTools.set_properties` — definitive answer

Question: how to make a georeferenced `Cesium3DTileset` render at the Unreal scene
ORIGIN (not at ECEF ~6000 km away) in UE 5.8 using ONLY the MCP's
`ObjectTools.set_properties` (which sets a UPROPERTY through the editor property
system, i.e. the same path as `PostEditChangeProperty`).

## Verdict: YES — `set_properties` already rebases.

Setting `OriginLatitude` / `OriginLongitude` / `OriginHeight` on the
`CesiumGeoreference` actor through the editor property system DOES trigger the
full recompute and rebase. No UFUNCTION call, no `RefreshTileset()`, no manual
recompute is required. Our earlier failure was order / linking, not capability.

## The proof chain (all in the local source)

### 1. `PostEditChangeProperty` → `Set*` → `UpdateGeoreference()`

`Source/CesiumRuntime/Private/CesiumGeoreference.cpp:704`

```cpp
void ACesiumGeoreference::PostEditChangeProperty(FPropertyChangedEvent& event) {
  Super::PostEditChangeProperty(event);
  if (!event.Property) return;
  FName propertyName = event.Property->GetFName();
  CESIUM_POST_EDIT_CHANGE(propertyName, ACesiumGeoreference, OriginPlacement);
  CESIUM_POST_EDIT_CHANGE(propertyName, ACesiumGeoreference, OriginLongitude);
  CESIUM_POST_EDIT_CHANGE(propertyName, ACesiumGeoreference, OriginLatitude);
  CESIUM_POST_EDIT_CHANGE(propertyName, ACesiumGeoreference, OriginHeight);
  CESIUM_POST_EDIT_CHANGE(propertyName, ACesiumGeoreference, Scale);
  CESIUM_POST_EDIT_CHANGE(propertyName, ACesiumGeoreference, Ellipsoid);
}
```

The macro (`Source/CesiumRuntime/Private/CesiumActors.h:8`):

```cpp
#define CESIUM_POST_EDIT_CHANGE(changedPropertyName, ClassName, PropertyName)  \
  if (changedPropertyName ==                                                   \
      GET_MEMBER_NAME_CHECKED(ClassName, PropertyName)) {                      \
    this->Set##PropertyName(this->PropertyName);                               \
    return;                                                                    \
  }
```

So editing `OriginLatitude` calls `SetOriginLatitude(this->OriginLatitude)`, and
each setter calls `UpdateGeoreference()` (`CesiumGeoreference.cpp:226-246`):

```cpp
void ACesiumGeoreference::SetOriginLatitude(double NewValue) {
  this->OriginLatitude = NewValue;
  this->UpdateGeoreference();
}
```

### 2. `UpdateGeoreference()` recomputes the coordinate system and broadcasts

`CesiumGeoreference.cpp:889` → `_updateCoordinateSystem()` (line 929):

```cpp
void ACesiumGeoreference::_updateCoordinateSystem() {
  if (this->OriginPlacement == EOriginPlacement::CartographicOrigin) {
    FVector origin = this->GetOriginLongitudeLatitudeHeight();
    this->_coordinateSystem = this->GetEllipsoid()->CreateCoordinateSystem(
        this->GetOriginEarthCenteredEarthFixed(),
        this->GetScale());
  } else { /* TrueOrigin: identity-ish, no rebase */ }
}
```

Then `UpdateGeoreference()` ends with `OnGeoreferenceUpdated.Broadcast();`
(line 915).

### 3. The tileset auto-reacts — no RefreshTileset needed

`ResolveGeoreference()` subscribes the tileset root to the delegate
(`Cesium3DTileset.cpp:264`):

```cpp
this->ResolvedGeoreference->OnGeoreferenceUpdated.AddUniqueDynamic(
    pRoot, &UCesium3DTilesetRoot::HandleGeoreferenceUpdated);
```

`HandleGeoreferenceUpdated` (`Cesium3DTilesetRoot.cpp:15`) calls
`_updateTilesetToUnrealRelativeWorldTransform()` (line 63), which recomputes
`ECEF → Unreal` and calls `pTileset->UpdateTransformFromCesium()`. The tiles
move to the new origin automatically.

`RefreshTileset()` only sets `_destroyOnNextTick` (re-downloads tiles) — NOT
needed for a georeference move.

## Defaults that are already correct (do NOT need to be set)

`Source/CesiumRuntime/Public/CesiumGeoreference.h`:

- `OriginPlacement = EOriginPlacement::CartographicOrigin;` (line 143) — already
  the default, this is the mode that maps lon/lat/height to the scene origin.
- No `SubLevelCamera` / sub-level needed for a single-level scene.

So you do NOT need to set `OriginPlacement` explicitly. (You may set it anyway
for safety; it also fires `UpdateGeoreference()`.)

## The one thing that actually matters: LINKAGE

The rebase only moves the tiles if the tileset's `ResolvedGeoreference` is the
SAME actor whose origin you edit. Resolution (`Cesium3DTileset.cpp:248`):

1. If `Cesium3DTileset.Georeference` (a `TSoftObjectPtr`) is set and valid → use it.
2. Else → `GetDefaultGeoreferenceForActor` finds (or creates) the actor tagged
   `DEFAULT_GEOREFERENCE` in the world (`CesiumGeoreference.cpp:144-172`).

If there is exactly ONE `CesiumGeoreference` in the level (the default one), the
tileset auto-resolves to it and you can edit that actor's origin directly. If
there are multiple, or you want to be explicit, set the tileset's `Georeference`
to point at the specific actor first.

Note `SetGeoreference()` (cpp:241) does `InvalidateResolvedGeoreference()` +
`ResolveGeoreference()` — i.e. it re-subscribes the delegate. Editing the
`Georeference` soft-pointer via the property system goes through
`Cesium3DTileset::PostEditChangeProperty` which calls the same resolve path, so
linking via `set_properties` also wires the delegate. Link FIRST, then set the
origin (so the delegate is subscribed before the broadcast).

## The minimal MCP `ObjectTools.set_properties` sequence

Actor A = the `CesiumGeoreference` actor. Actor B = the `Cesium3DTileset` actor.

If there's only one georeference (the default), step 1 is optional.

1. (Optional but recommended) On tileset B, link it to georeference A:
   - `Georeference` = (object ref to actor A)
   This subscribes B's root to A's `OnGeoreferenceUpdated`.

2. On georeference A, set the target location. Order within this group does not
   matter (each set fires its own `UpdateGeoreference`), but set all three; the
   LAST one fires the broadcast that lands the final transform:
   - `OriginLongitude` = <target lon, degrees>
   - `OriginLatitude`  = <target lat, degrees>
   - `OriginHeight`    = <target height, meters>

   (`OriginPlacement` = `CartographicOrigin` is already the default; set it
   explicitly only if a prior session changed it.)

After step 2, every `Cesium3DTileset` resolved to A is rebased to the scene
origin automatically. No `RefreshTileset`, no UFUNCTION call.

## Why the earlier attempt failed (most likely)

- The tileset's `ResolvedGeoreference` was a DIFFERENT actor than the one whose
  origin was edited (no/incorrect linkage), OR
- the origin was set on the georeference BEFORE the tileset existed / before the
  delegate was subscribed, so the broadcast had no listener and nothing
  re-fired afterward.

Fix: ensure single/explicit linkage, link before setting origin, and (if the
tileset was spawned after) re-touch any one origin property so a fresh
`OnGeoreferenceUpdated.Broadcast()` reaches the now-subscribed tileset root.
