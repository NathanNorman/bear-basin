"""Scene geometry in metres. Cross sections and unsourced dimensions remain estimates.

The assembly functions below are scoped to one fresh scene; build.py owns reset/save.
No Blender scene is modified when this module is imported.
"""

from dataclasses import dataclass
from typing import Any, Callable
import math
import bpy
import bmesh
from mathutils import Vector, Matrix
from .shapes import floorboard_outline, polygon_area, socket_miter_frame


@dataclass
class Geometry:
    members: dict
    knees: dict
    ring_polygons: dict
    rafters: dict
    leg_tops: dict
    net_fixings: list
    floor_support_y: float
    steel: Any
    knee_point: Callable
    rafter_bottom: Callable
    parameters: dict


def build_geometry():
    scene = bpy.context.scene
    RHO = 380.0  # kg/m3, cedar/fir. Total mass is reported against the 574 lb listing as a check on the section estimates.

    # ---------------- dimensions ----------------
    BH, SL = (
        1.08,
        0.08,
    )  # leg centreline half-width at ground, inward lean per metre (estimated taper)

    def lean(z):
        return BH - SL * z

    LEG = 0.070  # E  tower leg section
    RT, RH = 0.030, 0.140  # E  rail thickness / height
    DECK = 1.55  # Estimated layout:  deck top (listing: 5 ft)
    LEG_TOP = 2.25  # Estimated layout:  connect-board ring sits on leg tops; roof ring above -> 2.33
    EAVE, PEAK = 2.97, 3.58  # Estimated layout
    WALL_RAIL_Z, HANDRAIL_Z = 1.63, 2.08  # Estimated layout:  (wall top 2.13)

    def face(z):
        return (
            lean(z) + LEG / 2 + RT / 2
        )  # centre of a rail bolted to the outside of the legs

    def fup(side, s=SL):
        """'Up' direction lying in a sloped face (faces lean inward by s per metre; s<0 leans out). Passing this as member(up=)
        tilts a rail or board so its broad face sits flat on the leaning posts."""
        return {"+y": (0, -s, 1), "-y": (0, s, 1), "+x": (-s, 0, 1), "-x": (s, 0, 1)}[
            side
        ]

    # ---------------- helpers ----------------
    def coll(name):
        c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
        if c.name not in scene.collection.children:
            scene.collection.children.link(c)
        return c

    def mat(name, rgba):
        m = bpy.data.materials.get(name)
        if m is None:
            m = bpy.data.materials.new(name)
            m.diffuse_color = rgba
        return m

    CEDAR = mat("cedar", (0.62, 0.36, 0.18, 1))
    STEEL = mat("steel", (0.55, 0.57, 0.6, 1))
    # linear values of sRGB targets: blue #1C5CCC, tan #CDB084, brick red #963428
    BLUE = mat("blue_plastic", (0.0116, 0.107, 0.6038, 1))
    TARP = mat("tarp_tan", (0.6105, 0.4342, 0.2307, 1))
    ROPE = mat("rope", (0.86, 0.80, 0.62, 1))
    BRICK = mat("brick_red", (0.305, 0.0343, 0.0212, 1))

    M = {}  # name -> dict(obj, p0, p1, sec, code)

    def member(
        name, code, p0, p1, sec, c, m=CEDAR, up=(0, 0, 1), kind="wood", mass=None
    ):
        p0, p1 = Vector(p0), Vector(p1)
        a = p1 - p0
        L = a.length
        if L <= 1e-9 or min(sec) <= 0:
            raise ValueError(f"Invalid member dimensions: {name}")
        if name in M:
            raise ValueError(f"Duplicate member: {name}")
        a.normalize()
        upv = Vector(up)
        if abs(a.dot(upv.normalized())) > 0.98:
            upv = Vector((1, 0, 0))
        u = upv.cross(a).normalized()
        v = a.cross(u).normalized()
        mw = Matrix(
            ((u.x, v.x, a.x, 0), (u.y, v.y, a.y, 0), (u.z, v.z, a.z, 0), (0, 0, 0, 1))
        )
        mw.translation = (p0 + p1) / 2
        w, d, h = sec[0] / 2, sec[1] / 2, L / 2
        vs = [
            (-w, -d, -h),
            (w, -d, -h),
            (w, d, -h),
            (-w, d, -h),
            (-w, -d, h),
            (w, -d, h),
            (w, d, h),
            (-w, d, h),
        ]
        fs = [
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ]
        me = bpy.data.meshes.new(name)
        me.from_pydata(vs, [], fs)
        me.update()
        ob = bpy.data.objects.new(name, me)
        ob.matrix_world = mw
        ob.data.materials.append(m)
        c.objects.link(ob)
        ms = (
            mass
            if mass is not None
            else (sec[0] * sec[1] * L * RHO if kind == "wood" else 0.0)
        )
        ob["code"] = code
        ob["kind"] = kind
        ob["mass_kg"] = ms
        M[name] = dict(
            obj=ob, p0=p0, p1=p1, u=u, v=v, a=a, sec=sec, code=code, kind=kind, mass=ms
        )
        return name

    def rope(name, pts, c, r=0.007, m=ROPE):
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = r
        cu.resolution_u = 2
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (*p, 1)
        ob = bpy.data.objects.new(name, cu)
        ob.data.materials.append(m)
        c.objects.link(ob)
        return ob

    def leg_pt(sx, sy, z, mid=None):
        h = lean(z)
        return (sx * h if sx else 0.0, sy * h if sy else 0.0, z)

    # ================= TOWER FRAME (steps 7-34) =================
    T = coll("Tower_frame")
    LEGS = {
        "C02": (-1, 1),
        "C04A": (0, 1),
        "C01A": (1, 1),
        "C01B": (-1, -1),
        "C04B": (0, -1),
        "C03": (1, -1),
        "C05": (-1, 0),
        "C06": (1, 0),
    }
    for n, (sx, sy) in LEGS.items():
        member(n, n[:3], leg_pt(sx, sy, 0), leg_pt(sx, sy, LEG_TOP), (LEG, LEG), T)

    zb = 0.07  # base boards, flush with leg bottoms
    f = face(zb)
    fx = face(zb)
    member(
        "S04A",
        "S04A",
        (-fx - 0.02, f, zb),
        (fx + 0.02, f, zb),
        (RT, RH),
        T,
        up=fup("+y"),
    )  # back  (step 14)
    member(
        "S04",
        "S04",
        (-fx - 0.02, -f, zb),
        (fx + 0.02, -f, zb),
        (RT, RH),
        T,
        up=fup("-y"),
    )  # front (step 23)
    member(
        "S03_W", "S03", (-f, -fx, zb), (-f, fx, zb), (RT, RH), T, up=fup("-x")
    )  # west  (step 32)
    member(
        "S03_E", "S03", (f, -fx, zb), (f, fx, zb), (RT, RH), T, up=fup("+x")
    )  # east  (step 31)

    zr = DECK - 0.02 - RH / 2  # floor rails, top flush under the floorboards
    f = face(zr)
    member(
        "K07", "K07", (-f - 0.02, f, zr), (f + 0.02, f, zr), (RT, RH), T, up=fup("+y")
    )  # back  (step 15)
    member(
        "K06", "K06", (-f - 0.02, -f, zr), (f + 0.02, -f, zr), (RT, RH), T, up=fup("-y")
    )  # front (step 24)
    member(
        "K08_W", "K08", (-f, -f, zr), (-f, f, zr), (RT, RH), T, up=fup("-x")
    )  # west  (step 29)
    member(
        "K08_E", "K08", (f, -f, zr), (f, f, zr), (RT, RH), T, up=fup("+x")
    )  # east  (step 30)

    # ================= DECK STRUCTURE (steps 35-54) =================
    D = coll("Deck_structure")
    hi = lean(zr) - LEG / 2  # inside face of legs at rail height
    XE = face(zr) + RT / 2  # outer face of the end rails
    BLK, BLOCK_DEPTH = 0.07, 0.03  # Estimated 30 mm fixing depth for the specified 50 mm screws.
    # (name, leg centre sign (sx, sy), direction from the leg along the rail it sits under)
    fa17 = [
        ("FA17_C03", (1, -1), (0, 1)),
        ("FA17_C01B", (-1, -1), (0, 1)),
        ("FA17_C02", (-1, 1), (0, -1)),
        ("FA17_C01A", (1, 1), (0, -1)),
        ("FA17_C01A_y", (1, 1), (-1, 0)),
        ("FA17_C06", (1, 0), (0, 1)),
    ]
    for n, (
        sx,
        sy,
    ), ax in fa17:  # blocks screwed to the legs under the rail ends (steps 35-40)
        dx, dy = ax
        L_ = lean(zr)
        x = sx * L_ + dx * (LEG / 2 + BLOCK_DEPTH / 2)
        y = sy * L_ + dy * (LEG / 2 + BLOCK_DEPTH / 2)
        member(
            n, "FA17", (x, y, zr + RH / 2 - 0.10), (x, y, zr + RH / 2),
            (BLOCK_DEPTH, BLK) if dy else (BLK, BLOCK_DEPTH), D
        )
    XIN = face(zr) - RT / 2  # inside face of the end rails (K08)
    for sx in (
        -1,
        1,
    ):  # C11 wood braces bolted to the inside of each end rail (steps 47-48), beside the joist
        for y in (-0.29, 0.29):
            yb_ = y + (1 if y > 0 else -1) * (0.019 + 0.035)
            x = sx * (XIN - 0.035)
            member(
                f"C11_{'W' if sx < 0 else 'E'}_{'F' if y < 0 else 'B'}",
                "C11",
                (x, yb_ - 0.035, zr),
                (x, yb_ + 0.035, zr),
                (0.07, 0.10),
                D,
            )
    xj = XIN
    for y in (
        -0.29,
        0.29,
    ):  # K05 joists run rail to rail, bolted through the side of the C11 braces (steps 49-50)
        member(
            f"K05_{'F' if y < 0 else 'B'}",
            "K05",
            (-xj, y, zr + 0.01),
            (xj, y, zr + 0.01),
            (0.038, 0.12),
            D,
        )
    member(
        "KA11_C", "KA11", (-hi, 0, zr + 0.01), (hi, 0, zr + 0.01), (0.038, 0.12), D
    )  # between C05 and C06 (step 46)
    for y in (-0.78, 0.78):  # aligned with the knee braces (steps 53-54)
        member(
            f"KA11_{'F' if y < 0 else 'B'}",
            "KA11",
            (-(XE - RT), y, zr + 0.01),
            (XE - RT, y, zr + 0.01),
            (0.038, 0.12),
            D,
        )
    # KA13 knee braces, two per corner leg, one in each face plane (steps 41-45)
    KNEE = {}

    def knee_pt(kb, s, z, t):
        sx, sy = kb["sx"], kb["sy"]
        if kb["along"] == "x":
            return Vector(
                (sx * (lean(z) - LEG / 2 - s), sy * (lean(zr) + LEG / 2 - t), z)
            )
        return Vector((sx * (lean(zr) + LEG / 2 - t), sy * (lean(z) - LEG / 2 - s), z))

    def knee_brace(name, sx, sy, along):
        """KA13: 45-degree parallelogram, flat against the inside face of the floor rail, top cut flush with the rail top,
        bottom cut flush against the post's side face (step 42). along='x' sits on the side rail, 'y' on the end rail."""
        DROP, W, T = 0.30, 0.07, 0.03
        KNEE[name] = dict(sx=sx, sy=sy, along=along, DROP=DROP, T=T)
        h = (W / 2) / math.sin(
            math.pi / 4
        )  # half-width measured vertically/horizontally across the 45-degree band
        zt = zr + RH / 2  # rail top

        def pt(s, z, t):
            # s: distance from the post's inner side face along the rail; t: depth from the rail's inside face toward the deck
            if along == "x":
                return (sx * (lean(z) - LEG / 2 - s), sy * (lean(zr) + LEG / 2 - t), z)
            return (sx * (lean(zr) + LEG / 2 - t), sy * (lean(z) - LEG / 2 - s), z)

        quad = [
            (0, zt - DROP + h),
            (0, zt - DROP - h),
            (DROP + h, zt),
            (DROP - h, zt),
        ]  # A B C D in (s, z)
        vs = [pt(s, z, 0.0) for s, z in quad] + [pt(s, z, T) for s, z in quad]
        fs = [
            (0, 1, 2, 3),
            (7, 6, 5, 4),
            (0, 4, 5, 1),
            (1, 5, 6, 2),
            (2, 6, 7, 3),
            (3, 7, 4, 0),
        ]
        me = bpy.data.meshes.new(name)
        me.from_pydata(vs, [], fs)
        me.update()
        ob = bpy.data.objects.new(name, me)
        ob.data.materials.append(CEDAR)
        D.objects.link(ob)
        vol = (
            2 * h * DROP + 0
        ) * T  # parallelogram area = base (2h along s=0) x horizontal reach (DROP)
        p0 = (
            Vector(pt(0, zt - DROP, 0)) + Vector(pt(0, zt - DROP, T))
        ) / 2  # centre of the post-side cut
        p1 = (Vector(pt(DROP, zt - 0.035, 0)) + Vector(pt(DROP, zt - 0.035, T))) / 2
        a = (p1 - p0).normalized()
        u = Vector((0, sy, 0)) if along == "x" else Vector((sx, 0, 0))
        ob["code"] = "KA13"
        ob["kind"] = "wood"
        ob["mass_kg"] = vol * RHO
        M[name] = dict(
            obj=ob,
            p0=p0,
            p1=p1,
            u=u,
            v=a.cross(u).normalized(),
            a=a,
            sec=(T, W),
            code="KA13",
            kind="wood",
            mass=vol * RHO,
        )

    for leg, (sx, sy) in [
        ("C01A", (1, 1)),
        ("C02", (-1, 1)),
        ("C03", (1, -1)),
        ("C01B", (-1, -1)),
    ]:
        knee_brace(f"KA13_{leg}_x", sx, sy, "x")
        knee_brace(f"KA13_{leg}_y", sx, sy, "y")

    # ================= FLOORBOARDS: 28 boards in 22 rows (steps 62-74) =================
    FB = coll("Floorboards")
    ROWS = (
        ["W13", "W11"]
        + ["W09"] * 5
        + ["TBL"]
        + ["W09"] * 2
        + ["W10"] * 2
        + ["W09"] * 2
        + ["TBL"]
        + ["W09"] * 5
        + ["W11", "W13"]
    )
    XE = face(zr) + RT / 2  # outer face of the end rails
    NR = len(ROWS)
    x0 = -XE
    pitch = 2 * XE / NR
    BW, BT = pitch - 0.005, 0.019
    yr = face(zr) + RT / 2  # boards run to the outside of the side rails
    zbd = DECK - BT / 2
    TBL_X = []
    for i, code in enumerate(ROWS):
        x = x0 + pitch * (i + 0.5)
        if (
            code == "W13"
        ):  # short boards between corner leg and mid leg, both halves (FA17 + K08)
            for s in (-1, 1):
                member(
                    f"W13_{i}_{s}",
                    "W13",
                    (x, s * 0.05, zbd),
                    (x, s * (hi - 0.01), zbd),
                    (BW, BT),
                    FB,
                )
        elif code == "TBL":  # W02 + W01 + W02 around the table legs
            TBL_X.append(x)
            member(f"W02_{i}_F", "W02", (x, -yr, zbd), (x, -0.27, zbd), (BW, BT), FB)
            member(f"W01_{i}", "W01", (x, -0.25, zbd), (x, 0.25, zbd), (BW, BT), FB)
            member(f"W02_{i}_B", "W02", (x, 0.27, zbd), (x, yr, zbd), (BW, BT), FB)
        elif (
            code == "W10"
        ):  # Step 67: retain both rail supports, notch only the C04 corners.
            name = member(f"W10_{i}", "W10", (x, -yr, zbd), (x, yr, zbd), (BW, BT), FB)
            outline = floorboard_outline(
                x, BW, yr, LEG / 2 + 0.003, lean(DECK) - LEG / 2 - 0.003
            )
            vertices = [
                (px, py, zbd + dz) for dz in (-BT / 2, BT / 2) for px, py in outline
            ]
            count = len(outline)
            faces = [tuple(reversed(range(count))), tuple(range(count, count * 2))]
            faces += [
                (k, (k + 1) % count, (k + 1) % count + count, k + count)
                for k in range(count)
            ]
            obj = M[name]["obj"]
            obj.matrix_world = Matrix.Identity(4)
            obj.data.clear_geometry()
            obj.data.from_pydata(vertices, [], faces)
            obj.data.update()
            M[name]["outline_xy"] = outline
            M[name]["mass"] = polygon_area(outline) * BT * RHO
            obj["mass_kg"] = M[name]["mass"]
        else:
            member(f"{code}_{i}", code, (x, -yr, zbd), (x, yr, zbd), (BW, BT), FB)

    # ================= PICNIC TABLE on the deck (steps 51-52, 140-145) =================
    TB = coll("Picnic_table")
    for i, x in enumerate(TBL_X):
        for y in (-0.29, 0.29):
            member(
                f"CA10_{i}_{'F' if y < 0 else 'B'}",
                "CA10",
                (x, y + (0.055 if y < 0 else -0.055), zr - 0.04),
                (x, y + (0.055 if y < 0 else -0.055), DECK + 0.48),
                (0.07, 0.07),
                TB,
            )
        xo = x + (-1 if i == 0 else 1) * (
            0.035 + 0.015
        )  # on the outer faces of this leg pair
        member(
            f"F01_{i}",
            "F01",
            (xo, -0.324, DECK + 0.44),
            (xo, 0.324, DECK + 0.44),
            (0.03, 0.09),
            TB,
            up=(0, 0, 1),
        )  # 25.5 in (step 145)
        member(
            f"F03_{i}",
            "F03",
            (xo, -0.42, DECK + 0.22),
            (xo, 0.42, DECK + 0.22),
            (0.03, 0.09),
            TB,
        )
    TABLE_BOARD_WIDTH = 0.135
    for k in range(4):
        y = (k - 1.5) * TABLE_BOARD_WIDTH
        member(
            f"W05_{k}",
            "W05",
            (TBL_X[0] - 0.12, y, DECK + 0.495),
            (TBL_X[1] + 0.12, y, DECK + 0.495),
            (TABLE_BOARD_WIDTH, 0.019),
            TB,
        )
    for s in (-1, 1):
        for k, dy in enumerate((0.0, 0.10)):
            y = s * (0.30 + dy)
            member(
                f"Bench_{'F' if s < 0 else 'B'}_{'F08' if k == 0 else 'F02'}",
                "F08" if k == 0 else "F02",
                (TBL_X[0] - 0.08, y, DECK + 0.28),
                (TBL_X[1] + 0.08, y, DECK + 0.28),
                (0.095, 0.025),
                TB,
            )

    # ================= UPPER WALLS (steps 55-58, 164-171) =================
    W = coll("Walls")
    fw, fh = face(WALL_RAIL_Z), face(HANDRAIL_Z)
    member(
        "FA15_W",
        "FA15",
        (-fw, -fw, WALL_RAIL_Z),
        (-fw, fw, WALL_RAIL_Z),
        (RT, 0.09),
        W,
        up=fup("-x"),
    )  # step 167
    member(
        "FA15_F",
        "FA15",
        (-fw, -fw, WALL_RAIL_Z),
        (fw, -fw, WALL_RAIL_Z),
        (RT, 0.09),
        W,
        up=fup("-y"),
    )  # step 166
    member(
        "FA13_B",
        "FA13",
        (0, fw, WALL_RAIL_Z),
        (fw, fw, WALL_RAIL_Z),
        (RT, 0.09),
        W,
        up=fup("+y"),
    )  # step 164 (back, east half)
    member(
        "FA13_E",
        "FA13",
        (fw, 0, WALL_RAIL_Z),
        (fw, fw, WALL_RAIL_Z),
        (RT, 0.09),
        W,
        up=fup("+x"),
    )  # step 165 (east, back half)
    member(
        "F09_B",
        "F09",
        (-fh, fh, HANDRAIL_Z),
        (fh, fh, HANDRAIL_Z),
        (RT, 0.09),
        W,
        up=fup("+y"),
    )  # step 56 (spans the opening)
    member(
        "F09_W",
        "F09",
        (-fh, -fh, HANDRAIL_Z),
        (-fh, fh, HANDRAIL_Z),
        (RT, 0.09),
        W,
        up=fup("-x"),
    )  # step 57
    member(
        "F09_F",
        "F09",
        (-fh, -fh, HANDRAIL_Z),
        (fh, -fh, HANDRAIL_Z),
        (RT, 0.09),
        W,
        up=fup("-y"),
    )  # step 58
    member(
        "F04_E",
        "F04",
        (fh, 0, HANDRAIL_Z),
        (fh, fh, HANDRAIL_Z),
        (RT, 0.09),
        W,
        up=fup("+x"),
    )  # step 55
    WB_W, WB_T = 0.105, 0.016

    def wall_boards(tag, n, a, b, side, step, clear=None):
        """n evenly spaced boards on the outside face between parameter a..b along the face (2 in gaps per step 168).
        clear=(c0, c1): keep that span free (split the boards evenly either side of it)."""
        z0, z1 = WALL_RAIL_Z - 0.04, HANDRAIL_Z + 0.04
        if clear:
            ts = []
            for (lo, hi_), m in (((a, clear[0]), n // 2), ((clear[1], b), n - n // 2)):
                g_ = ((hi_ - lo) - m * WB_W) / (m + 1)
                ts += [lo + g_ * (k + 1) + WB_W * (k + 0.5) for k in range(m)]
        else:
            span = b - a
            gap = (span - n * WB_W) / (n + 1)
            ts = [a + gap * (k + 1) + WB_W * (k + 0.5) for k in range(n)]
        for k, t in enumerate(ts):
            o0, o1 = (
                face(z0) + RT / 2 + WB_T / 2,
                face(z1) + RT / 2 + WB_T / 2,
            )  # boards lean with the posts
            sg = 1 if side in ("B", "E") else -1
            if side in ("F", "B"):
                member(
                    f"W07_{tag}_{k}",
                    "W07",
                    (t, sg * o0, z0),
                    (t, sg * o1, z1),
                    (WB_T, WB_W),
                    W,
                    up=(1, 0, 0),
                )
            else:
                member(
                    f"W07_{tag}_{k}",
                    "W07",
                    (sg * o0, t, z0),
                    (sg * o1, t, z1),
                    (WB_T, WB_W),
                    W,
                    up=(0, 1, 0),
                )

    h = lean(1.85)
    wall_boards("B", 5, 0.04, h, "B", 168)
    wall_boards("E", 5, 0.04, h, "E", 169)
    wall_boards("F", 10, -h, h, "F", 170)
    wall_boards(
        "W", 10, -h, h, "W", 171, clear=(-0.07, 0.07)
    )  # swing beam + I-bracket pass through at C05
    member(
        "S05",
        "S05",
        (-face(0.95), -face(0.95), 0.95),
        (-face(0.95), face(0.95), 0.95),
        (RT, 0.09),
        W,
        up=fup("-x"),
    )  # opening block, swing face (step 185)

    def handle(n, leg_xy, side, c, z0=1.72, z1=1.98):
        """Grab handle on the side face of a leg: two standoffs screwed to the leg + a vertical grip (step 186 / 101).
        leg_xy(z) -> leg centre (x, y); side = unit vector (dx, dy) from the leg toward the grip."""
        sx, sy = side
        ST = 0.065
        pts = []
        for z in (z0, z1):
            lx, ly = leg_xy(z)
            f0 = (lx + sx * LEG / 2, ly + sy * LEG / 2, z)
            f1 = (lx + sx * (LEG / 2 + ST), ly + sy * (LEG / 2 + ST), z)
            mount = (f0[0] + sx * 0.008, f0[1] + sy * 0.008, z)
            member(
                f"{n}_foot{len(pts)}",
                "Handle",
                f0,
                mount,
                (0.035, 0.05),
                c,
                m=BLUE,
                kind="plastic",
                mass=0.025,
            )
            member(f"{n}_standoff{len(pts)}", "Handle", mount, f1,
                   (0.014, 0.014), c, m=BLUE, kind="plastic", mass=0.025)
            pts.append(f1)
        member(
            n,
            "Handle",
            pts[0],
            pts[1],
            (0.03, 0.03),
            c,
            m=BLUE,
            kind="plastic",
            mass=0.15,
        )

    # the upper opening is the back face's west half (x from C02 to C04A): handles on the outward (back) faces of its two legs
    handle("Handle_C04A", lambda z: (0.0, lean(z)), (0, 1), W)
    handle("Handle_C02", lambda z: (-lean(z), lean(z)), (0, 1), W)
    # ================= CONNECT-BOARD RINGS (steps 59-61 main structure, 118-120 roof, 134-139 bolted together) =================
    # Two identical flat rings: the main structure's lies on the tower leg tops; the roof's is screwed to the roof posts' bottom
    # ends and rests on it. Parts list: F11 has two angled ends, F12 and F13 one each. So each ring = F11 (back) + F11 (west),
    # mitred at C02/C01A/C01B; F12 (front) mitred at C01B with a square end over C03; F13 on the back half of the east side
    # (mitred at C01A, square end flush with C06's front face). The east front half is the doorway to the small deck.
    # Outer edges flush with the handrails.
    RING_C = lean(LEG_TOP)  # leg / roof-post centreline offset at the ring
    CBW, CBT = 0.115, 0.025  # Estimated stock; two layers accept M833 + BM825 hardware.
    RO = (
        RING_C + LEG / 2 + RT
    )  # outer edge, flush with the handrails' outer faces (step 59)
    RI = RO - CBW

    def ring_board(name, code, side, a0, a1, z0, c, mit0=True, mit1=True):
        """Flat board on the ring. side in B/F/W/E; a0..a1 = extent along the board on its outer edge.
        Mitred ends pull the inner edge in by CBW (45 degrees); square ends don't."""
        i0 = a0 + (CBW if mit0 else 0) * (1 if a1 > a0 else -1)
        i1 = a1 - (CBW if mit1 else 0) * (1 if a1 > a0 else -1)

        def P(t, o, z):
            return {"B": (t, o, z), "F": (t, -o, z), "W": (-o, t, z), "E": (o, t, z)}[
                side
            ]

        quad = [(a0, RO), (a1, RO), (i1, RI), (i0, RI)]
        vs = [P(t, o, z0) for t, o in quad] + [P(t, o, z0 + CBT) for t, o in quad]
        fs = [
            (3, 2, 1, 0),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ]
        me = bpy.data.meshes.new(name)
        me.from_pydata(vs, [], fs)
        me.update()
        ob = bpy.data.objects.new(name, me)
        ob.data.materials.append(CEDAR)
        c.objects.link(ob)
        zc_ = z0 + CBT / 2
        om = (RO + RI) / 2
        p0, p1 = Vector(P(a0, om, zc_)), Vector(P(a1, om, zc_))
        ax = (p1 - p0).normalized()
        u = Vector((0, 0, 1))
        ms = CBW * CBT * (abs(a1 - a0) - CBW * (int(mit0) + int(mit1)) / 2) * RHO
        ob["code"] = code
        ob["kind"] = "wood"
        ob["mass_kg"] = ms
        M[name] = dict(
            obj=ob,
            p0=p0,
            p1=p1,
            u=ax.cross(u).normalized(),
            v=u,
            a=ax,
            sec=(CBW, CBT),
            code=code,
            kind="wood",
            mass=ms,
        )
        RING_POLY[name] = dict(poly=[Vector(P(t, o, 0)[:2]) for t, o in quad], z0=z0)

    RING_POLY = {}

    def connect_ring(sfx, z0, c):
        ring_board("F11" + sfx + "_B", "F11", "B", -RO, RO, z0, c)
        ring_board("F11" + sfx + "_W", "F11", "W", -RO, RO, z0, c)
        ring_board("F12" + sfx, "F12", "F", -RO, RO, z0, c, mit0=True, mit1=False)
        ring_board("F13" + sfx, "F13", "E", RO, -LEG / 2, z0, c, mit0=True, mit1=False)

    connect_ring("", LEG_TOP, W)

    # ================= ROOF ASSEMBLY (steps 107-139) =================
    # Built upside down: F14/F15 rails flush with the posts' narrow ends, F16 flush with the wide ends (steps 109-117), connect
    # boards on the narrow ends (118-120), then flipped (121) and set on the tower (135). So in place: connect ring at the bottom,
    # F14 x3 + F15 (back half of east only) along the bottom, F16 x4 around the eave, posts flaring outward between them.
    R = coll("Roof")
    connect_ring("r", LEG_TOP + CBT, R)
    RP = LEG  # roof posts are the same stock as the tower legs
    rb, rt_ = (
        RING_C,
        0.985,
    )  # post centreline offset at bottom / eave (C09 'circular curve', step 108)
    zp0, zp1 = LEG_TOP + 2 * CBT, EAVE

    def pc(z):
        return rb + (rt_ - rb) * (z - zp0) / (zp1 - zp0)

    for n, (sx, sy) in {
        "C09_BE": (1, 1),
        "C09_BW": (-1, 1),
        "C09_FE": (1, -1),
        "C09_FW": (-1, -1),
    }.items():
        member(
            n, "C09", (sx * rb, sy * rb, zp0), (sx * rt_, sy * rt_, zp1), (RP, RP), R
        )
    for n, (sx, sy) in {
        "C10_B": (0, 1),
        "C10_F": (0, -1),
        "C10_W": (-1, 0),
        "C10_E": (1, 0),
    }.items():
        member(
            n, "C10", (sx * rb, sy * rb, zp0), (sx * rt_, sy * rt_, zp1), (RP, RP), R
        )
    FLARE = -(rt_ - rb) / (zp1 - zp0)
    RRH = 0.09

    def roof_rail(name, code, side, z, t0=None, t1=None):
        """Rail on the outside faces of the roof posts at height z. Back/front rails run past the corners to cover the side
        rails' ends; side rails butt between them."""
        off = pc(z) + RP / 2 + RT / 2
        full = off + RT / 2 if side in ("B", "F") else off - RT / 2
        a0 = -full if t0 is None else t0
        a1 = full if t1 is None else t1
        P = {
            "B": lambda t: (t, off, z),
            "F": lambda t: (t, -off, z),
            "W": lambda t: (-off, t, z),
            "E": lambda t: (off, t, z),
        }[side]
        member(
            name,
            code,
            P(a0),
            P(a1),
            (RT, RRH),
            R,
            up=fup({"B": "+y", "F": "-y", "W": "-x", "E": "+x"}[side], FLARE),
        )

    zb_r, zt_r = (
        zp0 + RRH / 2,
        zp1 - RRH / 2,
    )  # F14 bottom edge flush with post bottoms; F16 top edge flush with post tops (step 115)
    for sd in ("B", "F", "W"):
        roof_rail(f"F14_{sd}", "F14", sd, zb_r)
    roof_rail(
        "F15_E", "F15", "E", zb_r, t0=-RP / 2, t1=pc(zb_r) + RP / 2 - 0.0
    )  # step 116-117: C09_BE to C10_E only
    for sd in ("B", "F", "W", "E"):
        roof_rail(f"F16_{sd}", "F16", sd, zt_r)

    # hip rafters (KA12) sit ON the corner post tops, predrilled holes centred diagonally on the post top (steps 122-125),
    # rising to the rafter brace block KA09 at the apex (123, 126-129). The tarp lies over them (130).
    RFW, RFD = 0.07, 0.035  # E  rafter laid flat: 70 wide x 35 deep
    te = rt_ + RP / 2 + RT  # outer face of the eave rails at the top
    RAFT_D0 = rt_ * math.sqrt(2)  # plan distance from the apex to a corner post centre
    KB_HALF = (
        RFW / 2
    )  # KA09 brace block: one rafter width square, turned 45 degrees so each rafter meets a face
    cos_t = None
    RAFT_K = (
        PEAK - 0.012 - zp1 - RFD * 1.08
    ) / RAFT_D0  # slope: rafter top line reaches the peak (0.012 m under the tarp)
    cos_t = 1 / math.sqrt(1 + RAFT_K * RAFT_K)
    RD_V = RFD / cos_t

    def raft_bot(d):
        return (
            zp1 + (RAFT_D0 - d) * RAFT_K
        )  # rafter underside height at plan distance d from the apex

    RAFTERS = {}
    for n, (sx, sy) in {
        "KA12_BE": (1, 1),
        "KA12_BW": (-1, 1),
        "KA12_FE": (1, -1),
        "KA12_FW": (-1, -1),
    }.items():
        dl = (
            RAFT_D0 + (RP / 2) * math.sqrt(2) - 0.005
        )  # lower end at the post's outer corner
        du = KB_HALF  # upper end butts square against a face of the brace block
        e = Vector((sx, sy, 0)).normalized()
        w = Vector((0, 0, 1)).cross(e)
        vs = []
        for d_ in (
            dl,
            du,
        ):  # plumb-cut ends (vertical), so the top end sits flat on the block face
            for zz in (raft_bot(d_), raft_bot(d_) + RD_V):
                for sw in (-1, 1):
                    vs.append(tuple(e * d_ + w * sw * RFW / 2 + Vector((0, 0, zz))))
        fs = [
            (0, 1, 3, 2),
            (4, 6, 7, 5),
            (0, 4, 5, 1),
            (2, 3, 7, 6),
            (0, 2, 6, 4),
            (1, 5, 7, 3),
        ]
        me = bpy.data.meshes.new(n)
        me.from_pydata(vs, [], fs)
        me.update()
        ob = bpy.data.objects.new(n, me)
        ob.data.materials.append(CEDAR)
        R.objects.link(ob)
        c0 = e * dl + Vector((0, 0, raft_bot(dl) + RD_V / 2))
        c1 = e * du + Vector((0, 0, raft_bot(du) + RD_V / 2))
        ax_ = (c1 - c0).normalized()
        ms = RFW * RFD * (c1 - c0).length * RHO
        ob["code"] = "KA12"
        ob["kind"] = "wood"
        ob["mass_kg"] = ms
        M[n] = dict(
            obj=ob,
            p0=c0,
            p1=c1,
            u=w,
            v=ax_.cross(w).normalized(),
            a=ax_,
            sec=(RFW, RFD),
            code="KA12",
            kind="wood",
            mass=ms,
        )
        RAFTERS[n] = dict(e=e, post="C09_" + n.split("_")[1])
    member(
        "KA09",
        "KA09",
        (0, 0, raft_bot(KB_HALF)),
        (0, 0, raft_bot(KB_HALF) + RD_V),
        (2 * KB_HALF, 2 * KB_HALF),
        R,
        up=(1, 1, 0),
    )  # same depth as the rafters: flush top and bottom

    # tarp: pyramid resting on the rafters, eave edges on the F16 tops, corners at C09 (step 130), skirt screwed to F16 (131-133)
    CLR = 0.02  # tarp clears the rafter's top edges

    def tarp_hip(d):
        return raft_bot(d) + RD_V + CLR

    TZ = zp1 + 0.002
    SKIRT = 0.10
    PZ = tarp_hip(0.0)
    ZC = tarp_hip(te * math.sqrt(2))
    C4 = [(-te, -te), (te, -te), (te, te), (-te, te)]
    MID = [(0, -te), (te, 0), (0, te), (-te, 0)]
    vs = [(x, y, ZC) for x, y in C4] + [(x, y, TZ) for x, y in MID] + [(0, 0, PZ)]
    vs += [(x, y, ZC - SKIRT) for x, y in C4] + [(x, y, TZ - SKIRT) for x, y in MID]
    # Each skirt panel follows the rail's outward slope at its own height.
    vs = [(x * (pc(z) + RP / 2 + RT) / te,
           y * (pc(z) + RP / 2 + RT) / te, z) if i != 8 else (x, y, z)
          for i, (x, y, z) in enumerate(vs)]
    fs = []
    for i in range(4):
        c0, c1, m = i, (i + 1) % 4, 4 + i
        fs += [(c0, m, 8), (m, c1, 8), (9 + c0, 13 + i, m, c0), (13 + i, 9 + c1, c1, m)]
    me = bpy.data.meshes.new("Tarp")
    me.from_pydata(vs, [], fs)
    me.update()
    tarp = bpy.data.objects.new("Tarp", me)
    tarp.data.materials.append(TARP)
    R.objects.link(tarp)
    tarp["mass_kg"] = 3.0
    tarp["code"] = "Tarp"
    tarp["kind"] = "fabric"
    M["Tarp"] = dict(
        obj=tarp,
        p0=Vector((-te, 0, TZ)),
        p1=Vector((te, 0, TZ)),
        u=Vector((0, 1, 0)),
        v=Vector((0, 0, 1)),
        a=Vector((1, 0, 0)),
        sec=(2 * te, 0.001),
        code="Tarp",
        kind="fabric",
        mass=3.0,
    )

    # ================= SMALL DECK + SLIDE + LADDER (steps 75-106, 172) =================
    SD = coll("Small_deck")
    SDZ = 1.20  # Estimated layout
    SX0 = face(SDZ - 0.08) + RT  # tower east face
    SXO = 1.86  # Estimated layout:  outer legs
    SYF, SYB = -lean(SDZ), 0.0  # between C03 (front corner) and C06 (mid)

    def yf(z):
        return -lean(
            z
        )  # front side lies in the tower's sloped front plane (C07 leans like C03); C08 stays plumb in y like C06

    SDL_TOP = 1.98

    def sdx(z):
        return (
            SXO + 0.03 - 0.035 * z
        )  # small deck legs lean in like the tower ('angled edges')

    member(
        "C07",
        "C07",
        (sdx(0), yf(0), 0),
        (sdx(SDL_TOP), yf(SDL_TOP), SDL_TOP),
        (LEG, LEG),
        SD,
    )
    member("C08", "C08", (sdx(0), SYB, 0), (sdx(SDL_TOP), SYB, SDL_TOP), (LEG, LEG), SD)
    fo = lambda z: sdx(z) + LEG / 2 + RT / 2
    member(
        "S02",
        "S02",
        (fo(0.07), yf(0.07) - 0.04, 0.07),
        (fo(0.07), SYB + 0.04, 0.07),
        (RT, RH),
        SD,
        up=fup("+x", 0.035),
    )  # step 79
    zsr = SDZ - 0.02 - 0.06
    member(
        "K02_O",
        "K02",
        (fo(zsr), yf(zsr) - 0.04, zsr),
        (fo(zsr), SYB + 0.04, zsr),
        (RT, 0.12),
        SD,
        up=fup("+x", 0.035),
    )  # step 81
    member(
        "K02_T",
        "K02",
        (lean(zsr) + LEG / 2 + RT / 2, yf(zsr) - LEG / 2 - RT, zsr),
        (lean(zsr) + LEG / 2 + RT / 2, SYB + LEG / 2 + RT, zsr),
        (RT, 0.12),
        SD,
        up=fup("+x"),
    )  # step 90
    member(
        "K01",
        "K01",
        (lean(zsr), yf(zsr) - LEG / 2 - RT / 2, zsr),
        (sdx(zsr), yf(zsr) - LEG / 2 - RT / 2, zsr),
        (RT, 0.12),
        SD,
        up=fup("-y"),
    )  # step 86 (front)
    member(
        "K03",
        "K03",
        (lean(zsr), SYB + LEG / 2 + RT / 2, zsr),
        (sdx(zsr), SYB + LEG / 2 + RT / 2, zsr),
        (RT, 0.12),
        SD,
    )  # step 87 (inner)
    xm = (SX0 + SXO) / 2
    member(
        "KA10",
        "KA10",
        (xm, yf(zsr) - LEG / 2, zsr + 0.01),
        (xm, SYB + LEG / 2, zsr + 0.01),
        (0.038, 0.10),
        SD,
    )  # step 91
    member(
        "FA17_C07",
        "FA17",
        (sdx(zsr) - LEG / 2 - BLOCK_DEPTH / 2, yf(zsr), zsr - 0.04),
        (sdx(zsr) - LEG / 2 - BLOCK_DEPTH / 2, yf(zsr), zsr + 0.06),
        (BLK, BLOCK_DEPTH),
        SD,
    )
    member(
        "FA17_C08",
        "FA17",
        (sdx(zsr) - LEG / 2 - BLOCK_DEPTH / 2, SYB, zsr - 0.04),
        (sdx(zsr) - LEG / 2 - BLOCK_DEPTH / 2, SYB, zsr + 0.06),
        (BLK, BLOCK_DEPTH),
        SD,
    )
    SDB = (
        ["W12A"] + ["W08"] * 9 + ["W12", "W04"]
    )  # front edge -> inner edge (steps 93-97)
    sp = (SYB + LEG / 2 + RT - (SYF - LEG / 2 - RT)) / len(SDB)
    for i, code in enumerate(SDB):
        y = SYF - LEG / 2 - RT + sp * (i + 0.5)
        member(
            f"{code}_sd{i}",
            code,
            (lean(SDZ) + LEG / 2, y, SDZ - 0.0095),
            (fo(SDZ) + RT / 2, y, SDZ - 0.0095),
            (sp - 0.004, 0.019),
            SD,
        )
    member(
        "F07",
        "F07",
        (fo(SDL_TOP - 0.05), yf(SDL_TOP - 0.05) - 0.04, SDL_TOP - 0.05),
        (fo(SDL_TOP - 0.05), SYB + 0.04, SDL_TOP - 0.05),
        (RT, 0.09),
        SD,
        up=fup("+x", 0.035),
    )  # step 82
    member(
        "FA14",
        "FA14",
        (fo(SDZ + 0.08), yf(SDZ + 0.08), SDZ + 0.08),
        (fo(SDZ + 0.08), SYB, SDZ + 0.08),
        (RT, 0.09),
        SD,
        up=fup("+x", 0.035),
    )  # step 98
    for k in range(5):  # step 99
        zl, zh = SDZ + 0.04, SDL_TOP - 0.01  # boards fan with the sloped front leg
        y0 = yf(zl) + (k + 0.5) * (SYB - yf(zl)) / 5
        y1 = yf(zh) + (k + 0.5) * (SYB - yf(zh)) / 5
        member(
            f"W14_{k}",
            "W14",
            (fo(zl) + RT / 2 + WB_T / 2, y0, zl),
            (fo(zh) + RT / 2 + WB_T / 2, y1, zh),
            (WB_T, 0.09),
            SD,
            up=(0, 1, 0),
        )
    for tag, yy in (
        ("F", lambda z: yf(z) - LEG / 2 - RT / 2),
        ("B", lambda z: SYB + LEG / 2 + RT / 2),
    ):
        member(
            f"F05_low_{tag}",
            "F05",
            (lean(0.45) - LEG / 2, yy(0.45), 0.45),
            (sdx(0.45) + LEG / 2, yy(0.45), 0.45),
            (RT, 0.09),
            SD,
            up=fup("-y") if tag == "F" else (0, 0, 1),
        )  # step 88
        zt = SDL_TOP - 0.05
        member(
            f"F05_top_{tag}",
            "F05",
            (lean(zt) - LEG / 2, yy(zt), zt),
            (sdx(zt) + LEG / 2, yy(zt), zt),
            (RT, 0.09),
            SD,
            up=fup("-y") if tag == "F" else (0, 0, 1),
        )  # step 89
    # opening block (step 100): centred in the gap between K08_E's bottom edge and the small deck floor, ~2 in each side
    # (manual: ~2.75 in, never over 3.5 in), across the outer faces of C03 and C06, flush with K08_E
    KA14_H = 0.09
    zka = ((zr - RH / 2) + SDZ) / 2
    member(
        "KA14",
        "KA14",
        (face(zka), -lean(zka) - LEG / 2, zka),
        (face(zka), LEG / 2, zka),
        (RT, KA14_H),
        SD,
        up=fup("+x"),
    )
    print(
        f"KA14 gaps: above {(zr - RH / 2) - (zka + KA14_H / 2):.3f} m, below {(zka - KA14_H / 2) - SDZ:.3f} m"
    )  # step 100
    handle(
        "Handle_C08", lambda z: (sdx(z), SYB), (0, 1), SD, z0=1.30, z1=1.56
    )  # faces the ladder (step 101)

    LD = coll("Ladder")  # off the inner edge, toward the back (cover photo + step 193)
    LX, LWD, LRUN = 1.47, 0.42, 0.85
    LH = zsr + 0.04
    K03_OUT = SYB + LEG / 2 + RT  # outer face of K03
    LY0 = (
        K03_OUT + 0.045 * math.hypot(LH, LRUN) / LH - (LH - zsr) * LRUN / LH
    )  # upright's front edge touches K03 at rail height
    LAX = Vector((0, LRUN, -LH)).normalized()
    LN = Vector((0, LH, LRUN)).normalized()  # along the ladder / walking-face normal
    for n, s in (("K20", -1), ("K21", 1)):
        member(
            n,
            n,
            (LX + s * LWD / 2, LY0, LH),
            (LX + s * LWD / 2, LY0 + LRUN, 0.0),
            (0.035, 0.09),
            LD,
        )
    for k in range(4):
        t = (k + 1) / 5
        y = LY0 + t * LRUN
        z = LH * (1 - t)
        member(
            f"F23_{k}",
            "F23",
            (LX - LWD / 2, y, z),
            (LX + LWD / 2, y, z),
            (0.09, 0.025),
            LD,
        )
    w23c = Vector((0, LY0, LH)) + LAX * 0.10 - LN * (0.045 + 0.01)
    member(
        "W23",
        "W23",
        (LX - LWD / 2 - 0.0175, w23c.y, w23c.z),
        (LX + LWD / 2 + 0.0175, w23c.y, w23c.z),
        (0.09, 0.02),
        LD,
        up=tuple(LN),
    )
    ysk = LY0 + LRUN * (1 - 0.05 / LH)
    member(
        "Stake_K20",
        "Stake",
        (LX - LWD / 2 - 0.0175 - 0.006, ysk, 0.1),
        (LX - LWD / 2 - 0.0175 - 0.006, ysk, -0.30),
        (0.012, 0.012),
        LD,
        m=STEEL,
        kind="steel",
        mass=0.6,
    )

    SLD = coll("Slide")  # wave slide off W12A toward the front (step 172)

    def build_slide():
        """One molded part: U trough with rolled lips swept along a smooth wave path.
        Top lip lies on W12A (2x SW50, step 172); estimated flat runout; end curls down to the ground."""
        ys = SYF - LEG / 2 - RT  # front edge of the small deck
        T = 0.010  # wall thickness
        ctrl = [
            (0.10, SDZ + T),
            (0.0, SDZ + T),
            (-0.12, SDZ - 0.02),
            (-0.50, 0.93),
            (-0.80, 0.80),
            (-1.00, 0.76),
            (-1.40, 0.50),
            (-1.80, 0.32),
            (-2.10, 0.285),
            (-2.40, 0.28),
            (-2.52, 0.23),
            (-2.58, 0.12),
            (-2.60, T / 2),
        ]
        RUN = (
            1.90 / 2.60
        )  # listing depth 155 in (3.94 m) = ladder foot (+0.91) to slide end
        ctrl = [(ys + (dy * RUN if dy < 0 else dy), z) for dy, z in ctrl]

        def cr(p0, p1, p2, p3, t):  # Catmull-Rom
            return tuple(
                0.5
                * (
                    (2 * b)
                    + (-a + c) * t
                    + (2 * a - 5 * b + 4 * c - d) * t * t
                    + (-a + 3 * b - 3 * c + d) * t**3
                )
                for a, b, c, d in zip(p0, p1, p2, p3)
            )

        P = [ctrl[0]] + ctrl + [ctrl[-1]]
        path = []
        for i in range(1, len(P) - 2):
            for k in range(8):
                path.append(cr(P[i - 1], P[i], P[i + 1], P[i + 2], k / 8))
        path.append(ctrl[-1])
        HW, LIP, R = 0.205, 0.035, 0.045

        def section(hgt):
            pts = [(-HW - LIP, hgt), (-HW, hgt)]
            for k in range(5):
                a = math.pi + (math.pi / 2) * k / 4
                pts.append((-HW + R + R * math.cos(a), R + R * math.sin(a)))
            for k in range(5):
                a = 1.5 * math.pi + (math.pi / 2) * k / 4
                pts.append((HW - R + R * math.cos(a), R + R * math.sin(a)))
            pts += [(HW, hgt), (HW + LIP, hgt)]
            return pts

        verts, faces = [], []
        ns = None
        Ltot = len(path)
        for i, (y, z) in enumerate(path):
            y0, z0 = path[max(i - 1, 0)]
            y1, z1 = path[min(i + 1, Ltot - 1)]
            ty, tz = y1 - y0, z1 - z0
            l = math.hypot(ty, tz)
            ty, tz = ty / l, tz / l
            ny, nz_ = -tz, ty  # in-plane normal, pointing up off the bed
            if nz_ < 0:
                ny, nz_ = -ny, -nz_
            frac_end = max(
                0.0, (i - (Ltot - 22)) / 22
            )  # walls taper over the exit curl
            hgt = 0.13 * (1 - 0.85 * frac_end) + R * 0.85 * frac_end
            sec = section(max(hgt, R))
            ns = len(sec)
            for sx, sh in sec:
                verts.append((xm + sx, y + ny * sh, z + nz_ * sh))
            if i:
                b0, b1 = (i - 1) * ns, i * ns
                for k in range(ns - 1):
                    # Upward normals: solidify adds thickness below the riding surface.
                    faces.append((b1 + k, b1 + k + 1, b0 + k + 1, b0 + k))
        me = bpy.data.meshes.new("Slide")
        me.from_pydata(verts, [], faces)
        me.update()
        ob = bpy.data.objects.new("Slide", me)
        ob.data.materials.append(BLUE)
        SLD.objects.link(ob)
        mod = ob.modifiers.new("thickness", "SOLIDIFY")
        mod.thickness = T
        mod.offset = -1
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.modifier_apply(modifier="thickness")
        ob.select_set(False)
        for p in me.polygons:
            p.use_smooth = True
        ob["code"] = "Slide"
        ob["kind"] = "plastic"
        ob["mass_kg"] = 13.0
        p0, p1 = (
            Vector((xm, ctrl[0][0], ctrl[0][1])),
            Vector((xm, ctrl[2][0], ctrl[2][1])),
        )
        a = (p1 - p0).normalized()
        M["Slide"] = dict(
            obj=ob,
            p0=p0,
            p1=p1,
            u=Vector((1, 0, 0)),
            v=Vector((0, 0, 1)),
            a=a,
            sec=(2 * HW, T),
            code="Slide",
            kind="plastic",
            mass=13.0,
        )
        print(
            f"slide: top {SDZ:.2f} m, runout {0.28:.2f} m, end lip at ground, length along path {sum(math.dist(path[i], path[i + 1]) for i in range(Ltot - 1)):.2f} m"
        )

    build_slide()

    # ================= SWING BEAM + A-FRAME (steps 146-163, 191) =================
    SW = coll("Swing_frame")
    BZ = (
        1.956 - 0.07
    )  # Estimated layout:  beam TOP at 6'5" (listing: 6'6" top-to-ground); BZ = beam centreline
    # Y-bracket DRB-01 (parts drawing; layout confirmed by the user): a square beam cup, closed at the far end and open toward
    # the tower, with one leg socket welded to each side wall, set back from the closed end. The beam end runs between the two
    # leg tops to the closed end. Socket tops are level, 25 mm below the cup top. Two screw holes on the cup top, one near each
    # end (step 154); one screw per broad socket face (148-149).
    AX, AH = -3.03, 0.97  # A-frame plane x; leg foot spread from centre
    WT, SKT = 0.003, 0.078  # Estimated fit: 3 mm steel and 1 mm clearance per face.
    SLY, SLZ = 0.078, 0.148  # 70 x 140 mm beam plus walls and fitting clearance.
    YB_GAP, YB_FRONT = (
        0.05,
        0.11,
    )  # E  closed end set back behind the sockets; cup reach past them toward the tower
    XS0 = AX - SKT / 2 - YB_GAP  # cup's closed end
    SLL = YB_GAP + SKT + YB_FRONT
    BX1, BX0 = (
        -(lean(BZ) + LEG / 2),
        XS0 + 0.004,
    )  # beam: from the sleeve's end plate to the C05 post face
    member("B03", "B03", (BX0, 0, BZ), (BX1, 0, BZ), (0.07, 0.14), SW)
    WT = 0.003
    IB_SL, IB_H = 0.10, 0.14  # sleeve length on the beam; flange height
    IB_PARTS = []

    def ib_piece(p0, p1, sec):
        nm = f"_ib{len(IB_PARTS)}"
        member(
            nm, "DRB-02", p0, p1, sec, SW, m=BRICK, kind="steel", mass=0.0, up=(0, 0, 1)
        )
        IB_PARTS.append(nm)

    for sy in (
        -1,
        1,
    ):  # side plates: along the beam, then on past its end over the post's sides
        ib_piece(
            (BX1 - IB_SL, sy * (0.035 + WT / 2), BZ),
            (BX1 + LEG, sy * (0.035 + WT / 2), BZ),
            (WT, IB_H),
        )
    for sz in (-1, 1):  # top and bottom of the sleeve, on the beam only
        ib_piece(
            (BX1 - IB_SL, 0, BZ + sz * (0.07 + WT / 2)),
            (BX1, 0, BZ + sz * (0.07 + WT / 2)),
            (0.07 + 2 * WT, WT),
        )
    ibo = M[IB_PARTS[0]]["obj"]
    ibo.name = "DRB02_Ibracket"
    ibo.data.name = "DRB02_Ibracket"
    bm = bmesh.new()
    bm.from_mesh(ibo.data)
    for nm in IB_PARTS[1:]:
        so = M.pop(nm)["obj"]
        me2 = so.data.copy()
        me2.transform(ibo.matrix_world.inverted() @ so.matrix_world)
        bm.from_mesh(me2)
        bpy.data.objects.remove(so)
        bpy.data.meshes.remove(me2)
    bm.to_mesh(ibo.data)
    bm.free()
    M.pop(IB_PARTS[0])
    M["DRB02_Ibracket"] = dict(
        obj=ibo,
        p0=Vector((BX1 - IB_SL, 0, BZ)),
        p1=Vector((BX1, 0, BZ)),
        u=Vector((0, 1, 0)),
        v=Vector((0, 0, 1)),
        a=Vector((1, 0, 0)),
        sec=(0.07 + 2 * WT, 0.14 + 2 * WT),
        code="DRB-02",
        kind="steel",
        mass=1.6,
    )
    ibo["code"] = "DRB-02"
    ibo["kind"] = "steel"
    ibo["mass_kg"] = 1.6
    YB_PARTS = []

    def yb_piece(p0, p1, sec, up):
        nm = f"_yb{len(YB_PARTS)}"
        member(nm, "DRB-01", p0, p1, sec, SW, m=BRICK, kind="steel", mass=0.0, up=up)
        YB_PARTS.append(nm)

    def yb_prism(top4, bot4):
        """Steel piece from 4 top corners to 4 matching bottom corners (any shear)."""
        nm = f"_yb{len(YB_PARTS)}"
        me = bpy.data.meshes.new(nm)
        me.from_pydata(
            [tuple(v) for v in top4 + bot4],
            [],
            [
                (0, 1, 2, 3),
                (7, 6, 5, 4),
                (0, 4, 5, 1),
                (1, 5, 6, 2),
                (2, 6, 7, 3),
                (3, 7, 4, 0),
            ],
        )
        me.update()
        ob = bpy.data.objects.new(nm, me)
        ob.data.materials.append(BRICK)
        SW.objects.link(ob)
        M[nm] = dict(obj=ob)
        YB_PARTS.append(nm)

    yb_piece(
        (XS0, 0, BZ), (XS0 + 0.004, 0, BZ), (SLY, SLZ), (0, 0, 1)
    )  # sleeve end plate
    for sz in (-1, 1):
        yb_piece(
            (XS0, 0, BZ + sz * (SLZ / 2 - WT / 2)),
            (XS0 + SLL, 0, BZ + sz * (SLZ / 2 - WT / 2)),
            (SLY, WT),
            (0, 0, 1),
        )
    for sy in (-1, 1):
        yb_piece(
            (XS0, sy * (SLY / 2 - WT / 2), BZ),
            (XS0 + SLL, sy * (SLY / 2 - WT / 2), BZ),
            (WT, SLZ),
            (0, 0, 1),
        )
    # Straight square sleeves with vertical mitered ends flush on the cup.
    ZTOP = BZ + SLZ / 2
    H, SOCK = SKT / 2, 0.20
    XH = Vector((1, 0, 0))
    YB_DROP = 0.025
    ZS = ZTOP - YB_DROP
    socket_join_specs, socket_frames = [], []
    LEG_TOPS = {}
    for n, s in (("C20_F", -1), ("C20_B", 1)):
        th, qz = socket_miter_frame(SLY / 2, BZ - SLZ / 2, H, AH)
        yq = s * SLY / 2
        d = Vector((0, s * math.sin(th), -math.cos(th)))
        u = Vector((0, s * math.cos(th), math.sin(th)))
        Q = Vector((AX, yq, qz))
        first_vertex = sum(len(M[nm]["obj"].data.vertices) for nm in YB_PARTS)

        def corner(ex, eu, bottom):
            # A true miter: every end corner lies on the vertical cup wall.
            t = SOCK if bottom else max(-eu / math.tan(th),
                                        (qz + eu * math.sin(th) - ZS) / math.cos(th))
            return Q + XH * ex + u * eu + d * t

        def wall(ex0, ex1, eu0, eu1):
            cs = [(ex0, eu0), (ex1, eu0), (ex1, eu1), (ex0, eu1)]
            yb_prism([corner(ex, eu, False) for ex, eu in cs],
                     [corner(ex, eu, True) for ex, eu in cs])

        # Clip the high tip at the sleeve top; the vertical miter stops exactly
        # at the cup bottom. Split broad walls where the two end planes meet.
        split = (ZS - qz) * math.sin(th)
        wall(-H, H, H - WT, H)
        wall(-H, H, -H, -H + WT)
        for ex0, ex1 in ((H - WT, H), (-H, -H + WT)):
            wall(ex0, ex1, -H, split)
            wall(ex0, ex1, split, H)
        cap = [corner(ex, eu, False) for ex, eu in
               ((-H, -H), (H, -H), (H, split), (-H, split))]
        yb_prism(cap, [point + d * (WT / math.sin(th)) for point in cap])
        roof = [corner(ex, eu, False) for ex, eu in
                ((-H, split), (H, split), (H, H), (-H, H))]
        yb_prism(roof, [point + d * (WT / math.cos(th)) for point in roof])
        last_vertex = sum(len(M[nm]["obj"].data.vertices) for nm in YB_PARTS)
        socket_join_specs.append([s, yq, AX - H, AX + H,
                                  min(point.z for point in cap), max(point.z for point in cap)])
        socket_frames.append([s, yq, qz, math.sin(th), math.cos(th), H,
                              first_vertex, last_vertex])
        # A square-cut wooden leg fits beyond the miter's deepest corner.
        t0 = (0.035 * math.cos(th) + WT + 0.001) / math.sin(th)
        p0, p1 = Q + d * t0, Vector((AX, s * AH, 0.0))
        member(n, "C20", p0, p1, (0.07, 0.07), SW, up=(1, 0, 0))
        LEG_TOPS[n] = dict(p0=p0, d=d, u=u, mid=Q + d * (SOCK / 2))
    AF_Y0, AF_Z0 = abs(yq), qz
    yb = M[YB_PARTS[0]]["obj"]
    yb.name = "DRB01_Ybracket"
    yb.data.name = "DRB01_Ybracket"
    bm = bmesh.new()
    bm.from_mesh(yb.data)
    for nm in YB_PARTS[1:]:  # weld everything into one steel part
        so = M.pop(nm)["obj"]
        me2 = so.data.copy()
        me2.transform(yb.matrix_world.inverted() @ so.matrix_world)
        bm.from_mesh(me2)
        bpy.data.objects.remove(so)
        bpy.data.meshes.remove(me2)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(yb.data)
    bm.free()
    M.pop(YB_PARTS[0])
    M["DRB01_Ybracket"] = dict(
        obj=yb,
        p0=Vector((XS0, 0, BZ)),
        p1=Vector((XS0 + SLL, 0, BZ)),
        u=Vector((0, 1, 0)),
        v=Vector((0, 0, 1)),
        a=Vector((1, 0, 0)),
        sec=(SLY, SLZ),
        code="DRB-01",
        kind="steel",
        mass=2.2,
    )
    yb["code"] = "DRB-01"
    yb["kind"] = "steel"
    yb["mass_kg"] = 2.2
    import json
    yb["socket_join_specs"] = json.dumps(socket_join_specs)
    yb["socket_frames"] = json.dumps(socket_frames)
    for n, s in (("C20_F", -1), ("C20_B", 1)):
        ysk = s * (AF_Y0 + (AH - AF_Y0) * (1 - 0.06 / AF_Z0))
        member(
            f"Stake_{n}",
            "Stake",
            (AX + 0.041, ysk, 0.12),
            (AX + 0.041, ysk, -0.30),
            (0.012, 0.012),
            SW,
            m=STEEL,
            kind="steel",
            mass=0.6,
        )
    zf = 0.62
    yf30 = AF_Y0 + (AH - AF_Y0) * (1 - zf / AF_Z0)
    member(
        "F30",
        "F30",
        (AX + 0.05, -yf30 - 0.04, zf),
        (AX + 0.05, yf30 + 0.04, zf),
        (0.03, 0.09),
        SW,
        up=(0, 0, 1),
    )
    HANGERS = (-2.75, -2.30, -2.01, -1.56)  # Estimated layout

    def loop(name, centre, r, t, plane, c, m=STEEL):
        """Closed wire loop (ring, hook) in plane 'xz' or 'yz' around centre."""
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = t
        sp_ = cu.splines.new("POLY")
        sp_.points.add(15)
        sp_.use_cyclic_u = True
        for k in range(16):
            a_ = 2 * math.pi * k / 16
            cx, cz = r[0] * math.cos(a_), r[1] * math.sin(a_)
            sp_.points[k].co = (
                (centre[0] + cx, centre[1], centre[2] + cz, 1)
                if plane == "xz"
                else (centre[0], centre[1] + cx, centre[2] + cz, 1)
            )
        ob = bpy.data.objects.new(name, cu)
        ob.data.materials.append(m)
        c.objects.link(ob)
        return ob

    HANG_BOT = {}
    for i, x in enumerate(
        HANGERS
    ):  # swing hanger (step 159): bolt through the beam, pivot bracket, snap hook, O-ring
        zb_ = BZ - 0.07  # beam underside
        member(
            f"Hanger_{i}_plate",
            "Hanger",
            (x, 0, zb_ - 0.004),
            (x, 0, zb_),
            (0.03, 0.03),
            SW,
            m=STEEL,
            kind="steel",
            mass=0.02,
        )  # bearing collar
        vs = [
            (x - 0.022, 0, zb_ - 0.004),
            (x + 0.022, 0, zb_ - 0.004),
            (x + 0.006, 0, zb_ - 0.055),
            (x - 0.006, 0, zb_ - 0.055),
        ]
        me = bpy.data.meshes.new(f"Hanger_{i}")
        me.from_pydata(
            [(v[0], v[1] + o, v[2]) for o in (-0.009, 0.009) for v in vs],
            [],
            [
                (0, 1, 2, 3),
                (7, 6, 5, 4),
                (0, 4, 5, 1),
                (1, 5, 6, 2),
                (2, 6, 7, 3),
                (3, 7, 4, 0),
            ],
        )
        me.update()
        hb = bpy.data.objects.new(f"Hanger_{i}", me)
        hb.data.materials.append(STEEL)
        SW.objects.link(hb)
        hb["mass_kg"] = 0.15  # pivot bracket
        loop(
            f"Hook_{i}", (x, 0, zb_ - 0.095), (0.014, 0.036), 0.0035, "yz", SW
        )  # screw-gate snap hook
        member(
            f"Hook_{i}_gate",
            "Hanger",
            (x, 0.014, zb_ - 0.115),
            (x, 0.014, zb_ - 0.085),
            (0.008, 0.008),
            SW,
            m=STEEL,
            kind="steel",
            mass=0.0,
        )
        loop(
            f"Ring_{i}", (x, 0, zb_ - 0.150), (0.022, 0.022), 0.004, "xz", SW
        )  # O-ring the rope loops through
        HANG_BOT[i] = (x, 0, zb_ - 0.172)

    def swing_seat(name, cx, z, c):
        """Molded belt-style seat: curved up at the ends, tapered, lipped edges; rope brackets at each end."""
        L, T = 0.50, 0.012

        def dz(u):
            return 0.065 * abs(2 * u / L) ** 2.4

        def halfw(u):
            return 0.085 - 0.022 * (2 * u / L) ** 2

        verts, faces = [], []
        NU = 25
        for i in range(NU):
            u = -L / 2 + L * i / (NU - 1)
            hw = halfw(u)
            prof = [(-hw, 0.014), (-hw + 0.012, 0.0), (hw - 0.012, 0.0), (hw, 0.014)]
            for py, pz in prof:
                verts.append((cx + u, py, z + dz(u) + pz))
            if i:
                b0, b1 = (i - 1) * 4, i * 4
                for k in range(3):
                    faces.append((b0 + k, b0 + k + 1, b1 + k + 1, b1 + k))
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.update()
        ob = bpy.data.objects.new(name, me)
        ob.data.materials.append(BRICK)
        c.objects.link(ob)
        mod = ob.modifiers.new("t", "SOLIDIFY")
        mod.thickness = T
        mod.offset = -1
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.modifier_apply(modifier="t")
        ob.select_set(False)
        for p in me.polygons:
            p.use_smooth = True
        ob["code"] = "Seat"
        ob["kind"] = "plastic"
        ob["mass_kg"] = 1.2
        M[name] = dict(
            obj=ob,
            p0=Vector((cx - L / 2, 0, z)),
            p1=Vector((cx + L / 2, 0, z)),
            u=Vector((0, 1, 0)),
            v=Vector((0, 0, 1)),
            a=Vector((1, 0, 0)),
            sec=(0.17, T),
            code="Seat",
            kind="plastic",
            mass=1.2,
        )
        tops = []
        for s in (-1, 1):  # end brackets clamp the rope to the seat
            ue = s * (L / 2 - 0.025)
            zt = z + dz(ue)
            member(
                f"{name}_bracket_{'L' if s < 0 else 'R'}",
                "Seat bracket",
                (cx + ue, 0, zt - 0.02),
                (cx + ue, 0, zt + 0.05),
                (0.035, 0.05),
                c,
                m=BRICK,
                kind="plastic",
                mass=0.1,
                up=(1, 0, 0),
            )
            tops.append((cx + ue, 0, zt + 0.05))
        return tops

    SEAT_Z = 0.36  # minimum finished underside clearance; add thickness before solidify (step 192)
    for si, (xa, xb) in enumerate(((HANGERS[0], HANGERS[1]), (HANGERS[2], HANGERS[3]))):
        tops = swing_seat(f"Swing{si}_seat", (xa + xb) / 2, SEAT_Z + 0.012, SW)
        for x, top in zip((xa, xb), tops):
            rope(
                f"Swing{si}_rope_{x:.2f}",
                [HANG_BOT[HANGERS.index(x)], top],
                SW,
                r=0.008,
            )

    # ================= NETS (steps 173-184) =================
    NT = coll("Nets")
    NET_FIX = []  # (step, eye member, structure member, fastener type)

    def eye(name, centre, normal, c, size=0.028, thick=0.008):
        """Steel rope-end fitting: a small plate with its face against `normal` (pointing from the eye into the wood)."""
        n_ = Vector(normal).normalized()
        up = (0, 0, 1) if abs(n_.z) < 0.9 else (1, 0, 0)
        cv = Vector(centre)
        member(
            name,
            "Eye",
            cv - n_ * thick / 2,
            cv + n_ * thick / 2,
            (size, size),
            c,
            m=STEEL,
            kind="steel",
            mass=0.05,
            up=up,
        )

    # hammock cargo net: 8 eye bolts, one through each tower leg at the same height, eyes on the legs' inner faces (steps 174-179)
    EZ, SAG, N = 0.85, 0.32, 15
    EYE_T = 0.015  # Estimated eye body depth; shank must reach the far-side BM818.
    hh = lean(EZ) - LEG / 2 - EYE_T  # net perimeter sits on the inner side of the eyes

    def nz(x, y):
        return EZ - SAG * (1 - (x / hh) ** 2) * (1 - (y / hh) ** 2)

    for ax in (0, 1):
        for i in range(N):
            t = -hh + 2 * hh * i / (N - 1)
            ps = []
            for jj in range(N):
                s_ = -hh + 2 * hh * jj / (N - 1)
                x, y = (s_, t) if ax == 0 else (t, s_)
                ps.append((x, y, nz(x, y)))
            rope(f"Hammock_{ax}_{i}", ps, NT, r=0.006)
    for leg, (sx, sy), st in (
        ("C06", (1, 0), 175),
        ("C05", (-1, 0), 175),
        ("C04A", (0, 1), 176),
        ("C04B", (0, -1), 176),
        ("C01A", (1, 1), 177),
        ("C03", (1, -1), 177),
        ("C02", (-1, 1), 178),
        ("C01B", (-1, -1), 178),
    ):
        out = Vector((sx, sy, 0)).normalized()
        face_pt = Vector((sx * (lean(EZ) - LEG / 2), sy * (lean(EZ) - LEG / 2), EZ))
        eye(
            f"Hammock_eye_{leg}",
            face_pt - out * EYE_T / 2,
            out,
            NT,
            size=0.03,
            thick=EYE_T,
        )
        NET_FIX.append((st, f"Hammock_eye_{leg}", leg, "EYE"))

    # climbing net: in the plane of the back face's outer leg faces between C02 and C04A (steps 180-184).
    # Vertical ropes: tops bolted to the floor rail K07 (M833), bottoms to the base board S04A (M821);
    # horizontal ropes: ends screwed into the inner side faces of C02 and C04A (8x M8SW50).
    def ny(z):
        return (
            lean(z) + LEG / 2 - 0.015
        )  # rope plane, 15 mm inside the legs' outer faces

    ET = 0.005  # Estimated net fixing plate thickness for the specified M821/BM818 stack.
    for k_, x in enumerate((-0.65, -0.35)):
        zt_, zb2 = zr - 0.03, zb
        for tag, z, rail in (("top", zt_, "K07"), ("bot", zb2, "S04A")):
            yr_ = lean(z) + LEG / 2  # rail inner face
            eye(f"Climb_eye_{tag}_{k_}", (x, yr_ - ET / 2, z), (0, 1, 0), NT, thick=ET)
            NET_FIX.append(
                (
                    182 if tag == "top" else 183,
                    f"Climb_eye_{tag}_{k_}",
                    rail,
                    "M833" if tag == "top" else "M821",
                )
            )
        rope(f"Climb_v_{k_}", [(x, ny(zt_), zt_), (x, ny(zb2), zb2)], NT, r=0.009)
    for k_ in range(4):
        z = zr - (k_ + 1) * (zr - zb) / 5
        xw, xe = -lean(z) + LEG / 2, -LEG / 2  # inner side faces of C02 and C04A
        eye(f"Climb_eye_W_{k_}", (xw + ET / 2, ny(z), z), (-1, 0, 0), NT, thick=ET)
        eye(f"Climb_eye_E_{k_}", (xe - ET / 2, ny(z), z), (1, 0, 0), NT, thick=ET)
        NET_FIX += [
            (184, f"Climb_eye_W_{k_}", "C02", "M8SW50"),
            (184, f"Climb_eye_E_{k_}", "C04A", "M8SW50"),
        ]
        rope(f"Climb_h_{k_}", [(xw + ET, ny(z), z), (xe - ET, ny(z), z)], NT, r=0.009)

    return Geometry(
        members=M,
        knees=KNEE,
        ring_polygons=RING_POLY,
        rafters=RAFTERS,
        leg_tops=LEG_TOPS,
        net_fixings=NET_FIX,
        floor_support_y=yr,
        steel=STEEL,
        knee_point=knee_pt,
        rafter_bottom=raft_bot,
        parameters={
            "tarp_extent": te,
            "tarp_corner_z": ZC,
            "tarp_mid_z": TZ,
            "tarp_skirt": SKIRT,
            "roof_outer_slope": (rt_ - rb) / (zp1 - zp0),
            "roof_outer_intercept": pc(0) + RP / 2 + RT,
            "zr": zr,
            "RH": RH,
            "CBT": CBT,
            "RO": RO,
            "RI": RI,
            "RING_C": RING_C,
            "RD_V": RD_V,
            "KB_HALF": KB_HALF,
            "K03_OUT": K03_OUT,
            "zsr": zsr,
            "H": H,
            "XH": XH,
            "BX1": BX1,
            "IB_SL": IB_SL,
            "LEG": LEG,
            "WT": WT,
            "BZ": BZ,
            "XS0": XS0,
            "SLZ": SLZ,
            "SLL": SLL,
        },
    )
