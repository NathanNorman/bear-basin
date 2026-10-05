"""Manual hardware identifiers; dimensions, mass and capacities are estimates.
Capacities are not validated engineering ratings.
"""

FT = {  # d mm, L mm, unverified legacy single-shear placeholder in N (no supported uncertainty bound), mass g
    "M821": (8, 21, 4000, 18),
    "M833": (8, 33, 4000, 22),
    "M865": (8, 65, 4000, 32),
    "M896": (8, 96, 4000, 42),
    "M8107": (8, 107, 4000, 46),
    "M6SW35": (6, 35, 1800, 9),
    "M6SW55": (6, 55, 2000, 13),
    "M8SW50": (8, 50, 2800, 20),
    "M8SW60": (8, 60, 3000, 23),
    "SW16": (4, 16, 300, 2),
    "SW35": (4.5, 35, 900, 4),
    "SW50": (5, 50, 1200, 6),
    "SW60": (5, 60, 1300, 7),
    "SW75": (6, 75, 1600, 11),
    "EYE": (8, 100, 4000, 60),
    "HANGER": (10, 160, 8000, 250),
}
NUTS = {  # hardware page: name -> (flange r, flange t, barrel r, barrel length) m; barrel runs from the flange back toward the head
    "NM815": (0.012, 0.0015, 0.0055, 0.010),  # T-nut, pressed into the far face
    "BM818": (0.011, 0.003, 0.0065, 0.018),  # barrel nut
    "BM825": (0.011, 0.003, 0.0065, 0.025),  # barrel nut
    "Washer": (0.012, 0.002, 0.0, 0.0),
    "LockNut": (0.0085, 0.008, 0.0, 0.0),  # hex self-locking nut
}


def is_bolt(ft):
    return ft in ("HANGER", "EYE") or (
        ft.startswith("M8") and not ft.startswith("M8SW")
    )


# Inventory is a comparison source, not the assembly schedule: the manual is inconsistent.
MANUAL_INVENTORY = {
    "M821": 2,
    "M833": 16,
    "M865": 8,
    "M896": 28,
    "M8107": 48,
    "M6SW35": 20,
    "M6SW55": 12,
    "M8SW50": 70,
    "M8SW60": 2,
    "SW16": 24,
    "SW35": 405,
    "SW50": 54,
    "SW60": 124,
    "SW75": 20,
    "NM815": 80,
    "BM818": 21,
    "BM825": 14,
    "Washer": 8,
    "LockNut": 4,
}


def nut_for(step, ft, attached, base):
    """Far-side hardware. The hanger also has a head-side washer (step 159)."""
    if ft == "HANGER":
        return ["Washer", "LockNut"]
    if ft == "EYE" or step in (49, 50, 51, 52, 182, 183):
        return ["BM818"]
    if ft == "M833" and attached in ("F11r_B", "F11r_W", "F12r", "F13r"):
        return ["BM825"]
    return ["NM815"] if is_bolt(ft) else []


def nut_mass_kg(kind):
    """Volume-based estimate for steel hardware, including an 8/10 mm bore."""
    from math import pi

    flange_r, thickness, barrel_r, barrel_length = NUTS[kind]
    bore = 0.005 if kind in ("Washer", "LockNut") else 0.004
    volume = pi * max(0, flange_r**2 - bore**2) * thickness
    volume += pi * max(0, barrel_r**2 - bore**2) * barrel_length
    return volume * 7850


def source_steps(step, attached, base):
    """Some repeated assemblies use a representative step, not an exact per-face mapping."""
    if attached == "Tarp":
        return [131, 132, 133]
    return [step]
