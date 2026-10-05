"""Refine box proposals against member surfaces without changing the members.

Only failed placements are searched. This is a bounded geometric construction,
not an assertion that the resulting connections have an engineering rating.
"""

from dataclasses import dataclass
from .hardware import FT
from .validation import connected_face_components, union_intervals


SURFACE_TOLERANCE = 0.004
SEARCH_RADIUS = 0.100
RAY_EPSILON = 1e-5


def material_path(attached, base, length, penetration, tolerance=SURFACE_TOLERANCE):
    """Require an entry at the head and contiguous material into the base.

    Intervals are measured from head toward tip. In particular, an intersection
    behind the head or beyond the tip cannot count as base engagement.
    """
    for a0, a1 in attached:
        if not -tolerance <= a0 <= tolerance:
            continue
        a_end = min(length, a1)
        if a_end - max(0.0, a0) < 0.0005:
            continue
        for b0, b1 in base:
            b_start, b_end = max(0.0, b0), min(length, b1)
            if b_end - b_start < penetration:
                continue
            if b_end <= max(0.0, a0):
                continue
            if b_start <= a_end + tolerance:
                return True
    return False


def ray_spans(tree, head, axis, radius):
    """Closed-solid intervals from independently traced mesh crossings."""
    origin = head - axis * radius
    travel, hits = 0.0, []
    for _ in range(128):
        point, _, _, distance = tree.ray_cast(origin, axis, 2 * radius - travel)
        if point is None:
            break
        travel += distance
        hits.append(travel - radius)
        travel += RAY_EPSILON
        if travel >= 2 * radius:
            break
        origin = point + axis * RAY_EPSILON
    else:
        return None
    if len(hits) % 2:
        return None
    return list(zip(hits[::2], hits[1::2]))


@dataclass
class MemberSurface:
    tree: object
    shell_trees: list
    vertices: list
    triangles: list
    center: object
    radius: float

    def spans(self, head, axis):
        radius = self.radius + (head - self.center).length + 0.05
        intervals = []
        for shell in self.shell_trees:
            spans = ray_spans(shell, head, axis, radius)
            if spans is None:
                return None
            intervals.extend(spans)
        return union_intervals(intervals)


class MeshPlacementCache:
    """One immutable world-space BVH snapshot per assembly geometry."""

    def __init__(self, geometry):
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree

        self.members = geometry.members
        self.surfaces = {}
        for name, member in geometry.members.items():
            obj = member["obj"]
            mesh = obj.data
            vertices = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
            polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
            mesh.calc_loop_triangles()
            indices = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
            center = sum(vertices, Vector()) / len(vertices)
            self.surfaces[name] = MemberSurface(
                BVHTree.FromPolygons(vertices, polygons, all_triangles=False),
                [BVHTree.FromPolygons(vertices, shell, all_triangles=False)
                 for shell in connected_face_components(polygons)],
                vertices,
                [tuple(vertices[i] for i in triangle) for triangle in indices],
                center,
                max((point - center).length for point in vertices),
            )

    def valid(self, a, b, head, axis, length, penetration):
        attached, base = self.surfaces[a], self.surfaces[b]
        near = attached.tree.find_nearest(head)
        if near[0] is None or near[3] > SURFACE_TOLERANCE:
            return False
        # A line nearly tangent to the mounting face can flip from inside to
        # outside with Blender's single-precision coordinates or triangulation.
        # It does not represent a usable hole through that face.
        if abs(near[1].dot(axis)) < 0.02:
            return False
        aa, bb = attached.spans(head, axis), base.spans(head, axis)
        return aa is not None and bb is not None and material_path(
            aa, bb, length, penetration
        )

    def surface_candidates(self, name, seed, axis):
        """Project a local stencil onto triangles, including broad joist faces."""
        from mathutils.geometry import closest_point_on_tri

        surface, member = self.surfaces[name], self.members[name]
        offsets = [seed]
        for basis in (member["u"], member["v"], member["a"]):
            for distance in (-0.050, -0.025, -0.012, 0.012, 0.025, 0.050):
                offsets.append(seed + basis * distance)
        candidates, seen = [], set()

        def add(point):
            if (point - seed).length > SEARCH_RADIUS:
                return
            key = tuple(round(value, 5) for value in point)
            if key not in seen:
                candidates.append(point)
                seen.add(key)

        # Preserve the proposed hole's lateral position whenever simply seating
        # its head on the entry face is sufficient.
        spans = surface.spans(seed, axis)
        if spans is not None:
            for start, _ in spans:
                add(seed + axis * start)
        for triangle in surface.triangles:
            nearest = closest_point_on_tri(seed, *triangle)
            if (nearest - seed).length > SEARCH_RADIUS:
                continue
            centroid = sum(triangle[1:], triangle[0].copy()) / 3
            for point in offsets:
                projected = closest_point_on_tri(point, *triangle)
                # Do not trace exactly along a face edge or triangulation seam.
                toward_center = centroid - projected
                if toward_center.length > 0.002:
                    projected += toward_center.normalized() * 0.002
                add(projected)
        return sorted(candidates, key=lambda point: (point - seed).length_squared)

    def target_candidates(self, name, head, length):
        """Interior targets local to the closest part of the base member."""
        base, member = self.surfaces[name], self.members[name]
        point, normal, _, distance = base.tree.find_nearest(head)
        if point is None or distance > length - 0.003:
            return []
        targets = []
        for depth in (0.006, 0.015):
            targets.extend((point - normal * depth, point + normal * depth))
        along = member["a"]
        member_length = (member["p1"] - member["p0"]).length
        end_margin = min(0.006, member_length / 2)
        position = min(
            max((head - member["p0"]).dot(along), end_margin),
            member_length - end_margin,
        )
        middle = member["p0"] + along * position
        targets.append(middle)
        # The local centre is useful for toe screws: nearest-surface normals
        # alone can produce a line tangent to the attached member's broad face.
        for basis, half_size in zip((member["u"], member["v"]), member["sec"]):
            extent = max(0.0, half_size / 2 - 0.008)
            for sign in (-1, 1):
                targets.append(middle + basis * extent * sign)
        for offset in (-0.025, 0.025):
            targets.append(middle + along * offset)
        return targets

    def refine(self, a, b, ft, centres, axis):
        from mathutils import Vector

        axis = Vector(axis).normalized()
        length, diameter = FT[ft][1] / 1000, FT[ft][0] / 1000
        penetration = max(0.003, diameter / 2)
        preserved = [(Vector(center), axis.copy(), "mesh_preserved") for center in centres]
        # These intentionally non-box members need their own construction and
        # contact corrections; moving their hardware can conceal a geometry gap.
        if a in ("Tarp", "Slide") or a.startswith("DRB"):
            return preserved
        result, accepted = [], []
        for center in centres:
            center = Vector(center)
            seed = center - axis * length / 2
            if self.valid(a, b, seed, axis, length, penetration):
                result.append((center, axis.copy(), "mesh_preserved"))
                accepted.append(seed)
                continue
            near = self.surfaces[a].tree.find_nearest(seed)
            buried = near[0] is None or near[3] > SURFACE_TOLERANCE
            candidates = self.surface_candidates(a, seed, axis)
            solutions = []
            # Keep the existing direction first, changing only a failed hole's
            # position. Angled candidates are only for previously buried heads.
            for head in candidates:
                if self.valid(a, b, head, axis, length, penetration):
                    solutions.append((head, axis, "mesh_seated"))
            if not solutions and buried:
                for head in candidates:
                    for target in self.target_candidates(b, head, length):
                        direction = target - head
                        if direction.length < 0.003:
                            continue
                        direction.normalize()
                        if self.valid(a, b, head, direction, length, penetration):
                            solutions.append((head, direction, "mesh_toe"))
            if solutions:
                def score(solution):
                    head, direction, _ = solution
                    separation = min(((head - prior).length for prior in accepted), default=1.0)
                    return (
                        separation < 2 * diameter,
                        (head - seed).length + 0.020 * (1 - direction.dot(axis)),
                    )

                solutions = [s for s in solutions if all((s[0] - old).length > 0.0001 for old in accepted)]
                if solutions:
                    head, direction, method = min(solutions, key=score)
                    result.append((head + direction * length / 2, direction, method))
                    accepted.append(head)
                    continue
            # Failure is explicit and still independently checked by validation.
            result.append((center, axis.copy(), "mesh_unresolved"))
            accepted.append(seed)
        return result


def refine(geometry, a, b, ft, centres, axis):
    """Return ``(center, axis, method)`` for each proposed fastener in order."""
    cache = getattr(geometry, "_mesh_placement_cache", None)
    if cache is None:
        cache = MeshPlacementCache(geometry)
        geometry._mesh_placement_cache = cache
    return cache.refine(a, b, ft, centres, axis)
