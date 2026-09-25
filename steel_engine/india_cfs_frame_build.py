"""india_cfs_frame_build.py -- hot-rolled frame builder for CFS jobs whose plan is not a full NX x NY rectangle (L / Z / T / U / cruciform / split-level / podium) or whose lateral system needs chevron EBF links or moment
lines that the vendored regular-grid builder (example_build) cannot draw.

It is the frame_build of the GOLD-HR-B packages (gold_common.frame_build, work/gold-standard/IN_Ex9_*/gold_common.py)
driven by a JSON-declarative `gold` block of the CFS lateral spec instead of Python callables, so that it can cross
the subprocess boundary of india_cfs_lateral -> hr_vendor_runner (cfg['lateral_frame']['custom_build_module'] names this
module or a job-local .py path).  Nothing in steel_engine/hr_vendor is touched.

spec["gold"] = {
  "xcoords_m": [...], "ycoords_m": [...],            # optional non-uniform grid (else i * bay_x, j * bay_y)
  "present": {"default": [[i, j], ...], "1": [...], "3-5": [...]},   # column nodes present at storey k (k = 0 -> storey 1)
  "xbays": {"1-4": [["X", i, j], ...]},              # concentric X-braced bays (both diagonals) per storey range
  "ebf_bays": {"1-4": [["X", i, j], ...]}, "e_link_mm": 900.0,
  "ebf_beam_sec": {"X": {"1-4": sec}, "Y": {...}}, "ebf_link_sec": {...}, "ebf_brace_sec": {"1-4": sec},
  "brace_sec": {"1-4": sec},
  "moment_lines": [["X", j], ["Y", i]],             # rigid beam-column joints along a frame line
  "col_sec": {"lateral": {"1-4": sec}, "gravity": {"1-4": sec}}, "beam_sec": {"floor_X": sec, "floor_Y": sec, "roof_X": sec, "roof_Y": sec},
  "gravity_base": "pinned" | "fixed", "default_strong": "X" }
"""
from __future__ import annotations


def _rng_pick(groups, k):
    for rng, v in (groups or {}).items():
        if rng == "default":
            continue
        a, _, b = str(rng).partition("-")
        a = int(a); b = int(b) if b else a
        if a <= k <= b:
            return v
    return (groups or {}).get("default")


def make_gold(spec):
    """JSON gold block + section maps of the CFS spec -> the callables frame_build reads from cfg['_gold']."""
    g = spec["gold"]
    NX, NY = int(spec["NX"]), int(spec["NY"])
    NF = len(spec["heights_m"])
    full = [[i, j] for i in range(NX + 1) for j in range(NY + 1)]
    pres_spec = g.get("present") or {"default": full}

    def present(k):
        kk = 1 if k == 0 else k
        P = _rng_pick(pres_spec, kk)
        if P is None:
            P = pres_spec.get("default", full)
        return {tuple(p) for p in P}

    def xbays(k):
        return [tuple([d, int(i), int(j)]) for (d, i, j) in (_rng_pick(g.get("xbays"), k) or [])]

    def ebf_bays(k):
        return [tuple([d, int(i), int(j)]) for (d, i, j) in (_rng_pick(g.get("ebf_bays"), k) or [])]

    mset = {(m[0], int(m[1])) for m in (g.get("moment_lines") or spec.get("moment_lines") or [])}
    lateral_cols = set()
    for k in range(1, NF + 1):
        for (d, i, j) in xbays(k) + ebf_bays(k):
            lateral_cols.add((i, j)); lateral_cols.add((i + 1, j) if d == "X" else (i, j + 1))
    for (d, kk) in mset:
        for q in range((NX if d == "X" else NY) + 1):
            lateral_cols.add((q, kk) if d == "X" else (kk, q))

    def sfrs_col(i, j):
        return (i, j) in lateral_cols

    col_groups = g.get("col_sec") or spec.get("col_sec") or {}
    beam_groups = g.get("beam_sec") or spec.get("beam_sec") or {}

    def col_sec(i, j, k):
        grp = col_groups.get("lateral" if sfrs_col(i, j) else "gravity") or {}
        return _rng_pick(grp, k) or spec["col"]

    def beam_sec(i, j, k, dirn):
        roof = (k == NF)
        return (beam_groups.get(("roof" if roof else "floor") + "_" + dirn) or beam_groups.get("roof" if roof else "floor") or spec["beam"])

    def col_strong(i, j):
        for (d, kk) in mset:
            if (d == "X" and j == kk) or (d == "Y" and i == kk):
                return d
        for k in range(1, NF + 1):
            for (d, bi, bj) in xbays(k) + ebf_bays(k):
                if d == "X" and j == bj and i in (bi, bi + 1):
                    return "X"
                if d == "Y" and i == bi and j in (bj, bj + 1):
                    return "Y"
        return g.get("default_strong", spec.get("default_strong", "X"))

    def releases(i, j, k, dirn):
        if (dirn, j if dirn == "X" else i) in mset:
            return ("none", "none")
        return ("both", "none")

    def brace_sec(k):
        return _rng_pick(g.get("brace_sec"), k) or spec.get("brace")

    out = {"present": present, "sfrs_col": sfrs_col, "col_sec": col_sec, "beam_sec": beam_sec, "col_strong": col_strong,
           "releases": releases, "xbays": xbays, "brace_sec": brace_sec, "gravity_base": g.get("gravity_base", "pinned"),
           "lateral_cols": lateral_cols}
    if g.get("ebf_bays"):
        out.update({"ebf_bays": ebf_bays, "e_link_mm": float(g["e_link_mm"]),
                    "ebf_beam_sec": lambda dirn, k: _rng_pick((g.get("ebf_beam_sec") or {}).get(dirn), k),
                    "ebf_link_sec": lambda dirn, k: _rng_pick((g.get("ebf_link_sec") or {}).get(dirn), k),
                    "ebf_brace_sec": lambda k: _rng_pick(g.get("ebf_brace_sec"), k)})
    return out


def attach(cfg, spec):
    """Called by hr_vendor_runner after build_cfg: wires the custom builder into the HR cfg."""
    g = spec["gold"]
    gold = make_gold(spec)
    cfg["_gold"] = gold
    cfg["custom_build"] = frame_build
    cfg["plan"] = lambda k, NX_, NY_: gold["present"](k)
    if g.get("xcoords_m"):
        cfg["xcoords"] = [float(x) * 1000.0 for x in g["xcoords_m"]]
    if g.get("ycoords_m"):
        cfg["ycoords"] = [float(y) * 1000.0 for y in g["ycoords_m"]]
    cfg["braces"] = None          # braces are drawn by the builder (xbays / ebf_bays), not by the regular-grid callable
    cfg["sway_frame"] = bool(g.get("moment_lines") or spec.get("moment_lines"))
    if g.get("ebf_bays"):
        cfg["brace_config"] = "chevron"
    return cfg


def _xy(cfg, i, j):
    xco = cfg.get("xcoords"); yco = cfg.get("ycoords")
    return ((xco[i] if xco else i * cfg["SX"]), (yco[j] if yco else j * cfg["SY"]))


def frame_build(cfg, transf="PDelta"):
    """Generic custom_build driven by cfg['_gold'] (port of gold_common.frame_build, GOLD-HR-B):
      present(k) -> set of (i, j); sfrs_col(i, j) -> fixed base; col_sec(i, j, k); beam_sec(i, j, k, dirn);
      col_strong(i, j); releases(i, j, k, dirn); xbays(k) -> [(dirn, i, j)] X-braced bays; brace_sec(k);
      ebf_bays(k) chevron EBF bays with a centre link (ebf_beam_sec / ebf_link_sec / ebf_brace_sec, e_link_mm,
      IS 18168 11.4 stiffener rule); gravity_base 'pinned' (default) | 'fixed'."""
    import openseespy.opensees as ops
    import engine3d as E
    import sections as S
    g = cfg["_gold"]
    ops.wipe(); ops.model("basic", "-ndm", 3, "-ndf", 6)
    NF = len(cfg["heights"]); NX, NY = cfg["NX"], cfg["NY"]
    z = E.zlevels(cfg)
    XY = lambda i, j: _xy(cfg, i, j)
    pres = {k: set(g["present"](k)) for k in range(NF + 1)}
    for k in range(NF + 1):
        for (i, j) in pres[k]:
            x, y = XY(i, j); ops.node(E.ntag(i, j, k), x, y, z[k])
    bases = {}
    for (i, j) in pres[0]:
        fixed = g["sfrs_col"](i, j) or g.get("gravity_base", "pinned") == "fixed"
        ops.fix(E.ntag(i, j, 0), 1, 1, 1, *((1, 1, 1) if fixed else (0, 0, 0)))
        bases[(i, j)] = "fixed" if fixed else "pinned"
    cm = {}
    for k in range(1, NF + 1):
        pts = pres[k]
        cx = sum(XY(i, j)[0] for i, j in pts) / len(pts); cy = sum(XY(i, j)[1] for i, j in pts) / len(pts)
        cm[k] = (cx, cy); ops.node(E.mtag(k), cx, cy, z[k]); ops.fix(E.mtag(k), 0, 0, 1, 1, 1, 0)
    et = 1; eles = []; links = []; col_tag = {}
    for i in range(NX + 1):
        for j in range(NY + 1):
            sd = g["col_strong"](i, j)
            for k in range(NF):
                if (i, j) in pres[k] and (i, j) in pres[k + 1]:
                    sec = g["col_sec"](i, j, k + 1)
                    E.add_column(et, E.ntag(i, j, k), E.ntag(i, j, k + 1), sec, sd)
                    eles.append((et, "col", sec, E.ntag(i, j, k), E.ntag(i, j, k + 1))); col_tag[(i, j, k + 1)] = et; et += 1
    ops.uniaxialMaterial("Elastic", 1, E.E)
    xb = g.get("xbays") or (lambda k: [])
    eb = g.get("ebf_bays") or (lambda k: [])
    e_link = float(g.get("e_link_mm") or 0.0)
    for k in range(1, NF + 1):
        P = pres[k]
        ebays = set(eb(k)); xbays = set(xb(k))
        for dirn in ("X", "Y"):
            rng = [(i, j) for j in range(NY + 1) for i in range(NX)] if dirn == "X" else \
                  [(i, j) for i in range(NX + 1) for j in range(NY)]
            for (i, j) in rng:
                b = (i + 1, j) if dirn == "X" else (i, j + 1)
                if (i, j) not in P or b not in P:
                    continue
                A, B = E.ntag(i, j, k), E.ntag(*b, k)
                if (dirn, i, j) in ebays:
                    xa, ya = XY(i, j); xb_, yb_ = XY(*b)
                    L = (xb_ - xa) if dirn == "X" else (yb_ - ya)
                    s1 = (L - e_link) / 2.0; s2 = (L + e_link) / 2.0
                    if dirn == "X":
                        L1 = k * 100000 + (50 + i) * 100 + j; L2 = k * 100000 + (60 + i) * 100 + j
                        ops.node(L1, xa + s1, ya, z[k]); ops.node(L2, xa + s2, ya, z[k])
                    else:
                        L1 = k * 100000 + (70 + j) * 100 + i; L2 = k * 100000 + (80 + j) * 100 + i
                        ops.node(L1, xa, ya + s1, z[k]); ops.node(L2, xa, ya + s2, z[k])
                    bsec, lsec, brs = g["ebf_beam_sec"](dirn, k), g["ebf_link_sec"](dirn, k), g["ebf_brace_sec"](k)
                    E.add_beam(et, A, L1, bsec, releases=("none", "none")); eles.append((et, "beam", bsec, A, L1)); tb1 = et; et += 1
                    p = S.props(lsec)
                    Avz = (p["d"] - 2 * p["tf"]) * p["tw"]; Avy = 2 * p["bf"] * p["tf"]
                    ops.element("ElasticTimoshenkoBeam", et, L1, L2, E.E, E.Gmod, p["A"], p["J"], p["Ix"], p["Iy"], Avy, Avz, 3)
                    eles.append((et, "beam", lsec, L1, L2)); tl = et; et += 1
                    E.add_beam(et, L2, B, bsec, releases=("none", "none")); eles.append((et, "beam", bsec, L2, B)); tb2 = et; et += 1
                    brA = S.props(brs)["A"]
                    ops.element("Truss", et, E.ntag(i, j, k - 1), L1, brA, 1); eles.append((et, "brace", brs, E.ntag(i, j, k - 1), L1)); tr1 = et; et += 1
                    ops.element("Truss", et, E.ntag(*b, k - 1), L2, brA, 1); eles.append((et, "brace", brs, E.ntag(*b, k - 1), L2)); tr2 = et; et += 1
                    links.append({"tag": tl, "e_mm": e_link, "bay_L_mm": L, "dir": dirn, "storey": k,
                                  "brace_tags": [tr1, tr2], "beam_tags": [tb1, tb2],
                                  "column_tags": [t for t in (col_tag.get((i, j, k)), col_tag.get((b[0], b[1], k))) if t],
                                  "end_stiffeners": {"both_sides": True, "width_mm": p["bf"] - 2 * p["tw"] + 2.0,
                                                     "t_mm": max(0.75 * p["tw"], 10.0) + 2.0},
                                  "intermediate_stiffener_spacing_mm": round(min(30 * p["tw"] - 0.2 * p["d"], e_link / 2.0) - 5.0),
                                  "braced_both_flanges": True, "connected_to_column": False,
                                  "continuous_link_beam": (bsec == lsec), "doubler": False})
                else:
                    sec = g["beam_sec"](i, j, k, dirn)
                    rel = g["releases"](i, j, k, dirn)
                    E.add_beam(et, A, B, sec, releases=rel); eles.append((et, "beam", sec, A, B)); et += 1
        for (dirn, i, j) in xbays:
            a = (i, j); b = (i + 1, j) if dirn == "X" else (i, j + 1)
            brs = g["brace_sec"](k); brA = S.props(brs)["A"]
            if a in pres[k - 1] and b in pres[k]:
                ops.element("Truss", et, E.ntag(*a, k - 1), E.ntag(*b, k), brA, 1)
                eles.append((et, "brace", brs, E.ntag(*a, k - 1), E.ntag(*b, k))); et += 1
            if a in pres[k] and b in pres[k - 1]:
                ops.element("Truss", et, E.ntag(*a, k), E.ntag(*b, k - 1), brA, 1)
                eles.append((et, "brace", brs, E.ntag(*a, k), E.ntag(*b, k - 1))); et += 1
    info = {"cm": cm, "present": pres, "z": z, "NF": NF, "ele": eles, "links": links, "bases": bases}
    link_nodes = {}
    for ln in links:
        for (t, kind, sec, n1, n2) in eles:
            if t == ln["tag"]:
                link_nodes.setdefault(ln["storey"], []).extend([n1, n2])
    for k in range(1, NF + 1):
        sl = [E.ntag(i, j, k) for (i, j) in pres[k]] + link_nodes.get(k, [])
        ops.rigidDiaphragm(3, E.mtag(k), *sl)
        w = E.floor_w(cfg, k); m = w / E.g
        pts = pres[k]; xs = [XY(i, j)[0] for i, j in pts]; ys = [XY(i, j)[1] for i, j in pts]
        Bx = max(xs) - min(xs) + cfg["SX"]; By = max(ys) - min(ys) + cfg["SY"]
        ops.mass(E.mtag(k), m, m, 0.0, 0.0, 0.0, m * (Bx ** 2 + By ** 2) / 12.0)
    return info
