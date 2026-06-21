#!/usr/bin/env python3
"""cesium_rebase.py - rebase Cesium tiles to a geographic origin in a LIVE editor.

THIS RUNS *INSIDE* UNREAL. It is meant to be sent over the remote-exec channel,
e.g.:

    python3 ue_exec.py --file cesium_rebase.py            # uses NYC defaults
    LON=-73.9857 LAT=40.7484 HEIGHT=0 python3 ue_exec.py --file cesium_rebase.py

Why this exists:
  The MCP property-set path writes raw UPROPERTYs and SKIPS the Cesium
  BlueprintSetters, so tiles stay at ECEF (earth-centered) coords and render in
  the wrong place / scale. The rebase only fires through the FUNCTION calls
  CesiumGeoreference.set_origin_longitude_latitude_height(...) and
  Cesium3DTileset.refresh_tileset(). Calling them via Python remote-exec is the
  fix.

Origin args are read from environment variables so a single file can be reused:
  LON    longitude in degrees   (default -73.9857  = Times Square area, NYC)
  LAT    latitude  in degrees   (default  40.7484)
  HEIGHT height in meters       (default  0.0)
"""

import os
import unreal  # available only inside the editor's Python runtime


def _f(name, default):
    raw = os.environ.get(name)
    try:
        return float(raw) if raw not in (None, "") else float(default)
    except (TypeError, ValueError):
        unreal.log_warning(
            "[cesium_rebase] {0}={1!r} is not a number; using {2}".format(name, raw, default)
        )
        return float(default)


def rebase(lon, lat, height):
    eus = unreal.EditorActorSubsystem()
    actors = eus.get_all_level_actors()

    georefs = [a for a in actors if isinstance(a, unreal.CesiumGeoreference)]
    tilesets = [a for a in actors if isinstance(a, unreal.Cesium3DTileset)]

    if not georefs:
        unreal.log_error(
            "[cesium_rebase] No CesiumGeoreference actor in the level. "
            "Add one (and at least one Cesium3DTileset) before rebasing."
        )
    if not tilesets:
        unreal.log_warning("[cesium_rebase] No Cesium3DTileset actors found in the level.")

    # Fire the BlueprintSetter FUNCTIONS (not raw property writes) on each georef.
    # UE 5.8 Cesium signature: SetOriginLongitudeLatitudeHeight(FVector) where the
    # vector is (X=longitude, Y=latitude, Z=height). The rebase is only valid when
    # OriginPlacement == CartographicOrigin, so force that first.
    for geo in georefs:
        try:
            geo.set_origin_placement(unreal.OriginPlacement.CARTOGRAPHIC_ORIGIN)
        except Exception as e:  # older/newer API surface; non-fatal (default is already Cartographic)
            unreal.log_warning("[cesium_rebase] set_origin_placement skipped: {0}".format(e))
        geo.set_origin_longitude_latitude_height(unreal.Vector(lon, lat, height))
        unreal.log(
            "[cesium_rebase] {0}.set_origin_longitude_latitude_height(Vector({1}, {2}, {3}))".format(
                geo.get_name(), lon, lat, height
            )
        )

    # Force every tileset to re-request tiles against the new origin.
    for ts in tilesets:
        ts.refresh_tileset()
        unreal.log("[cesium_rebase] {0}.refresh_tileset()".format(ts.get_name()))

    print(
        "[cesium_rebase] DONE - {0} georeference(s) rebased to "
        "(lon={1}, lat={2}, height={3}), {4} tileset(s) refreshed.".format(
            len(georefs), lon, lat, height, len(tilesets)
        )
    )


if __name__ == "__main__":
    LON = _f("LON", -73.9857)
    LAT = _f("LAT", 40.7484)
    HEIGHT = _f("HEIGHT", 0.0)
    rebase(LON, LAT, HEIGHT)
