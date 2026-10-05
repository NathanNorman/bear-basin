"""Build the Bear Basin visualization in background Blender.

Usage: blender --background --factory-startup --python-exit-code 1 --python build.py -- --output-dir PATH
"""

from collections import Counter
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    parser.add_argument(
        "--strict-mesh",
        action="store_true",
        help="Fail if any mesh placement check fails (diagnostics are always written).",
    )
    args = parser.parse_args(argv)
    # Blender does not always add the script directory to sys.path.
    sys.path.insert(0, str(HERE))
    import bpy
    from bear_basin.geometry import build_geometry
    from bear_basin.joints import build_joints
    from bear_basin.assembly import build_hardware
    from bear_basin.validation import validate_records, validate_meshes
    from bear_basin.report import annotate_scene, manifest

    if not bpy.app.background:
        raise RuntimeError(
            "Build requires background Blender; it resets its own scene."
        )
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    geometry = build_geometry()
    joints = build_joints(geometry)
    fasteners, nuts, missing, gaps = build_hardware(geometry, joints)
    validation = validate_records(geometry.members, joints, fasteners, nuts)
    validation["mesh"] = (
        dict(
            checked=0,
            unchecked=len(fasteners),
            failed=0,
            failures=[],
            reason="record validation failed",
        )
        if validation["errors"]
        else validate_meshes(geometry, fasteners, nuts=nuts)
    )
    validation["scope"] = (
        "record consistency and modeled mesh contact; no physical simulation validation"
    )
    validation["placement_gaps"] = gaps
    validation["placement_methods"] = dict(
        Counter(item["placement"] for item in fasteners)
    )
    validation["status"] = (
        "failed"
        if validation["errors"] or missing
        else "needs_review"
        if validation["mesh"]["failed"] or gaps
        else "passed"
    )
    annotate_scene(geometry)
    data = manifest(geometry, joints, fasteners, nuts, validation)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in [("validation.json", validation), ("bear_basin.json", data)]:
        with (args.output_dir / name).open("w") as stream:
            json.dump(payload, stream, indent=2, allow_nan=False)
            stream.write("\n")
    print(
        f"members={len(geometry.members)} joints={len(joints)} fasteners={len(fasteners)}"
    )
    print(
        f"validation: {validation['status']}; mesh checked={len(fasteners)}, failed={validation['mesh']['failed']}"
    )
    print(f"mass estimate: {data['mass']['total_kg']:.2f} kg")
    for kind, count in validation["inventory"].items():
        if count["difference"]:
            print(
                f"inventory discrepancy: {kind}: modeled {count['modeled']}, manual {count['manual']}"
            )
    if (
        validation["errors"]
        or missing
        or (args.strict_mesh and (validation["mesh"]["failed"] or gaps))
    ):
        raise RuntimeError("Model validation failed; inspect validation.json")
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_dir / "bear_basin.blend"))


if __name__ == "__main__":
    main(
        sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else []
        if "bpy" in sys.modules
        else sys.argv[1:]
    )
