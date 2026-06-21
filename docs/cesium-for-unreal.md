# Cesium for Unreal — Reference

Offline grep reference for the Cesium for Unreal plugin actors/components: tileset
loading from Cesium ion or a URL, georeferencing, sun/sky, and polygon clipping.
Property/function names captured from the Cesium for Unreal C++ API ref docs and source headers.

## Source URLs used

- https://cesium.com/learn/unreal/ (tutorials hub)
- https://cesium.com/learn/cesium-unreal/ref-doc/api-design.html (API design guide)
- https://cesium.com/learn/cesium-unreal/ref-doc/Cesium3DTileset_8h_source.html
- https://cesium.com/learn/cesium-unreal/ref-doc/CesiumGeoreference_8h_source.html
- https://cesium.com/learn/cesium-unreal/ref-doc/CesiumCartographicPolygon_8h_source.html
- https://cesium.com/learn/cesium-unreal/ref-doc/classACesiumSunSky.html
- https://cesium.com/learn/cesium-unreal/ref-doc/structFCesiumPointCloudShading.html
- https://github.com/CesiumGS/cesium-unreal (README / releases)

Plugin: **Cesium for Unreal**. Install via the UE Marketplace/Fab, or extract the release
ZIP into `Engine/Plugins/Marketplace`. Policy: supports the three most recent UE versions
(UE4 lives on the `ue4-main` branch). Latest release at capture: **v2.27.0 (2026-06-01)**.

---

## ACesium3DTileset  (Cesium3DTileset actor)

The actor that streams a 3D Tiles tileset (incl. photorealistic 3D Tiles and Gaussian
splat tilesets). Header: `Source/CesiumRuntime/Public/Cesium3DTileset.h`.

### Source selection
- `ETilesetSource TilesetSource` — `FromCesiumIon` or `FromUrl` (enum `ETilesetSource`)
- `FString Url` — used when `TilesetSource == FromUrl`
- `int64 IonAssetID` — Cesium ion asset id (when `FromCesiumIon`)
- `FString IonAccessToken` — ion access token
- `UCesiumIonServer* CesiumIonServer` — which ion server (default = the project's ion server)

### Level of detail / quality
- `double MaximumScreenSpaceError` — LOD refinement threshold (lower = higher detail/more tiles; default 16.0). Getter/setter: `GetMaximumScreenSpaceError()` / `SetMaximumScreenSpaceError(double)`. Values below ~8 can stall rendering.
- `FCesiumPointCloudShading PointCloudShading` — point-cloud / splat attenuation settings (see struct below)

### Georeferencing
- `TSoftObjectPtr<ACesiumGeoreference> Georeference` — the georeference this tileset is positioned against

### Culling / update toggles
- `bool EnableFrustumCulling` — cull tiles outside the view frustum
- `bool EnableFogCulling`
- `bool EnableOcclusionCulling`
- `bool SuspendUpdate` — pause tileset selection/streaming updates
- `bool CreatePhysicsMeshes` — generate collision meshes for tiles
- `bool EnableWaterMask`

### Functions
- `void RefreshTileset()` — reload/refresh the tileset
- `double GetMaximumScreenSpaceError()` / `void SetMaximumScreenSpaceError(double)`
- `bool GetEnableOcclusionCulling()` (and the matching toggle getters/setters)

NOTE: `GetBoundingVolumeCenter` is NOT in this header (it lives on the cesium-native
tile/bounding-volume side, not the actor).

---

## FCesiumPointCloudShading  (struct)

Point-cloud / Gaussian-splat point attenuation, set on `Cesium3DTileset.PointCloudShading`.

- `bool Attenuation` (default `false`) — whether to perform point attenuation
- `float GeometricErrorScale` (default `1.0f`) — scale applied to the tile's geometric error before computing attenuation
- `float MaximumAttenuation` (default `0.0f`) — max point attenuation in pixels
- `float BaseResolution` (default `0.0f`) — average base resolution of the dataset, in meters

---

## ACesiumGeoreference  (CesiumGeoreference actor)

Maps the WGS84 globe (ECEF / longitude-latitude-height) into the Unreal world.
Header: `Source/CesiumRuntime/Public/CesiumGeoreference.h`.

### Properties
- `EOriginPlacement OriginPlacement` — origin placement mode (e.g. `EOriginPlacement::CartographicOrigin`; also `TrueOrigin` / `BoundingVolumeOrigin`)
- `double OriginLongitude` — custom-origin longitude, degrees [-180, 180]
- `double OriginLatitude` — custom-origin latitude, degrees [-90, 90]
- `double OriginHeight` — custom-origin height, meters above the ellipsoid
- `double Scale` — percentage scale of the globe in the Unreal world
- `UCesiumEllipsoid* Ellipsoid` — the ellipsoid in use (WGS84 default)
- `UCesiumSubLevelSwitcherComponent* SubLevelSwitcher`
- `FGeoreferenceUpdated OnGeoreferenceUpdated` — delegate fired whenever the georeference changes
- `FGeoreferenceEllipsoidChanged OnEllipsoidChanged`

### Origin getters/setters
- `SetOriginLongitudeLatitudeHeight(const FVector&)` — set origin from (lon, lat, height); this is the API equivalent of the editor's **"Place Origin Here"**
- `GetOriginLongitudeLatitudeHeight()`
- `SetOriginEarthCenteredEarthFixed(const FVector&)` / `GetOriginEarthCenteredEarthFixed()`
- `GetOriginPlacement()` / `SetOriginPlacement(EOriginPlacement)`
- `GetOriginLatitude()` / `SetOriginLatitude(double)` (and Longitude/Height/Scale equivalents)
- `GetEllipsoid()` / `SetEllipsoid(UCesiumEllipsoid*)`

### Coordinate transforms
- `TransformLongitudeLatitudeHeightPositionToUnreal(const FVector&)` — (lon, lat, height) -> Unreal world position
- `TransformUnrealPositionToLongitudeLatitudeHeight(const FVector&)` — Unreal -> (lon, lat, height)
- `TransformEarthCenteredEarthFixedPositionToUnreal(const FVector&)` — ECEF -> Unreal
- `ComputeEastSouthUpToUnrealTransformation(const FVector&)` — local ESU basis at an Unreal position

NOTE on naming: older Cesium versions exposed `SetGeoreferenceOriginLongitudeLatitudeHeight`;
current API uses `SetOriginLongitudeLatitudeHeight`. The editor button is still labeled
"Place Origin Here." `OriginPlacement` enum is `EOriginPlacement` (modes:
TrueOrigin, BoundingVolumeOrigin, CartographicOrigin).

---

## ACesiumSunSky  (CesiumSunSky actor)

Globe-aware sun + sky/atmosphere driven by geographic location and time.
Ref: `classACesiumSunSky`.

- `UCesiumGlobeAnchorComponent* GlobeAnchor` — ties the actor to the globe (location comes from its anchor / the georeference)
- `double SolarTime` — current solar time, hours from midnight
- `double TimeZone` — hours offset from GMT
- `int32 Day` / `int32 Month` (1=Jan..12=Dec) / `int32 Year`
- `double NorthOffset` — offset in the sun's position
- `bool UseDaylightSavingTime` — adjust solar time for DST

NOTE: `Georeference` on CesiumSunSky is now `Georeference_DEPRECATED` (protected) — the
sun/sky derives its lon/lat from the GlobeAnchor + the scene georeference rather than its
own georeference property. `UpdateAtmosphereAtRuntime`, `EnableMobileRendering`,
`UseLevelDirectionalLight`, `Latitude`, `Longitude` were NOT confirmed on the class-ref
page (see gaps) — historically present, may have moved between versions.

---

## ACesiumCartographicPolygon + polygon clipping

`ACesiumCartographicPolygon` defines a polygon on the globe (header
`CesiumCartographicPolygon.h`):
- `USplineComponent* Polygon` — the polygon, edited as a spline in the editor
- `UCesiumGlobeAnchorComponent* GlobeAnchor` — ties the polygon precisely to the globe
- `CreateCartographicPolygon(const FTransform& worldToTileset)` — returns a `CesiumGeospatial::CartographicPolygon` built from the current spline
- `SetPolygonPoints(...)` — Blueprint-callable; populate spline points from position arrays in a given CRS

### Clipping / raster-overlay workflow
1. Place an `ACesiumCartographicPolygon` and shape its spline over the area to clip.
2. Add a **CesiumPolygonRasterOverlay** component to the target `Cesium3DTileset`.
3. Add the polygon actor to the overlay's **Polygons** array.
4. Enable the overlay's **ExcludeSelectedTiles** option to cut a hole in the tileset
   (e.g. to drop in a custom ground mesh), or leave it off to clip-in.

NOTE: `CesiumPolygonRasterOverlay` property names (Polygons array, ExcludeSelectedTiles,
InvertSelection) were not fetched verbatim from its own header — see gaps.

---

## Gaussian splat / KHR_gaussian_splatting / SPZ support

Cesium for Unreal supports **3D Gaussian Splat tilesets** — there is a dedicated tutorial
"View 3D Gaussian splat tilesets with LODs in Cesium for Unreal" on cesium.com/learn/unreal.
- Splat tilesets are 3D Tiles whose glTF content uses the **KHR_gaussian_splatting** extension
  (and the SPZ compression sub-extension; see `khr-gaussian-splatting.md`).
- They load through a normal `ACesium3DTileset` (FromCesiumIon or FromUrl), same as any other
  3D Tiles dataset — point/splat rendering is governed by `PointCloudShading`
  (`Attenuation`, `MaximumAttenuation`, `GeometricErrorScale`, `BaseResolution`).
- See the base glTF extension semantics in `khr-gaussian-splatting.md` for the on-the-wire format.

---

## Typical actor set for a georeferenced scene

- `ACesium3DTileset` — the streamed data (e.g. Google Photorealistic 3D Tiles, ion asset, or a splat tileset)
- `ACesiumGeoreference` — one per level; defines where on the globe the Unreal origin sits
- `ACesiumSunSky` — globe-anchored lighting/atmosphere
- `DynamicPawn` (CesiumGlobeAnchor pawn) — fly/walk the globe; or any pawn + `UCesiumGlobeAnchorComponent`

---

## Known gaps / not captured verbatim

- **CesiumSunSky**: `UpdateAtmosphereAtRuntime`, `EnableMobileRendering`,
  `UseLevelDirectionalLight`, `LevelDirectionalLight`, `Latitude`, `Longitude` were not
  on the fetched class-ref page (Georeference there is the deprecated alias). Confirm in-editor.
- **CesiumPolygonRasterOverlay** component property names (Polygons / ExcludeSelectedTiles /
  InvertSelection) described from the documented workflow, not pulled from its header.
- The cesium-unreal GitHub README does not mention splat/SPZ explicitly; splat support is
  documented in the cesium.com tutorial + via the KHR_gaussian_splatting glTF extension.
- `EOriginPlacement` full enumerator list (only `CartographicOrigin` appeared verbatim in the
  header excerpt; TrueOrigin/BoundingVolumeOrigin are the other standard modes).
