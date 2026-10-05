"""Independently inspect saved artifacts in a fresh background Blender process.

This script never imports the builder or constructs model geometry. Example:
  blender --background --factory-startup --python-exit-code 1 \
    --python tests/verify_artifacts.py -- --blend bear_basin.blend \
    --manifest bear_basin.json --glb viewer/bear_basin.glb \
    --receipt artifact-verification.json
"""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct
import sys


def finite(values):
    return all(isinstance(value, (int, float)) and math.isfinite(value) for value in values)


def close(left, right, tolerance=1e-6):
    return len(left) == len(right) and all(
        math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)
        for a, b in zip(left, right)
    )


def bounds(points):
    """Axis-aligned bounds of already-transformed vertices, as min XYZ + max XYZ."""
    lower, upper, count = [math.inf] * 3, [-math.inf] * 3, 0
    for point in points:
        for axis in range(3):
            lower[axis] = min(lower[axis], point[axis])
            upper[axis] = max(upper[axis], point[axis])
        count += 1
    if not count:
        raise ValueError("Cannot measure an empty component")
    return lower + upper


def gltf_transform(node):
    """glTF matrices are column-major; TRS uses XYZW quaternion ordering."""
    from mathutils import Matrix, Quaternion, Vector

    if "matrix" in node:
        values = node["matrix"]
        if len(values) != 16 or not finite(values):
            raise ValueError("Invalid glTF node matrix")
        return Matrix([[values[column * 4 + row] for column in range(4)] for row in range(4)])
    translation = node.get("translation", [0, 0, 0])
    rotation = node.get("rotation", [0, 0, 0, 1])
    scale = node.get("scale", [1, 1, 1])
    if not (len(translation) == 3 and len(rotation) == 4 and len(scale) == 3
            and finite(translation + rotation + scale)):
        raise ValueError("Invalid glTF node TRS transform")
    quaternion = Quaternion((rotation[3], *rotation[:3]))
    return (Matrix.Translation(Vector(translation))
            @ quaternion.to_matrix().to_4x4() @ Matrix.Diagonal((*scale, 1)))


def parse_glb(path):
    """Read actual GLB chunks, including binary position buffers, without the exporter."""
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("GLB is truncated")
    magic, version, length = struct.unpack_from("<4sII", data)
    if (magic, version, length) != (b"glTF", 2, len(data)):
        raise ValueError("Invalid GLB header")
    offset, chunks = 12, []
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("Truncated GLB chunk header")
        size, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        if size % 4 or offset + size > len(data):
            raise ValueError("Invalid GLB chunk length")
        chunks.append((kind, data[offset:offset + size]))
        offset += size
    if not chunks or chunks[0][0] != 0x4E4F534A:
        raise ValueError("GLB first chunk must be JSON")
    if Counter(kind for kind, _ in chunks)[0x4E4F534A] != 1:
        raise ValueError("GLB must contain one JSON chunk")
    binary = [payload for kind, payload in chunks if kind == 0x004E4942]
    if len(binary) != 1:
        raise ValueError("GLB must contain one embedded binary chunk")
    document = json.loads(chunks[0][1])
    if document.get("asset", {}).get("version") != "2.0":
        raise ValueError("GLB JSON must declare glTF 2.0")
    buffers = document.get("buffers", [])
    if len(buffers) != 1 or "uri" in buffers[0]:
        raise ValueError("GLB must be self-contained with one embedded buffer")
    if not 0 <= len(binary[0]) - buffers[0]["byteLength"] <= 3:
        raise ValueError("GLB buffer length does not match binary chunk")
    return document, binary[0]


def check_artifacts(bpy, args):
    from mathutils import Matrix, Vector

    errors, checks = [], {}

    def require(condition, message):
        if not condition:
            errors.append(message)

    def same_names(actual, expected, label):
        missing, extra = sorted(expected - actual), sorted(actual - expected)
        require(not missing and not extra,
                f"{label}: missing {missing[:12]} ({len(missing)} total); "
                f"extra {extra[:12]} ({len(extra)} total)")

    data = json.loads(args.manifest.read_text())
    require(data.get("schema_version") == 2, "Manifest schema must be version 2")
    components = data["components"]
    require(bool(components), "Manifest has no components")
    ids = [component["id"] for component in components.values()]
    require(all(isinstance(value, str) and value for value in ids),
            "Manifest component IDs must be nonempty strings")
    require(len(ids) == len(set(ids)), "Manifest component IDs are not unique")
    validation = data["validation"]
    require(validation.get("status") == "passed", "Manifest validation has not passed")
    require(not validation.get("errors"), "Manifest record errors are present")
    mesh_check = validation["mesh"]
    require(mesh_check.get("checked") == len(data["fasteners"]),
            "Manifest mesh check count differs from fastener count")
    require(mesh_check.get("unchecked") == 0 and mesh_check.get("failed") == 0,
            "Manifest has unchecked or failed mesh checks")

    bpy.ops.wm.open_mainfile(filepath=str(args.blend.resolve()))
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    require(scene.unit_settings.system == "METRIC"
            and math.isclose(scene.unit_settings.scale_length, 1),
            "Saved blend must use metres")
    objects = {obj.name: obj for obj in scene.objects
               if obj.type in {"MESH", "CURVE", "SURFACE", "FONT"} and obj.name != "Ground"}
    same_names(set(objects), set(components), "Saved scene components")
    scene_ids, scene_mass, curve_names, scene_bounds = [], [], set(), {}
    vertex_count = 0
    for name, obj in objects.items():
        scene_ids.append(obj.get("part_id"))
        require(len(obj.modifiers) == 0, f"{name}: unapplied modifiers")
        transform = [float(value) for row in obj.matrix_world for value in row]
        require(finite(transform), f"{name}: nonfinite saved transform")
        mass = obj.get("mass_kg")
        valid_mass = isinstance(mass, (int, float)) and math.isfinite(mass) and mass >= 0
        require(valid_mass, f"{name}: missing, negative or nonfinite scene mass")
        if valid_mass:
            scene_mass.append(mass)
        if obj.type == "MESH":
            require(len(obj.data.vertices) > 0 and len(obj.data.polygons) > 0,
                    f"{name}: empty saved mesh")
            vertex_count += len(obj.data.vertices)
            require(all(finite(vertex.co) for vertex in obj.data.vertices),
                    f"{name}: nonfinite saved vertices")
        elif obj.type == "CURVE":
            curve_names.add(name)
            points = [point.co for spline in obj.data.splines
                      for point in (spline.bezier_points if spline.type == "BEZIER" else spline.points)]
            require(bool(points) and all(finite(point) for point in points),
                    f"{name}: empty or nonfinite saved curve")
        # Temporary evaluated meshes include the actual bevelled curve surface.
        # to_mesh_clear releases the temporary data; the saved scene is not edited.
        evaluated = obj.evaluated_get(depsgraph)
        evaluated_mesh = evaluated.to_mesh()
        try:
            if evaluated_mesh is None:
                errors.append(f"{name}: saved component cannot be evaluated as a mesh")
            else:
                scene_bounds[name] = bounds(evaluated.matrix_world @ vertex.co
                                            for vertex in evaluated_mesh.vertices)
                require(finite(scene_bounds[name]), f"{name}: nonfinite saved world bounds")
        finally:
            evaluated.to_mesh_clear()
        component = components.get(name)
        if component is None:
            continue
        expected_transform = [value for row in component["transform"] for value in row]
        require(finite(expected_transform) and close(transform, expected_transform),
                f"{name}: saved transform differs from manifest")
        for scene_key, manifest_key in (("part_id", "id"), ("code", "code"),
                                        ("kind", "kind"), ("mass_source", "mass_source")):
            require(obj.get(scene_key) == component[manifest_key],
                    f"{name}: scene {scene_key} differs from manifest")
        require(valid_mass and close([mass], [component["mass_kg"]]),
                f"{name}: saved mass differs from manifest")
        group = obj.users_collection[0].name if obj.users_collection else ""
        require(group == component["group"], f"{name}: saved collection differs from manifest")
    require(all(isinstance(value, str) and value for value in scene_ids),
            "Saved scene component IDs must be nonempty strings")
    require(len(scene_ids) == len(set(scene_ids)), "Saved scene component IDs are not unique")
    manifest_mass = math.fsum(component["mass_kg"] for component in components.values())
    require(close([math.fsum(scene_mass)], [manifest_mass]), "Saved and manifest mass sums differ")
    require(close([manifest_mass], [data["mass"]["total_kg"]]), "Manifest total mass does not sum")
    fastener_ids = {item["id"] for item in data["fasteners"]}
    require(len(fastener_ids) == len(data["fasteners"]), "Manifest fastener IDs are not unique")
    require(fastener_ids <= set(scene_ids), "Saved scene is missing fastener identities")
    require(sum(obj.get("code") in {"NM815", "BM818", "BM825", "Washer", "LockNut"}
                for obj in objects.values()) == len(data["nuts"]),
            "Saved nut/washer object count differs from manifest")
    checks.update(scene_components=len(objects), scene_mesh_vertices=vertex_count,
                  scene_curves=len(curve_names), fasteners=len(fastener_ids),
                  nuts_and_washers=len(data["nuts"]), mass_kg=math.fsum(scene_mass))

    # A contact at one edge is insufficient: each sleeve must have a complete
    # vertical mating rectangle against the cup. Inspect the saved polygons.
    bracket = objects.get('DRB01_Ybracket')
    require(bracket is not None, 'Saved scene is missing the Y-bracket')
    joins = json.loads(bracket.get('socket_join_specs', '[]')) if bracket else []
    require(len(joins) == 2, 'Y-bracket needs two flush socket interfaces')
    checked_joins = 0
    for side, y, x0, x1, z0, z1 in joins:
        expected = sorted([(x0, z0), (x1, z0), (x1, z1), (x0, z1)])
        found = False
        for polygon in bracket.data.polygons:
            if len(polygon.vertices) != 4:
                continue
            vertices = [bracket.matrix_world @ bracket.data.vertices[i].co
                        for i in polygon.vertices]
            if not all(abs(point.y - y) < 1e-5 for point in vertices):
                continue
            actual = sorted((point.x, point.z) for point in vertices)
            if all(close(a, b, 1e-5) for a, b in zip(actual, expected)):
                found = True
                break
        require(found, f'Y-bracket socket {side}: no flush mating face across the cup height')
        checked_joins += int(found)
    checks['flush_socket_interfaces'] = checked_joins
    frames = json.loads(bracket.get('socket_frames', '[]')) if bracket else []
    require(len(frames) == 2, 'Y-bracket needs two constant-section sleeve frames')
    stock_checks = 0
    contact_heights = []
    for side, yq, qz, sine, cosine, half_width, first, last in frames:
        require(0 <= first < last <= len(bracket.data.vertices), 'Invalid sleeve vertex range')
        if not 0 <= first < last <= len(bracket.data.vertices):
            continue
        points = [bracket.matrix_world @ vertex.co for vertex in bracket.data.vertices[first:last]]
        offsets = [side * (point.y - yq) * cosine + (point.z - qz) * sine
                   for point in points]
        constant_stock = all(abs(offset) <= half_width + 1e-5 for offset in offsets)
        require(constant_stock, f'Y-bracket socket {side}: widened or wedge-shaped sleeve')
        stock_checks += int(constant_stock)
        spec = next((join for join in joins if join[0] == side), None)
        overlaps = []
        for polygon in bracket.data.polygons:
            points = [bracket.matrix_world @ bracket.data.vertices[i].co for i in polygon.vertices]
            if not all(abs(point.y - yq) < 1e-5 for point in points):
                continue
            # The cup face runs substantially farther along the beam than a sleeve.
            if max(point.x for point in points) - min(point.x for point in points) <= 2 * half_width + 1e-5:
                continue
            if spec:
                overlaps.append(min(spec[5], max(point.z for point in points)) -
                                max(spec[4], min(point.z for point in points)))
        overlap = max(overlaps, default=0)
        require(overlap > .1, f'Y-bracket socket {side}: insufficient flush cup-wall overlap')
        cup_bottom = min((point.z for polygon in bracket.data.polygons
                          for point in [bracket.matrix_world @ bracket.data.vertices[i].co
                                        for i in polygon.vertices]
                          if abs(point.y - yq) < 1e-5), default=0)
        require(spec is not None and abs(spec[4] - cup_bottom) < 1e-5,
                f'Y-bracket socket {side}: mating end extends below cup bottom')
        contact_heights.append(overlap)
    checks['constant_section_sleeves'] = stock_checks
    checks['socket_cup_contact_heights_m'] = contact_heights

    gltf, binary = parse_glb(args.glb)
    nodes, meshes = gltf.get("nodes", []), gltf.get("meshes", [])
    mesh_nodes = [node for node in nodes if "mesh" in node]
    glb_names = [node.get("name") for node in mesh_nodes]
    require(len(glb_names) == len(set(glb_names)), "GLB mesh-node names are not unique")
    same_names(set(glb_names), set(components), "Exported mesh components")
    active_nodes = gltf["scenes"][gltf.get("scene", 0)].get("nodes", [])
    visited, world_transforms = set(), {}
    pending = [(index, Matrix.Identity(4)) for index in active_nodes]
    while pending:
        index, parent_transform = pending.pop()
        require(isinstance(index, int) and 0 <= index < len(nodes), "GLB scene references an invalid node")
        if not isinstance(index, int) or not 0 <= index < len(nodes):
            continue
        require(index not in visited, f"GLB node {index} has multiple parents or a cycle")
        if index in visited:
            continue
        visited.add(index)
        world_transforms[index] = parent_transform @ gltf_transform(nodes[index])
        pending.extend((child, world_transforms[index]) for child in nodes[index].get("children", []))
    require(all(index in visited for index, node in enumerate(nodes) if "mesh" in node),
            "Some exported mesh components are unreachable from the default scene")
    glb_ids = []
    for node in mesh_nodes:
        name, extras = node.get("name"), node.get("extras", {})
        for field in ("matrix", "translation", "rotation", "scale"):
            require(finite(node.get(field, [])), f"{name}: nonfinite exported {field}")
        mesh_index = node["mesh"]
        require(isinstance(mesh_index, int) and 0 <= mesh_index < len(meshes),
                f"{name}: invalid exported mesh reference")
        glb_ids.append(extras.get("part_id"))
        if name not in components:
            continue
        for glb_key, manifest_key in (("part_id", "id"), ("code", "code"), ("kind", "kind"),
                                      ("group", "group"), ("mass_source", "mass_source")):
            require(extras.get(glb_key) == components[name][manifest_key],
                    f"{name}: exported {glb_key} differs from manifest")
        mass = extras.get("mass_kg")
        require(isinstance(mass, (int, float)) and finite([mass])
                and close([mass], [components[name]["mass_kg"]]),
                f"{name}: exported mass differs from manifest")
    require(len(glb_ids) == len(set(glb_ids)) and set(glb_ids) == set(ids),
            "Exported component IDs differ from manifest")
    position_accessors = set()
    for mesh in meshes:
        require(bool(mesh.get("primitives")), "GLB contains an empty mesh")
        for primitive in mesh.get("primitives", []):
            position = primitive.get("attributes", {}).get("POSITION")
            require(isinstance(position, int), "GLB primitive has no POSITION accessor")
            if isinstance(position, int):
                position_accessors.add(position)
    exported_vertices, positions_by_accessor = 0, {}
    for index in sorted(position_accessors):
        accessor = gltf["accessors"][index]
        if accessor.get("componentType") != 5126 or accessor.get("type") != "VEC3" or "sparse" in accessor:
            errors.append(f"GLB position accessor {index}: unsupported position encoding")
            continue
        view = gltf["bufferViews"][accessor["bufferView"]]
        count, stride = accessor["count"], view.get("byteStride", 12)
        start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        end = start + max(0, count - 1) * stride + 12
        if not (count > 0 and stride >= 12 and view.get("buffer") == 0
                and start >= view.get("byteOffset", 0)
                and end <= view.get("byteOffset", 0) + view["byteLength"]
                and end <= len(binary)):
            errors.append(f"GLB position accessor {index}: invalid binary bounds")
            continue
        positions = [struct.unpack_from("<3f", binary, start + number * stride)
                     for number in range(count)]
        require(all(finite(position) for position in positions),
                f"GLB position accessor {index}: nonfinite vertices")
        positions_by_accessor[index] = positions
        exported_vertices += count
    max_bounds_error, bounds_checked = 0.0, 0
    for index, node in enumerate(nodes):
        if "mesh" not in node or index not in world_transforms or node.get("name") not in scene_bounds:
            continue
        positions = (point for primitive in meshes[node["mesh"]]["primitives"]
                     for point in positions_by_accessor[primitive["attributes"]["POSITION"]])
        gltf_world = (world_transforms[index] @ Vector(point) for point in positions)
        # Blender Z-up (x, y, z) is exported to glTF Y-up (x, z, -y).
        exported_bounds = bounds((point.x, -point.z, point.y) for point in gltf_world)
        error = max(abs(a - b) for a, b in zip(scene_bounds[node["name"]], exported_bounds))
        max_bounds_error = max(max_bounds_error, error)
        require(finite(exported_bounds) and error <= 0.001,
                f"{node['name']}: exported world bounds differ by {error:.6f} m (limit 0.001 m)")
        bounds_checked += 1
    require(bounds_checked == len(components), "World bounds were not checked for every component")
    checks.update(exported_mesh_nodes=len(mesh_nodes), exported_meshes=len(meshes),
                  exported_position_vertices=exported_vertices,
                  curve_components_exported=len(curve_names & set(glb_names)),
                  component_world_bounds_checked=bounds_checked,
                  max_world_bounds_error_m=max_bounds_error,
                  world_bounds_tolerance_m=0.001)
    return errors, checks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("blend", "manifest", "glb", "receipt"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args(argv)
    import bpy
    if not bpy.app.background:
        raise RuntimeError("Artifact verification requires background Blender; interactive scene untouched")
    errors, checks = [], {}
    try:
        errors, checks = check_artifacts(bpy, args)
    except Exception as error:
        errors.append(f"Verification could not complete: {type(error).__name__}: {error}")
    inputs = {}
    for label in ("blend", "manifest", "glb"):
        path = getattr(args, label).resolve()
        inputs[label] = {"path": str(path)}
        if path.is_file():
            inputs[label].update(bytes=path.stat().st_size,
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    receipt = dict(status="failed" if errors else "passed", inputs=inputs,
                   blender_version=bpy.app.version_string, checks=checks,
                   error_count=len(errors), errors=errors[:40],
                   scope="Saved scene and exported component integrity; no physical simulation or strength claim")
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": receipt["status"], "checks": checks,
                      "error_count": len(errors), "receipt": str(args.receipt)}))
    if errors:
        raise RuntimeError(f"Artifact verification failed: {errors[:4]}")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
