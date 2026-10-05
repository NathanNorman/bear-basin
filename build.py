"""Bear Basin (Little Tikes 651281), built from the 193 assembly steps.
Run: blender -b --python build.py

Frame: x points away from the swings (swings at -x), y+ = back (side A: S04A/K07, climbing net, upper opening),
y- = front (side B: S04/K06, the cover-photo side), z up, origin on the ground at the tower centre.

Leg map (manual codes):  back  y+ : C02 (x-)  C04A (x0)  C01A (x+)
                         front y- : C01B (x-) C04B (x0)  C03 (x+)
                         west  x- : C05 (y0)   east x+ : C06 (y0)
Heights come from the manual's Vertical Height diagram (p.4); lumber cross-sections are ESTIMATES (manual gives none).
"""
import bpy, math, json, os
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
RHO = 380.0   # kg/m3, cedar/fir. Total mass is reported against the 574 lb listing as a check on the section estimates.

# ---------------- dimensions ----------------
BH, SL = 1.08, 0.08          # leg centreline half-width at ground, inward lean per metre (M: 1.10 base -> 0.91 top)
def lean(z): return BH - SL*z
LEG = 0.070                  # E  tower leg section
RT, RH = 0.030, 0.140        # E  rail thickness / height
DECK = 1.55                  # M  deck top (listing: 5 ft)
LEG_TOP = 2.25               # M  connect-board ring sits on leg tops; roof ring above -> 2.33
EAVE, PEAK = 2.97, 3.58      # M
WALL_RAIL_Z, HANDRAIL_Z = 1.63, 2.08   # M  (wall top 2.13)
def face(z): return lean(z) + LEG/2 + RT/2   # centre of a rail bolted to the outside of the legs
def fup(side, s=SL):
    """'Up' direction lying in a sloped face (faces lean inward by s per metre; s<0 leans out). Passing this as member(up=)
    tilts a rail or board so its broad face sits flat on the leaning posts."""
    return {"+y": (0, -s, 1), "-y": (0, s, 1), "+x": (-s, 0, 1), "-x": (s, 0, 1)}[side]

# ---------------- helpers ----------------
def coll(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in scene.collection.children: scene.collection.children.link(c)
    return c

def mat(name, rgba):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.diffuse_color = rgba
    return m
CEDAR = mat("cedar", (0.62, 0.36, 0.18, 1)); CEDAR2 = mat("cedar_dark", (0.48, 0.26, 0.12, 1))
STEEL = mat("steel", (0.55, 0.57, 0.6, 1))
# linear values of sRGB targets: blue #1C5CCC, tan #CDB084, brick red #963428
BLUE = mat("blue_plastic", (0.0116, 0.107, 0.6038, 1))
TARP = mat("tarp_tan", (0.6105, 0.4342, 0.2307, 1)); ROPE = mat("rope", (0.86, 0.80, 0.62, 1)); BRICK = mat("brick_red", (0.305, 0.0343, 0.0212, 1))

M = {}   # name -> dict(obj, p0, p1, sec, code)
def member(name, code, p0, p1, sec, c, m=CEDAR, up=(0, 0, 1), kind="wood", mass=None):
    p0, p1 = Vector(p0), Vector(p1)
    a = p1 - p0; L = a.length; a.normalize()
    upv = Vector(up)
    if abs(a.dot(upv)) > 0.98: upv = Vector((1, 0, 0))
    u = upv.cross(a).normalized(); v = a.cross(u).normalized()
    mw = Matrix(((u.x, v.x, a.x, 0), (u.y, v.y, a.y, 0), (u.z, v.z, a.z, 0), (0, 0, 0, 1))); mw.translation = (p0+p1)/2
    w, d, h = sec[0]/2, sec[1]/2, L/2
    vs = [(-w,-d,-h),(w,-d,-h),(w,d,-h),(-w,d,-h),(-w,-d,h),(w,-d,h),(w,d,h),(-w,d,h)]
    fs = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    ob = bpy.data.objects.new(name, me); ob.matrix_world = mw; ob.data.materials.append(m); c.objects.link(ob)
    ms = mass if mass is not None else (sec[0]*sec[1]*L*RHO if kind == "wood" else 0.0)
    ob["code"] = code; ob["kind"] = kind; ob["mass_kg"] = ms
    M[name] = dict(obj=ob, p0=p0, p1=p1, u=u, v=v, a=a, sec=sec, code=code, kind=kind, mass=ms)
    return name

def rope(name, pts, c, r=0.007, m=ROPE):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.resolution_u = 2
    sp = cu.splines.new('POLY'); sp.points.add(len(pts)-1)
    for i, p in enumerate(pts): sp.points[i].co = (*p, 1)
    ob = bpy.data.objects.new(name, cu); ob.data.materials.append(m); c.objects.link(ob); return ob

def leg_pt(sx, sy, z, mid=None):
    h = lean(z)
    return (sx*h if sx else 0.0, sy*h if sy else 0.0, z)

# ================= TOWER FRAME (steps 7-34) =================
T = coll("Tower_frame")
LEGS = {"C02": (-1, 1), "C04A": (0, 1), "C01A": (1, 1), "C01B": (-1, -1), "C04B": (0, -1), "C03": (1, -1), "C05": (-1, 0), "C06": (1, 0)}
for n, (sx, sy) in LEGS.items():
    member(n, n[:3], leg_pt(sx, sy, 0), leg_pt(sx, sy, LEG_TOP), (LEG, LEG), T)

zb = 0.07   # base boards, flush with leg bottoms
f = face(zb); fx = face(zb)
member("S04A", "S04A", (-fx-0.02, f, zb), (fx+0.02, f, zb), (RT, RH), T, up=fup("+y"))  # back  (step 14)
member("S04", "S04", (-fx-0.02, -f, zb), (fx+0.02, -f, zb), (RT, RH), T, up=fup("-y"))  # front (step 23)
member("S03_W", "S03", (-f, -fx, zb), (-f, fx, zb), (RT, RH), T, up=fup("-x"))    # west  (step 32)
member("S03_E", "S03", (f, -fx, zb), (f, fx, zb), (RT, RH), T, up=fup("+x"))  # east  (step 31)

zr = DECK - 0.02 - RH/2      # floor rails, top flush under the floorboards
f = face(zr)
member("K07", "K07", (-f-0.02, f, zr), (f+0.02, f, zr), (RT, RH), T, up=fup("+y"))  # back  (step 15)
member("K06", "K06", (-f-0.02, -f, zr), (f+0.02, -f, zr), (RT, RH), T, up=fup("-y"))  # front (step 24)
member("K08_W", "K08", (-f, -f, zr), (-f, f, zr), (RT, RH), T, up=fup("-x"))  # west  (step 29)
member("K08_E", "K08", (f, -f, zr), (f, f, zr), (RT, RH), T, up=fup("+x"))  # east  (step 30)

# ================= DECK STRUCTURE (steps 35-54) =================
D = coll("Deck_structure")
hi = lean(zr) - LEG/2        # inside face of legs at rail height
XE = face(zr) + RT/2         # outer face of the end rails
BLK = 0.07
# (name, leg centre sign (sx, sy), direction from the leg along the rail it sits under)
fa17 = [("FA17_C03", (1, -1), (0, 1)), ("FA17_C01B", (-1, -1), (0, 1)), ("FA17_C02", (-1, 1), (0, -1)), ("FA17_C01A", (1, 1), (0, -1)),
        ("FA17_C01A_y", (1, 1), (-1, 0)), ("FA17_C06", (1, 0), (0, 1))]
for n, (sx, sy), ax in fa17:      # blocks screwed to the legs under the rail ends (steps 35-40)
    dx, dy = ax; L_ = lean(zr)
    x = sx*L_ + dx*(LEG/2 + BLK/2); y = sy*L_ + dy*(LEG/2 + BLK/2)
    member(n, "FA17", (x, y, zr + RH/2 - 0.10), (x, y, zr + RH/2), (BLK, BLK), D)
XIN = face(zr) - RT/2                # inside face of the end rails (K08)
for sx in (-1, 1):                # C11 wood braces bolted to the inside of each end rail (steps 47-48), beside the joist
    for y in (-0.29, 0.29):
        yb_ = y + (1 if y > 0 else -1)*(0.019 + 0.035)
        x = sx*(XIN - 0.035)
        member(f"C11_{'W' if sx<0 else 'E'}_{'F' if y<0 else 'B'}", "C11", (x, yb_-0.035, zr), (x, yb_+0.035, zr), (0.07, 0.10), D)
xj = XIN
for y in (-0.29, 0.29):           # K05 joists run rail to rail, bolted through the side of the C11 braces (steps 49-50)
    member(f"K05_{'F' if y<0 else 'B'}", "K05", (-xj, y, zr+0.01), (xj, y, zr+0.01), (0.038, 0.12), D)
member("KA11_C", "KA11", (-hi, 0, zr+0.01), (hi, 0, zr+0.01), (0.038, 0.12), D)    # between C05 and C06 (step 46)
for y in (-0.78, 0.78):           # aligned with the knee braces (steps 53-54)
    member(f"KA11_{'F' if y<0 else 'B'}", "KA11", (-(XE - RT), y, zr+0.01), (XE - RT, y, zr+0.01), (0.038, 0.12), D)
# KA13 knee braces, two per corner leg, one in each face plane (steps 41-45)
KNEE = {}
def knee_pt(kb, s, z, t):
    sx, sy = kb["sx"], kb["sy"]
    if kb["along"] == "x": return Vector((sx*(lean(z) - LEG/2 - s), sy*(lean(zr) + LEG/2 - t), z))
    return Vector((sx*(lean(zr) + LEG/2 - t), sy*(lean(z) - LEG/2 - s), z))
def knee_brace(name, sx, sy, along):
    """KA13: 45-degree parallelogram, flat against the inside face of the floor rail, top cut flush with the rail top,
    bottom cut flush against the post's side face (step 42). along='x' sits on the side rail, 'y' on the end rail."""
    DROP, W, T = 0.30, 0.07, 0.03
    KNEE[name] = dict(sx=sx, sy=sy, along=along, DROP=DROP, T=T)
    h = (W/2)/math.sin(math.pi/4)             # half-width measured vertically/horizontally across the 45-degree band
    zt = zr + RH/2                             # rail top
    def pt(s, z, t):
        # s: distance from the post's inner side face along the rail; t: depth from the rail's inside face toward the deck
        if along == "x": return (sx*(lean(z) - LEG/2 - s), sy*(lean(zr) + LEG/2 - t), z)
        return (sx*(lean(zr) + LEG/2 - t), sy*(lean(z) - LEG/2 - s), z)
    quad = [(0, zt - DROP + h), (0, zt - DROP - h), (DROP + h, zt), (DROP - h, zt)]   # A B C D in (s, z)
    vs = [pt(s, z, 0.0) for s, z in quad] + [pt(s, z, T) for s, z in quad]
    fs = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    ob = bpy.data.objects.new(name, me); ob.data.materials.append(CEDAR); D.objects.link(ob)
    vol = (2*h*DROP + 0)*T                     # parallelogram area = base (2h along s=0) x horizontal reach (DROP)
    p0 = (Vector(pt(0, zt - DROP, 0)) + Vector(pt(0, zt - DROP, T)))/2   # centre of the post-side cut
    p1 = (Vector(pt(DROP, zt - 0.035, 0)) + Vector(pt(DROP, zt - 0.035, T)))/2
    a = (p1 - p0).normalized(); u = Vector((0, sy, 0)) if along == "x" else Vector((sx, 0, 0))
    ob["code"] = "KA13"; ob["kind"] = "wood"; ob["mass_kg"] = vol*RHO
    M[name] = dict(obj=ob, p0=p0, p1=p1, u=u, v=a.cross(u).normalized(), a=a, sec=(T, W), code="KA13", kind="wood", mass=vol*RHO)
for leg, (sx, sy) in [("C01A", (1, 1)), ("C02", (-1, 1)), ("C03", (1, -1)), ("C01B", (-1, -1))]:
    knee_brace(f"KA13_{leg}_x", sx, sy, "x"); knee_brace(f"KA13_{leg}_y", sx, sy, "y")

# ================= FLOORBOARDS: 28 boards in 22 rows (steps 62-74) =================
FB = coll("Floorboards")
ROWS = ["W13", "W11"] + ["W09"]*5 + ["TBL"] + ["W09"]*2 + ["W10"]*2 + ["W09"]*2 + ["TBL"] + ["W09"]*5 + ["W11", "W13"]
XE = face(zr) + RT/2                       # outer face of the end rails
NR = len(ROWS); x0 = -XE; pitch = 2*XE/NR; BW, BT = pitch - 0.005, 0.019
yr = face(zr) + RT/2      # boards run to the outside of the side rails
zbd = DECK - BT/2
TBL_X = []
for i, code in enumerate(ROWS):
    x = x0 + pitch*(i + 0.5)
    if code == "W13":        # short boards between corner leg and mid leg, both halves (FA17 + K08)
        for s in (-1, 1): member(f"W13_{i}_{s}", "W13", (x, s*0.05, zbd), (x, s*(hi - 0.01), zbd), (BW, BT), FB)
    elif code == "TBL":      # W02 + W01 + W02 around the table legs
        TBL_X.append(x)
        member(f"W02_{i}_F", "W02", (x, -yr, zbd), (x, -0.33, zbd), (BW, BT), FB)
        member(f"W01_{i}", "W01", (x, -0.25, zbd), (x, 0.25, zbd), (BW, BT), FB)
        member(f"W02_{i}_B", "W02", (x, 0.33, zbd), (x, yr, zbd), (BW, BT), FB)
    elif code == "W10":      # notched around the C04 legs: tight against them
        member(f"W10_{i}", "W10", (x, -hi, zbd), (x, hi, zbd), (BW, BT), FB)
    else:
        member(f"{code}_{i}", code, (x, -yr, zbd), (x, yr, zbd), (BW, BT), FB)

# ================= PICNIC TABLE on the deck (steps 51-52, 140-145) =================
TB = coll("Picnic_table")
for i, x in enumerate(TBL_X):
    for y in (-0.29, 0.29):
        member(f"CA10_{i}_{'F' if y<0 else 'B'}", "CA10", (x, y + (0.055 if y < 0 else -0.055), zr - 0.04), (x, y + (0.055 if y < 0 else -0.055), DECK + 0.48), (0.07, 0.07), TB)
    xo = x + (-1 if i == 0 else 1)*(0.035 + 0.015)     # on the outer faces of this leg pair
    member(f"F01_{i}", "F01", (xo, -0.324, DECK + 0.44), (xo, 0.324, DECK + 0.44), (0.03, 0.09), TB, up=(0, 0, 1))  # 25.5 in (step 145)
    member(f"F03_{i}", "F03", (xo, -0.42, DECK + 0.22), (xo, 0.42, DECK + 0.22), (0.03, 0.09), TB)
for k, y in enumerate((-0.21, -0.07, 0.07, 0.21)):
    member(f"W05_{k}", "W05", (TBL_X[0] - 0.12, y, DECK + 0.495), (TBL_X[1] + 0.12, y, DECK + 0.495), (0.135, 0.019), TB)
for s in (-1, 1):
    for k, dy in enumerate((0.0, 0.10)):
        y = s*(0.30 + dy)
        member(f"Bench_{'F' if s<0 else 'B'}_{'F08' if k==0 else 'F02'}", "F08" if k == 0 else "F02",
               (TBL_X[0] - 0.08, y, DECK + 0.28), (TBL_X[1] + 0.08, y, DECK + 0.28), (0.095, 0.025), TB)

# ================= UPPER WALLS (steps 55-58, 164-171) =================
W = coll("Walls")
fw, fh = face(WALL_RAIL_Z), face(HANDRAIL_Z)
member("FA15_W", "FA15", (-fw, -fw, WALL_RAIL_Z), (-fw, fw, WALL_RAIL_Z), (RT, 0.09), W, up=fup("-x"))  # step 167
member("FA15_F", "FA15", (-fw, -fw, WALL_RAIL_Z), (fw, -fw, WALL_RAIL_Z), (RT, 0.09), W, up=fup("-y"))  # step 166
member("FA13_B", "FA13", (0, fw, WALL_RAIL_Z), (fw, fw, WALL_RAIL_Z), (RT, 0.09), W, up=fup("+y"))  # step 164 (back, east half)
member("FA13_E", "FA13", (fw, 0, WALL_RAIL_Z), (fw, fw, WALL_RAIL_Z), (RT, 0.09), W, up=fup("+x"))  # step 165 (east, back half)
member("F09_B", "F09", (-fh, fh, HANDRAIL_Z), (fh, fh, HANDRAIL_Z), (RT, 0.09), W, up=fup("+y"))  # step 56 (spans the opening)
member("F09_W", "F09", (-fh, -fh, HANDRAIL_Z), (-fh, fh, HANDRAIL_Z), (RT, 0.09), W, up=fup("-x"))  # step 57
member("F09_F", "F09", (-fh, -fh, HANDRAIL_Z), (fh, -fh, HANDRAIL_Z), (RT, 0.09), W, up=fup("-y"))  # step 58
member("F04_E", "F04", (fh, 0, HANDRAIL_Z), (fh, fh, HANDRAIL_Z), (RT, 0.09), W, up=fup("+x"))  # step 55
WB_W, WB_T = 0.105, 0.016
def wall_boards(tag, n, a, b, side, step, clear=None):
    """n evenly spaced boards on the outside face between parameter a..b along the face (2 in gaps per step 168).
    clear=(c0, c1): keep that span free (split the boards evenly either side of it)."""
    z0, z1 = WALL_RAIL_Z - 0.04, HANDRAIL_Z + 0.04
    if clear:
        ts = []
        for (lo, hi_), m in (((a, clear[0]), n//2), ((clear[1], b), n - n//2)):
            g_ = ((hi_ - lo) - m*WB_W)/(m + 1); ts += [lo + g_*(k + 1) + WB_W*(k + 0.5) for k in range(m)]
    else:
        span = b - a; gap = (span - n*WB_W)/(n + 1)
        ts = [a + gap*(k + 1) + WB_W*(k + 0.5) for k in range(n)]
    for k, t in enumerate(ts):
        o0, o1 = face(z0) + RT/2 + WB_T/2, face(z1) + RT/2 + WB_T/2     # boards lean with the posts
        sg = 1 if side in ("B", "E") else -1
        if side in ("F", "B"):
            member(f"W07_{tag}_{k}", "W07", (t, sg*o0, z0), (t, sg*o1, z1), (WB_T, WB_W), W, up=(1, 0, 0))
        else:
            member(f"W07_{tag}_{k}", "W07", (sg*o0, t, z0), (sg*o1, t, z1), (WB_T, WB_W), W, up=(0, 1, 0))
h = lean(1.85)
wall_boards("B", 5, 0.04, h, "B", 168); wall_boards("E", 5, 0.04, h, "E", 169)
wall_boards("F", 10, -h, h, "F", 170); wall_boards("W", 10, -h, h, "W", 171, clear=(-0.07, 0.07))   # swing beam + I-bracket pass through at C05
member("S05", "S05", (-face(0.95), -face(0.95), 0.95), (-face(0.95), face(0.95), 0.95), (RT, 0.09), W, up=fup("-x"))  # opening block, swing face (step 185)
def handle(n, leg_xy, side, c, z0=1.72, z1=1.98):
    """Grab handle on the side face of a leg: two standoffs screwed to the leg + a vertical grip (step 186 / 101).
    leg_xy(z) -> leg centre (x, y); side = unit vector (dx, dy) from the leg toward the grip."""
    sx, sy = side; ST = 0.065
    pts = []
    for z in (z0, z1):
        lx, ly = leg_xy(z); f0 = (lx + sx*LEG/2, ly + sy*LEG/2, z); f1 = (lx + sx*(LEG/2 + ST), ly + sy*(LEG/2 + ST), z)
        member(f"{n}_foot{len(pts)}", "Handle", f0, f1, (0.035, 0.035), c, m=BLUE, kind="plastic", mass=0.05); pts.append(f1)
    member(n, "Handle", pts[0], pts[1], (0.03, 0.03), c, m=BLUE, kind="plastic", mass=0.15)
# the upper opening is the back face's west half (x from C02 to C04A): handles on the outward (back) faces of its two legs
handle("Handle_C04A", lambda z: (0.0, lean(z)), (0, 1), W)
handle("Handle_C02", lambda z: (-lean(z), lean(z)), (0, 1), W)
# ================= CONNECT-BOARD RINGS (steps 59-61 main structure, 118-120 roof, 134-139 bolted together) =================
# Two identical flat rings: the main structure's lies on the tower leg tops; the roof's is screwed to the roof posts' bottom
# ends and rests on it. Parts list: F11 has two angled ends, F12 and F13 one each. So each ring = F11 (back) + F11 (west),
# mitred at C02/C01A/C01B; F12 (front) mitred at C01B with a square end over C03; F13 on the back half of the east side
# (mitred at C01A, square end flush with C06's front face). The east front half is the doorway to the small deck.
# Outer edges flush with the handrails.
RING_C = lean(LEG_TOP)                     # leg / roof-post centreline offset at the ring
CBW, CBT = 0.115, 0.028                    # E  connect board width, thickness
RO = RING_C + LEG/2 + RT                     # outer edge, flush with the handrails' outer faces (step 59)
RI = RO - CBW
def ring_board(name, code, side, a0, a1, z0, c, mit0=True, mit1=True):
    """Flat board on the ring. side in B/F/W/E; a0..a1 = extent along the board on its outer edge.
    Mitred ends pull the inner edge in by CBW (45 degrees); square ends don't."""
    i0 = a0 + (CBW if mit0 else 0) * (1 if a1 > a0 else -1)
    i1 = a1 - (CBW if mit1 else 0) * (1 if a1 > a0 else -1)
    def P(t, o, z):
        return {"B": (t, o, z), "F": (t, -o, z), "W": (-o, t, z), "E": (o, t, z)}[side]
    quad = [(a0, RO), (a1, RO), (i1, RI), (i0, RI)]
    vs = [P(t, o, z0) for t, o in quad] + [P(t, o, z0 + CBT) for t, o in quad]
    fs = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], fs); me.update()
    ob = bpy.data.objects.new(name, me); ob.data.materials.append(CEDAR); c.objects.link(ob)
    zc_ = z0 + CBT/2; om = (RO + RI)/2
    p0, p1 = Vector(P(a0, om, zc_)), Vector(P(a1, om, zc_)); ax = (p1 - p0).normalized()
    u = Vector((0, 0, 1)); ms = CBW*CBT*abs(a1 - a0)*RHO
    ob["code"] = code; ob["kind"] = "wood"; ob["mass_kg"] = ms
    M[name] = dict(obj=ob, p0=p0, p1=p1, u=ax.cross(u).normalized(), v=u, a=ax, sec=(CBW, CBT), code=code, kind="wood", mass=ms)
    RING_POLY[name] = dict(poly=[Vector(P(t, o, 0)[:2]) for t, o in quad], z0=z0)
RING_POLY = {}
def connect_ring(sfx, z0, c):
    ring_board("F11" + sfx + "_B", "F11", "B", -RO, RO, z0, c)
    ring_board("F11" + sfx + "_W", "F11", "W", -RO, RO, z0, c)
    ring_board("F12" + sfx, "F12", "F", -RO, RO, z0, c, mit0=True, mit1=False)
    ring_board("F13" + sfx, "F13", "E", RO, -LEG/2, z0, c, mit0=True, mit1=False)
connect_ring("", LEG_TOP, W)

# ================= ROOF ASSEMBLY (steps 107-139) =================
# Built upside down: F14/F15 rails flush with the posts' narrow ends, F16 flush with the wide ends (steps 109-117), connect
# boards on the narrow ends (118-120), then flipped (121) and set on the tower (135). So in place: connect ring at the bottom,
# F14 x3 + F15 (back half of east only) along the bottom, F16 x4 around the eave, posts flaring outward between them.
R = coll("Roof")
connect_ring("r", LEG_TOP + CBT, R)
RP = LEG                                   # roof posts are the same stock as the tower legs
rb, rt_ = RING_C, 0.985                      # post centreline offset at bottom / eave (C09 'circular curve', step 108)
zp0, zp1 = LEG_TOP + 2*CBT, EAVE
def pc(z): return rb + (rt_ - rb)*(z - zp0)/(zp1 - zp0)
for n, (sx, sy) in {"C09_BE": (1, 1), "C09_BW": (-1, 1), "C09_FE": (1, -1), "C09_FW": (-1, -1)}.items():
    member(n, "C09", (sx*rb, sy*rb, zp0), (sx*rt_, sy*rt_, zp1), (RP, RP), R)
for n, (sx, sy) in {"C10_B": (0, 1), "C10_F": (0, -1), "C10_W": (-1, 0), "C10_E": (1, 0)}.items():
    member(n, "C10", (sx*rb, sy*rb, zp0), (sx*rt_, sy*rt_, zp1), (RP, RP), R)
FLARE = -(rt_ - rb)/(zp1 - zp0)
RRH = 0.09
def roof_rail(name, code, side, z, t0=None, t1=None):
    """Rail on the outside faces of the roof posts at height z. Back/front rails run past the corners to cover the side
    rails' ends; side rails butt between them."""
    off = pc(z) + RP/2 + RT/2
    full = off + RT/2 if side in ("B", "F") else off - RT/2
    a0 = -full if t0 is None else t0; a1 = full if t1 is None else t1
    P = {"B": lambda t: (t, off, z), "F": lambda t: (t, -off, z), "W": lambda t: (-off, t, z), "E": lambda t: (off, t, z)}[side]
    member(name, code, P(a0), P(a1), (RT, RRH), R, up=fup({"B": "+y", "F": "-y", "W": "-x", "E": "+x"}[side], FLARE))
zb_r, zt_r = zp0 + RRH/2, zp1 - RRH/2      # F14 bottom edge flush with post bottoms; F16 top edge flush with post tops (step 115)
for sd in ("B", "F", "W"): roof_rail(f"F14_{sd}", "F14", sd, zb_r)
roof_rail("F15_E", "F15", "E", zb_r, t0=-RP/2, t1=pc(zb_r) + RP/2 - 0.0)          # step 116-117: C09_BE to C10_E only
for sd in ("B", "F", "W", "E"): roof_rail(f"F16_{sd}", "F16", sd, zt_r)

# hip rafters (KA12) sit ON the corner post tops, predrilled holes centred diagonally on the post top (steps 122-125),
# rising to the rafter brace block KA09 at the apex (123, 126-129). The tarp lies over them (130).
RFW, RFD = 0.07, 0.035                     # E  rafter laid flat: 70 wide x 35 deep
te = rt_ + RP/2 + RT                       # outer face of the eave rails at the top
RAFT_D0 = rt_*math.sqrt(2)                      # plan distance from the apex to a corner post centre
KB_HALF = RFW/2                             # KA09 brace block: one rafter width square, turned 45 degrees so each rafter meets a face
cos_t = None
RAFT_K = (PEAK - 0.012 - zp1 - RFD*1.08)/RAFT_D0     # slope: rafter top line reaches the peak (0.012 m under the tarp)
cos_t = 1/math.sqrt(1 + RAFT_K*RAFT_K); RD_V = RFD/cos_t
def raft_bot(d): return zp1 + (RAFT_D0 - d)*RAFT_K    # rafter underside height at plan distance d from the apex
RAFTERS = {}
for n, (sx, sy) in {"KA12_BE": (1, 1), "KA12_BW": (-1, 1), "KA12_FE": (1, -1), "KA12_FW": (-1, -1)}.items():
    dl = RAFT_D0 + (RP/2)*math.sqrt(2) - 0.005  # lower end at the post's outer corner
    du = KB_HALF                           # upper end butts square against a face of the brace block
    e = Vector((sx, sy, 0)).normalized(); w = Vector((0, 0, 1)).cross(e)
    vs = []
    for d_ in (dl, du):                    # plumb-cut ends (vertical), so the top end sits flat on the block face
        for zz in (raft_bot(d_), raft_bot(d_) + RD_V):
            for sw in (-1, 1): vs.append(tuple(e*d_ + w*sw*RFW/2 + Vector((0, 0, zz))))
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(n); me.from_pydata(vs, [], fs); me.update()
    ob = bpy.data.objects.new(n, me); ob.data.materials.append(CEDAR); R.objects.link(ob)
    c0 = e*dl + Vector((0, 0, raft_bot(dl) + RD_V/2)); c1 = e*du + Vector((0, 0, raft_bot(du) + RD_V/2))
    ax_ = (c1 - c0).normalized(); ms = RFW*RFD*(c1 - c0).length*RHO
    ob["code"] = "KA12"; ob["kind"] = "wood"; ob["mass_kg"] = ms
    M[n] = dict(obj=ob, p0=c0, p1=c1, u=w, v=ax_.cross(w).normalized(), a=ax_, sec=(RFW, RFD), code="KA12", kind="wood", mass=ms)
    RAFTERS[n] = dict(e=e, post="C09_" + n.split("_")[1])
ztop_apex = raft_bot(0.0) + RD_V
member("KA09", "KA09", (0, 0, raft_bot(KB_HALF)), (0, 0, raft_bot(KB_HALF) + RD_V), (2*KB_HALF, 2*KB_HALF), R, up=(1, 1, 0))   # same depth as the rafters: flush top and bottom

# tarp: pyramid resting on the rafters, eave edges on the F16 tops, corners at C09 (step 130), skirt screwed to F16 (131-133)
CLR = 0.02                                  # tarp clears the rafter's top edges
def tarp_hip(d): return raft_bot(d) + RD_V + CLR
TZ = zp1 + 0.002; SKIRT = 0.10; PZ = tarp_hip(0.0); ZC = tarp_hip(te*math.sqrt(2))
C4 = [(-te, -te), (te, -te), (te, te), (-te, te)]; MID = [(0, -te), (te, 0), (0, te), (-te, 0)]
vs = [(x, y, ZC) for x, y in C4] + [(x, y, TZ) for x, y in MID] + [(0, 0, PZ)]
vs += [(x, y, ZC - SKIRT) for x, y in C4] + [(x, y, TZ - SKIRT) for x, y in MID]
fs = []
for i in range(4):
    c0, c1, m = i, (i + 1) % 4, 4 + i
    fs += [(c0, m, 8), (m, c1, 8), (9 + c0, 13 + i, m, c0), (13 + i, 9 + c1, c1, m)]
me = bpy.data.meshes.new("Tarp"); me.from_pydata(vs, [], fs); me.update()
tarp = bpy.data.objects.new("Tarp", me); tarp.data.materials.append(TARP); R.objects.link(tarp); tarp["mass_kg"] = 3.0

# ================= SMALL DECK + SLIDE + LADDER (steps 75-106, 172) =================
SD = coll("Small_deck")
SDZ = 1.20                                   # M
SX0 = face(SDZ - 0.08) + RT                  # tower east face
SXO = 1.86                                   # M  outer legs
SYF, SYB = -lean(SDZ), 0.0                   # between C03 (front corner) and C06 (mid)
def yf(z): return -lean(z)                    # front side lies in the tower's sloped front plane (C07 leans like C03); C08 stays plumb in y like C06
SDL_TOP = 1.98
def sdx(z): return SXO + 0.03 - 0.035*z       # small deck legs lean in like the tower ('angled edges')
member("C07", "C07", (sdx(0), yf(0), 0), (sdx(SDL_TOP), yf(SDL_TOP), SDL_TOP), (LEG, LEG), SD)
member("C08", "C08", (sdx(0), SYB, 0), (sdx(SDL_TOP), SYB, SDL_TOP), (LEG, LEG), SD)
fo = lambda z: sdx(z) + LEG/2 + RT/2
member("S02", "S02", (fo(0.07), yf(0.07) - 0.04, 0.07), (fo(0.07), SYB + 0.04, 0.07), (RT, RH), SD, up=fup("+x", 0.035))  # step 79
zsr = SDZ - 0.02 - 0.06
member("K02_O", "K02", (fo(zsr), yf(zsr) - 0.04, zsr), (fo(zsr), SYB + 0.04, zsr), (RT, 0.12), SD, up=fup("+x", 0.035))  # step 81
member("K02_T", "K02", (lean(zsr) + LEG/2 + RT/2, yf(zsr) - LEG/2 - RT, zsr), (lean(zsr) + LEG/2 + RT/2, SYB + LEG/2 + RT, zsr), (RT, 0.12), SD, up=fup("+x"))  # step 90
member("K01", "K01", (lean(zsr), yf(zsr) - LEG/2 - RT/2, zsr), (sdx(zsr), yf(zsr) - LEG/2 - RT/2, zsr), (RT, 0.12), SD, up=fup("-y"))  # step 86 (front)
member("K03", "K03", (lean(zsr), SYB + LEG/2 + RT/2, zsr), (sdx(zsr), SYB + LEG/2 + RT/2, zsr), (RT, 0.12), SD) # step 87 (inner)
xm = (SX0 + SXO)/2
member("KA10", "KA10", (xm, yf(zsr) - LEG/2, zsr + 0.01), (xm, SYB + LEG/2, zsr + 0.01), (0.038, 0.10), SD)                       # step 91
member("FA17_C07", "FA17", (sdx(zsr) - LEG, yf(zsr), zsr - 0.04), (sdx(zsr) - LEG, yf(zsr), zsr + 0.06), (0.07, 0.07), SD)
member("FA17_C08", "FA17", (sdx(zsr) - LEG, SYB, zsr - 0.04), (sdx(zsr) - LEG, SYB, zsr + 0.06), (0.07, 0.07), SD)
SDB = ["W12A"] + ["W08"]*9 + ["W12", "W04"]    # front edge -> inner edge (steps 93-97)
sp = (SYB + LEG/2 + RT - (SYF - LEG/2 - RT))/len(SDB)
for i, code in enumerate(SDB):
    y = SYF - LEG/2 - RT + sp*(i + 0.5)
    member(f"{code}_sd{i}", code, (lean(SDZ) + LEG/2, y, SDZ - 0.0095), (fo(SDZ) + RT/2, y, SDZ - 0.0095), (sp - 0.004, 0.019), SD)
member("F07", "F07", (fo(SDL_TOP - 0.05), yf(SDL_TOP - 0.05) - 0.04, SDL_TOP - 0.05), (fo(SDL_TOP - 0.05), SYB + 0.04, SDL_TOP - 0.05), (RT, 0.09), SD, up=fup("+x", 0.035))  # step 82
member("FA14", "FA14", (fo(SDZ + 0.08), yf(SDZ + 0.08), SDZ + 0.08), (fo(SDZ + 0.08), SYB, SDZ + 0.08), (RT, 0.09), SD, up=fup("+x", 0.035))  # step 98
for k in range(5):                                                                                                                         # step 99
    zl, zh = SDZ + 0.04, SDL_TOP - 0.01        # boards fan with the sloped front leg
    y0 = yf(zl) + (k + 0.5)*(SYB - yf(zl))/5; y1 = yf(zh) + (k + 0.5)*(SYB - yf(zh))/5
    member(f"W14_{k}", "W14", (fo(zl) + RT/2 + WB_T/2, y0, zl), (fo(zh) + RT/2 + WB_T/2, y1, zh), (WB_T, 0.09), SD, up=(0, 1, 0))
for tag, yy in (("F", lambda z: yf(z) - LEG/2 - RT/2), ("B", lambda z: SYB + LEG/2 + RT/2)):
    member(f"F05_low_{tag}", "F05", (lean(0.45) + LEG/2, yy(0.45), 0.45), (sdx(0.45) - LEG/2, yy(0.45), 0.45), (RT, 0.09), SD, up=fup("-y") if tag == "F" else (0, 0, 1))               # step 88
    zt = SDL_TOP - 0.05
    member(f"F05_top_{tag}", "F05", (lean(zt) + LEG/2, yy(zt), zt), (sdx(zt), yy(zt), zt), (RT, 0.09), SD, up=fup("-y") if tag == "F" else (0, 0, 1))  # step 89
# opening block (step 100): centred in the gap between K08_E's bottom edge and the small deck floor, ~2 in each side
# (manual: ~2.75 in, never over 3.5 in), across the outer faces of C03 and C06, flush with K08_E
KA14_H = 0.09; zka = ((zr - RH/2) + SDZ)/2
member("KA14", "KA14", (face(zka), -lean(zka) - LEG/2, zka), (face(zka), LEG/2, zka), (RT, KA14_H), SD, up=fup("+x"))
print(f"KA14 gaps: above {(zr - RH/2) - (zka + KA14_H/2):.3f} m, below {(zka - KA14_H/2) - SDZ:.3f} m")                                       # step 100
handle("Handle_C08", lambda z: (sdx(z), SYB), (0, 1), SD, z0=1.30, z1=1.56)    # faces the ladder (step 101)

LD = coll("Ladder")                         # off the inner edge, toward the back (cover photo + step 193)
LX, LWD, LRUN = 1.47, 0.42, 0.85
LH = zsr + 0.04
K03_OUT = SYB + LEG/2 + RT                  # outer face of K03
LY0 = K03_OUT + 0.045*math.hypot(LH, LRUN)/LH - (LH - zsr)*LRUN/LH   # upright's front edge touches K03 at rail height
LAX = Vector((0, LRUN, -LH)).normalized(); LN = Vector((0, LH, LRUN)).normalized()   # along the ladder / walking-face normal
for n, s in (("K20", -1), ("K21", 1)):
    member(n, n, (LX + s*LWD/2, LY0, LH), (LX + s*LWD/2, LY0 + LRUN, 0.0), (0.035, 0.09), LD)
for k in range(4):
    t = (k + 1)/5; y = LY0 + t*LRUN; z = LH*(1 - t)
    member(f"F23_{k}", "F23", (LX - LWD/2, y, z), (LX + LWD/2, y, z), (0.09, 0.025), LD)
w23c = Vector((0, LY0, LH)) + LAX*0.10 - LN*(0.045 + 0.01)
member("W23", "W23", (LX - LWD/2 - 0.0175, w23c.y, w23c.z), (LX + LWD/2 + 0.0175, w23c.y, w23c.z), (0.09, 0.02), LD, up=tuple(LN))
ysk = LY0 + LRUN*(1 - 0.05/LH)
member("Stake_K20", "Stake", (LX - LWD/2 - 0.0175 - 0.006, ysk, 0.1), (LX - LWD/2 - 0.0175 - 0.006, ysk, -0.30), (0.012, 0.012), LD, m=STEEL, kind="steel", mass=0.6)

SLD = coll("Slide")                         # wave slide off W12A toward the front (step 172)
def build_slide():
    """One molded part: U trough with rolled lips swept along a smooth wave path.
    Top lip lies on W12A (2x SW50, step 172); flat runout ~0.28 m (ASTM F1148 exit 7-15 in); end curls down to the ground."""
    ys = SYF - LEG/2 - RT                       # front edge of the small deck
    T = 0.010                                   # wall thickness
    ctrl = [(0.10, SDZ + T/2), (0.0, SDZ + T/2), (-0.12, SDZ - 0.02), (-0.50, 0.93), (-0.80, 0.80), (-1.00, 0.76),
            (-1.40, 0.50), (-1.80, 0.32), (-2.10, 0.285), (-2.40, 0.28), (-2.52, 0.23), (-2.58, 0.12), (-2.60, T/2)]
    RUN = 1.90 / 2.60                           # listing depth 155 in (3.94 m) = ladder foot (+0.91) to slide end
    ctrl = [(ys + (dy*RUN if dy < 0 else dy), z) for dy, z in ctrl]
    def cr(p0, p1, p2, p3, t):                  # Catmull-Rom
        return tuple(0.5*((2*b) + (-a + c)*t + (2*a - 5*b + 4*c - d)*t*t + (-a + 3*b - 3*c + d)*t**3) for a, b, c, d in zip(p0, p1, p2, p3))
    P = [ctrl[0]] + ctrl + [ctrl[-1]]
    path = []
    for i in range(1, len(P) - 2):
        for k in range(8): path.append(cr(P[i-1], P[i], P[i+1], P[i+2], k/8))
    path.append(ctrl[-1])
    HW, LIP, R = 0.205, 0.035, 0.045
    def section(hgt):
        pts = [(-HW - LIP, hgt), (-HW, hgt)]
        for k in range(5): a = math.pi + (math.pi/2)*k/4; pts.append((-HW + R + R*math.cos(a), R + R*math.sin(a)))
        for k in range(5): a = 1.5*math.pi + (math.pi/2)*k/4; pts.append((HW - R + R*math.cos(a), R + R*math.sin(a)))
        pts += [(HW, hgt), (HW + LIP, hgt)]
        return pts
    verts, faces = [], []; ns = None; Ltot = len(path)
    for i, (y, z) in enumerate(path):
        y0, z0 = path[max(i - 1, 0)]; y1, z1 = path[min(i + 1, Ltot - 1)]
        ty, tz = y1 - y0, z1 - z0; l = math.hypot(ty, tz); ty, tz = ty/l, tz/l
        ny, nz_ = -tz, ty                         # in-plane normal, pointing up off the bed
        if nz_ < 0: ny, nz_ = -ny, -nz_
        frac_end = max(0.0, (i - (Ltot - 22))/22) # walls taper over the exit curl
        hgt = 0.13*(1 - 0.85*frac_end) + R*0.85*frac_end
        sec = section(max(hgt, R))
        ns = len(sec)
        for (sx, sh) in sec: verts.append((xm + sx, y + ny*sh, z + nz_*sh))
        if i:
            b0, b1 = (i - 1)*ns, i*ns
            for k in range(ns - 1): faces.append((b0 + k, b0 + k + 1, b1 + k + 1, b1 + k))
    me = bpy.data.meshes.new("Slide"); me.from_pydata(verts, [], faces); me.update()
    ob = bpy.data.objects.new("Slide", me); ob.data.materials.append(BLUE); SLD.objects.link(ob)
    mod = ob.modifiers.new("thickness", 'SOLIDIFY'); mod.thickness = T; mod.offset = -1
    bpy.context.view_layer.objects.active = ob; ob.select_set(True); bpy.ops.object.modifier_apply(modifier="thickness"); ob.select_set(False)
    for p in me.polygons: p.use_smooth = True
    ob["code"] = "Slide"; ob["kind"] = "plastic"; ob["mass_kg"] = 13.0
    p0, p1 = Vector((xm, ctrl[0][0], ctrl[0][1])), Vector((xm, ctrl[2][0], ctrl[2][1]))
    a = (p1 - p0).normalized()
    M["Slide"] = dict(obj=ob, p0=p0, p1=p1, u=Vector((1, 0, 0)), v=Vector((0, 0, 1)), a=a, sec=(2*HW, T), code="Slide", kind="plastic", mass=13.0)
    print(f"slide: top {SDZ:.2f} m, runout {0.28:.2f} m, end lip at ground, length along path {sum(math.dist(path[i], path[i+1]) for i in range(Ltot - 1)):.2f} m")
build_slide()

# ================= SWING BEAM + A-FRAME (steps 146-163, 191) =================
SW = coll("Swing_frame")
BZ = 1.956 - 0.07                            # M  beam TOP at 6'5" (listing: 6'6" top-to-ground); BZ = beam centreline
# Y-bracket DRB-01 (parts drawing; layout confirmed by the user): a square beam cup, closed at the far end and open toward
# the tower, with one leg socket welded to each side wall, set back from the closed end. The beam end runs between the two
# leg tops to the closed end. Socket tops are level and flush with the cup top. Two screw holes on the cup's top near its
# open end (step 154); one screw per broad socket face (148-149).
import bmesh
AX, AH = -3.03, 0.97                          # A-frame plane x; leg foot spread from centre
WT, SKT = 0.003, 0.085                        # steel wall, socket outer size
SLY, SLZ = 0.085, 0.155                       # beam cup outer width / height
YB_GAP, YB_FRONT = 0.05, 0.11                 # E  closed end set back behind the sockets; cup reach past them toward the tower
XS0 = AX - SKT/2 - YB_GAP                     # cup's closed end
SLL = YB_GAP + SKT + YB_FRONT
BX1, BX0 = -(lean(BZ) + LEG/2), XS0 + 0.004   # beam: from the sleeve's end plate to the C05 post face
member("B03", "B03", (BX0, 0, BZ), (BX1, 0, BZ), (0.07, 0.14), SW)
WT = 0.003
import bmesh
IB_SL, IB_H = 0.10, 0.14                      # sleeve length on the beam; flange height
IB_PARTS = []
def ib_piece(p0, p1, sec):
    nm = f"_ib{len(IB_PARTS)}"; member(nm, "DRB-02", p0, p1, sec, SW, m=BRICK, kind="steel", mass=0.0, up=(0, 0, 1)); IB_PARTS.append(nm)
for sy in (-1, 1):                             # side plates: along the beam, then on past its end over the post's sides
    ib_piece((BX1 - IB_SL, sy*(0.035 + WT/2), BZ), (BX1 + LEG, sy*(0.035 + WT/2), BZ), (WT, IB_H))
for sz in (-1, 1):                             # top and bottom of the sleeve, on the beam only
    ib_piece((BX1 - IB_SL, 0, BZ + sz*(0.07 + WT/2)), (BX1, 0, BZ + sz*(0.07 + WT/2)), (0.07 + 2*WT, WT))
ibo = M[IB_PARTS[0]]["obj"]; ibo.name = "DRB02_Ibracket"; ibo.data.name = "DRB02_Ibracket"
bm = bmesh.new(); bm.from_mesh(ibo.data)
for nm in IB_PARTS[1:]:
    so = M.pop(nm)["obj"]; me2 = so.data.copy(); me2.transform(ibo.matrix_world.inverted() @ so.matrix_world)
    bm.from_mesh(me2); bpy.data.objects.remove(so); bpy.data.meshes.remove(me2)
bm.to_mesh(ibo.data); bm.free(); M.pop(IB_PARTS[0])
M["DRB02_Ibracket"] = dict(obj=ibo, p0=Vector((BX1 - IB_SL, 0, BZ)), p1=Vector((BX1, 0, BZ)), u=Vector((0, 1, 0)), v=Vector((0, 0, 1)),
                          a=Vector((1, 0, 0)), sec=(0.07 + 2*WT, 0.14 + 2*WT), code="DRB-02", kind="steel", mass=1.6)
ibo["code"] = "DRB-02"; ibo["kind"] = "steel"; ibo["mass_kg"] = 1.6
YB_PARTS = []
def yb_piece(p0, p1, sec, up):
    nm = f"_yb{len(YB_PARTS)}"; member(nm, "DRB-01", p0, p1, sec, SW, m=BRICK, kind="steel", mass=0.0, up=up); YB_PARTS.append(nm)
def yb_prism(top4, bot4):
    """Steel piece from 4 top corners to 4 matching bottom corners (any shear)."""
    nm = f"_yb{len(YB_PARTS)}"
    me = bpy.data.meshes.new(nm); me.from_pydata([tuple(v) for v in top4 + bot4], [],
        [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]); me.update()
    ob = bpy.data.objects.new(nm, me); ob.data.materials.append(BRICK); SW.objects.link(ob)
    M[nm] = dict(obj=ob); YB_PARTS.append(nm)
yb_piece((XS0, 0, BZ), (XS0 + 0.004, 0, BZ), (SLY, SLZ), (0, 0, 1))                       # sleeve end plate
for sz in (-1, 1): yb_piece((XS0, 0, BZ + sz*(SLZ/2 - WT/2)), (XS0 + SLL, 0, BZ + sz*(SLZ/2 - WT/2)), (SLY, WT), (0, 0, 1))
for sy in (-1, 1): yb_piece((XS0, sy*(SLY/2 - WT/2), BZ), (XS0 + SLL, sy*(SLY/2 - WT/2), BZ), (WT, SLZ), (0, 0, 1))
# leg sockets: top cut level and flush with the sleeve top, inner face tight against the sleeve side (parts drawing)
ZTOP = BZ + SLZ/2; H = SKT/2; SOCK = 0.20; XH = Vector((1, 0, 0))
YB_DROP = 0.025                                 # E  socket tops sit this far below the cup top (parts drawing)
ZS = ZTOP - YB_DROP
LEG_TOPS = {}
for n, s in (("C20_F", -1), ("C20_B", 1)):
    yq = s*(SLY/2 + H)
    for _ in range(4):                          # socket's inner face tight against the cup's side wall along the top plane
        th = math.atan2(AH - abs(yq), ZS); yq = s*(SLY/2 + H/math.cos(th))
    th = math.atan2(AH - abs(yq), ZS)
    d = Vector((0, s*math.sin(th), -math.cos(th))); u = Vector((0, s*math.cos(th), math.sin(th)))   # down the leg / outward-up
    Q = Vector((AX, yq, ZS))
    def corner(ex, eu, bottom):
        t = SOCK if bottom else eu*math.tan(th)       # top corners lie on the level plane, bottom cut square to the leg
        return Q + XH*ex + u*eu + d*t
    def wall(ex0, ex1, eu0, eu1):
        cs = [(ex0, eu0), (ex1, eu0), (ex1, eu1), (ex0, eu1)]
        yb_prism([corner(ex, eu, False) for ex, eu in cs], [corner(ex, eu, True) for ex, eu in cs])
    wall(-H, H, H - WT, H); wall(-H, H, -H, -H + WT)              # outer and inner walls
    wall(H - WT, H, -H, H); wall(-H, -H + WT, -H, H)              # the two broad faces (screwed, steps 148-149)
    cap = [corner(ex, eu, False) for ex, eu in ((-H, -H), (H, -H), (H, H), (-H, H))]
    yb_prism(cap, [c - Vector((0, 0, WT)) for c in cap])           # level top plate
    t0 = (0.035*math.sin(th) + WT + 0.001)/math.cos(th)            # square leg top sits just under the plate
    p0, p1 = Q + d*t0, Vector((AX, s*AH, 0.0))
    member(n, "C20", p0, p1, (0.07, 0.07), SW, up=(1, 0, 0))
    LEG_TOPS[n] = dict(p0=p0, d=d, u=u, mid=Q + d*(SOCK/2))
AF_Y0, AF_Z0 = abs(yq), ZS                         # leg axis line (used by the stakes and the F30 brace)
yb = M[YB_PARTS[0]]["obj"]; yb.name = "DRB01_Ybracket"; yb.data.name = "DRB01_Ybracket"
bm = bmesh.new(); bm.from_mesh(yb.data)
for nm in YB_PARTS[1:]:                       # weld everything into one steel part
    so = M.pop(nm)["obj"]; me2 = so.data.copy(); me2.transform(yb.matrix_world.inverted() @ so.matrix_world)
    bm.from_mesh(me2); bpy.data.objects.remove(so); bpy.data.meshes.remove(me2)
bm.to_mesh(yb.data); bm.free()
M.pop(YB_PARTS[0])
M["DRB01_Ybracket"] = dict(obj=yb, p0=Vector((XS0, 0, BZ)), p1=Vector((XS0 + SLL, 0, BZ)), u=Vector((0, 1, 0)), v=Vector((0, 0, 1)),
                          a=Vector((1, 0, 0)), sec=(SLY, SLZ), code="DRB-01", kind="steel", mass=2.2)
yb["code"] = "DRB-01"; yb["kind"] = "steel"; yb["mass_kg"] = 2.2
for n, s in (("C20_F", -1), ("C20_B", 1)):
    ysk = s*(AF_Y0 + (AH - AF_Y0)*(1 - 0.06/AF_Z0))
    member(f"Stake_{n}", "Stake", (AX + 0.041, ysk, 0.12), (AX + 0.041, ysk, -0.30), (0.012, 0.012), SW, m=STEEL, kind="steel", mass=0.6)
zf = 0.62; yf30 = AF_Y0 + (AH - AF_Y0)*(1 - zf/AF_Z0)
member("F30", "F30", (AX + 0.05, -yf30 - 0.04, zf), (AX + 0.05, yf30 + 0.04, zf), (0.03, 0.09), SW, up=(0, 0, 1))
HANGERS = (-2.75, -2.30, -2.01, -1.56)       # M
def loop(name, centre, r, t, plane, c, m=STEEL):
    """Closed wire loop (ring, hook) in plane 'xz' or 'yz' around centre."""
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = t
    sp_ = cu.splines.new('POLY'); sp_.points.add(15); sp_.use_cyclic_u = True
    for k in range(16):
        a_ = 2*math.pi*k/16; cx, cz = r[0]*math.cos(a_), r[1]*math.sin(a_)
        sp_.points[k].co = ((centre[0] + cx, centre[1], centre[2] + cz, 1) if plane == "xz" else (centre[0], centre[1] + cx, centre[2] + cz, 1))
    ob = bpy.data.objects.new(name, cu); ob.data.materials.append(m); c.objects.link(ob); return ob
HANG_BOT = {}
for i, x in enumerate(HANGERS):                # swing hanger (step 159): bolt through the beam, pivot bracket, snap hook, O-ring
    zb_ = BZ - 0.07                            # beam underside
    member(f"Hanger_{i}_plate", "Hanger", (x, 0, zb_ - 0.004), (x, 0, zb_), (0.03, 0.03), SW, m=STEEL, kind="steel", mass=0.02)        # bearing collar
    vs = [(x - 0.022, 0, zb_ - 0.004), (x + 0.022, 0, zb_ - 0.004), (x + 0.006, 0, zb_ - 0.055), (x - 0.006, 0, zb_ - 0.055)]
    me = bpy.data.meshes.new(f"Hanger_{i}"); me.from_pydata([(v[0], v[1] + o, v[2]) for o in (-0.009, 0.009) for v in vs], [],
        [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]); me.update()
    hb = bpy.data.objects.new(f"Hanger_{i}", me); hb.data.materials.append(STEEL); SW.objects.link(hb); hb["mass_kg"] = 0.15   # pivot bracket
    loop(f"Hook_{i}", (x, 0, zb_ - 0.095), (0.014, 0.036), 0.0035, "yz", SW)           # screw-gate snap hook
    member(f"Hook_{i}_gate", "Hanger", (x, 0.014, zb_ - 0.115), (x, 0.014, zb_ - 0.085), (0.008, 0.008), SW, m=STEEL, kind="steel", mass=0.0)
    loop(f"Ring_{i}", (x, 0, zb_ - 0.150), (0.022, 0.022), 0.004, "xz", SW)              # O-ring the rope loops through
    HANG_BOT[i] = (x, 0, zb_ - 0.172)

def swing_seat(name, cx, z, c):
    """Molded belt-style seat: curved up at the ends, tapered, lipped edges; rope brackets at each end."""
    L, T = 0.50, 0.012
    def dz(u): return 0.065*abs(2*u/L)**2.4
    def halfw(u): return 0.085 - 0.022*(2*u/L)**2
    verts, faces = [], []; NU = 25
    for i in range(NU):
        u = -L/2 + L*i/(NU - 1); hw = halfw(u)
        prof = [(-hw, 0.014), (-hw + 0.012, 0.0), (hw - 0.012, 0.0), (hw, 0.014)]
        for (py, pz) in prof: verts.append((cx + u, py, z + dz(u) + pz))
        if i:
            b0, b1 = (i - 1)*4, i*4
            for k in range(3): faces.append((b0 + k, b0 + k + 1, b1 + k + 1, b1 + k))
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    ob = bpy.data.objects.new(name, me); ob.data.materials.append(BRICK); c.objects.link(ob)
    mod = ob.modifiers.new("t", 'SOLIDIFY'); mod.thickness = T; mod.offset = -1
    bpy.context.view_layer.objects.active = ob; ob.select_set(True); bpy.ops.object.modifier_apply(modifier="t"); ob.select_set(False)
    for p in me.polygons: p.use_smooth = True
    ob["code"] = "Seat"; ob["kind"] = "plastic"; ob["mass_kg"] = 1.2
    M[name] = dict(obj=ob, p0=Vector((cx - L/2, 0, z)), p1=Vector((cx + L/2, 0, z)), u=Vector((0, 1, 0)), v=Vector((0, 0, 1)),
                   a=Vector((1, 0, 0)), sec=(0.17, T), code="Seat", kind="plastic", mass=1.2)
    tops = []
    for s in (-1, 1):                            # end brackets clamp the rope to the seat
        ue = s*(L/2 - 0.025); zt = z + dz(ue)
        member(f"{name}_bracket_{'L' if s < 0 else 'R'}", "Seat bracket", (cx + ue, 0, zt - 0.02), (cx + ue, 0, zt + 0.05), (0.035, 0.05), c, m=BRICK, kind="plastic", mass=0.1, up=(1, 0, 0))
        tops.append((cx + ue, 0, zt + 0.05))
    return tops
SEAT_Z = 0.36                                    # seat top ~14 in at its lowest point (step 163)
for si, (xa, xb) in enumerate(((HANGERS[0], HANGERS[1]), (HANGERS[2], HANGERS[3]))):
    tops = swing_seat(f"Swing{si}_seat", (xa + xb)/2, SEAT_Z - 0.012, SW)
    for x, top in zip((xa, xb), tops):
        rope(f"Swing{si}_rope_{x:.2f}", [HANG_BOT[HANGERS.index(x)], top], SW, r=0.008)

# ================= NETS (steps 173-184) =================
NT = coll("Nets")
NET_FIX = []                                   # (step, eye member, structure member, fastener type)
def eye(name, centre, normal, c, size=0.028, thick=0.008):
    """Steel rope-end fitting: a small plate with its face against `normal` (pointing from the eye into the wood)."""
    n_ = Vector(normal).normalized(); up = (0, 0, 1) if abs(n_.z) < 0.9 else (1, 0, 0)
    cv = Vector(centre)
    member(name, "Eye", cv - n_*thick/2, cv + n_*thick/2, (size, size), c, m=STEEL, kind="steel", mass=0.05, up=up)
# hammock cargo net: 8 eye bolts, one through each tower leg at the same height, eyes on the legs' inner faces (steps 174-179)
EZ, SAG, N = 0.85, 0.32, 15
EYE_T = 0.02
hh = lean(EZ) - LEG/2 - EYE_T                  # net perimeter sits on the inner side of the eyes
def nz(x, y): return EZ - SAG*(1 - (x/hh)**2)*(1 - (y/hh)**2)
for ax in (0, 1):
    for i in range(N):
        t = -hh + 2*hh*i/(N - 1); ps = []
        for jj in range(N):
            s_ = -hh + 2*hh*jj/(N - 1); x, y = (s_, t) if ax == 0 else (t, s_); ps.append((x, y, nz(x, y)))
        rope(f"Hammock_{ax}_{i}", ps, NT, r=0.006)
for leg, (sx, sy), st in (("C06", (1, 0), 175), ("C05", (-1, 0), 175), ("C04A", (0, 1), 176), ("C04B", (0, -1), 176),
                          ("C01A", (1, 1), 177), ("C03", (1, -1), 177), ("C02", (-1, 1), 178), ("C01B", (-1, -1), 178)):
    out = Vector((sx, sy, 0)).normalized()
    face_pt = Vector((sx*(lean(EZ) - LEG/2), sy*(lean(EZ) - LEG/2), EZ))
    eye(f"Hammock_eye_{leg}", face_pt - out*EYE_T/2, out, NT, size=0.03, thick=EYE_T)
    NET_FIX.append((st, f"Hammock_eye_{leg}", leg, "EYE"))
# climbing net: in the plane of the back face's outer leg faces between C02 and C04A (steps 180-184).
# Vertical ropes: tops bolted to the floor rail K07 (M833), bottoms to the base board S04A (M821);
# horizontal ropes: ends screwed into the inner side faces of C02 and C04A (8x M8SW50).
def ny(z): return lean(z) + LEG/2 - 0.015       # rope plane, 15 mm inside the legs' outer faces
ET = 0.008
for k_, x in enumerate((-0.65, -0.35)):
    zt_, zb2 = zr - 0.03, zb
    for tag, z, rail in (("top", zt_, "K07"), ("bot", zb2, "S04A")):
        yr_ = lean(z) + LEG/2                   # rail inner face
        eye(f"Climb_eye_{tag}_{k_}", (x, yr_ - ET/2, z), (0, 1, 0), NT, thick=ET)
        NET_FIX.append((182 if tag == "top" else 183, f"Climb_eye_{tag}_{k_}", rail, "M833" if tag == "top" else "M821"))
    rope(f"Climb_v_{k_}", [(x, ny(zt_), zt_), (x, ny(zb2), zb2)], NT, r=0.009)
for k_ in range(4):
    z = zr - (k_ + 1)*(zr - zb)/5
    xw, xe = -lean(z) + LEG/2, -LEG/2           # inner side faces of C02 and C04A
    eye(f"Climb_eye_W_{k_}", (xw + ET/2, ny(z), z), (-1, 0, 0), NT, thick=ET)
    eye(f"Climb_eye_E_{k_}", (xe - ET/2, ny(z), z), (1, 0, 0), NT, thick=ET)
    NET_FIX += [(184, f"Climb_eye_W_{k_}", "C02", "M8SW50"), (184, f"Climb_eye_E_{k_}", "C04A", "M8SW50")]
    rope(f"Climb_h_{k_}", [(xw + ET, ny(z), z), (xe - ET, ny(z), z)], NT, r=0.009)

# ================= FASTENERS (every step's hardware) =================
FT = {   # d mm, L mm, est. single-shear ultimate capacity in cedar N (ESTIMATES +/-50%), mass g
    "M821": (8, 21, 4000, 18), "M833": (8, 33, 4000, 22), "M865": (8, 65, 4000, 32), "M896": (8, 96, 4000, 42), "M8107": (8, 107, 4000, 46),
    "M6SW35": (6, 35, 1800, 9), "M6SW55": (6, 55, 2000, 13), "M8SW50": (8, 50, 2800, 20), "M8SW60": (8, 60, 3000, 23),
    "SW16": (4, 16, 300, 2), "SW35": (4.5, 35, 900, 4), "SW50": (5, 50, 1200, 6), "SW60": (5, 60, 1300, 7), "SW75": (6, 75, 1600, 11),
    "EYE": (8, 100, 4000, 60), "HANGER": (10, 160, 8000, 250),
}
J = []   # (step, attached_member, base_member, fastener, count)
def j(step, a, b, ft, n): J.append((step, a, b, ft, n))
for leg, n in (("C01A", 2), ("C04A", 2), ("C02", 2)): j(14, "S04A", leg, "M896", n)
for leg, n in (("C01A", 2), ("C04A", 1), ("C02", 2)): j(15, "K07", leg, "M8107", n)
for leg, n in (("C01B", 2), ("C04B", 2), ("C03", 2)): j(23, "S04", leg, "M896", n)
for leg, n in (("C01B", 2), ("C04B", 1), ("C03", 2)): j(24, "K06", leg, "M8107", n)
j(29, "K08_W", "C02", "M8107", 1); j(29, "K08_W", "C01B", "M8107", 1); j(30, "K08_E", "C03", "M8107", 1); j(30, "K08_E", "C01A", "M8107", 1)
j(31, "S03_E", "C03", "M896", 2); j(31, "S03_E", "C01A", "M896", 2); j(32, "S03_W", "C02", "M896", 2); j(32, "S03_W", "C01B", "M896", 2)
j(33, "C06", "K08_E", "M8107", 1); j(33, "C06", "S03_E", "M896", 2); j(34, "C05", "K08_W", "M8107", 1); j(34, "C05", "S03_W", "M896", 2)
for n, leg in (("FA17_C03", "C03"), ("FA17_C01B", "C01B"), ("FA17_C02", "C02"), ("FA17_C01A", "C01A"), ("FA17_C01A_y", "C01A"), ("FA17_C06", "C06")):
    j(35, n, leg, "SW50", 2)
for leg in ("C01A", "C02", "C03", "C01B"):
    for ax, rail in (("x", "K07" if leg in ("C01A", "C02") else "K06"), ("y", "K08_E" if leg in ("C01A", "C03") else "K08_W")):
        j(42, f"KA13_{leg}_{ax}", rail, "M865", 1); j(42, f"KA13_{leg}_{ax}", leg, "M8SW50", 1)
j(46, "KA11_C", "C05", "SW75", 2); j(46, "KA11_C", "C06", "SW75", 2)
for side in ("W", "E"):
    for fb in ("F", "B"): j(47, f"K08_{side}", f"C11_{side}_{fb}", "M8107", 2)      # bolts from outside the rail into T-nuts in the brace
for fb in ("F", "B"):
    j(49, f"C11_W_{fb}", f"K05_{fb}", "M8107", 1); j(49, f"C11_E_{fb}", f"K05_{fb}", "M8107", 1)
    j(53, f"KA11_{fb}", "K08_W", "SW75", 2); j(53, f"KA11_{fb}", "K08_E", "SW75", 2)
for i in range(2):
    for fb in ("F", "B"): j(51, f"CA10_{i}_{fb}", f"K05_{fb}", "M8107", 2)
# floorboards: two SW35 at every support they cross (8 per full board, matching steps 62-74)
SUPPORTS_Y = {"K06": -yr, "K05_F": -0.29, "K05_B": 0.29, "K07": yr}
for name, d in list(M.items()):
    if d["code"] in ("W09", "W11", "W10", "W02", "W01"):
        y0, y1 = sorted((d["p0"].y, d["p1"].y))
        for sup, ys in SUPPORTS_Y.items():
            if y0 - 0.03 <= ys <= y1 + 0.03: j(62, name, sup, "SW35", 2)
        if d["code"] in ("W01", "W02") and y0 - 0.03 <= 0 <= y1 + 0.03: j(65, name, "KA11_C", "SW35", 1)
    if d["code"] == "W13":
        west, front = d["p0"].x < 0, d["p1"].y < 0
        blk = {(True, True): "FA17_C01B", (True, False): "FA17_C02", (False, True): "FA17_C03", (False, False): "FA17_C01A"}[(west, front)]
        j(63, name, "K08_W" if west else "K08_E", "SW35", 3); j(63, name, blk, "SW35", 3)
j(55, "F04_E", "C06", "SW60", 2); j(55, "F04_E", "C01A", "SW60", 2)
for rail, legs in (("F09_B", ("C01A", "C04A", "C02")), ("F09_W", ("C02", "C05", "C01B")), ("F09_F", ("C01B", "C04B", "C03")),
                   ("FA15_F", ("C01B", "C04B", "C03")), ("FA15_W", ("C02", "C05", "C01B")), ("S05", ("C02", "C05", "C01B"))):
    for leg in legs: j(56, rail, leg, "SW60", 2)
j(164, "FA13_B", "C01A", "SW60", 2); j(164, "FA13_B", "C04A", "SW60", 2); j(165, "FA13_E", "C01A", "SW60", 2); j(165, "FA13_E", "C06", "SW60", 2)
j(59, "F13", "C06", "SW60", 2); j(59, "F13", "C01A", "SW60", 2)
for rail, legs in (("F11_B", ("C02", "C04A", "C01A")), ("F11_W", ("C02", "C05", "C01B")), ("F12", ("C01B", "C04B", "C03"))):
    for leg in legs: j(61, rail, leg, "SW60", 2)
for name, d in M.items():     # wall boards: 4 SW35 each (2 top, 2 bottom), steps 168-171, 99
    if d["code"] == "W07":
        tag = name.split("_")[1]
        top = {"B": "F09_B", "E": "F04_E", "F": "F09_F", "W": "F09_W"}[tag]; bot = {"B": "FA13_B", "E": "FA13_E", "F": "FA15_F", "W": "FA15_W"}[tag]
        j(168, name, top, "SW35", 2); j(168, name, bot, "SW35", 2)
    if d["code"] == "W14": j(99, name, "F07", "SW35", 2); j(99, name, "FA14", "SW35", 2)
for h_, leg, st in (("Handle_C04A", "C04A", 186), ("Handle_C02", "C02", 186), ("Handle_C08", "C08", 101)):
    j(st, f"{h_}_foot0", leg, "M6SW35", 1); j(st, f"{h_}_foot1", leg, "M6SW35", 1)
# roof (steps 110-139)
for rail, legs in (("F16_B", ("C09_BW", "C10_B", "C09_BE")), ("F16_F", ("C09_FW", "C10_F", "C09_FE")), ("F16_W", ("C09_FW", "C10_W", "C09_BW")),
                   ("F16_E", ("C09_FE", "C10_E", "C09_BE")), ("F14_B", ("C09_BW", "C10_B", "C09_BE")), ("F14_F", ("C09_FW", "C10_F", "C09_FE")),
                   ("F14_W", ("C09_FW", "C10_W", "C09_BW")), ("F15_E", ("C10_E", "C09_BE"))):
    for leg in legs: j(110, rail, leg, "M8SW50", 2)
for cb, legs in (("F13r", ("C10_E", "C09_BE")), ("F11r_B", ("C09_BW", "C10_B", "C09_BE")), ("F11r_W", ("C09_FW", "C10_W", "C09_BW")), ("F12r", ("C09_FW", "C10_F", "C09_FE"))):
    for leg in legs: j(120, cb, leg, "SW60", 2)
for r in ("KA12_BE", "KA12_BW", "KA12_FE", "KA12_FW"):
    j(125, r, "C09_" + r.split("_")[1], "SW60", 2); j(126, r, "KA09", "SW60", 1)
j(136, "F13r", "F13", "M833", 2); j(137, "F12r", "F12", "M833", 4); j(138, "F11r_B", "F11_B", "M833", 4); j(139, "F11r_W", "F11_W", "M833", 4)
# picnic table
for i in range(2):
    j(141, f"F03_{i}", f"CA10_{i}_F", "M8SW50", 2); j(141, f"F03_{i}", f"CA10_{i}_B", "M8SW50", 2)
    j(141, f"F01_{i}", f"CA10_{i}_F", "SW60", 2); j(141, f"F01_{i}", f"CA10_{i}_B", "SW60", 2)
for name in M:
    if name.startswith("Bench_"): j(143, name, "F03_0", "SW50", 2); j(143, name, "F03_1", "SW50", 2)
    if name.startswith("W05_"): j(145, name, "F01_0", "SW35", 2); j(145, name, "F01_1", "SW35", 2)
# small deck
j(79, "S02", "C07", "M896", 2); j(79, "S02", "C08", "M896", 2); j(81, "K02_O", "C07", "M8107", 1); j(81, "K02_O", "C08", "M8107", 1)
j(82, "F07", "C07", "M6SW55", 2); j(82, "F07", "C08", "M6SW55", 2)
j(86, "K01", "C03", "M8107", 2); j(86, "K01", "C07", "M8107", 2); j(87, "K03", "C08", "M8107", 2); j(87, "K03", "C06", "M8107", 2)
for tag, tl, sl in (("F", "C03", "C07"), ("B", "C06", "C08")):
    j(88, f"F05_low_{tag}", tl, "SW60", 2); j(88, f"F05_low_{tag}", sl, "SW60", 2)
    j(89, f"F05_top_{tag}", tl, "M6SW55", 2); j(89, f"F05_top_{tag}", sl, "M6SW55", 2)
j(90, "K02_T", "C03", "M8107", 1); j(90, "K02_T", "C06", "M8107", 1); j(91, "KA10", "K01", "SW75", 2); j(91, "KA10", "K03", "SW75", 2)
j(92, "FA17_C07", "C07", "SW50", 2); j(92, "FA17_C08", "C08", "SW50", 2)
for name, d in M.items():
    if name.endswith(tuple(f"_sd{i}" for i in range(12))):
        j(93, name, "K02_T", "SW35", 2); j(93, name, "KA10", "SW35", 1); j(93, name, "K02_O", "SW35", 2)
j(98, "FA14", "C07", "SW60", 2); j(98, "FA14", "C08", "SW60", 2); j(100, "KA14", "C06", "SW75", 2); j(100, "KA14", "C03", "SW75", 2)
j(172, "Slide", "W12A_sd0", "SW50", 2)
for k in range(4): j(104, f"F23_{k}", "K20", "SW50", 2); j(104, f"F23_{k}", "K21", "SW50", 2)
j(105, "W23", "K20", "SW50", 2); j(105, "W23", "K21", "SW50", 2); j(106, "K20", "K03", "M8SW60", 1); j(106, "K21", "K03", "M8SW60", 1)
j(190, "Stake_K20", "K20", "SW35", 1)
# swing frame
j(148, "DRB01_Ybracket", "C20_F", "M6SW35", 1); j(148, "DRB01_Ybracket", "C20_B", "M6SW35", 1); j(149, "DRB01_Ybracket", "C20_F", "M6SW35", 1); j(149, "DRB01_Ybracket", "C20_B", "M6SW35", 1); j(150, "F30", "C20_F", "SW60", 2); j(150, "F30", "C20_B", "SW60", 2)
j(151, "DRB02_Ibracket", "B03", "M6SW35", 2); j(152, "DRB02_Ibracket", "B03", "M6SW35", 2); j(154, "DRB01_Ybracket", "B03", "M6SW35", 2); j(157, "DRB02_Ibracket", "C05", "M6SW35", 2); j(158, "DRB02_Ibracket", "C05", "M6SW35", 2)
for i in range(4): j(159, f"Hanger_{i}_plate", "B03", "HANGER", 1)
j(191, "Stake_C20_F", "C20_F", "SW50", 2); j(191, "Stake_C20_B", "C20_B", "SW50", 2)
for st, e_, base, ft in NET_FIX: j(st, e_, base, ft, 1)

def seg_closest(p1, q1, p2, q2):
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f_ = d1.dot(d1), d2.dot(d2), d2.dot(r)
    c = d1.dot(r); b = d1.dot(d2); den = a*e - b*b
    s = min(max((b*f_ - c*e)/den, 0), 1) if den > 1e-12 else 0.0
    t = (b*s + f_)/e
    if t < 0: t = 0; s = min(max(-c/a, 0), 1)
    elif t > 1: t = 1; s = min(max((b - c)/a, 0), 1)
    return p1 + d1*s, p2 + d2*t

FX = coll("Fasteners")
fmesh = {}
def frustum(bm, r0, r1, z0, z1, seg=12):
    """Closed cone/cylinder section along local +Z."""
    ring0 = [bm.verts.new((r0*math.cos(2*math.pi*k/seg), r0*math.sin(2*math.pi*k/seg), z0)) for k in range(seg)]
    ring1 = [bm.verts.new((r1*math.cos(2*math.pi*k/seg), r1*math.sin(2*math.pi*k/seg), z1)) for k in range(seg)]
    bm.faces.new(list(reversed(ring0))); bm.faces.new(ring1)
    for k in range(seg): bm.faces.new((ring0[k], ring0[(k + 1) % seg], ring1[(k + 1) % seg], ring1[k]))

def fastener_mesh(ft):
    """Hardware page shapes. Local +Z points from the head into the wood; origin at the shank's midpoint.
    Bolts and machine screws (M..): wide flanged pan head sitting on the surface. Wood screws (SW..): countersunk flat
    head, flush with the surface. Swing hanger bolt: plain shank (the collar and bracket are modelled separately)."""
    if ft in fmesh: return fmesh[ft]
    d, L = FT[ft][0]/1000, FT[ft][1]/1000
    bm = bmesh.new()
    if ft.startswith("SW"):
        frustum(bm, d/2, d/2, -L/2 + d*0.9, L/2 - d*0.6, 8); frustum(bm, d/2, 0.0005, L/2 - d*0.6, L/2, 8)   # shank + point
        frustum(bm, d*0.95, d/2, -L/2, -L/2 + d*0.9, 12)                                                     # countersunk head
    elif ft == "HANGER":
        frustum(bm, d/2, d/2, -L/2, L/2, 10)
    else:
        frustum(bm, d/2, d/2, -L/2, L/2, 8)
        frustum(bm, d*1.35, d*1.1, -L/2 - 0.004, -L/2, 14)                                                   # flanged pan head
    me = bpy.data.meshes.new(f"fast_{ft}"); bm.to_mesh(me); bm.free()
    me.materials.append(STEEL); fmesh[ft] = me; return me

NUTS = {   # hardware page: name -> (flange r, flange t, barrel r, barrel length) m; barrel runs from the flange back toward the head
    "NM815": (0.012, 0.0015, 0.0055, 0.010),     # T-nut, pressed into the far face
    "BM818": (0.011, 0.003, 0.0065, 0.018),      # barrel nut
    "BM825": (0.011, 0.003, 0.0065, 0.025),      # barrel nut
    "Washer": (0.012, 0.002, 0.0, 0.0),
    "LockNut": (0.0085, 0.008, 0.0, 0.0),        # hex self-locking nut
}
nmesh = {}
def nut_mesh(kind):
    if kind in nmesh: return nmesh[kind]
    fr, ft_, br, bl = NUTS[kind]; bm = bmesh.new()
    if kind == "LockNut": frustum(bm, fr, fr, 0, ft_, 6)
    elif kind == "Washer": frustum(bm, fr, fr, 0, ft_, 14)
    else: frustum(bm, fr, fr, 0, ft_, 14); frustum(bm, br, br, ft_, ft_ + bl, 10)
    me = bpy.data.meshes.new(f"nut_{kind}"); bm.to_mesh(me); bm.free(); me.materials.append(STEEL); nmesh[kind] = me; return me

def nut_for(step, ft, a, b):
    """Which nut the manual pairs with each bolt (NM815 T-nuts in the frame, BM818 at steps 49-52, BM825 on the
    ring bolts, washer + self-locking nut on the swing hangers)."""
    if ft == "HANGER": return ["Washer", "LockNut"]
    if step in (49, 50, 51, 52): return ["BM818"]
    if ft == "M833" and a in ("F11r_B", "F11r_W", "F12r", "F13r"): return ["BM825"]
    if is_bolt(ft) and ft != "EYE": return ["NM815"]
    return []
def obb(d):
    """Member as an oriented box: centre, unit axes (u, v, a), half-extents."""
    c = (d["p0"] + d["p1"])/2
    return c, (d["u"], d["v"], d["a"]), (d["sec"][0]/2, d["sec"][1]/2, (d["p1"] - d["p0"]).length/2)

def interval(box, ax):
    c, axes, hx = box
    r = sum(h*abs(e.dot(ax)) for e, h in zip(axes, hx))
    m = c.dot(ax); return m - r, m + r

def is_bolt(ft): return ft in ("HANGER", "EYE") or (ft.startswith("M8") and not ft.startswith("M8SW"))

def local_obb(d, other):
    """Box of the part of d near `other`: long parts (legs, rails) are clipped around the closest point so a leaning
    2 m leg doesn't look 20 cm wide. Parallel parts (stacked boards) stay whole."""
    c, axes, hx = obb(d)
    if abs(d["a"].dot(other["a"])) > 0.95: return c, axes, hx
    pa, _ = seg_closest(d["p0"], d["p1"], other["p0"], other["p1"])
    half = min(hx[2], max(other["sec"])/2 + 0.06)
    s = (pa - d["p0"]).dot(d["a"]); Ld = (d["p1"] - d["p0"]).length
    s = min(max(s, half), Ld - half)
    return d["p0"] + d["a"]*s, axes, (hx[0], hx[1], half)

def explicit_fasteners(a, b, ft, n):
    """Joints whose fastener positions the manual pins down and box contact can't infer."""
    L = FT[ft][1]/1000; down = Vector((0, 0, -1))
    if a in RING_POLY and not b.startswith("F1"):   # connect board <-> leg top / roof post bottom (steps 59-61, 120)
        poly = RING_POLY[a]["poly"]; z0 = RING_POLY[a]["z0"]
        def inpoly(q):
            sg = None
            for i_ in range(len(poly)):
                p1_, p2_ = poly[i_], poly[(i_ + 1) % len(poly)]
                cr = (p2_.x - p1_.x)*(q[1] - p1_.y) - (p2_.y - p1_.y)*(q[0] - p1_.x)
                if abs(cr) < 1e-12: continue
                if sg is None: sg = cr > 0
                elif (cr > 0) != sg: return False
            return True
        d = M[b]; post_up = d["p0"].z > z0            # roof post standing on the board, or tower leg under it
        end = d["p0"] if post_up else d["p1"]
        cand = [(end.x + gx, end.y + gy) for gx in np.linspace(-0.023, 0.023, 9) for gy in np.linspace(-0.023, 0.023, 9)]
        cand = [q for q in cand if all(inpoly((q[0] + ex, q[1] + ey)) for ex, ey in ((0, 0), (0.012, 0), (-0.012, 0), (0, 0.012), (0, -0.012)))]
        if not cand: return None
        bd = M[a]["a"]; cq = np.array(cand); sv = cq @ np.array([bd.x, bd.y])
        picks = [cq[int(np.argmin(sv))], cq[int(np.argmax(sv))]] if n >= 2 else [cq[len(cq)//2]]
        ax = Vector((0, 0, 1)) if post_up else Vector((0, 0, -1))
        zh = z0 if post_up else z0 + CBT               # head on the board's outer face
        return [Vector((float(q[0]), float(q[1]), zh)) + ax*(L/2) for q in picks[:n]], ax
    if a in KNEE:                                  # step 42: bolt through the upper end into the rail, screw through the lower cut into the post
        kb = KNEE[a]; zt = zr + RH/2
        if ft == "M865":
            hd = knee_pt(kb, kb["DROP"] - 0.035, zt - 0.035, kb["T"]); tp = knee_pt(kb, kb["DROP"] - 0.035, zt - 0.035, 0.0)
            ax = (tp - hd).normalized(); return [hd + ax*L/2], ax
        hd = knee_pt(kb, 0.03, zt - kb["DROP"] + 0.03, kb["T"]/2); tp = knee_pt(kb, -0.02, zt - kb["DROP"] + 0.03, kb["T"]/2)
        ax = (tp - hd).normalized(); return [hd + ax*L/2], ax
    if a in RAFTERS and b.startswith("C09"):       # step 124: two holes centred diagonally over the post top, driven down
        e = RAFTERS[a]["e"]; pc_ = M[b]["p1"]
        pts = []
        for off in (-0.018, 0.018):
            q = Vector((pc_.x, pc_.y, 0)) + e*off; d = q.length
            ztop = raft_bot(d) + RD_V
            pts.append(Vector((q.x, q.y, ztop - L/2)))
        return pts, down
    if a in RAFTERS and b == "KA09":               # step 129: toe-screwed from the rafter's top end into the brace block
        e = RAFTERS[a]["e"]; dh = KB_HALF + 0.04
        hd = e*dh + Vector((0, 0, raft_bot(dh) + RD_V))
        tgt = Vector((0, 0, raft_bot(KB_HALF) + RD_V/2))
        ax = (tgt - hd).normalized(); return [hd + ax*L/2], ax
    if a in ("K20", "K21") and b == "K03":         # step 106: through the upright's top end into the floor rail
        x = M[a]["p0"].x; hd = Vector((x, K03_OUT + 0.035, zsr)); ax = Vector((0, -1, 0))
        return [hd + ax*L/2], ax
    if a == "DRB01_Ybracket" and b.startswith("C20"):   # mid-length of each socket: tower-side face (148), outward face (149)
        lt = LEG_TOPS[b]; nrm_ = XH if CUR_STEP == 148 else lt["u"]
        hd = lt["mid"] + nrm_*H; ax = -nrm_
        return [hd + ax*L/2], ax
    if a == "DRB02_Ibracket":                     # side plates: 2 screws per side, into the beam (151-152) or the post (157-158)
        sy = 1 if CUR_STEP in (151, 157) else -1; ax = Vector((0, -sy, 0))
        xc = BX1 - IB_SL/2 if b == "B03" else BX1 + LEG/2
        return [Vector((xc, sy*(0.035 + WT), BZ + dz)) + ax*L/2 for dz in (-0.035, 0.035)[:n]], ax
    if a == "DRB01_Ybracket" and b == "B03":      # step 154: two screws down through the sleeve's top holes into the beam
        ax = Vector((0, 0, -1))
        return [Vector((XS0 + xo, 0, BZ + SLZ/2)) + ax*L/2 for xo in (0.025, SLL - 0.025)[:n]], ax   # one hole near each end of the cup top (parts drawing)
    if ft == "M833" and a in ("F11r_B", "F11r_W", "F12r", "F13r"):   # ring-to-ring bolts between the posts, heads on the roof ring (steps 136-139)
        A = M[a]; zt = A["p0"].z + CBT/2; om = (RO + RI)/2
        side = {"F11r_B": "B", "F12r": "F", "F11r_W": "W", "F13r": "E"}[a]
        ts = {"B": (-RING_C/2, RING_C/2), "F": (-RING_C/2, RING_C/2), "W": (-RING_C/2, RING_C/2), "E": (RING_C/2,)}[side]
        pts = []
        for t in ts:
            for w in ((-0.025, 0.025) if n > len(ts) else (0.0,)):
                o = om + w
                x, y = {"B": (t, o), "F": (t, -o), "W": (-o, t), "E": (o, t)}[side]
                pts.append(Vector((x, y, zt - L/2)))
        return pts[:n], down
    return None

def place_fasteners_patch(A, B, L, n, bolt=False):
    """Find the face where A meets B (the axis of least box overlap), seat the heads flush on A's outer face pointing
    into B, and spread n fasteners over the patch where the two parts overlap. Returns (centres, axis, gap_m)."""
    ba, bb = local_obb(A, B), local_obb(B, A)
    cands = []
    for e in list(ba[1]) + list(bb[1]):
        if all(abs(e.dot(f_)) < 0.999 for f_ in cands): cands.append(e.normalized())
    best = None
    for e in cands:
        a0, a1 = interval(ba, e); b0, b1 = interval(bb, e)
        ov = min(a1, b1) - max(a0, b0)
        if best is None or ov < best[0]: best = (ov, e)
    ov, nrm = best
    if (bb[0] - ba[0]).dot(nrm) < 0: nrm = -nrm
    a0, a1 = interval(ba, nrm); b0, b1 = interval(bb, nrm)
    s_c = (a1 + b0)/2                                     # contact plane
    s_h = a0 if bolt else max(a0, s_c - 0.6*L)            # bolts: head on A's outer face; screws: counterbored if A is deep
    t1 = None
    for e in (A["a"], A["u"], A["v"]):
        t = e - nrm*e.dot(nrm)
        if t.length > 0.3: t1 = t.normalized(); break
    t2 = nrm.cross(t1).normalized()
    patch = []
    for t in (t1, t2):
        p0_, p1_ = interval(ba, t); q0, q1 = interval(bb, t)
        lo, hi_ = max(p0_, q0), min(p1_, q1)
        if hi_ < lo: lo = hi_ = (lo + hi_)/2
        patch.append(((lo + hi_)/2, hi_ - lo))
    (c1, e1), (c2, e2) = patch
    long_, short_ = (0, 1) if e1 >= e2 else (1, 0)
    cs, es = [c1, c2], [e1, e2]; ts = [t1, t2]
    pts = []
    rows = 2 if (n >= 4 and es[short_] > 0.06) else 1
    per = math.ceil(n/rows)
    for r in range(rows):
        cnt = per if r < rows - 1 else n - per*(rows - 1)
        inset_s = min(0.02, es[short_]*0.25)
        off_s = 0.0 if rows == 1 else (-1 if r == 0 else 1)*(es[short_]/2 - inset_s)
        inset = min(0.025, es[long_]*0.2); span = max(0.0, es[long_] - 2*inset)
        for k in range(cnt):
            off_l = 0.0 if cnt == 1 else (k/(cnt - 1) - 0.5)*span
            q = [0.0, 0.0]; q[long_] = cs[long_] + off_l; q[short_] = cs[short_] + off_s
            pts.append(nrm*(s_h + L/2) + ts[0]*q[0] + ts[1]*q[1])
    return pts, nrm, max(0.0, -ov)

import numpy as np
def inside_np(box, P, nrm, inset):
    """Points P (N,3) inside box, shrunk by `inset` on the box axes that lie in the contact plane."""
    c, axes, hx = box
    Q = P - np.array(c)
    ok = np.ones(len(P), bool)
    for e, h in zip(axes, hx):
        w = 1.0 - abs(e.dot(nrm))
        ok &= np.abs(Q @ np.array(e)) <= h - inset*w + 1e-4
    return ok

def place_fasteners(A, B, L, n, bolt=False):
    """Find the face where A meets B (axis of least overlap between the local boxes), then sample the contact plane for
    spots where the whole fastener fits: head in A, shank through the joint, tip in B, with an edge margin. Spread n
    fasteners along the long direction of that region. Returns (centres, axis, gap_m)."""
    ba, bb = local_obb(A, B), local_obb(B, A)
    cands = []
    for e in list(ba[1]) + list(bb[1]):
        if all(abs(e.dot(f_)) < 0.999 for f_ in cands): cands.append(e.normalized())
    best = None
    for e in cands:
        a0, a1 = interval(ba, e); b0, b1 = interval(bb, e)
        ov = min(a1, b1) - max(a0, b0)
        if best is None or ov < best[0]: best = (ov, e)
    ov, nrm = best
    if (bb[0] - ba[0]).dot(nrm) < 0: nrm = -nrm
    a0, a1 = interval(ba, nrm); b0, b1 = interval(bb, nrm)
    s_c = (a1 + b0)/2
    s_h = a0 if bolt else max(a0, s_c - 0.6*L)
    t1 = None
    for e in (A["a"], A["u"], A["v"], B["a"]):
        t = e - nrm*e.dot(nrm)
        if t.length > 0.3: t1 = t.normalized(); break
    t2 = nrm.cross(t1).normalized()
    mid = (ba[0] + bb[0])/2; mid = mid + nrm*(s_c - mid.dot(nrm))
    R = min(0.35, max(max(ba[2]), max(bb[2])))
    g = np.linspace(-R, R, 81)
    G1, G2 = np.meshgrid(g, g); G1 = G1.ravel(); G2 = G2.ravel()
    P = np.array(mid)[None, :] + G1[:, None]*np.array(t1) + G2[:, None]*np.array(t2)
    nv = np.array(nrm)
    tip_allow = 0.012 if bolt else 0.0
    for inset in (0.012, 0.008, 0.005, 0.002, 0.0):
        d_in = 0.001
        ok = inside_np(ba, P + nv*(s_h - s_c + d_in), nrm, inset)
        ok &= inside_np(ba, P - nv*d_in, nrm, inset)
        ok &= inside_np(bb, P + nv*d_in, nrm, inset)
        ok &= inside_np(bb, P + nv*(s_h + L - s_c - d_in - tip_allow), nrm, inset)
        if ok.sum() >= 1: break
    if ok.sum() == 0:
        return place_fasteners_patch(A, B, L, n, bolt)
    U = np.stack([G1[ok], G2[ok]], 1)
    cen = U.mean(0)
    if len(U) > 2:
        w_, v_ = np.linalg.eigh(np.cov((U - cen).T)); pa_ = v_[:, -1]; pb_ = v_[:, 0]
    else:
        pa_, pb_ = np.array([1.0, 0]), np.array([0, 1.0])
    sa = (U - cen) @ pa_; sb = (U - cen) @ pb_
    width = sb.max() - sb.min()
    rows = 2 if (n >= 4 and width > 0.05) else 1
    per = math.ceil(n/rows); chosen = []
    for r_ in range(rows):
        cnt = per if r_ < rows - 1 else n - per*(rows - 1)
        off = 0.0 if rows == 1 else (-1 if r_ == 0 else 1)*width/4
        for k_ in range(cnt):
            ta = 0.0 if cnt == 1 else sa.min() + (sa.max() - sa.min())*(k_/(cnt - 1))
            tgt = cen + pa_*ta + pb_*off
            dist = ((U - tgt)**2).sum(1)
            for idx in np.argsort(dist):
                if idx not in chosen: chosen.append(int(idx)); break
    pts = []
    for idx in chosen:
        q = mid + t1*float(U[idx, 0]) + t2*float(U[idx, 1])
        pts.append(q + nrm*(s_h + L/2 - s_c))
    return pts, nrm, max(0.0, -ov)



records = []; missing = []; not_touching = []; nut_records = []
for (step, a, b, ft, n) in J:
    CUR_STEP = step
    if a not in M or b not in M: missing.append((step, a, b)); continue
    if n == 0: continue
    A, B = M[a], M[b]
    ex = explicit_fasteners(a, b, ft, n)
    if ex: centres, nrm, gap_m = ex[0], ex[1], 0.0
    else: centres, nrm, gap_m = place_fasteners(A, B, FT[ft][1]/1000, n, bolt=is_bolt(ft))
    if gap_m > 0.004: not_touching.append((step, a, b, round(gap_m, 3)))
    for k, c in enumerate(centres):
        ob = bpy.data.objects.new(f"{ft}_s{step}_{a}_{k}", fastener_mesh(ft)); FX.objects.link(ob)
        ob.location = c; ob.rotation_euler = nrm.to_track_quat('Z', 'Y').to_euler()
        records.append(dict(step=step, attached=a, base=b, type=ft, pos=list(c), axis=list(nrm)))
        stack = 0.0
        for nk in nut_for(step, ft, a, b):          # nut on the base part's far face, facing back toward the head
            bx = local_obb(B, A); lo, hi2 = interval(bx, nrm)
            far = hi2 if ft != "HANGER" else c.dot(nrm) + FT[ft][1]/2000 - 0.012
            pos = c + nrm*(far - c.dot(nrm) + stack)
            no = bpy.data.objects.new(f"{nk}_s{step}_{a}_{k}", nut_mesh(nk)); FX.objects.link(no)
            no.location = pos; no.rotation_euler = (-nrm).to_track_quat('Z', 'Y').to_euler() if nk not in ("Washer", "LockNut") else nrm.to_track_quat('Z', 'Y').to_euler()
            if nk in ("Washer", "LockNut"): stack += NUTS[nk][1]
            nut_records.append(dict(step=step, type=nk, bolt=ft, pos=list(pos)))
def inside(d, p, tol):
    c, axes, hx = obb(d); q = p - c
    return all(abs(q.dot(e)) <= h + tol for e, h in zip(axes, hx))
bad_fast = []
for r in records:
    A_, B_ = M[r["attached"]], M[r["base"]]
    if "Slide" in (A_["code"], B_["code"]) or r["attached"] in KNEE or r["attached"] in ("DRB01_Ybracket", "DRB02_Ibracket"): continue   # shapes a box cannot describe
    c = Vector(r["pos"]); ax = Vector(r["axis"]); L = FT[r["type"]][1]/1000
    bolt = is_bolt(r["type"])
    head, tip = c - ax*L/2, c + ax*L/2
    if not inside(A_, head, 0.004) or not inside(B_, tip, (0.02 if r["type"] == "HANGER" else 0.012) if bolt else 0.004):
        def loc(d, p_):
            c_, axes, hx = obb(d); q = p_ - c_
            return [round(abs(q.dot(e)) - h, 3) for e, h in zip(axes, hx)]
        bad_fast.append((r["step"], r["attached"], r["base"], r["type"], "head-excess", loc(A_, head), "tip-excess", loc(B_, tip)))
def in_ring(name, q):
    poly = RING_POLY[name]["poly"]; sg = None
    for i_ in range(len(poly)):
        p1_, p2_ = poly[i_], poly[(i_ + 1) % len(poly)]
        cr = (p2_.x - p1_.x)*(q.y - p1_.y) - (p2_.y - p1_.y)*(q.x - p1_.x)
        if abs(cr) < 1e-12: continue
        if sg is None: sg = cr > 0
        elif (cr > 0) != sg: return False
    return True
for r in records:                                  # mitred connect boards: the fastener must pass through the board's real outline
    for nm in (r["attached"], r["base"]):
        if nm in RING_POLY and not in_ring(nm, Vector(r["pos"])): bad_fast.append((r["step"], r["attached"], r["base"], r["type"], "outside mitred outline of", nm))
print(f"fasteners whose head is not in the attached part or tip not in the base part: {len(bad_fast)}")
for bf in bad_fast[:40]: print("   ", bf)
from collections import Counter as _C
nc = _C(r["type"] for r in nut_records)
print("nuts/washers placed:", dict(nc), " manual lists: NM815 80, BM818 21, BM825 14, Washer 8, Self-locking nut 4")
by_type = {}
for r in records: by_type[r["type"]] = by_type.get(r["type"], 0) + 1

# ================= ground + report =================
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0)); g = bpy.context.object; g.name = "Ground"
g.data.materials.append(mat("ground", (0.32, 0.27, 0.18, 1)))
wood = sum(d["mass"] for d in M.values() if d["kind"] == "wood")
other = sum(d["mass"] for d in M.values() if d["kind"] != "wood") + 3.0 + 5.0 + 2.0   # + tarp, hammock, climbing net
fmass = sum(FT[r["type"]][3] for r in records)/1000
json.dump(dict(
    frame="x away from swings, y+ back (side A), z up; metres",
    members={k: dict(code=d["code"], kind=d["kind"], mass_kg=round(d["mass"], 3), p0=list(d["p0"]), p1=list(d["p1"]), section_m=list(d["sec"])) for k, d in M.items()},
    fastener_types={k: dict(d_mm=v[0], L_mm=v[1], shear_capacity_N_estimate=v[2], mass_g=v[3]) for k, v in FT.items()},
    joints=[dict(step=s, attached=a, base=b, type=t, count=n) for (s, a, b, t, n) in J],
    fasteners=records, nuts=nut_records), open(os.path.join(HERE, "bear_basin.json"), "w"), indent=1)
print(f"members={len(M)} fasteners={len(records)} joints={len(J)} missing_refs={missing}")
print(f"joints whose parts do not touch (gap m): {len(not_touching)}")
for nt in not_touching: print("   ", nt)
print("fasteners by type:", dict(sorted(by_type.items())))
print(f"mass: wood {wood:.1f} kg @ {RHO:.0f} kg/m3 + other {other:.1f} kg + fasteners {fmass:.1f} kg = {wood+other+fmass:.1f} kg (listing 574 lb = 260 kg)")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "bear_basin.blend"))
