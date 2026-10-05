"""Validation and accounting independent of the positioning heuristics.

Record checks run without Blender. Mesh checks inspect real world-space triangles,
including custom shapes that the previous box checks silently skipped.
"""

from collections import Counter
import math
from .hardware import FT, NUTS, MANUAL_INVENTORY, nut_for


def validate_records(members, joints, fasteners, nuts):
    errors = []
    declared = Counter()
    ids = set()
    definitions = {}
    for i, joint in enumerate(joints):
        step, attached, base, kind, count = joint
        joint_id = f"joint_{i:04d}"
        definitions[joint_id] = (step, attached, base, kind)
        if attached not in members or base not in members:
            errors.append(f"{joint_id}: unknown member {attached} / {base}")
        if kind not in FT or type(count) is not int or count <= 0:
            errors.append(f"{joint_id}: invalid hardware/count")
        else:
            declared[joint_id] = count
    actual = Counter()
    expected_nuts = Counter()
    for item in fasteners:
        fid = item["id"]
        if fid in ids:
            errors.append(f"Duplicate fastener id: {fid}")
        ids.add(fid)
        jid = item["joint_id"]
        actual[jid] += 1
        if jid not in declared:
            errors.append(f"{fid}: unknown joint {jid}")
        if (
            jid in definitions
            and tuple(item[key] for key in ("step", "attached", "base", "type"))
            != definitions[jid]
        ):
            errors.append(f"{fid}: assignment differs from declared joint")
        for field in ("pos", "axis"):
            values = item[field]
            if len(values) != 3 or not all(math.isfinite(x) for x in values):
                errors.append(f"{fid}: invalid {field}")
        if abs(sum(x * x for x in item["axis"]) - 1) > 1e-5:
            errors.append(f"{fid}: axis is not a unit vector")
        for kind in nut_for(item["step"], item["type"], item["attached"], item["base"]):
            expected_nuts[(fid, kind, "base")] += 1
        if item["type"] == "HANGER":
            expected_nuts[(fid, "Washer", "head")] += 1
    for jid in declared.keys() | actual.keys():
        if declared[jid] != actual[jid]:
            errors.append(f"{jid}: expected {declared[jid]}, placed {actual[jid]}")
    actual_nuts = Counter((n["fastener_id"], n["type"], n["side"]) for n in nuts)
    for key in expected_nuts.keys() | actual_nuts.keys():
        if expected_nuts[key] != actual_nuts[key]:
            errors.append(f"Incorrect nut/washer stack: {key}")
    for name, member in members.items():
        mass = member["mass"]
        if not math.isfinite(mass) or mass < 0:
            errors.append(f"{name}: invalid mass")
    counts = Counter(f["type"] for f in fasteners) + Counter(n["type"] for n in nuts)
    inventory = {
        kind: {
            "manual": count,
            "modeled": counts[kind],
            "difference": counts[kind] - count,
        }
        for kind, count in MANUAL_INVENTORY.items()
    }
    return {"errors": errors, "inventory": inventory}


def interval_overlap(interval, start, end, tolerance=0.0):
    """True for an intersection, including a segment wholly inside the interval."""
    lo, hi = interval
    return max(lo, start) <= min(hi, end) + tolerance


def interval_gap(left, right):
    """Minimum separation of two unions of intervals on the same line."""
    return min(
        (max(a0 - b1, b0 - a1, 0.0) for a0, a1 in left for b0, b1 in right),
        default=math.inf,
    )


def union_intervals(intervals, epsilon=1e-5):
    """Solid union: overlapping closed shells do not create imaginary cavities."""
    result = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1] + epsilon:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def connected_face_components(polygons):
    """Group faces by shared vertex indices, retaining separate joined solids."""
    parents = list(range(len(polygons)))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    owner = {}
    for index, polygon in enumerate(polygons):
        for vertex in polygon:
            if vertex in owner:
                parents[root(index)] = root(owner[vertex])
            else:
                owner[vertex] = index
    groups = {}
    for index, polygon in enumerate(polygons):
        groups.setdefault(root(index), []).append(polygon)
    return list(groups.values())


def line_intervals(tree, head, axis, radius, sheet=False):
    """Intersect the infinite fastener line with the actual mesh, from outside its bounds."""
    origin = head - axis * radius
    end = 2 * radius
    travelled = 0.0
    hits = []
    for _ in range(128):
        hit, _, _, distance = tree.ray_cast(origin, axis, end - travelled)
        if hit is None:
            break
        travelled += distance
        hits.append(travelled - radius)
        epsilon = 1e-5
        travelled += epsilon
        origin = hit + axis * epsilon
        if travelled >= end:
            break
    else:
        raise ValueError("Mesh line intersection exceeded its bounded iteration limit")
    if sheet:
        return [(hit, hit) for hit in hits]
    if len(hits) % 2:
        raise ValueError(
            "Mesh line has an odd number of crossings; inspect mesh closure"
        )
    return list(zip(hits[::2], hits[1::2]))


def path_issues(attached, base, length, diameter, tolerance=0.004, sheet=False):
    """Audit material along the physical shank, independently of its placement."""
    reasons = []
    minimum = max(0.003, diameter / 2)
    attached = [span for span in attached if interval_overlap(span, 0, length, 1e-5)]
    base = [(max(0, lo), min(length, hi)) for lo, hi in base
            if interval_overlap((lo, hi), 0, length)]
    if not attached:
        reasons.append("shank does not intersect attached material")
    if not base:
        reasons.append("shank does not intersect base material")
    elif max(hi - lo for lo, hi in base) < minimum:
        reasons.append(f"base engagement is less than {minimum:.4f} m")
    entries = [span for span in attached if -tolerance <= span[0] <= tolerance]
    if attached and not entries:
        reasons.append("head does not start at the attached material entry")
    if entries and not sheet:
        entries = [span for span in entries
                   if min(length, span[1]) - max(0, span[0]) >= 0.0005]
        if not entries:
            reasons.append("shank has no meaningful attached material engagement")
    if attached and base:
        gap = interval_gap(attached, base)
        if gap > tolerance:
            reasons.append(f"meshes are separated by {gap:.4f} m along the fastener")
        elif entries and not any(
            b1 - b0 >= minimum
            and b1 > max(0, a0)
            and b0 <= min(length, a1) + tolerance
            for a0, a1 in entries for b0, b1 in base
        ):
            reasons.append("material at the head has no continuous path into the base")
    return reasons


def nut_reached(kind, position, length):
    """The nominal bolt reaches material that represents the nut's thread zone."""
    _, flange, _, barrel = NUTS[kind]
    if kind == "Washer":
        return length >= position + flange - 1e-5
    start, end = ((position, position + flange) if kind == "LockNut"
                  else (position - barrel, position))
    return min(length, end) - max(0, start) >= min(0.003, end - start) - 1e-5


def validate_meshes(geometry, fasteners, tolerance=0.004, nuts=None):
    """Check actual mesh contact and fastener seating, including custom shapes.

    Geometry checks are separate from physical strength or real-world accuracy.
    The tolerance accommodates the source model's approximate dimensions.
    """
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    trees, shell_trees, vertices_by_name = {}, {}, {}
    for name, part in geometry.members.items():
        obj = part["obj"]
        vertices = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
        vertices_by_name[name] = vertices
        polygons = [tuple(poly.vertices) for poly in obj.data.polygons]
        trees[name] = BVHTree.FromPolygons(vertices, polygons, all_triangles=False)
        shell_trees[name] = [
            BVHTree.FromPolygons(vertices, shell, all_triangles=False)
            for shell in connected_face_components(polygons)
        ]
    failures = []
    nuts_by_fastener = {}
    for nut in nuts or []:
        nuts_by_fastener.setdefault(nut["fastener_id"], []).append(nut)
    for item in fasteners:
        center, axis = Vector(item["pos"]), Vector(item["axis"])
        length = FT[item["type"]][1] / 1000
        head = center - axis * length / 2
        reasons, spans = [], []
        if "mesh_unresolved" in item.get("placement", ""):
            reasons.append("mesh placement refinement was unresolved")
        nearest = trees[item["attached"]].find_nearest(head)
        if nearest[0] is None or nearest[3] > tolerance:
            reasons.append("head is not on the attached mesh surface")
        for label, name in (("attached", item["attached"]), ("base", item["base"])):
            radius = (
                max((point - head).length for point in vertices_by_name[name]) + 0.1
            )
            try:
                intervals = union_intervals(
                    span
                    for tree in shell_trees[name]
                    for span in line_intervals(
                        tree, head, axis, radius,
                        sheet=geometry.members[name]["kind"] == "fabric",
                    )
                )
            except ValueError as error:
                reasons.append(f"{label}: {error}")
                intervals = []
            spans.append(intervals)
        reasons.extend(path_issues(
            *spans, length, FT[item["type"]][0] / 1000, tolerance,
            sheet=geometry.members[item["attached"]]["kind"] == "fabric",
        ))
        base_spans = [span for span in spans[1] if interval_overlap(span, 0, length)]
        far_face = max((span[1] for span in base_spans), default=None)
        stack = 0.0
        for nut in nuts_by_fastener.get(item["id"], []):
            offset = Vector(nut["pos"]) - head
            axial = offset.dot(axis)
            if (offset - axis * axial).length > tolerance:
                reasons.append(f"{nut['type']} is not aligned with its fastener")
            if nut["side"] == "head":
                if abs(axial) > tolerance:
                    reasons.append("head washer is not seated at the fastener head")
                continue
            if far_face is None or abs(axial - stack - far_face) > tolerance:
                reasons.append(f"{nut['type']} is not seated at the base mesh exit")
            if not nut_reached(nut["type"], axial, length):
                reasons.append(f"fastener does not reach {nut['type']} engagement region")
            if nut["type"] in ("Washer", "LockNut"):
                stack += NUTS[nut["type"]][1]
        if reasons:
            failures.append(
                dict(
                    id=item["id"],
                    step=item["step"],
                    attached=item["attached"],
                    base=item["base"],
                    reasons=reasons,
                )
            )
    return dict(
        checked=len(fasteners),
        unchecked=0,
        failed=len(failures),
        failures=failures,
        surface_tolerance_m=tolerance,
        nut_records_checked=len(nuts or []),
    )
