#!/usr/bin/env python3
"""Write the beach level and the Stage 1 plate as glTF 2.0.

Godot plays these files. The meshes are not stored as a Godot-only scene.
"""

import json
import math
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLATE_SPEC = os.path.join(ROOT, "data", "plate.json")
LEVEL_PATH = os.path.join(ROOT, "assets", "beach", "level.gltf")
PLATE_PATH = os.path.join(ROOT, "assets", "plates", "plate.gltf")

FLOAT = 5126
UINT = 5125
ARRAY_BUFFER = 34962
ELEMENT_BUFFER = 34963


def smoothstep(edge0, edge1, value):
    span = edge1 - edge0
    if span == 0:
        return 0.0
    t = max(0.0, min(1.0, (value - edge0) / span))
    return t * t * (3.0 - 2.0 * t)


def terrain_height(x, z):
    inland = max(0.0, min(1.0, (z - 0.5) / 24.0))
    dune = math.sin(x * 0.16) * 0.32 * inland
    dune += math.sin(x * 0.05 + z * 0.19) * 0.7 * inland * inland
    shelf = smoothstep(-1.0, 7.0, z) * 0.62
    return shelf + dune


def terrain_normal(x, z):
    left = terrain_height(x - 0.45, z)
    right = terrain_height(x + 0.45, z)
    down = terrain_height(x, z - 0.45)
    up = terrain_height(x, z + 0.45)
    nx, ny, nz = left - right, 0.9, down - up
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / length, ny / length, nz / length)


class GltfWriter:
    def __init__(self):
        self.buffer = bytearray()
        self.views = []
        self.accessors = []
        self.meshes = []
        self.nodes = []
        self.materials = []
        self.images = []
        self.textures = []
        self.samplers = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]

    def _align(self):
        while len(self.buffer) % 4:
            self.buffer.append(0)

    def _view(self, data, target):
        self._align()
        offset = len(self.buffer)
        self.buffer.extend(data)
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(data), "target": target}
        index = len(self.views)
        self.views.append(view)
        return index

    def add_vec3(self, values):
        flat = [component for triple in values for component in triple]
        view = self._view(struct.pack("<" + "f" * len(flat), *flat), ARRAY_BUFFER)
        lows = [min(item[axis] for item in values) for axis in range(3)]
        highs = [max(item[axis] for item in values) for axis in range(3)]
        accessor = {
            "bufferView": view,
            "componentType": FLOAT,
            "count": len(values),
            "type": "VEC3",
            "min": lows,
            "max": highs,
        }
        index = len(self.accessors)
        self.accessors.append(accessor)
        return index

    def add_vec2(self, values):
        flat = [component for pair in values for component in pair]
        view = self._view(struct.pack("<" + "f" * len(flat), *flat), ARRAY_BUFFER)
        accessor = {
            "bufferView": view,
            "componentType": FLOAT,
            "count": len(values),
            "type": "VEC2",
        }
        index = len(self.accessors)
        self.accessors.append(accessor)
        return index

    def add_indices(self, values):
        view = self._view(struct.pack("<" + "I" * len(values), *values), ELEMENT_BUFFER)
        accessor = {
            "bufferView": view,
            "componentType": UINT,
            "count": len(values),
            "type": "SCALAR",
        }
        index = len(self.accessors)
        self.accessors.append(accessor)
        return index

    def add_mesh(self, name, positions, normals, uvs, indices, material):
        mesh = {
            "name": name,
            "primitives": [{
                "attributes": {
                    "POSITION": self.add_vec3(positions),
                    "NORMAL": self.add_vec3(normals),
                    "TEXCOORD_0": self.add_vec2(uvs),
                },
                "indices": self.add_indices(indices),
                "material": material,
            }],
        }
        index = len(self.meshes)
        self.meshes.append(mesh)
        return index

    def add_material(self, name, color, roughness, texture=None, alpha=None, double_sided=False, extras=None, occlusion=None):
        pbr = {
            "baseColorFactor": color,
            "metallicFactor": 0.0,
            "roughnessFactor": roughness,
        }
        if texture is not None:
            pbr["baseColorTexture"] = {"index": texture}
        material = {"name": name, "pbrMetallicRoughness": pbr, "doubleSided": double_sided}
        if alpha:
            material["alphaMode"] = alpha
            material["alphaCutoff"] = 0.45
        if occlusion is not None:
            material["occlusionTexture"] = {"index": occlusion, "strength": 0.0}
        if extras:
            material["extras"] = extras
        index = len(self.materials)
        self.materials.append(material)
        return index

    def add_image(self, uri):
        image = len(self.images)
        self.images.append({"uri": uri})
        texture = len(self.textures)
        self.textures.append({"sampler": 0, "source": image})
        return texture

    def add_node(self, name, mesh=None, translation=None, extras=None):
        node = {"name": name}
        if mesh is not None:
            node["mesh"] = mesh
        if translation is not None:
            node["translation"] = list(translation)
        if extras:
            node["extras"] = extras
        index = len(self.nodes)
        self.nodes.append(node)
        return index

    def pack(self, bin_name, extras):
        document = {
            "asset": {
                "version": "2.0",
                "generator": "stillwater export_beach_gltf.py",
                "extras": extras,
            },
            "scene": 0,
            "scenes": [{"name": "Beach", "nodes": list(range(len(self.nodes)))}],
            "nodes": self.nodes,
            "meshes": self.meshes,
            "materials": self.materials,
            "accessors": self.accessors,
            "bufferViews": self.views,
            "buffers": [{"uri": bin_name, "byteLength": len(self.buffer)}],
        }
        if self.images:
            document["images"] = self.images
            document["textures"] = self.textures
            document["samplers"] = self.samplers
        return document, bytes(self.buffer)


def grid_mesh(cells_x, cells_z, point_at):
    positions = []
    normals = []
    uvs = []
    indices = []
    for z in range(cells_z + 1):
        for x in range(cells_x + 1):
            fx = x / cells_x
            fz = z / cells_z
            position, normal = point_at(fx, fz)
            positions.append(position)
            normals.append(normal)
            uvs.append((fx, fz))
    stride = cells_x + 1
    for z in range(cells_z):
        for x in range(cells_x):
            a = z * stride + x
            b = a + 1
            c = a + stride
            d = c + 1
            indices.extend((a, c, b, b, c, d))
    return positions, normals, uvs, indices


def build_terrain():
    def point_at(fx, fz):
        x = -24.0 + fx * 48.0
        z = -3.0 + fz * 36.0
        return (x, terrain_height(x, z), z), terrain_normal(x, z)

    return grid_mesh(40, 36, point_at)


def build_ocean():
    def point_at(fx, fz):
        x = (fx - 0.5) * 78.0
        z = -16.0 + (fz - 0.5) * 46.0
        wave = math.sin(x * 0.35) * 0.04 + math.sin(z * 0.22) * 0.03
        return (x, 0.2 + wave, z), (0.0, 1.0, 0.0)

    return grid_mesh(48, 28, point_at)


def build_navmesh():
    corners = ((-16.0, 6.0), (16.0, 6.0), (16.0, 22.0), (-16.0, 22.0))
    positions = [(x, terrain_height(x, z) + 0.2, z) for x, z in corners]
    normals = [(0.0, 1.0, 0.0)] * 4
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    indices = [0, 2, 1, 0, 3, 2]
    return positions, normals, uvs, indices


def build_plate(width, height):
    half = width * 0.5
    positions = [
        (-half, 0.0, 0.0),
        (half, 0.0, 0.0),
        (half, height, 0.0),
        (-half, height, 0.0),
    ]
    normals = [(0.0, 0.0, 1.0)] * 4
    # glTF V is 0 at the top of the image. Godot flips it on import.
    uvs = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
    indices = [0, 1, 2, 0, 2, 3]
    return positions, normals, uvs, indices


def write_pair(path, document, blob, buffer_name):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    document["buffers"][0]["uri"] = buffer_name
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2)
        handle.write("\n")
    buffer_path = os.path.join(folder, buffer_name)
    with open(buffer_path, "wb") as handle:
        handle.write(blob)
    print("wrote", os.path.relpath(path, ROOT))
    print("wrote", os.path.relpath(buffer_path, ROOT))


def export_plate(spec):
    writer = GltfWriter()
    color = writer.add_image("stand_in.png")
    depth = writer.add_image("stand_in_depth.png")
    material = writer.add_material(
        "Plate",
        [1.0, 1.0, 1.0, 1.0],
        0.72,
        texture=color,
        alpha="MASK",
        double_sided=True,
        occlusion=depth,
        extras={
            "stillwater_stage": 1,
            "finished_look": False,
            "sfw_mode": False,
            "depthTexture": "stand_in_depth.png",
        },
    )
    mesh = writer.add_mesh("Plate", *build_plate(float(spec["width"]), float(spec["height"])), material)
    writer.add_node("Plate", mesh=mesh, extras={"finished_look": False, "stage": 1})
    document, blob = writer.pack("plate.bin", {
        "stillwater": "stage 1 plate",
        "finished_look": False,
        "note": "Shared glTF. Godot plays this file. It is not a Godot-only scene.",
    })
    write_pair(PLATE_PATH, document, blob, "plate.buffer")


def export_level(spec):
    writer = GltfWriter()
    sand = writer.add_material("Sand", [0.79, 0.67, 0.46, 1.0], 0.92)
    water = writer.add_material("Water", [0.08, 0.35, 0.45, 1.0], 0.18, double_sided=True)
    plate_color = writer.add_image("../plates/stand_in.png")
    plate_mat = writer.add_material(
        "Plate",
        [1.0, 1.0, 1.0, 1.0],
        0.72,
        texture=plate_color,
        alpha="MASK",
        double_sided=True,
        extras={"stillwater_stage": 1, "finished_look": False, "sfw_mode": False},
    )
    hidden = writer.add_material("Navmesh", [0.2, 0.55, 0.4, 1.0], 1.0)
    terrain = writer.add_mesh("Terrain", *build_terrain(), sand)
    ocean = writer.add_mesh("Ocean", *build_ocean(), water)
    navmesh = writer.add_mesh("Navmesh", *build_navmesh(), hidden)
    plate = writer.add_mesh("Plate", *build_plate(float(spec["width"]), float(spec["height"])), plate_mat)
    feet_y = terrain_height(0.0, 14.0)
    writer.add_node("Terrain", mesh=terrain)
    writer.add_node("Ocean", mesh=ocean)
    writer.add_node("Navmesh", mesh=navmesh, extras={"walkable": True})
    writer.add_node("PlayerStart", translation=(0.0, feet_y, 14.0))
    writer.add_node(
        "Plate",
        mesh=plate,
        translation=(0.0, feet_y, 14.0),
        extras={"finished_look": False, "stage": 1, "sfw_mode": False},
    )
    document, blob = writer.pack("level.bin", {
        "stillwater": "beach level",
        "note": "Shared glTF. Godot plays this file. It is not a Godot-only scene.",
    })
    write_pair(LEVEL_PATH, document, blob, "level.buffer")


def main():
    with open(PLATE_SPEC, encoding="utf-8") as handle:
        spec = json.load(handle)
    export_plate(spec)
    export_level(spec)


if __name__ == "__main__":
    main()
