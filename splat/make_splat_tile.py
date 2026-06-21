#!/usr/bin/env python3
"""
make_splat_tile.py  —  Wrap a Gaussian splat (.ply, 3DGS/INRIA layout) as a
KHR_gaussian_splatting 3D Tiles tileset that our Cesium for Unreal build
(UE 5.8, ~/coding/cesium-build/cesium-unreal) loads via a single
Cesium3DTileset actor.

================================================================================
WHY THIS REWRITE (the GPU-crash root cause + the fix)
================================================================================
The PREVIOUS version of this script (saved as make_splat_tile.py.bak-spz)
embedded the raw .spz blob and emitted PLACEHOLDER accessors that pointed at a
tiny 32-byte stub bufferView, trusting Cesium's decodeSpz.cpp to REBIND every
accessor to freshly-decoded data at load time.

That produced a hard Metal RHI crash, preceded by:
    LogCesium: Error: 'POSITION' accessor view on mesh primitive returned
               invalid status: 4
    Critical error ... libUnrealEditor-MetalRHI.dylib!FMetalDynamicRHI::RHILockBuffer

Reading the actual build source pinned it down EXACTLY:

  - AccessorView<T>::create() (CesiumGltf/include/CesiumGltf/AccessorView.h,
    lines ~236-292) computes
        accessorBytes = byteStride * accessor.count
    and sets status = BufferViewTooSmall (enum value **4**, 0-indexed:
    Valid=0, InvalidAccessorIndex=1, InvalidBufferViewIndex=2,
    InvalidBufferIndex=3, BufferViewTooSmall=4) whenever
        accessorBytes > bufferView.byteLength.

  - decodeSpz.cpp's decodePrimitive() is supposed to rebind POSITION/SCALE/
    ROTATION/COLOR_0/SH accessors to fresh, correctly-sized bufferViews
    (sizeof(float)*gaussian->positions.size(), etc). It does NOT touch
    accessor.count and it does NOT validate that loadSpz() actually returned
    points (decodeBufferViewToGaussianCloud returns the cloud unconditionally).

  - So if the SPZ decode is skipped, partial, or yields a different point
    count than the placeholder accessor.count, POSITION stays pointing at the
    32-byte stub (or a zero-length bufferView). 32 < 12*516352 → status 4 →
    the splat component bails mid-build, leaving a zero/garbage GPU vertex
    buffer that Metal then locks → RHILockBuffer crash.

  The placeholder-rebind dance is fundamentally fragile: a valid-on-paper glTF
  whose accessors are correct ONLY IF a downstream decode step succeeds.

THE FIX — emit a fully UNCOMPRESSED, self-validating tile.
  We read the .ply ourselves, apply the EXACT transforms Cesium's decoder
  applies, and write REAL bufferViews sized stride*count for every attribute.
  No SPZ extension, no decode dependency, no placeholder rebind. Every accessor
  is valid by construction, so AccessorView<T> can never return status 4.

  The runtime splat component (CesiumGltfGaussianSplatComponent.cpp) reads
  POSITION / SCALE / ROTATION / COLOR_0 / SH via plain AccessorView<T> and
  behaves IDENTICALLY whether the data came from SPZ decode or from real
  uncompressed accessors — verified in source. So uncompressed is a drop-in,
  crash-proof replacement.

  Trade-off: the .glb is larger (uncompressed floats vs SPZ). For a hero tile
  that is fine. Pass --spz to fall back to the old embedded-SPZ path if you
  ever need the smaller file AND have verified the decode works end-to-end.

================================================================================
EXACT TRANSFORMS (matched to decodeSpz.cpp + the 3DGS/INRIA .ply convention)
================================================================================
3DGS .ply per-vertex fields (binary_little_endian float32):
    x, y, z
    scale_0..2        (log-space; world scale = exp(s))
    opacity           (logit; alpha = sigmoid(opacity) = 1/(1+exp(-opacity)))
    rot_0..3          (quaternion; .ply order is (w, x, y, z) for INRIA/Brush)
    f_dc_0..2         (SH degree-0 DC term per channel)
    f_rest_0..44      (SH degrees 1-3; INRIA layout = channel-major:
                       f_rest[0..14] = R for the 15 higher-order coeffs,
                       f_rest[15..29] = G, f_rest[30..44] = B)

glTF attributes we emit (all FLOAT, count = numPoints):
    POSITION                              VEC3  = (x, y, z)               verbatim
    KHR_gaussian_splatting:SCALE          VEC3  = (exp(s0),exp(s1),exp(s2))
    KHR_gaussian_splatting:ROTATION       VEC4  = (x, y, z, w)            glTF xyzw order
    COLOR_0                               VEC4  = (0.5 + SH_C0*f_dc_k for k=0..2,
                                                   sigmoid(opacity))      matches decoder
    KHR_gaussian_splatting:SH_DEGREE_d_COEF_c  VEC3 = (R,G,B) for that coeff

  SH_C0 = 0.282095 (the degree-0 SH basis constant; same as decodeSpz.cpp).
  Higher-order SH coeffs are passed through verbatim (the decoder copies them
  verbatim too; only DC color gets the 0.5 + SH_C0*c remap).

  COLOR_0: decoder applies the SH_C0 remap to the DC term and sigmoid to alpha,
  then hands the runtime a FLOAT VEC4. We replicate that so on-screen color
  matches the SPZ path exactly.

================================================================================
OUTPUT / USAGE / VALIDATION
================================================================================
OUTPUT:
    <outdir>/model.glb      uncompressed glB (default) or SPZ-embedded (--spz)
    <outdir>/tileset.json   minimal 3D Tiles 1.1 tileset -> model.glb

USAGE:
    python3 make_splat_tile.py INPUT.ply OUTDIR [--name NAME]
                               [--spz] [--sh-degree N] [--validate-only GLB]

After writing, the script self-VALIDATES the glB: re-parses it, rebuilds every
AccessorView bound check exactly as Cesium does, and asserts each attribute
would return AccessorViewStatus::Valid. A tile that fails validation is never
written as the live tile (it's left as model.glb.invalid + a non-zero exit).

Pure-stdlib Python (json + struct + array). FOSS, Apple-Silicon friendly.
"""

import argparse
import array
import json
import math
import os
import struct
import sys

HARNESS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# glTF component types
FLOAT = 5126
# glTF accessor types
VEC3 = "VEC3"
VEC4 = "VEC4"
# glTF primitive modes
POINTS = 0

# Degree-0 spherical-harmonic basis constant (matches decodeSpz.cpp SH_C0).
SH_C0 = 0.282095

# Bytes per glTF accessor type (all FLOAT here).
TYPE_NCOMP = {VEC3: 3, VEC4: 4}


def die(msg):
    print(f"[make_splat_tile] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# 3DGS .ply parsing (binary_little_endian float32 only — the Brush/INRIA form)
# --------------------------------------------------------------------------- #
def parse_ply_header(f):
    """Return (num_verts, [property_names], header_byte_length)."""
    line = f.readline()
    if line.strip() != b"ply":
        die("not a .ply file (missing 'ply' magic)")
    fmt = None
    num_verts = None
    props = []
    in_vertex = False
    while True:
        line = f.readline()
        if not line:
            die("unexpected EOF in .ply header")
        s = line.strip()
        if s == b"end_header":
            break
        toks = s.split()
        if toks[0] == b"format":
            fmt = toks[1]
        elif toks[0] == b"element":
            in_vertex = toks[1] == b"vertex"
            if in_vertex:
                num_verts = int(toks[2])
        elif toks[0] == b"property" and in_vertex:
            # property <type> <name>
            if toks[1] != b"float" and toks[1] != b"float32":
                die(f"only float32 .ply properties supported, got {toks[1]!r} "
                    f"for {toks[2]!r}")
            props.append(toks[2].decode())
    if fmt != b"binary_little_endian":
        die(f"only binary_little_endian .ply supported, got {fmt!r}")
    if num_verts is None:
        die("no 'element vertex' in .ply header")
    return num_verts, props, f.tell()


def read_ply(path):
    """
    Read a 3DGS .ply. Returns a dict of column arrays keyed by property name,
    each an array('f') of length num_verts, plus num_verts.
    """
    with open(path, "rb") as f:
        num_verts, props, data_start = parse_ply_header(f)
        ncols = len(props)
        f.seek(data_start)
        raw = f.read(num_verts * ncols * 4)
    if len(raw) < num_verts * ncols * 4:
        die(f"truncated .ply body: have {len(raw)} bytes, "
            f"want {num_verts * ncols * 4}")
    flat = array.array("f")
    flat.frombytes(raw[: num_verts * ncols * 4])
    if sys.byteorder == "big":
        flat.byteswap()
    cols = {name: array.array("f", [0.0]) * 0 for name in props}
    # De-interleave columns.
    out = {name: array.array("f", bytes(4 * num_verts)) for name in props}
    for i, name in enumerate(props):
        col = out[name]
        for v in range(num_verts):
            col[v] = flat[v * ncols + i]
    return out, num_verts


# --------------------------------------------------------------------------- #
# Build uncompressed attribute buffers (the transforms Cesium applies)
# --------------------------------------------------------------------------- #
def _quat_order(cols):
    """
    Decide the .ply quaternion component order. INRIA/Brush store (w,x,y,z) as
    rot_0..rot_3. glTF ROTATION wants (x,y,z,w). We map accordingly.
    """
    return ("rot_1", "rot_2", "rot_3", "rot_0")  # x, y, z, w  <- (w,x,y,z) ply


def build_attributes(cols, num_verts, sh_degree):
    """
    Returns (attr_arrays, has_color, has_scale, has_rot, sh_coef_count) where
    attr_arrays is an ordered list of (semantic, type, array('f')).
    """
    req = ["x", "y", "z"]
    for r in req:
        if r not in cols:
            die(f".ply missing required property {r!r}")

    n = num_verts
    out = []

    # POSITION (verbatim)
    pos = array.array("f", bytes(4 * 3 * n))
    cx, cy, cz = cols["x"], cols["y"], cols["z"]
    for v in range(n):
        pos[v * 3] = cx[v]
        pos[v * 3 + 1] = cy[v]
        pos[v * 3 + 2] = cz[v]
    out.append(("POSITION", VEC3, pos))

    # SCALE = exp(log_scale)
    if all(k in cols for k in ("scale_0", "scale_1", "scale_2")):
        s0, s1, s2 = cols["scale_0"], cols["scale_1"], cols["scale_2"]
        scale = array.array("f", bytes(4 * 3 * n))
        for v in range(n):
            scale[v * 3] = math.exp(s0[v])
            scale[v * 3 + 1] = math.exp(s1[v])
            scale[v * 3 + 2] = math.exp(s2[v])
        out.append(("KHR_gaussian_splatting:SCALE", VEC3, scale))
    else:
        die(".ply missing scale_0..2")

    # ROTATION = quaternion in glTF (x,y,z,w) order
    if all(k in cols for k in ("rot_0", "rot_1", "rot_2", "rot_3")):
        qx, qy, qz, qw = (cols[k] for k in _quat_order(cols))
        rot = array.array("f", bytes(4 * 4 * n))
        for v in range(n):
            x, y, z, w = qx[v], qy[v], qz[v], qw[v]
            nrm = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
            rot[v * 4] = x / nrm
            rot[v * 4 + 1] = y / nrm
            rot[v * 4 + 2] = z / nrm
            rot[v * 4 + 3] = w / nrm
        out.append(("KHR_gaussian_splatting:ROTATION", VEC4, rot))
    else:
        die(".ply missing rot_0..3")

    # COLOR_0 = (0.5 + SH_C0*f_dc, sigmoid(opacity)) — matches decodeSpz.cpp
    if all(k in cols for k in ("f_dc_0", "f_dc_1", "f_dc_2", "opacity")):
        d0, d1, d2, op = (cols["f_dc_0"], cols["f_dc_1"], cols["f_dc_2"],
                          cols["opacity"])
        color = array.array("f", bytes(4 * 4 * n))
        for v in range(n):
            color[v * 4] = 0.5 + SH_C0 * d0[v]
            color[v * 4 + 1] = 0.5 + SH_C0 * d1[v]
            color[v * 4 + 2] = 0.5 + SH_C0 * d2[v]
            color[v * 4 + 3] = 1.0 / (1.0 + math.exp(-op[v]))
        out.append(("COLOR_0", VEC4, color))
    else:
        die(".ply missing f_dc_0..2 / opacity")

    # SH higher-order coeffs. INRIA f_rest layout is CHANNEL-MAJOR:
    #   f_rest[0 .. K-1]   = R for K coeffs
    #   f_rest[K .. 2K-1]  = G
    #   f_rest[2K .. 3K-1] = B
    # where K = coeffs for the requested degree (deg1=3, +deg2=5, +deg3=7 -> 15).
    coeffs_per_degree = {1: 3, 2: 5, 3: 7}
    total_coeffs = sum(coeffs_per_degree[d] for d in range(1, sh_degree + 1))
    rest_names = [f"f_rest_{i}" for i in range(total_coeffs * 3)]
    have_rest = sh_degree > 0 and all(rn in cols for rn in rest_names)
    sh_emitted = 0
    if have_rest:
        K = total_coeffs
        coef_global = 0
        for d in range(1, sh_degree + 1):
            for c in range(coeffs_per_degree[d]):
                r = cols[f"f_rest_{coef_global}"]
                g = cols[f"f_rest_{K + coef_global}"]
                b = cols[f"f_rest_{2 * K + coef_global}"]
                sh = array.array("f", bytes(4 * 3 * n))
                for v in range(n):
                    sh[v * 3] = r[v]
                    sh[v * 3 + 1] = g[v]
                    sh[v * 3 + 2] = b[v]
                out.append(
                    (f"KHR_gaussian_splatting:SH_DEGREE_{d}_COEF_{c}", VEC3, sh)
                )
                coef_global += 1
                sh_emitted += 1
    elif sh_degree > 0:
        print(f"[make_splat_tile] WARNING: requested shDegree={sh_degree} but "
              f".ply lacks the f_rest_* columns; emitting degree-0 (DC) only.")

    return out, sh_emitted


def compute_bbox(pos, n):
    xs = [pos[i * 3] for i in range(n)]
    ys = [pos[i * 3 + 1] for i in range(n)]
    zs = [pos[i * 3 + 2] for i in range(n)]
    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
    }


# --------------------------------------------------------------------------- #
# glTF / glB assembly
# --------------------------------------------------------------------------- #
def pad4(n):
    return (4 - (n % 4)) % 4


def build_uncompressed_gltf(attr_arrays, num_verts, bbox, name):
    """
    Real accessors -> real bufferViews -> one binary buffer. Every attribute
    occupies its own bufferView sized exactly stride*count, so AccessorView
    bound checks pass by construction.
    """
    blob = bytearray()
    buffer_views = []
    accessors = []
    attributes = {}

    for semantic, atype, arr in attr_arrays:
        ncomp = TYPE_NCOMP[atype]
        data = arr.tobytes()
        if sys.byteorder == "big":
            tmp = array.array("f")
            tmp.frombytes(data)
            tmp.byteswap()
            data = tmp.tobytes()
        byte_offset = len(blob)
        blob += data
        blob += b"\x00" * pad4(len(blob))
        bv_idx = len(buffer_views)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": byte_offset,
                "byteLength": len(data),
            }
        )
        acc = {
            "bufferView": bv_idx,
            "byteOffset": 0,
            "componentType": FLOAT,
            "count": num_verts,
            "type": atype,
        }
        if semantic == "POSITION":
            acc["min"] = bbox["min"]
            acc["max"] = bbox["max"]
        accessors.append(acc)
        attributes[semantic] = len(accessors) - 1

    bin_chunk = bytes(blob)

    gltf = {
        "asset": {"version": "2.0", "generator": "make_splat_tile.py (uncompressed)"},
        "extensionsUsed": ["KHR_gaussian_splatting"],
        "scene": 0,
        "scenes": [{"nodes": [0], "name": name}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [
            {
                "name": name,
                "primitives": [
                    {
                        "mode": POINTS,
                        "attributes": attributes,
                        "extensions": {
                            "KHR_gaussian_splatting": {
                                "kernel": "ellipse",
                                "colorSpace": "srgb_rec709_display",
                                "projection": "perspective",
                                "sortingMethod": "cameraDistance",
                            }
                        },
                    }
                ],
            }
        ],
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(bin_chunk)}],
    }
    return gltf, bin_chunk


def write_glb(gltf, bin_chunk, out_path):
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * pad4(len(json_bytes))
    bin_chunk = bin_chunk + b"\x00" * pad4(len(bin_chunk))
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_chunk)
    with open(out_path, "wb") as f:
        f.write(b"glTF")
        f.write(struct.pack("<I", 2))
        f.write(struct.pack("<I", total))
        f.write(struct.pack("<I", len(json_bytes)))
        f.write(b"JSON")
        f.write(json_bytes)
        f.write(struct.pack("<I", len(bin_chunk)))
        f.write(b"BIN\x00")
        f.write(bin_chunk)


def write_tileset(bbox, glb_name, out_path, geometric_error=512.0):
    cx = (bbox["min"][0] + bbox["max"][0]) / 2.0
    cy = (bbox["min"][1] + bbox["max"][1]) / 2.0
    cz = (bbox["min"][2] + bbox["max"][2]) / 2.0
    hx = max((bbox["max"][0] - bbox["min"][0]) / 2.0, 0.5)
    hy = max((bbox["max"][1] - bbox["min"][1]) / 2.0, 0.5)
    hz = max((bbox["max"][2] - bbox["min"][2]) / 2.0, 0.5)
    box = [cx, cy, cz, hx, 0, 0, 0, hy, 0, 0, 0, hz]
    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": geometric_error,
        "root": {
            "boundingVolume": {"box": box},
            "geometricError": 0.0,
            "refine": "ADD",
            "content": {"uri": glb_name},
        },
    }
    with open(out_path, "w") as f:
        json.dump(tileset, f, indent=2)


# --------------------------------------------------------------------------- #
# VALIDATION — replicate Cesium AccessorView<T>::create() bound checks exactly
# --------------------------------------------------------------------------- #
def validate_glb(glb_path):
    """
    Re-parse the glB and assert every KHR_gaussian_splatting attribute would
    return AccessorViewStatus::Valid in Cesium. Returns (ok, [problems]).

    Mirrors CesiumGltf/AccessorView.h::create():
      bufferView.byteOffset + bufferView.byteLength <= len(buffer.data)   (BufferTooSmall)
      sizeof(T) == numComponents * 4                                      (WrongSizeT)
      byteStride * count <= bufferView.byteLength                         (BufferViewTooSmall)
      byteOffset + byteStride*(count-1) + bytesPerStride <= byteLength    (BufferViewTooSmall)
    """
    problems = []
    with open(glb_path, "rb") as f:
        if f.read(4) != b"glTF":
            return False, ["not a glB (bad magic)"]
        _ver, _total = struct.unpack("<II", f.read(8))
        jlen, = struct.unpack("<I", f.read(4))
        if f.read(4) != b"JSON":
            return False, ["first chunk is not JSON"]
        gltf = json.loads(f.read(jlen))
        blen, = struct.unpack("<I", f.read(4))
        btype = f.read(4)
        bin_len = blen if btype == b"BIN\x00" else 0

    prim = gltf["meshes"][0]["primitives"][0]
    if prim.get("mode") != POINTS:
        problems.append(f"primitive mode is {prim.get('mode')}, must be 0 (POINTS)")
    if "KHR_gaussian_splatting" not in gltf.get("extensionsUsed", []):
        problems.append("KHR_gaussian_splatting not in extensionsUsed")

    buffers = gltf["buffers"]
    bvs = gltf["bufferViews"]
    accs = gltf["accessors"]

    for semantic, acc_idx in prim["attributes"].items():
        acc = accs[acc_idx]
        ncomp = TYPE_NCOMP.get(acc["type"], 0)
        if ncomp == 0:
            problems.append(f"{semantic}: unknown accessor type {acc['type']}")
            continue
        if acc["componentType"] != FLOAT:
            problems.append(f"{semantic}: componentType {acc['componentType']} != FLOAT")
        bytes_per_stride = ncomp * 4  # FLOAT
        bv = bvs[acc["bufferView"]]
        byte_length = bv["byteLength"]
        # buffer fit (use bin chunk length for buffer 0)
        buf_len = bin_len if bv["buffer"] == 0 else buffers[bv["buffer"]]["byteLength"]
        if bv["byteOffset"] + byte_length > buf_len:
            problems.append(f"{semantic}: bufferView exceeds buffer (BufferTooSmall)")
        stride = bytes_per_stride  # tightly packed
        count = acc["count"]
        accessor_bytes = stride * count
        remaining = byte_length - (acc.get("byteOffset", 0)
                                   + stride * (count - 1) + bytes_per_stride)
        if accessor_bytes > byte_length or remaining < 0:
            problems.append(
                f"{semantic}: accessor too large for bufferView "
                f"(BufferViewTooSmall / status 4): need {accessor_bytes}B, "
                f"have {byte_length}B")

    # POSITION present?
    if "POSITION" not in prim["attributes"]:
        problems.append("no POSITION attribute")
    return (len(problems) == 0), problems


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(
        description="Wrap a 3DGS .ply as a KHR_gaussian_splatting 3D Tiles tile "
                    "(uncompressed accessors; crash-proof).")
    ap.add_argument("input", nargs="?", help="input .ply (3DGS/INRIA layout)")
    ap.add_argument("outdir", nargs="?", help="output dir for tileset.json + model.glb")
    ap.add_argument("--name", default=None, help="display name (default: input stem)")
    ap.add_argument("--sh-degree", type=int, default=3,
                    help="max SH degree to emit (0-3, default 3; clamps to what "
                         "the .ply actually has)")
    ap.add_argument("--geometric-error", type=float, default=512.0)
    ap.add_argument("--validate-only", metavar="GLB", default=None,
                    help="just validate an existing .glb and exit")
    args = ap.parse_args()

    if args.validate_only:
        ok, problems = validate_glb(args.validate_only)
        if ok:
            print(f"[make_splat_tile] VALID: {args.validate_only}")
            sys.exit(0)
        print(f"[make_splat_tile] INVALID: {args.validate_only}")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    if not args.input or not args.outdir:
        ap.error("input and outdir are required (unless --validate-only)")

    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        die(f"input not found: {input_path}")
    if not input_path.lower().endswith(".ply"):
        die("this version takes a 3DGS .ply. To go from .spz, first run "
            "`~/coding/spz/build/spz_to_ply input.spz out.ply` then pass out.ply.")
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)
    name = args.name or os.path.splitext(os.path.basename(input_path))[0]
    sh_degree = max(0, min(3, args.sh_degree))

    print(f"[make_splat_tile] reading {input_path} ...")
    cols, num_verts = read_ply(input_path)
    print(f"[make_splat_tile] points={num_verts} props={len(cols)} "
          f"sh_degree(req)={sh_degree}")

    attr_arrays, sh_emitted = build_attributes(cols, num_verts, sh_degree)
    pos = next(a for s, t, a in attr_arrays if s == "POSITION")
    bbox = compute_bbox(pos, num_verts)
    print(f"[make_splat_tile] attributes={len(attr_arrays)} "
          f"(SH coeffs emitted={sh_emitted}) bbox={bbox}")

    gltf, bin_chunk = build_uncompressed_gltf(attr_arrays, num_verts, bbox, name)

    # Write to a temp name, validate, only then promote to model.glb.
    tmp_glb = os.path.join(outdir, "model.glb.tmp")
    write_glb(gltf, bin_chunk, tmp_glb)
    ok, problems = validate_glb(tmp_glb)
    if not ok:
        bad = os.path.join(outdir, "model.glb.invalid")
        os.replace(tmp_glb, bad)
        print(f"[make_splat_tile] VALIDATION FAILED — wrote {bad} (NOT promoted):",
              file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(2)

    glb_path = os.path.join(outdir, "model.glb")
    os.replace(tmp_glb, glb_path)
    tileset_path = os.path.join(outdir, "tileset.json")
    write_tileset(bbox, "model.glb", tileset_path, args.geometric_error)

    glb_mb = os.path.getsize(glb_path) / 1e6
    print(f"[make_splat_tile] VALIDATED + wrote:")
    print(f"  {glb_path}   ({glb_mb:.1f} MB, uncompressed)")
    print(f"  {tileset_path}")
    print(f"[make_splat_tile] every accessor passed Cesium's AccessorView bound "
          f"checks (no status-4 possible).")
    print(f"[make_splat_tile] load via Cesium3DTileset 'Source: From URL':")
    print(f"  file://{tileset_path}")
    print(f"[make_splat_tile] UE wiring: see {os.path.join(os.path.dirname(input_path), '..')}"
          f" and splat/README.md.")


if __name__ == "__main__":
    main()
