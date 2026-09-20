#!/usr/bin/env python3
"""validate_is811.py -- geometric validator for the IS 811 catalogue rows (WP3.3 / CFSREPO-02).

Rules (thin-wall mid-line geometry from the printed h, b, c, t, Ri; corners rounded at r = Ri + t/2):
  A      |A / A_geom - 1|            <= 4 %
  M      |M / (0.785 A) - 1|         <= 2 %   (mass = 7850 kg/m3 x A;  0.785 kg/m per cm2)
  Ix     |Ix / Ix_thinwall - 1|      <= 8 %   (mid-line polyline with rounded corners)
  Iu+Iv  |(Iu + Iv) / (Ix + Iy) - 1| <= 2 %   (angles / zeds, principal-axis invariance)
Rows failing any rule are quarantined (found:false) by build_is811_shapes.py.

Usage:  python3 steel_engine/tools/validate_is811.py [steel_engine/is811_shapes.csv]
"""
from __future__ import annotations
import csv
import math
import sys

TOL = {"A": 0.04, "M": 0.02, "Ix": 0.08, "Iuv": 0.02}


def _path(rec):
    """Ordered mid-line vertices of the printed section (one open path, straight corners) and the corner count.
    Coordinates: x to the right, y up; web(s) vertical."""
    p = rec["Type"]
    h, b, t = rec["h_mm"], rec["b_mm"], rec["t_mm"]
    c = rec.get("c_mm") or 0.0
    hm, bm = h - t, b - t            # mid-line web height / flange width
    if p in ("EA", "UA"):
        return [(0, h - t / 2.0), (0, 0), (b - t / 2.0, 0)]
    if p in ("CWS", "CWR"):
        return [(b - t / 2.0, 0), (0, 0), (0, hm), (b - t / 2.0, hm)]
    if p in ("CLS", "CLR"):
        cm = c - t / 2.0
        return [(bm, cm), (bm, 0), (0, 0), (0, hm), (bm, hm), (bm, hm - cm)]
    if p in ("HS", "HRH", "HRB"):
        cm = c - t / 2.0
        return [(-cm, 0), (0, 0), (0, hm), (bm, hm), (bm, 0), (bm + cm, 0)]
    if p == "LZ":
        cm = c - t / 2.0
        return [(-bm, cm), (-bm, 0), (0, 0), (0, hm), (bm, hm), (bm, hm - cm)]
    return None


def _round_corners(path, r, n=8):
    """Replace every interior vertex by a circular arc of radius r (mid-line bend radius) tangent to both legs."""
    if r <= 0 or len(path) < 3:
        return list(path)
    out = [path[0]]
    for i in range(1, len(path) - 1):
        (x0, y0), (x1, y1), (x2, y2) = path[i - 1], path[i], path[i + 1]
        d1 = math.hypot(x1 - x0, y1 - y0); d2 = math.hypot(x2 - x1, y2 - y1)
        u1 = ((x0 - x1) / d1, (y0 - y1) / d1); u2 = ((x2 - x1) / d2, (y2 - y1) / d2)
        cos_t = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        theta = math.acos(cos_t)                       # interior angle
        tan_len = r / math.tan(theta / 2.0)            # distance from vertex to tangent point
        tan_len = min(tan_len, 0.5 * d1, 0.5 * d2)
        a = (x1 + u1[0] * tan_len, y1 + u1[1] * tan_len)
        bpt = (x1 + u2[0] * tan_len, y1 + u2[1] * tan_len)
        # arc centre along the bisector
        bis = (u1[0] + u2[0], u1[1] + u2[1]); bl = math.hypot(*bis) or 1.0
        bis = (bis[0] / bl, bis[1] / bl)
        dc = r / math.sin(theta / 2.0)
        cx, cy = x1 + bis[0] * dc, y1 + bis[1] * dc
        a0 = math.atan2(a[1] - cy, a[0] - cx); a1 = math.atan2(bpt[1] - cy, bpt[0] - cx)
        da = a1 - a0
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        for k in range(n + 1):
            ang = a0 + da * k / n
            out.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    out.append(path[-1])
    return out


def _segments(rec):
    path = _path(rec)
    if not path:
        return None, 0
    t = rec["t_mm"]
    r = (rec.get("Ri_mm") or 1.5 * t) + t / 2.0
    pts = _round_corners(path, r)
    return [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1)], len(path) - 2


def thinwall_props(rec):
    segs, ncorner = _segments(rec)
    if not segs:
        return None
    t = rec["t_mm"]
    A = 0.0; Sx = 0.0; Sy = 0.0
    for x1, y1, x2, y2 in segs:
        L = math.hypot(x2 - x1, y2 - y1)
        A += L * t; Sx += L * t * (y1 + y2) / 2.0; Sy += L * t * (x1 + x2) / 2.0
    yc, xc = Sx / A, Sy / A
    Ixx = 0.0; Iyy = 0.0
    for x1, y1, x2, y2 in segs:
        L = math.hypot(x2 - x1, y2 - y1)
        ym, xm = (y1 + y2) / 2.0, (x1 + x2) / 2.0
        Ixx += t * L * (y2 - y1) ** 2 / 12.0 + t * L * (ym - yc) ** 2
        Iyy += t * L * (x2 - x1) ** 2 / 12.0 + t * L * (xm - xc) ** 2
    return {"A_geom": A, "Ix": Ixx, "Iy": Iyy, "n_corners": ncorner}


def validate_row(rec):
    """rec: dict with Type, h_mm, b_mm, c_mm, t_mm, Ri_mm, A_mm2, Mass_kg_m, Ix_mm4, Iy_mm4, Iu_mm4, Iv_mm4."""
    fails = []
    tw = thinwall_props(rec)
    A, M, Ix, Iy = rec.get("A_mm2"), rec.get("Mass_kg_m"), rec.get("Ix_mm4"), rec.get("Iy_mm4")
    if tw is None or A is None:
        return {"status": "FAIL", "failures": ["geometry not computable (type %s)" % rec.get("Type")]}
    if abs(A / tw["A_geom"] - 1.0) > TOL["A"]:
        fails.append("A %.1f vs thin-wall %.1f mm2 (%.1f %%)" % (A, tw["A_geom"], 100 * (A / tw["A_geom"] - 1)))
    if M is not None and abs(M / (0.785 * A / 100.0) - 1.0) > TOL["M"]:
        fails.append("M %.3f vs 0.785A = %.3f kg/m" % (M, 0.785 * A / 100.0))
    if Ix is None:
        fails.append("Ix missing")
    elif abs(Ix / tw["Ix"] - 1.0) > TOL["Ix"]:
        fails.append("Ix %.0f vs thin-wall %.0f mm4 (%.1f %%)" % (Ix, tw["Ix"], 100 * (Ix / tw["Ix"] - 1)))
    Iu, Iv = rec.get("Iu_mm4"), rec.get("Iv_mm4")
    if Iu is not None and Iv is not None and Ix is not None and Iy is not None:
        if abs((Iu + Iv) / (Ix + Iy) - 1.0) > TOL["Iuv"]:
            fails.append("Iu+Iv %.0f vs Ix+Iy %.0f" % (Iu + Iv, Ix + Iy))
    if rec.get("Type") == "EA" and Ix is not None and Iy is not None and abs(Ix - Iy) > 1e-6 * Ix:
        fails.append("equal angle Ix != Iy")
    return {"status": "PASS" if not fails else "FAIL", "failures": fails, "thinwall": tw}


def main(path):
    rows = list(csv.DictReader(open(path, newline="")))
    n_fail = 0
    for r in rows:
        rec = {}
        for k, v in r.items():
            if v in ("", None):
                rec[k] = None
            elif k.endswith(("_mm", "_mm2", "_mm4", "_mm3", "_mm6", "_kg_m")):
                rec[k] = float(v)
            else:
                rec[k] = v
        v = validate_row(rec)
        if v["status"] != "PASS":
            n_fail += 1
            print("FAIL", r["Label"], v["failures"])
    print("%d rows, %d failures" % (len(rows), n_fail))
    return n_fail


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1] if len(sys.argv) > 1 else "steel_engine/is811_shapes.csv") else 0)
