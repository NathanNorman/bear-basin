"""Versioned model manifest and complete scene mass accounting."""

import math
from .hardware import FT, source_steps


def annotate_scene(geometry):
    """Give every rendered object a stable identity and explicit mass provenance."""
    import bpy

    for obj in bpy.context.scene.objects:
        if obj.type not in ("MESH", "CURVE") or obj.name == "Ground":
            continue
        obj["part_id"] = obj.get("part_id", obj.name)
        obj["code"] = obj.get("code", obj.name.split("_")[0])
        if obj.type == "CURVE":
            is_rope = obj.name.startswith(("Swing", "Hammock", "Climb"))
            density = 1100 if is_rope else 7850
            length = 0.0
            for spline in obj.data.splines:
                points = [point.co.to_3d() for point in spline.points]
                length += sum((b - a).length for a, b in zip(points, points[1:]))
                if spline.use_cyclic_u and len(points) > 1:
                    length += (points[0] - points[-1]).length
            obj["kind"] = "rope" if is_rope else "steel"
            obj["mass_kg"] = length * math.pi * obj.data.bevel_depth**2 * density
            obj["mass_source"] = "estimated radius, length and material density"
        else:
            obj["kind"] = obj.get("kind", "fabric" if obj.name == "Tarp" else "steel")
            obj["mass_source"] = "estimate; dimensions and density are not measured"
        if "mass_kg" not in obj:
            raise ValueError(f"Missing mass estimate for {obj.name}")


def manifest(geometry, joints, fasteners, nuts, validation):
    import bpy

    # Newly positioned hardware has deferred world matrices until Blender's
    # dependency graph updates. Capture the transforms that will be saved.
    bpy.context.view_layer.update()
    components = {}
    for obj in bpy.context.scene.objects:
        if obj.type not in ("MESH", "CURVE") or obj.name == "Ground":
            continue
        components[obj.name] = dict(
            id=obj["part_id"],
            code=obj["code"],
            kind=obj["kind"],
            group=obj.users_collection[0].name if obj.users_collection else "",
            mass_kg=float(obj["mass_kg"]),
            mass_source=obj["mass_source"],
            transform=[list(row) for row in obj.matrix_world],
        )
    mass = sum(item["mass_kg"] for item in components.values())
    return dict(
        schema_version=2,
        step_semantics="step is a representative assembly reference; source_steps lists grouped references",
        frame="x away from swings, y+ back (side A), z up; metres",
        purpose="assembly visualization; simulation is not configured or validated",
        source="Little Tikes 651281 assembly manual; see docs/review.md for discrepancies",
        members={
            name: dict(
                code=d["code"],
                kind=d["kind"],
                mass_kg=d["mass"],
                p0=list(d["p0"]),
                p1=list(d["p1"]),
                section_m=list(d["sec"]),
                axes=[list(d[axis]) for axis in ("u", "v", "a")],
            )
            for name, d in geometry.members.items()
        },
        components=components,
        fastener_types={
            name: dict(
                d_mm=v[0], L_mm=v[1], mass_g=v[3], shear_capacity_N_unverified=v[2]
            )
            for name, v in FT.items()
        },
        joints=[
            dict(
                id=f"joint_{i:04d}",
                step=s,
                source_steps=source_steps(s, a, b),
                attached=a,
                base=b,
                type=t,
                count=n,
            )
            for i, (s, a, b, t, n) in enumerate(joints)
        ],
        fasteners=fasteners,
        nuts=nuts,
        validation=validation,
        mass=dict(
            total_kg=mass,
            source="sum of scene component estimates",
            listing_kg_unverified=574 * 0.45359237,
            difference_pct=(mass / (574 * 0.45359237) - 1) * 100,
        ),
        limitations=[
            "Lumber sections, bracket dimensions and material densities are estimates.",
            "Fastener capacities are unverified placeholders, without a supported uncertainty bound.",
            "No rigid bodies, constraints, inertia, soil or anchoring simulation is configured.",
            "Net meshes do not specify load-bearing attachment topology.",
            "Sun shades are not modeled.",
        ],
    )
