"""Checks a binary glTF (.glb) before the app keeps it, and reads what mesh it holds.

A file with only the right extension is refused (Codex finding N05). This reads the header and
the chunks, parses the JSON, and walks every mesh primitive: its POSITION accessor and its
indices must point inside the file's own binary chunk. Nothing in the file is executed.
"""
import json
import math
import struct

GLB_MAGIC = b"glTF"
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942
MAX_BYTES = 2 * 1024 ** 3
_COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
_TYPE_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
_TRIANGLES, _STRIP, _FAN = 4, 5, 6


def glb_stats(path):
    """Mesh numbers for a valid .glb: vertices, faces, bounding box. Raises ValueError with a plain reason."""
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12:
            raise ValueError("the file is too short to be a .glb")
        magic, _version, length = struct.unpack("<4sII", head)
        if magic != GLB_MAGIC:
            raise ValueError("the file has no glTF header")
        if length > MAX_BYTES:
            raise ValueError("the file is larger than 2 GB")
        data = head + f.read(length)
    return glb_stats_bytes(data)


def _chunks(data):
    if len(data) < 20:
        raise ValueError("the file is too short to be a .glb")
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != GLB_MAGIC:
        raise ValueError("the file has no glTF header")
    if version != 2:
        raise ValueError(f"glTF container version {version}, not 2")
    if length != len(data):
        raise ValueError("the length in the header does not match the file")
    off, doc, binary = 12, None, None
    while off < length:
        if off + 8 > length:
            raise ValueError("a chunk header runs past the end of the file")
        size, kind = struct.unpack_from("<II", data, off)
        off += 8
        if off + size > length:
            raise ValueError("a chunk runs past the end of the file")
        if kind == CHUNK_JSON and doc is None:
            doc = data[off:off + size]
        elif kind == CHUNK_BIN and binary is None:
            binary = data[off:off + size]
        off += size
    if doc is None:
        raise ValueError("the file has no JSON chunk")
    try:
        parsed = json.loads(doc.decode("utf-8").rstrip(" \x00"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("the JSON chunk is not valid JSON")
    if not isinstance(parsed, dict):
        raise ValueError("the JSON chunk is not a glTF object")
    return parsed, binary or b""


def _index(rows, i, what):
    if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(rows) or not isinstance(rows[i], dict):
        raise ValueError(f"a primitive points at a missing {what}")
    return rows[i]


def _accessor(doc, binary, i, need_type=None):
    acc = _index(doc.get("accessors") or [], i, "accessor")
    count = acc.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError("an accessor has no elements")
    kind, comp = acc.get("type"), acc.get("componentType")
    if kind not in _TYPE_COUNT or comp not in _COMPONENT_BYTES:
        raise ValueError("an accessor has an unknown element type")
    if need_type and kind != need_type:
        raise ValueError(f"an accessor is {kind}, not {need_type}")
    if "bufferView" not in acc:
        return acc  # all zeros by the spec; nothing to read past
    view = _index(doc.get("bufferViews") or [], acc["bufferView"], "buffer view")
    buf = _index(doc.get("buffers") or [], view.get("buffer"), "buffer")
    if buf.get("uri") is not None:
        raise ValueError("the mesh data points outside the file")
    v_off, v_len = view.get("byteOffset", 0), view.get("byteLength")
    a_off = acc.get("byteOffset", 0)
    if not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in (v_off, v_len, a_off)):
        raise ValueError("a buffer view has a bad offset or length")
    if v_off + v_len > len(binary):
        raise ValueError("a buffer view runs past the binary chunk")
    elem = _TYPE_COUNT[kind] * _COMPONENT_BYTES[comp]
    stride = view.get("byteStride") or elem
    if not isinstance(stride, int) or stride < elem:
        raise ValueError("a buffer view has a bad stride")
    if a_off + stride * (count - 1) + elem > v_len:
        raise ValueError("an accessor runs past its buffer view")
    return acc


def _box(acc):
    lo, hi = acc.get("min"), acc.get("max")
    ok = (isinstance(lo, list) and isinstance(hi, list) and len(lo) == 3 and len(hi) == 3
          and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in lo + hi))
    return (lo, hi) if ok else None


def glb_stats_bytes(data):
    doc, binary = _chunks(data)
    version = str((doc.get("asset") or {}).get("version") or "")
    if version.split(".")[0] != "2":
        raise ValueError("asset.version is not 2.x")
    meshes = doc.get("meshes")
    if not isinstance(meshes, list) or not meshes:
        raise ValueError("the file has no mesh")
    vertices = faces = 0
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for mesh in meshes:
        prims = mesh.get("primitives") if isinstance(mesh, dict) else None
        if not isinstance(prims, list) or not prims:
            raise ValueError("a mesh has no primitives")
        for prim in prims:
            if not isinstance(prim, dict):
                raise ValueError("a mesh primitive is not an object")
            pos = _accessor(doc, binary, (prim.get("attributes") or {}).get("POSITION"), "VEC3")
            vertices += pos["count"]
            n = _accessor(doc, binary, prim["indices"], "SCALAR")["count"] if "indices" in prim else pos["count"]
            mode = prim.get("mode", _TRIANGLES)
            if mode == _TRIANGLES:
                faces += n // 3
            elif mode in (_STRIP, _FAN):
                faces += max(0, n - 2)
            box = _box(pos)
            if box:
                lo = [min(a, b) for a, b in zip(lo, box[0])]
                hi = [max(a, b) for a, b in zip(hi, box[1])]
    if faces < 1:
        raise ValueError("the mesh has no triangles")
    bbox = {"min": lo, "max": hi} if all(math.isfinite(x) for x in lo + hi) else None
    return {"vertices": vertices, "faces": faces, "bbox": bbox, "meshes": len(meshes), "bytes": len(data)}
