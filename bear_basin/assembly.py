"""Construct hardware meshes and placement records for an assembly schedule."""

import math
import bpy
import bmesh
from .hardware import FT, NUTS, is_bolt, nut_for, nut_mass_kg, source_steps
from .placement import explicit_fasteners, place_fasteners
from .mesh_placement import refine


def build_hardware(geometry, joints):
    M, J, STEEL = geometry.members, joints, geometry.steel
    FX = bpy.data.collections.new("Fasteners")
    bpy.context.scene.collection.children.link(FX)
    fmesh = {}

    def frustum(bm, r0, r1, z0, z1, seg=12):
        """Closed cone/cylinder section along local +Z."""
        ring0 = [
            bm.verts.new(
                (
                    r0 * math.cos(2 * math.pi * k / seg),
                    r0 * math.sin(2 * math.pi * k / seg),
                    z0,
                )
            )
            for k in range(seg)
        ]
        ring1 = [
            bm.verts.new(
                (
                    r1 * math.cos(2 * math.pi * k / seg),
                    r1 * math.sin(2 * math.pi * k / seg),
                    z1,
                )
            )
            for k in range(seg)
        ]
        bm.faces.new(list(reversed(ring0)))
        bm.faces.new(ring1)
        for k in range(seg):
            bm.faces.new(
                (ring0[k], ring0[(k + 1) % seg], ring1[(k + 1) % seg], ring1[k])
            )

    def fastener_mesh(ft):
        """Hardware page shapes. Local +Z points from the head into the wood; origin at the shank's midpoint.
        Bolts and machine screws (M..): wide flanged pan head sitting on the surface. Wood screws (SW..): countersunk flat
        head, flush with the surface. Swing hanger bolt: plain shank (the collar and bracket are modelled separately)."""
        if ft in fmesh:
            return fmesh[ft]
        d, L = FT[ft][0] / 1000, FT[ft][1] / 1000
        bm = bmesh.new()
        if ft.startswith("SW"):
            frustum(bm, d / 2, d / 2, -L / 2 + d * 0.9, L / 2 - d * 0.6, 8)
            frustum(bm, d / 2, 0.0005, L / 2 - d * 0.6, L / 2, 8)  # shank + point
            frustum(
                bm, d * 0.95, d / 2, -L / 2, -L / 2 + d * 0.9, 12
            )  # countersunk head
        elif ft == "HANGER":
            frustum(bm, d / 2, d / 2, -L / 2, L / 2, 10)
        else:
            frustum(bm, d / 2, d / 2, -L / 2, L / 2, 8)
            frustum(
                bm, d * 1.35, d * 1.1, -L / 2 - 0.004, -L / 2, 14
            )  # flanged pan head
        me = bpy.data.meshes.new(f"fast_{ft}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(STEEL)
        fmesh[ft] = me
        return me

    nmesh = {}

    def nut_mesh(kind):
        if kind in nmesh:
            return nmesh[kind]
        fr, ft_, br, bl = NUTS[kind]
        bm = bmesh.new()
        if kind == "LockNut":
            frustum(bm, fr, fr, 0, ft_, 6)
        elif kind == "Washer":
            frustum(bm, fr, fr, 0, ft_, 14)
        else:
            frustum(bm, fr, fr, -ft_, 0, 14)
            frustum(bm, br, br, 0, bl, 10)
        me = bpy.data.meshes.new(f"nut_{kind}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(STEEL)
        nmesh[kind] = me
        return me

    records = []
    missing = []
    not_touching = []
    nut_records = []
    for joint_index, (step, a, b, ft, n) in enumerate(J):
        joint_id = f"joint_{joint_index:04d}"
        if a not in M or b not in M:
            missing.append((step, a, b))
            continue
        if ft not in FT or not isinstance(n, int) or n <= 0:
            raise ValueError(f"Invalid joint: {joint_id}")
        A, B = M[a], M[b]
        ex = explicit_fasteners(geometry, step, a, b, ft, n)
        if ex:
            centres, nrm, gap_m, method = ex[0], ex[1], None, "explicit"
        else:
            centres, nrm, gap_m, method = place_fasteners(
                A, B, FT[ft][1] / 1000, n, bolt=is_bolt(ft)
            )
        if gap_m is not None and gap_m > 0.004:
            not_touching.append((step, a, b, round(gap_m, 3)))
        if len(centres) != n:
            raise ValueError(f"{joint_id}: placed {len(centres)} of {n} fasteners")
        refined = refine(geometry, a, b, ft, centres, nrm)
        for k, (c, nrm, mesh_method) in enumerate(refined):
            fastener_id = f"{joint_id}_{k}"
            ob = bpy.data.objects.new(f"{ft}_s{step}_{a}_{b}_{k}", fastener_mesh(ft))
            FX.objects.link(ob)
            ob.location = c
            ob.rotation_euler = nrm.to_track_quat("Z", "Y").to_euler()
            ob["code"] = ft
            ob["kind"] = "steel"
            ob["mass_kg"] = FT[ft][3] / 1000
            ob["part_id"] = fastener_id
            records.append(
                dict(
                    id=fastener_id,
                    joint_id=joint_id,
                    source_steps=source_steps(step, a, b),
                    placement=method + "+" + mesh_method,
                    step=step,
                    attached=a,
                    base=b,
                    type=ft,
                    pos=list(c),
                    axis=list(nrm),
                )
            )
            # Step 159 places a washer below the beam as well as above it.
            if ft == "HANGER":
                pos = c - nrm * (FT[ft][1] / 2000)
                washer = bpy.data.objects.new(
                    f"Washer_head_{fastener_id}", nut_mesh("Washer")
                )
                FX.objects.link(washer)
                washer.location = pos
                washer.rotation_euler = (-nrm).to_track_quat("Z", "Y").to_euler()
                washer["code"] = "Washer"
                washer["kind"] = "steel"
                washer["mass_kg"] = nut_mass_kg("Washer")
                nut_records.append(
                    dict(
                        fastener_id=fastener_id,
                        side="head",
                        step=step,
                        type="Washer",
                        bolt=ft,
                        pos=list(pos),
                    )
                )
            stack = 0.0
            for nk in nut_for(
                step, ft, a, b
            ):  # nut on the base part's far face, facing back toward the head
                head = c - nrm * (FT[ft][1] / 2000)
                spans = geometry._mesh_placement_cache.surfaces[b].spans(head, nrm)
                engaged = [hi for lo, hi in (spans or []) if hi > 0 and lo < FT[ft][1] / 1000]
                if not engaged:
                    raise ValueError(f"{fastener_id}: no base exit for nut placement")
                far = max(engaged)
                pos = head + nrm * (far + stack)
                no = bpy.data.objects.new(f"{nk}_{fastener_id}", nut_mesh(nk))
                FX.objects.link(no)
                no.location = pos
                no.rotation_euler = (
                    (-nrm).to_track_quat("Z", "Y").to_euler()
                    if nk not in ("Washer", "LockNut")
                    else nrm.to_track_quat("Z", "Y").to_euler()
                )
                if nk in ("Washer", "LockNut"):
                    stack += NUTS[nk][1]
                no["code"] = nk
                no["kind"] = "steel"
                no["mass_kg"] = nut_mass_kg(nk)
                nut_records.append(
                    dict(
                        fastener_id=fastener_id,
                        side="base",
                        step=step,
                        type=nk,
                        bolt=ft,
                        pos=list(pos),
                    )
                )

    return records, nut_records, missing, not_touching
