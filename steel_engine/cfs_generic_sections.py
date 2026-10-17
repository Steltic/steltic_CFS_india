"""cfs_generic_sections.py -- computed thin lipped C and lipped Z sections (2026-10 first wave, owner decision).

IS 811:1987 lists deep lipped channels (150 mm and deeper) only in 3.15 / 4 / 5 mm.  Indian LGSF and PEB secondary
framing is roll-formed from pre-galvanised high-tensile coil, 1.0-3.15 mm thick.  IS 801:1975 is section-agnostic
(5.2: "properties of sections ... shall be determined in accordance with conventional methods of structural design"),
so this module computes the properties of a family of generic thin sections from their geometry.  The IS 811
catalogue (is811_sections) stays available unchanged.

Family (labels make the thickness and the grade obvious):
    C<h>X<b>X<c>X<t>-G350   lipped channel   e.g. C200X65X20X1.6-G350
    Z<h>X<b>X<c>X<t>-G350   lipped zed, equal flanges  e.g. Z250X70X20X2.0-G350
  h = overall depth, b = overall flange width, c = overall lip depth, t = BASE-METAL thickness (IS 801 3.6: thickness
  exclusive of coatings), all mm.  Depths 100 / 150 / 200 / 250 / 300 mm with the flange and lip of DEPTH_TABLE;
  thicknesses 1.0, 1.2, 1.6, 2.0, 2.5, 3.15 mm.

Material (declared with every section): IS 277 grade 350 pre-galvanised coil, Z275 zinc coating, Fy = 350 MPa.
  IS 801 Table 2 (corpus transcription, IS_801_1975.md p.11) has the row "36 kgf/mm2 -> F = 2 160 kgf/cm2";
  36 kgf/mm2 = 36 x 9.80665 = 353.0 MPa, so Fy = 350 MPa sits inside that row (F = 0.60 x 350 = 210 MPa <= 211.8 MPa).
  IS 801 2.1 names IS 1079 sheet; 2.2 permits other steels "provided such steel conforms to the chemical and mechanical
  requirements of IS 1079 ... and its weldability is guaranteed" -- the mill certificate of the IS 277 coil must show
  that (design engineer's item, VERIFY).  The zinc coating is not counted in t or in the section properties (3.6).

Geometry (assumption, stated in every record): inside corner radius Ri = 1.5 t (the IS 811 7.1.1 rule, so the generic
family is computed on the same basis as the catalogue); the lipped zed has equal flanges (the IS 811 Table 10 shape;
nesting laps of real zeds use flanges a few mm apart, which changes the properties by well under 1 %).

Properties: thin-walled centreline model with the corners as arcs (8 straight chords per corner): A, centroid, Ix, Iy,
Ixy, principal Iu / Iv / tan alpha (zed), Zx = Ix / (h/2), Zy, radii, J = sum(l t^3 / 3), shear centre and warping
constant Cw from the sectorial coordinate.  The same routine reproduces the printed IS 811 values of CLR / LZ rows
(tests/test_fix_FW1_generic_sections.py) -- that is the "conventional method" check.
Units: mm, mm2, mm4, mm3, mm6, kg/m (base metal, 7850 kg/m3: M = 0.785 A with A in cm2, as IS 811).
"""
from __future__ import annotations

import math
import re

GRADES = {350: {"Fy_MPa": 350.0, "grade": "IS 277 grade 350", "coating": "Z275",
                "table2_row": "IS 801:1975 Table 2 row 36 kgf/mm2 (= 353.0 MPa) -> F = 2 160 kgf/cm2; Fy 350 MPa <= 353.0 MPa"}}
DEPTH_TABLE = {100: (50.0, 15.0), 150: (60.0, 20.0), 200: (65.0, 20.0), 250: (70.0, 20.0), 300: (80.0, 25.0)}
THICKNESSES = (1.0, 1.2, 1.6, 2.0, 2.5, 3.15)
FAMILIES = {"thin_C_G350": ("C", 350), "thin_Z_G350": ("Z", 350)}
MATERIAL_TEXT = ("IS 277 grade 350 pre-galvanised steel coil (Fy 350 MPa), Z275 zinc coating; t is the base-metal "
                 "thickness exclusive of the coating (IS 801 3.6); IS 801 Table 2 36 kgf/mm2 row (353 MPa) covers Fy 350 MPa; "
                 "IS 801 2.2: the coil must meet the IS 1079 chemical and mechanical requirements (mill certificate, VERIFY)")
RHO = 7850e-9          # kg/mm3
LABEL_RE = re.compile(r"^([CZ])(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)-G(\d+)$")
SRC = "cfs_generic_sections (computed from geometry, IS 801 5.2 conventional methods)"


def looks_generic(name) -> bool:
    return bool(LABEL_RE.match(str(name or "").strip().upper().replace(" ", "")))


def _fmt(v):
    v = float(v)
    if abs(v - round(v)) < 1e-9 and v >= 10:
        return "%d" % round(v)
    s = ("%.2f" % v).rstrip("0")
    return s + "0" if s.endswith(".") else s


def make_label(kind, h, b, c, t, grade=350):
    return "%s%sX%sX%sX%s-G%d" % (kind.upper(), _fmt(h), _fmt(b), _fmt(c), _fmt(t), int(grade))


def parse_label(name):
    m = LABEL_RE.match(str(name or "").strip().upper().replace(" ", ""))
    if not m:
        raise KeyError("not a generic thin-section label: %r (form C200X65X20X1.6-G350 / Z250X70X20X2.0-G350)" % (name,))
    kind, h, b, c, t, g = m.groups()
    return kind, float(h), float(b), float(c), float(t), int(g)


# ---------------------------------------------------------------------------------------------------------------
# centreline geometry
# ---------------------------------------------------------------------------------------------------------------
def _arc(cx, cy, r, a0, a1, n=8):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def centreline(kind, h, b, c, t, Ri=None, n_arc=8):
    """Centreline polyline (x horizontal, y vertical; web along y) of a lipped C or lipped Z with corner arcs of
    centreline radius r = Ri + t/2.  C: flanges and lips point to +x.  Z: top flange to +x, bottom flange to -x."""
    Ri = 1.5 * t if Ri is None else Ri
    r = Ri + t / 2.0
    xw = t / 2.0                                    # web centreline (outer face of web at x = 0)
    yt, yb = h - t / 2.0, t / 2.0                   # flange centrelines
    xt = b - t / 2.0                                # flange tip / lip centreline (C and Z top flange)
    pts = []
    # top lip tip -> top lip / flange corner
    pts.append((xt, h - c))
    pts += _arc(xt - r, yt - r, r, 0.0, math.pi / 2.0, n_arc)                 # lip -> flange corner
    pts += _arc(xw + r, yt - r, r, math.pi / 2.0, math.pi, n_arc)             # flange -> web corner
    if kind == "C":
        pts += _arc(xw + r, yb + r, r, math.pi, 1.5 * math.pi, n_arc)         # web -> bottom flange
        pts += _arc(xt - r, yb + r, r, 1.5 * math.pi, 2.0 * math.pi, n_arc)   # bottom flange -> lip
        pts.append((xt, c))
    else:
        # zed: bottom flange to -x from the web; the web centreline is at x = xw for both flanges
        xb = -(b - t / 2.0) + t                     # bottom flange tip centreline (flange width b measured from the
        #                                             web's far face, x = t, as the top flange is from x = 0)
        pts += [(x, y) for (x, y) in _arc(xw - r, yb + r, r, 0.0, -0.5 * math.pi, n_arc)]   # web -> bottom flange
        pts += _arc(xb + r, yb + r, r, 1.5 * math.pi, math.pi, n_arc)          # bottom flange -> lip
        pts.append((xb, c))
    # drop duplicate consecutive points
    out = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-9:
            out.append(p)
    return out


def thin_wall_props(pts, t):
    """Open thin-walled section properties of a centreline polyline of uniform thickness t (mm)."""
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    A = 0.0; Sx = 0.0; Sy = 0.0
    for (x1, y1), (x2, y2) in segs:
        L = math.hypot(x2 - x1, y2 - y1)
        A += L * t; Sx += L * t * (y1 + y2) / 2.0; Sy += L * t * (x1 + x2) / 2.0
    xc, yc = Sy / A, Sx / A
    Ix = Iy = Ixy = 0.0
    for (x1, y1), (x2, y2) in segs:
        L = math.hypot(x2 - x1, y2 - y1)
        a1, b1, a2, b2 = x1 - xc, y1 - yc, x2 - xc, y2 - yc
        Ix += L * t * (b1 * b1 + b1 * b2 + b2 * b2) / 3.0
        Iy += L * t * (a1 * a1 + a1 * a2 + a2 * a2) / 3.0
        Ixy += L * t * (2 * a1 * b1 + a1 * b2 + a2 * b1 + 2 * a2 * b2) / 6.0
    J = sum(math.hypot(x2 - x1, y2 - y1) * t ** 3 / 3.0 for (x1, y1), (x2, y2) in segs)

    def sectorial(px, py):
        w = [0.0]
        for (x1, y1), (x2, y2) in segs:
            w.append(w[-1] + (x1 - px) * (y2 - py) - (x2 - px) * (y1 - py))
        return w
    # shear centre from the sectorial coordinate about the centroid (pole P = centroid)
    w = sectorial(xc, yc)
    Iwx = Iwy = 0.0                                  # integral of w * x dA and w * y dA (centroidal x, y)
    for i, ((x1, y1), (x2, y2)) in enumerate(segs):
        L = math.hypot(x2 - x1, y2 - y1)
        a1, b1, a2, b2 = x1 - xc, y1 - yc, x2 - xc, y2 - yc
        w1, w2 = w[i], w[i + 1]
        Iwx += L * t * (2 * a1 * w1 + a1 * w2 + a2 * w1 + 2 * a2 * w2) / 6.0
        Iwy += L * t * (2 * b1 * w1 + b1 * w2 + b2 * w1 + 2 * b2 * w2) / 6.0
    # w_S = w_P - dx (y - y0) + dy (x - x0): orthogonality to x and y ->
    #   -Ixy dx + Iy dy = -Iwx ;  -Ix dx + Ixy dy = -Iwy
    det = (-Ixy) * Ixy - Iy * (-Ix)
    dx = ((-Iwx) * Ixy - Iy * (-Iwy)) / det
    dy = ((-Ixy) * (-Iwy) - (-Iwx) * (-Ix)) / det
    xs, ys = xc + dx, yc + dy
    ws = sectorial(xs, ys)
    wbar = sum(math.hypot(x2 - x1, y2 - y1) * t * (ws[i] + ws[i + 1]) / 2.0 for i, ((x1, y1), (x2, y2)) in enumerate(segs)) / A
    Cw = 0.0
    for i, ((x1, y1), (x2, y2)) in enumerate(segs):
        L = math.hypot(x2 - x1, y2 - y1)
        u1, u2 = ws[i] - wbar, ws[i + 1] - wbar
        Cw += L * t * (u1 * u1 + u1 * u2 + u2 * u2) / 3.0
    return {"A": A, "xc": xc, "yc": yc, "Ix": Ix, "Iy": Iy, "Ixy": Ixy, "J": J, "xs": xs, "ys": ys, "Cw": Cw}


def _geometry_limits(kind, h, b, c, t, Ri, Fy_MPa):
    """IS 801 5.2.3 / 5.2.4 / 5.2.2.1 geometric limits (corpus IS_801_1975.md p.8-9)."""
    k = Ri + t
    w_fl = b - 2.0 * k
    w_web = h - 2.0 * k
    w_lip = c - k
    Fy_kgf = Fy_MPa / 0.0980665
    arg = (w_fl / t) ** 2 - 281200.0 / Fy_kgf
    dmin = max(2.8 * t * (arg ** (1.0 / 6.0) if arg > 0 else 0.0), 4.8 * t)
    rows = [
        {"check": "5.2.3(a) flange w/t (simple lip) <= 60", "value": w_fl / t, "limit": 60.0},
        {"check": "5.2.3(c) lip w/t (unstiffened) <= 60", "value": w_lip / t, "limit": 60.0},
        {"check": "5.2.4(a) web h/t (unstiffened web) <= 150", "value": w_web / t, "limit": 150.0},
        {"check": "5.2.2.1 lip depth >= dmin", "value": dmin, "limit": c, "note": "dmin = 2.8 t (6th root)((w/t)^2 - 281 200/Fy) >= 4.8 t"},
    ]
    for r in rows:
        r["dc"] = r["value"] / r["limit"] if r["limit"] else None
        r["ok"] = r["value"] <= r["limit"] + 1e-9
        r["clause"] = "IS 801 " + r["check"].split(" ")[0]
    return rows


def props(name) -> dict:
    """Section properties of a generic thin label in the is811_sections.props format (mm units).  KeyError when the
    label is malformed or the grade is not one this family carries."""
    kind, h, b, c, t, g = parse_label(name)
    if g not in GRADES:
        raise KeyError("generic section %r: grade G%d not in the family (G350 only: Fy 350 MPa inside the IS 801 Table 2 "
                       "36 kgf/mm2 row)" % (name, g))
    gr = GRADES[g]
    Ri = 1.5 * t
    pts = centreline(kind, h, b, c, t, Ri)
    p = thin_wall_props(pts, t)
    A = p["A"]
    lab = make_label(kind, h, b, c, t, g)
    Ix, Iy, Ixy = p["Ix"], p["Iy"], p["Ixy"]
    out = {"label": lab, "designation": "%s %s x %s x %s x %s (G%d)" % ("lipped channel" if kind == "C" else "lipped zed",
                                                                        _fmt(h), _fmt(b), _fmt(c), _fmt(t), g),
           "type": "CLR" if kind == "C" else "LZ", "family": "thin_%s_G%d" % (kind, g), "generic": True,
           "type_name": ("lipped channel" if kind == "C" else "lipped zed, equal flanges") + " (computed thin section, not an IS 811 table row)",
           "table": None, "table_name": None, "pdf_page": None,
           "h": h, "b": b, "c": c, "t": t, "Ri": Ri, "A": A, "mass_kg_m": A * RHO * 1000.0,
           "Fy": gr["Fy_MPa"], "_Fy_found": True, "grade": gr["grade"], "coating": gr["coating"], "grade_label": "G%d" % g,
           "material": MATERIAL_TEXT, "grade_cite": gr["table2_row"] + "; " + MATERIAL_TEXT,
           "units": "N-mm (mm, mm2, mm4, mm3, mm6, kg/m)", "source": SRC,
           "geometry_basis": "centreline thin-wall model, inside corner radius Ri = 1.5 t (IS 811 7.1.1 rule), "
                             + ("equal flanges" if kind == "Z" else "lips turned inwards"),
           "lipped": True, "hat": False}
    if kind == "C":
        # channel: x-x (bending) axis horizontal, y-y parallel to the web; Cy = centroid from the back of the web
        Cy = p["xc"]                                   # outer face of the web at x = 0
        x0 = abs(p["xs"] - p["xc"])
        out.update(Ix=Ix, Iy=Iy, Iu=None, Iv=None, Ixy=0.0, tan_alpha=None, Cx=None, Cy=Cy, x0=x0,
                   Zx=Ix / (h / 2.0), Zy=Iy / max(b - Cy, 1e-9), Zu=None, Zv=None,
                   singly_symmetric=True, point_symmetric=False, nonsymmetric=False,
                   m_shear_centre_from_web_mid_mm=abs(p["xs"] - t / 2.0))
    else:
        Iavg = (Ix + Iy) / 2.0
        R = math.sqrt(((Ix - Iy) / 2.0) ** 2 + Ixy ** 2)
        Iu, Iv = Iavg + R, Iavg - R
        alpha = 0.5 * math.atan2(2.0 * abs(Ixy), Ix - Iy)
        out.update(Ix=Ix, Iy=Iy, Iu=Iu, Iv=Iv, Ixy=abs(Ixy), tan_alpha=math.tan(alpha), Cx=None, Cy=None, x0=None,
                   Zx=Ix / (h / 2.0), Zy=Iy / max(b - t / 2.0, 1e-9), Zu=None, Zv=None,
                   singly_symmetric=False, point_symmetric=True, nonsymmetric=False)
    out["J"] = p["J"]
    out["Cw"] = p["Cw"]
    out["rx"] = math.sqrt(Ix / A)
    out["ry"] = math.sqrt(Iy / A)
    out["ru"] = math.sqrt(out["Iu"] / A) if out.get("Iu") else None
    out["rv"] = math.sqrt(out["Iv"] / A) if out.get("Iv") else None
    out["r_min"] = min(r for r in (out["rx"], out["ry"], out["ru"], out["rv"]) if r)
    for k in ("_x0_found", "_J_found", "_Cw_found"):
        out[k] = True if (k != "_x0_found" or out.get("x0") is not None) else False
    k = Ri + t
    out["flats"] = {"web": max(h - 2 * k, 0.0), "flange": max(b - 2 * k, 0.0), "lip": max(c - k, 0.0)}
    out["flats_basis"] = "Ri = 1.5 t; flat = overall - bends (IS 801 3.4)"
    out["is801_geometry"] = _geometry_limits(kind, h, b, c, t, Ri, gr["Fy_MPa"])
    out["is801_geometry_ok"] = all(r["ok"] for r in out["is801_geometry"][:3])     # 5.2.3 / 5.2.4 (lip 5.2.2.1 handled
    return out                                                                      # by the member checks)


def family_labels(family: str) -> list:
    """Every label of a family (thin_C_G350 / thin_Z_G350), depth x thickness grid."""
    if family not in FAMILIES:
        raise KeyError("unknown generic family %r (known: %s)" % (family, ", ".join(FAMILIES)))
    kind, g = FAMILIES[family]
    return [make_label(kind, h, bc[0], bc[1], t, g) for h, bc in sorted(DEPTH_TABLE.items()) for t in THICKNESSES]


def catalogue(family: str) -> list:
    """[(label, mass_kg_m, h, t, is801_geometry_ok)] sorted by mass."""
    rows = []
    for lab in family_labels(family):
        p = props(lab)
        rows.append((lab, p["mass_kg_m"], p["h"], p["t"], p["is801_geometry_ok"]))
    return sorted(rows, key=lambda r: (r[1], r[2]))
