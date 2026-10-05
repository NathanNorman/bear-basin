"""Export the generated Blender model without modifying its saved source.

Run with Blender in background mode. Importing this module has no scene effects:
    blender --background --factory-startup --python-exit-code 1 \\
        --python export_glb.py -- --input bear_basin.blend --output viewer/bear_basin.glb
"""

import argparse
import os
from pathlib import Path
import struct
import sys
import tempfile


HERE = Path(__file__).resolve().parent


def parse_args(argv=None):
    """Read Blender's script arguments, or a normal Python CLI (for --help)."""
    if argv is None:
        if "--" in sys.argv:
            argv = sys.argv[sys.argv.index("--") + 1:]
        elif Path(sys.argv[0]).resolve() == Path(__file__).resolve():
            argv = sys.argv[1:]
        else:
            argv = []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "bear_basin.blend")
    parser.add_argument("--output", type=Path, default=HERE / "viewer" / "bear_basin.glb")
    return parser.parse_args(argv)


def prepare_scene(bpy):
    """Prepare the transient background scene, preserving object extras."""
    scene = bpy.context.scene
    ground = scene.objects.get("Ground")
    if ground is not None:
        bpy.data.objects.remove(ground, do_unlink=True)

    # The builder's authoritative colours are material.diffuse_color. Populate
    # glTF's Principled shader even when Blender already created default nodes.
    for material in bpy.data.materials:
        material.use_nodes = True
        shader = material.node_tree.nodes.get("Principled BSDF")
        if shader is not None:
            shader.inputs["Base Color"].default_value = material.diffuse_color
            shader.inputs["Roughness"].default_value = 0.8

    for obj in scene.objects:
        if "group" not in obj:
            obj["group"] = obj.users_collection[0].name if obj.users_collection else ""

    # glTF exports mesh geometry. Bevelled curves include the climbing net,
    # swing ropes, hammock, and hooks; leaving them as curves drops these parts.
    curves = [obj for obj in scene.objects if obj.type in {"CURVE", "SURFACE", "FONT"}]
    if curves:
        curve_metadata = {
            obj.name: {key: obj[key] for key in ("part_id", "code", "kind", "mass_kg", "mass_source", "group") if key in obj}
            for obj in curves
        }
        bpy.ops.object.select_all(action="DESELECT")
        for obj in curves:
            obj.hide_set(False)
            obj.hide_viewport = False
            obj.hide_select = False
            obj.select_set(True)
        bpy.context.view_layer.objects.active = curves[0]
        result = bpy.ops.object.convert(target="MESH")
        if "FINISHED" not in result:
            raise RuntimeError("Failed to convert curved model components to meshes")
        remaining = [obj.name for obj in scene.objects if obj.type in {"CURVE", "SURFACE", "FONT"}]
        if remaining:
            raise RuntimeError(f"Unconverted model components: {', '.join(remaining)}")
        for name, metadata in curve_metadata.items():
            converted = scene.objects.get(name)
            if converted is None or converted.type != "MESH":
                raise RuntimeError(f"Curve conversion lost model component {name}")
            if any(key not in converted or converted[key] != value for key, value in metadata.items()):
                raise RuntimeError(f"Curve conversion lost component metadata on {name}")


def validate_glb(path):
    """Reject a missing, truncated, or invalid glTF 2 binary before publication."""
    with path.open("rb") as stream:
        header = stream.read(12)
    if len(header) != 12:
        raise RuntimeError("Blender export did not produce a complete GLB header")
    magic, version, length = struct.unpack("<4sII", header)
    if magic != b"glTF" or version != 2 or length != path.stat().st_size or length <= 12:
        raise RuntimeError("Blender export did not produce a valid glTF 2 binary")


def export_model(input_path, output_path):
    # Import lazily: CLI parsing and test discovery must never load or clear a
    # user's currently open Blender scene.
    import bpy

    if not bpy.app.background:
        raise RuntimeError("Export requires Blender --background; the interactive scene was not changed")
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Model file does not exist: {input_path}")
    if input_path == output_path:
        raise ValueError("Export output must differ from the source model")
    if output_path.suffix.lower() != ".glb":
        raise ValueError("Export output must have a .glb extension")

    bpy.ops.wm.open_mainfile(filepath=str(input_path))
    prepare_scene(bpy)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output_path.stem}-", suffix=".glb", dir=output_path.parent)
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        result = bpy.ops.export_scene.gltf(
            filepath=str(temporary_path),
            export_format="GLB",
            export_extras=True,
            export_apply=True,
            export_yup=True,
            use_selection=False,
            use_active_scene=True,
        )
        if "FINISHED" not in result:
            raise RuntimeError("Blender cancelled the GLB export")
        validate_glb(temporary_path)
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Exported {output_path}")


def main(argv=None):
    args = parse_args(argv)
    export_model(args.input, args.output)


if __name__ == "__main__":
    main()
