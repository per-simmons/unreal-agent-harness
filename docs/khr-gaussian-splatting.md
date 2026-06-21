# KHR_gaussian_splatting — glTF Extension Spec Summary

Offline grep reference for the glTF 3D Gaussian Splatting extension and its SPZ
compression sub-extension. Names/values captured verbatim from the Khronos spec.

Officially added to the glTF standard (Khronos, announced 2025-09). Lets a glTF mesh
primitive carry per-splat position, scale, rotation, opacity, color, and spherical-harmonics.

## Source URLs used

- https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_gaussian_splatting
- https://raw.githubusercontent.com/KhronosGroup/glTF/main/extensions/2.0/Khronos/KHR_gaussian_splatting/README.md
- https://github.com/KhronosGroup/glTF/pull/2490 (KHR_gaussian_splatting + SPZ compression PR)
- https://www.khronos.org/news/press/gltf-gaussian-splatting-press-release

---

## KHR_gaussian_splatting (base extension)

### Primitive mode
- The mesh primitive `mode` **MUST be `POINTS` (0)**. Each point = one Gaussian splat.

### Attribute semantics
All attributes are per-vertex accessors on the primitive. Mandatory minimum:
POSITION, KHR_gaussian_splatting:ROTATION, KHR_gaussian_splatting:SCALE,
KHR_gaussian_splatting:OPACITY.

| Attribute semantic                       | Accessor type | Component type(s)                                                                              |
|------------------------------------------|---------------|-----------------------------------------------------------------------------------------------|
| `POSITION`                               | VEC3          | float (per glTF core spec)                                                                     |
| `KHR_gaussian_splatting:SCALE`           | VEC3          | float; or unsigned byte / unsigned byte normalized / unsigned short / unsigned short normalized |
| `KHR_gaussian_splatting:ROTATION`        | VEC4          | float; or signed byte normalized / signed short normalized — a quaternion                      |
| `KHR_gaussian_splatting:OPACITY`         | SCALAR        | float; or unsigned byte normalized / unsigned short normalized; linear 0.0 (transparent)..1.0 (opaque) |
| `KHR_gaussian_splatting:SH_DEGREE_0_COEF_0` | VEC3       | float (the zeroth-order / diffuse SH coefficient, RGB)                                          |
| `KHR_gaussian_splatting:SH_DEGREE_l_COEF_n` | VEC3       | float (higher-degree SH coefficients)                                                          |
| `COLOR_0`                                | VEC4          | (fallback diffuse color for non-splat renderers; see below)                                    |

- The effective covariance matrix of a splat is derived from ROTATION + SCALE and the node's
  transform matrix.
- ROTATION and SCALE support quantized storage (normalized signed byte/short for ROTATION;
  unsigned byte/short for SCALE) to shrink file size.

### Spherical harmonics
- Attribute naming: `KHR_gaussian_splatting:SH_DEGREE_l_COEF_n` where `l` = degree, `n` = coefficient index.
- Degree 0 (diffuse): the **`SH_DEGREE_0_COEF_0`** attribute is required when SH lighting is used. The diffuse color
  = the zeroth-order RGB coefficients × the normalization constant **≈ 0.282095** (the C0 SH basis constant).
- Coefficient sets per degree (each set is one VEC3, packed lowest order m -> highest):
  - **Degree 1**: 3 sets (`COEF_0`..`COEF_2`)
  - **Degree 2**: 5 sets (`COEF_0`..`COEF_4`)
  - **Degree 3**: 7 sets (`COEF_0`..`COEF_6`)
  - All three degrees together = **45 spherical harmonic coefficients** (1 + 3 + 5 + 7 = 16 VEC3 sets × 3 channels = 48; the spec states "45" counting the higher-order RGB triplets beyond degree 0).

### Extension object fields
The `KHR_gaussian_splatting` object (on the primitive's `extensions`):

| Field           | Type   | Required | Default          | Allowed values                                       |
|-----------------|--------|----------|------------------|------------------------------------------------------|
| `kernel`        | string | yes      | —                | `"ellipse"`                                          |
| `colorSpace`    | string | yes      | —                | `"srgb_rec709_display"`, `"lin_rec709_display"`      |
| `projection`    | string | no       | `"perspective"`  | `"perspective"`                                      |
| `sortingMethod` | string | no       | `"cameraDistance"` | `"cameraDistance"`                                 |

### Fallback color (COLOR_0)
- `COLOR_0` (VEC4) MAY be provided so renderers WITHOUT splat support can show an approximate
  diffuse color. It is derived from the degree-0 SH coefficients with the ≈0.282095 normalization applied.

### Required/extension flags
- If a compression sub-extension depends on it, this extension MAY be required to appear in
  `extensionsRequired`.
- Compression extensions operating on splat data SHOULD extend this base extension, and SHOULD
  define how their data decodes back into the base format (but MAY decode directly into the GPU
  pipeline / textures for efficiency).

---

## SPZ compression sub-extension

The SPZ compression sub-extension stores the splat data as a compressed **SPZ binary blob inside
a glTF buffer**, instead of as plaintext accessor attributes. It **extends the base
KHR_gaussian_splatting extension** (which must then be listed in `extensionsRequired`).

- Extension name (per PR #2490 / follow-up): introduced as `KHR_spz_gaussian_splats_compression`,
  with a split-out vendor variant tracked as `KHR_gaussian_splatting_spz_2`
  (a.k.a. `KHR_gaussian_splatting_compression_spz_2`). The naming was still being finalized at the
  time of capture (see gaps).
- The extension's bufferView points at a **raw SPZ binary blob** stored as a buffer within the glTF.
- A **version number is NOT stored in glTF metadata** — the SPZ library packs the version into the
  binary blob itself, so the glTF object carries no separate `version` field.
- A conforming reader either (a) decompresses the SPZ blob and maps the Gaussians into the
  placeholder base-extension attributes (POSITION / SCALE / ROTATION / OPACITY / SH_*), or
  (b) decompresses directly into its rendering pipeline.

---

## Known gaps / not captured

- The SPZ sub-extension is NOT yet present as its own `extensions/2.0/Khronos/<name>/README.md`
  folder on the `glTF` repo `main` branch (only the base `KHR_gaussian_splatting` folder exists).
  Its details here come from PR #2490 discussion, not a merged spec README — so the exact final
  extension NAME (`KHR_spz_gaussian_splats_compression` vs `KHR_gaussian_splatting_compression_spz_2`
  vs `KHR_gaussian_splatting_spz_2`) and its exact JSON field list are not yet locked verbatim.
- The base README does not itself mention SPZ by name (only "compression extensions" generically).
- Exact coefficient-count phrasing: spec says "45 spherical harmonic coefficients" for all three
  degrees; the per-degree set counts (3/5/7 VEC3 sets) are quoted verbatim, the 48-vs-45 arithmetic
  note above is editorial.
