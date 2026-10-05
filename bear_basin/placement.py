"""Fastener positioning. Explicit joints use geometry context; generic joints sample local boxes."""

import math
import numpy as np
from mathutils import Vector
from .hardware import FT


def seg_closest(p1, q1, p2, q2):
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f_ = d1.dot(d1), d2.dot(d2), d2.dot(r)
    c = d1.dot(r)
    b = d1.dot(d2)
    den = a * e - b * b
    s = min(max((b * f_ - c * e) / den, 0), 1) if den > 1e-12 else 0.0
    t = (b * s + f_) / e
    if t < 0:
        t = 0
        s = min(max(-c / a, 0), 1)
    elif t > 1:
        t = 1
        s = min(max((b - c) / a, 0), 1)
    return p1 + d1 * s, p2 + d2 * t


def obb(d):
    """Member as an oriented box: centre, unit axes (u, v, a), half-extents."""
    c = (d["p0"] + d["p1"]) / 2
    return (
        c,
        (d["u"], d["v"], d["a"]),
        (d["sec"][0] / 2, d["sec"][1] / 2, (d["p1"] - d["p0"]).length / 2),
    )


def interval(box, ax):
    c, axes, hx = box
    r = sum(h * abs(e.dot(ax)) for e, h in zip(axes, hx))
    m = c.dot(ax)
    return m - r, m + r


def local_obb(d, other):
    """Box of the part of d near `other`: long parts (legs, rails) are clipped around the closest point so a leaning
    2 m leg doesn't look 20 cm wide. Parallel parts (stacked boards) stay whole."""
    c, axes, hx = obb(d)
    if abs(d["a"].dot(other["a"])) > 0.95:
        return c, axes, hx
    pa, _ = seg_closest(d["p0"], d["p1"], other["p0"], other["p1"])
    half = min(hx[2], max(other["sec"]) / 2 + 0.06)
    s = (pa - d["p0"]).dot(d["a"])
    Ld = (d["p1"] - d["p0"]).length
    s = min(max(s, half), Ld - half)
    return d["p0"] + d["a"] * s, axes, (hx[0], hx[1], half)


def explicit_fasteners(geometry, step, a, b, ft, n):
    """Joints whose fastener positions the manual pins down and box contact can't infer."""
    M = geometry.members
    KNEE, RING_POLY, RAFTERS = geometry.knees, geometry.ring_polygons, geometry.rafters
    LEG_TOPS = geometry.leg_tops
    knee_pt, raft_bot = geometry.knee_point, geometry.rafter_bottom
    zr = geometry.parameters["zr"]
    RH = geometry.parameters["RH"]
    CBT = geometry.parameters["CBT"]
    RO = geometry.parameters["RO"]
    RI = geometry.parameters["RI"]
    RING_C = geometry.parameters["RING_C"]
    RD_V = geometry.parameters["RD_V"]
    KB_HALF = geometry.parameters["KB_HALF"]
    K03_OUT = geometry.parameters["K03_OUT"]
    zsr = geometry.parameters["zsr"]
    H = geometry.parameters["H"]
    XH = geometry.parameters["XH"]
    BX1 = geometry.parameters["BX1"]
    IB_SL = geometry.parameters["IB_SL"]
    LEG = geometry.parameters["LEG"]
    WT = geometry.parameters["WT"]
    BZ = geometry.parameters["BZ"]
    XS0 = geometry.parameters["XS0"]
    SLZ = geometry.parameters["SLZ"]
    SLL = geometry.parameters["SLL"]
    L = FT[ft][1] / 1000
    down = Vector((0, 0, -1))
    if a.startswith("Handle_") and "_foot" in a:
        # Leave the screw head accessible beside the grip's central standoff.
        direction = -M[a]["a"]
        head = M[a]["p1"] + M[a]["v"] * 0.016
        return [head + direction * L / 2], direction
    if a.startswith("Climb_eye_"):
        # Seat the head on the fixing plate, avoiding projected box padding on
        # the short M821 bolts used at the lower rail.
        direction = M[a]["a"]
        return [M[a]["p0"] + direction * L / 2], direction
    if a == "Slide":
        # Two holes through the flat mounting bed, clear of the rounded side walls.
        top = M[a]["p0"]
        return [Vector((top.x + dx, top.y - 0.025, top.z)) + down * L / 2
                for dx in (-0.10, 0.10)], down
    if step == 104 and a in ("K20", "K21"):
        # Screws enter the upright's outside face and run into each rung end.
        rung = M[b]
        direction = Vector((1 if a == "K20" else -1, 0, 0))
        center = (rung["p0"] + rung["p1"]) / 2
        upright_x = M[a]["p0"].x
        return [Vector((upright_x - direction.x * 0.0175,
                        center.y + dy, center.z)) + direction * L / 2
                for dy in (-0.022, 0.022)], direction
    if a == "Tarp":
        # Through the skirt into each rail, six evenly spaced positions (spacing estimated).
        extent = geometry.parameters["tarp_extent"]
        corner_z = geometry.parameters["tarp_corner_z"]
        middle_z = geometry.parameters["tarp_mid_z"]
        skirt = geometry.parameters["tarp_skirt"]
        side = b.rsplit("_", 1)[1]
        outward = Vector(
            {"B": (0, 1, 0), "F": (0, -1, 0), "W": (-1, 0, 0), "E": (1, 0, 0)}[side]
        )
        along = Vector((1, 0, 0)) if side in ("B", "F") else Vector((0, 1, 0))
        points = []
        for offset in np.linspace(-extent * 0.85, extent * 0.85, n):
            z = middle_z + (corner_z - middle_z) * abs(offset) / extent - skirt / 2
            outer = geometry.parameters["roof_outer_intercept"] + z * geometry.parameters["roof_outer_slope"]
            head = outward * outer + along * float(offset) + Vector((0, 0, z))
            points.append(head - outward * L / 2)
        return points, -outward
    if a in RING_POLY and not b.startswith(
        "F1"
    ):  # connect board <-> leg top / roof post bottom (steps 59-61, 120)
        poly = RING_POLY[a]["poly"]
        z0 = RING_POLY[a]["z0"]

        def inpoly(q):
            sg = None
            for i_ in range(len(poly)):
                p1_, p2_ = poly[i_], poly[(i_ + 1) % len(poly)]
                cr = (p2_.x - p1_.x) * (q[1] - p1_.y) - (p2_.y - p1_.y) * (q[0] - p1_.x)
                if abs(cr) < 1e-12:
                    continue
                if sg is None:
                    sg = cr > 0
                elif (cr > 0) != sg:
                    return False
            return True

        d = M[b]
        post_up = (
            d["p0"].z > z0
        )  # roof post standing on the board, or tower leg under it
        end = d["p0"] if post_up else d["p1"]
        cand = [
            (end.x + gx, end.y + gy)
            for gx in np.linspace(-0.023, 0.023, 9)
            for gy in np.linspace(-0.023, 0.023, 9)
        ]
        cand = [
            q
            for q in cand
            if all(
                inpoly((q[0] + ex, q[1] + ey))
                for ex, ey in ((0, 0), (0.012, 0), (-0.012, 0), (0, 0.012), (0, -0.012))
            )
        ]
        if not cand:
            return None
        bd = M[a]["a"]
        cq = np.array(cand)
        sv = cq @ np.array([bd.x, bd.y])
        picks = (
            [cq[int(np.argmin(sv))], cq[int(np.argmax(sv))]]
            if n >= 2
            else [cq[len(cq) // 2]]
        )
        ax = Vector((0, 0, 1)) if post_up else Vector((0, 0, -1))
        zh = z0 if post_up else z0 + CBT  # head on the board's outer face
        return [
            Vector((float(q[0]), float(q[1]), zh)) + ax * (L / 2) for q in picks[:n]
        ], ax
    if (
        a in KNEE
    ):  # step 42: bolt through the upper end into the rail, screw through the lower cut into the post
        kb = KNEE[a]
        zt = zr + RH / 2
        if ft == "M865":
            hd = knee_pt(kb, kb["DROP"] - 0.035, zt - 0.035, kb["T"])
            tp = knee_pt(kb, kb["DROP"] - 0.035, zt - 0.035, 0.0)
            ax = (tp - hd).normalized()
            return [hd + ax * L / 2], ax
        hd = knee_pt(kb, 0.03, zt - kb["DROP"] + 0.03, kb["T"] / 2)
        tp = knee_pt(kb, -0.02, zt - kb["DROP"] + 0.03, kb["T"] / 2)
        ax = (tp - hd).normalized()
        return [hd + ax * L / 2], ax
    if a in RAFTERS and b.startswith(
        "C09"
    ):  # step 124: two holes centred diagonally over the post top, driven down
        e = RAFTERS[a]["e"]
        pc_ = M[b]["p1"]
        pts = []
        for off in (-0.018, 0.018):
            q = Vector((pc_.x, pc_.y, 0)) + e * off
            d = q.length
            ztop = raft_bot(d) + RD_V
            pts.append(Vector((q.x, q.y, ztop - L / 2)))
        return pts, down
    if (
        a in RAFTERS and b == "KA09"
    ):  # step 129: toe-screwed from the rafter's top end into the brace block
        e = RAFTERS[a]["e"]
        dh = KB_HALF + 0.04
        hd = e * dh + Vector((0, 0, raft_bot(dh) + RD_V))
        tgt = Vector((0, 0, raft_bot(KB_HALF) + RD_V / 2))
        ax = (tgt - hd).normalized()
        return [hd + ax * L / 2], ax
    if (
        a in ("K20", "K21") and b == "K03"
    ):  # step 106: through the upright's top end into the floor rail
        x = M[a]["p0"].x
        hd = Vector((x, K03_OUT + 0.035, zsr))
        ax = Vector((0, -1, 0))
        return [hd + ax * L / 2], ax
    if a == "DRB01_Ybracket" and b.startswith(
        "C20"
    ):  # mid-length of each socket: tower-side face (148), outward face (149)
        lt = LEG_TOPS[b]
        nrm_ = XH if step == 148 else lt["u"]
        hd = lt["mid"] + nrm_ * H
        ax = -nrm_
        return [hd + ax * L / 2], ax
    if (
        a == "DRB02_Ibracket"
    ):  # side plates: 2 screws per side, into the beam (151-152) or the post (157-158)
        sy = 1 if step in (151, 157) else -1
        ax = Vector((0, -sy, 0))
        xc = BX1 - IB_SL / 2 if b == "B03" else BX1 + LEG / 2
        return [
            Vector((xc, sy * (0.035 + WT), BZ + dz)) + ax * L / 2
            for dz in (-0.035, 0.035)[:n]
        ], ax
    if (
        a == "DRB01_Ybracket" and b == "B03"
    ):  # step 154: two screws down through the sleeve's top holes into the beam
        ax = Vector((0, 0, -1))
        return [
            Vector((XS0 + xo, 0, BZ + SLZ / 2)) + ax * L / 2
            for xo in (0.025, SLL - 0.025)[:n]
        ], ax  # one hole near each end of the cup top (parts drawing)
    if ft == "M833" and a in (
        "F11r_B",
        "F11r_W",
        "F12r",
        "F13r",
    ):  # ring-to-ring bolts between the posts, heads on the roof ring (steps 136-139)
        A = M[a]
        zt = A["p0"].z + CBT / 2
        om = (RO + RI) / 2
        side = {"F11r_B": "B", "F12r": "F", "F11r_W": "W", "F13r": "E"}[a]
        ts = {
            "B": (-RING_C / 2, RING_C / 2),
            "F": (-RING_C / 2, RING_C / 2),
            "W": (-RING_C / 2, RING_C / 2),
            "E": (RING_C / 2,),
        }[side]
        pts = []
        for t in ts:
            for w in (-0.025, 0.025) if n > len(ts) else (0.0,):
                o = om + w
                x, y = {"B": (t, o), "F": (t, -o), "W": (-o, t), "E": (o, t)}[side]
                pts.append(Vector((x, y, zt - L / 2)))
        return pts[:n], down
    return None


def contact_frame(A, B, L, bolt=False):
    """Find the face where A meets B (the axis of least box overlap), seat the heads flush on A's outer face pointing
    into B, and spread n fasteners over the patch where the two parts overlap. Returns the shared local contact frame."""
    ba, bb = local_obb(A, B), local_obb(B, A)
    cands = []
    for e in list(ba[1]) + list(bb[1]):
        if all(abs(e.dot(f_)) < 0.999 for f_ in cands):
            cands.append(e.normalized())
    best = None
    for e in cands:
        a0, a1 = interval(ba, e)
        b0, b1 = interval(bb, e)
        ov = min(a1, b1) - max(a0, b0)
        if best is None or ov < best[0]:
            best = (ov, e)
    ov, nrm = best
    if (bb[0] - ba[0]).dot(nrm) < 0:
        nrm = -nrm
    a0, a1 = interval(ba, nrm)
    b0, b1 = interval(bb, nrm)
    s_c = (a1 + b0) / 2  # contact plane
    s_h = (
        a0 if bolt else max(a0, s_c - 0.6 * L)
    )  # Legacy recess estimate; actual-mesh validation flags unmodeled counterbores.
    t1 = None
    for e in (A["a"], A["u"], A["v"]):
        t = e - nrm * e.dot(nrm)
        if t.length > 0.3:
            t1 = t.normalized()
            break
    t2 = nrm.cross(t1).normalized()
    return ba, bb, ov, nrm, s_c, s_h, t1, t2


def projected_positions(frame, L, n):
    """Estimated positions labeled in records; actual mesh validation is authoritative."""
    ba, bb, ov, nrm, s_c, s_h, t1, t2 = frame
    patch = []
    for t in (t1, t2):
        p0_, p1_ = interval(ba, t)
        q0, q1 = interval(bb, t)
        lo, hi_ = max(p0_, q0), min(p1_, q1)
        if hi_ < lo:
            lo = hi_ = (lo + hi_) / 2
        patch.append(((lo + hi_) / 2, hi_ - lo))
    (c1, e1), (c2, e2) = patch
    long_, short_ = (0, 1) if e1 >= e2 else (1, 0)
    cs, es = [c1, c2], [e1, e2]
    ts = [t1, t2]
    pts = []
    rows = 2 if (n >= 4 and es[short_] > 0.06) else 1
    per = math.ceil(n / rows)
    for r in range(rows):
        cnt = per if r < rows - 1 else n - per * (rows - 1)
        inset_s = min(0.02, es[short_] * 0.25)
        off_s = 0.0 if rows == 1 else (-1 if r == 0 else 1) * (es[short_] / 2 - inset_s)
        inset = min(0.025, es[long_] * 0.2)
        span = max(0.0, es[long_] - 2 * inset)
        for k in range(cnt):
            off_l = 0.0 if cnt == 1 else (k / (cnt - 1) - 0.5) * span
            q = [0.0, 0.0]
            q[long_] = cs[long_] + off_l
            q[short_] = cs[short_] + off_s
            pts.append(nrm * (s_h + L / 2) + ts[0] * q[0] + ts[1] * q[1])
    return pts, nrm, max(0.0, -ov), "projected"


def inside_np(box, P, nrm, inset):
    """Points P (N,3) inside box, shrunk by `inset` on the box axes that lie in the contact plane."""
    c, axes, hx = box
    Q = P - np.array(c)
    ok = np.ones(len(P), bool)
    for e, h in zip(axes, hx):
        w = 1.0 - abs(e.dot(nrm))
        ok &= np.abs(Q @ np.array(e)) <= h - inset * w + 1e-4
    return ok


def place_fasteners(A, B, L, n, bolt=False):
    """Find the face where A meets B (axis of least overlap between the local boxes), then sample the contact plane for
    spots where the whole fastener fits: head in A, shank through the joint, tip in B, with an edge margin. Spread n
    fasteners along the long direction of that region. Returns (centres, axis, gap_m, method)."""
    frame = contact_frame(A, B, L, bolt)
    ba, bb, ov, nrm, s_c, s_h, t1, t2 = frame
    mid = (ba[0] + bb[0]) / 2
    mid = mid + nrm * (s_c - mid.dot(nrm))
    R = min(0.35, max(max(ba[2]), max(bb[2])))
    g = np.linspace(-R, R, 81)
    G1, G2 = np.meshgrid(g, g)
    G1 = G1.ravel()
    G2 = G2.ravel()
    P = np.array(mid)[None, :] + G1[:, None] * np.array(t1) + G2[:, None] * np.array(t2)
    nv = np.array(nrm)
    tip_allow = 0.012 if bolt else 0.0
    for inset in (0.012, 0.008, 0.005, 0.002, 0.0):
        d_in = 0.001
        ok = inside_np(ba, P + nv * (s_h - s_c + d_in), nrm, inset)
        ok &= inside_np(ba, P - nv * d_in, nrm, inset)
        ok &= inside_np(bb, P + nv * d_in, nrm, inset)
        ok &= inside_np(bb, P + nv * (s_h + L - s_c - d_in - tip_allow), nrm, inset)
        for part in (A, B):
            if "outline_xy" in part:
                poly = part["outline_xy"]
                in_poly = np.zeros(len(P), dtype=bool)
                for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
                    if y1 != y2:
                        crosses = (y1 > P[:, 1]) != (y2 > P[:, 1])
                        in_poly ^= crosses & (
                            P[:, 0] < (x2 - x1) * (P[:, 1] - y1) / (y2 - y1) + x1
                        )
                ok &= in_poly
        if ok.sum() >= n:
            break
    if ok.sum() == 0:
        return projected_positions(frame, L, n)
    U = np.stack([G1[ok], G2[ok]], 1)
    cen = U.mean(0)
    if len(U) > 2:
        w_, v_ = np.linalg.eigh(np.cov((U - cen).T))
        pa_ = v_[:, -1]
        pb_ = v_[:, 0]
    else:
        pa_, pb_ = np.array([1.0, 0]), np.array([0, 1.0])
    sa = (U - cen) @ pa_
    sb = (U - cen) @ pb_
    width = sb.max() - sb.min()
    rows = 2 if (n >= 4 and width > 0.05) else 1
    per = math.ceil(n / rows)
    chosen = []
    for r_ in range(rows):
        cnt = per if r_ < rows - 1 else n - per * (rows - 1)
        off = 0.0 if rows == 1 else (-1 if r_ == 0 else 1) * width / 4
        for k_ in range(cnt):
            ta = (
                0.0 if cnt == 1 else sa.min() + (sa.max() - sa.min()) * (k_ / (cnt - 1))
            )
            tgt = cen + pa_ * ta + pb_ * off
            dist = ((U - tgt) ** 2).sum(1)
            for idx in np.argsort(dist):
                if idx not in chosen:
                    chosen.append(int(idx))
                    break
    pts = []
    for idx in chosen:
        q = mid + t1 * float(U[idx, 0]) + t2 * float(U[idx, 1])
        pts.append(q + nrm * (s_h + L / 2 - s_c))
    return pts, nrm, max(0.0, -ov), "sampled"
