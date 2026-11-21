extends RefCounted

# Reads the committed glTF files and PNG pictures. Headless runs do not
# need the .godot import cache for the beach.

const FLOAT := 5126
const UINT := 5125


static func load_nodes(gltf_path: String) -> Dictionary:
    if not FileAccess.file_exists(gltf_path):
        push_error("Missing glTF: " + gltf_path)
        return {}
    var doc = JSON.parse_string(FileAccess.get_file_as_string(gltf_path))
    if typeof(doc) != TYPE_DICTIONARY:
        push_error("glTF is not a JSON object: " + gltf_path)
        return {}
    var buffer := _read_buffer(gltf_path, doc)
    var views: Array = doc.get("bufferViews", [])
    var accessors: Array = doc.get("accessors", [])
    var meshes: Array = doc.get("meshes", [])
    var found := {}
    for node in doc.get("nodes", []):
        if typeof(node) != TYPE_DICTIONARY:
            continue
        var name := str(node.get("name", ""))
        var entry := {"translation": Vector3.ZERO, "mesh": null}
        var translation = node.get("translation", null)
        if typeof(translation) == TYPE_ARRAY and translation.size() >= 3:
            entry.translation = Vector3(float(translation[0]), float(translation[1]), float(translation[2]))
        if node.has("mesh"):
            var index := int(node.get("mesh"))
            if index >= 0 and index < meshes.size():
                entry.mesh = _build_mesh(meshes[index], buffer, views, accessors)
        found[name] = entry
    return found


static func texture_from_file(res_path: String) -> Texture2D:
    if res_path == "" or not FileAccess.file_exists(res_path):
        return null
    var image := Image.load_from_file(ProjectSettings.globalize_path(res_path))
    if image == null or image.is_empty():
        push_error("Could not read picture: " + res_path)
        return null
    return ImageTexture.create_from_image(image)


static func shader_from_file(res_path: String) -> Shader:
    var shader := Shader.new()
    shader.code = FileAccess.get_file_as_string(res_path)
    return shader


static func _read_buffer(gltf_path: String, doc: Dictionary) -> PackedByteArray:
    var buffers: Array = doc.get("buffers", [])
    if buffers.is_empty() or typeof(buffers[0]) != TYPE_DICTIONARY:
        return PackedByteArray()
    var uri := str(buffers[0].get("uri", ""))
    var path := gltf_path.get_base_dir().path_join(uri)
    if not FileAccess.file_exists(path):
        push_error("Missing glTF buffer: " + path)
        return PackedByteArray()
    return FileAccess.get_file_as_bytes(path)


static func _build_mesh(mesh_def, buffer: PackedByteArray, views: Array, accessors: Array) -> ArrayMesh:
    var mesh := ArrayMesh.new()
    if typeof(mesh_def) != TYPE_DICTIONARY:
        return mesh
    var primitives: Array = mesh_def.get("primitives", [])
    if primitives.is_empty() or typeof(primitives[0]) != TYPE_DICTIONARY:
        return mesh
    var primitive: Dictionary = primitives[0]
    var attributes: Dictionary = primitive.get("attributes", {})
    var positions := _vec3(_accessor(accessors, attributes.get("POSITION", -1)), buffer, views)
    var normals := _vec3(_accessor(accessors, attributes.get("NORMAL", -1)), buffer, views)
    var uvs := _vec2(_accessor(accessors, attributes.get("TEXCOORD_0", -1)), buffer, views)
    var indices := _indices(_accessor(accessors, primitive.get("indices", -1)), buffer, views)
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = positions
    arrays[Mesh.ARRAY_NORMAL] = normals
    arrays[Mesh.ARRAY_TEX_UV] = uvs
    arrays[Mesh.ARRAY_INDEX] = indices
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    return mesh


static func _accessor(accessors: Array, index) -> Dictionary:
    var at := int(index)
    if at < 0 or at >= accessors.size() or typeof(accessors[at]) != TYPE_DICTIONARY:
        return {}
    return accessors[at]


static func _view_start(accessor: Dictionary, views: Array) -> int:
    if accessor.is_empty():
        return -1
    var view_index := int(accessor.get("bufferView", -1))
    if view_index < 0 or view_index >= views.size() or typeof(views[view_index]) != TYPE_DICTIONARY:
        return -1
    var view: Dictionary = views[view_index]
    return int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))


static func _vec3(accessor: Dictionary, buffer: PackedByteArray, views: Array) -> PackedVector3Array:
    var out := PackedVector3Array()
    var start := _view_start(accessor, views)
    if start < 0 or int(accessor.get("componentType", 0)) != FLOAT:
        return out
    var count := int(accessor.get("count", 0))
    out.resize(count)
    for index in count:
        var offset := start + index * 12
        out[index] = Vector3(buffer.decode_float(offset), buffer.decode_float(offset + 4), buffer.decode_float(offset + 8))
    return out


static func _vec2(accessor: Dictionary, buffer: PackedByteArray, views: Array) -> PackedVector2Array:
    var out := PackedVector2Array()
    var start := _view_start(accessor, views)
    if start < 0 or int(accessor.get("componentType", 0)) != FLOAT:
        return out
    var count := int(accessor.get("count", 0))
    out.resize(count)
    for index in count:
        var offset := start + index * 8
        out[index] = Vector2(buffer.decode_float(offset), buffer.decode_float(offset + 4))
    return out


static func _indices(accessor: Dictionary, buffer: PackedByteArray, views: Array) -> PackedInt32Array:
    var out := PackedInt32Array()
    var start := _view_start(accessor, views)
    if start < 0 or int(accessor.get("componentType", 0)) != UINT:
        return out
    var count := int(accessor.get("count", 0))
    out.resize(count)
    for index in count:
        out[index] = buffer.decode_u32(start + index * 4)
    return out
