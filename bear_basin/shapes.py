"""Small geometry calculations independent of Blender."""


def polygon_area(points):
    return (
        abs(
            sum(
                x1 * y2 - x2 * y1
                for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
            )
        )
        / 2
    )


def floorboard_outline(x, width, rail_extent, notch_x, notch_y):
    """W10: a full-length plank with two inner corners cut around C04 posts."""
    low, high = x - width / 2, x + width / 2
    if x > 0:
        return [
            (low, -notch_y),
            (notch_x, -notch_y),
            (notch_x, -rail_extent),
            (high, -rail_extent),
            (high, rail_extent),
            (notch_x, rail_extent),
            (notch_x, notch_y),
            (low, notch_y),
        ]
    return [
        (-px, py)
        for px, py in reversed(
            floorboard_outline(-x, width, rail_extent, notch_x, notch_y)
        )
    ]


def socket_miter_frame(cup_side, bottom_z, half_width, foot_y):
    """Solve a constant-width inclined sleeve whose end mates to a vertical cup.

    The lower inner corner is bottom_z. The axis passes through the ground foot,
    while the complete top-end plane stays on cup_side.
    """
    import math
    if not 0 < cup_side < foot_y or min(bottom_z, half_width) <= 0:
        raise ValueError('Invalid socket fit dimensions')
    lo, hi = 0.01, math.pi / 2 - 0.01
    for _ in range(70):
        angle = (lo + hi) / 2
        end_foot = cup_side + bottom_z * math.tan(angle) + half_width / math.cos(angle)
        if end_foot < foot_y:
            lo = angle
        else:
            hi = angle
    angle = (lo + hi) / 2
    center_z = bottom_z + half_width / math.sin(angle)
    if center_z <= 0:
        raise ValueError('Socket end cannot fit above ground')
    return angle, center_z
