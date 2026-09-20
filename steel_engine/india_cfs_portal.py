"""india_cfs_portal.py -- the ALL-CFS portal frame path (owner ruling for CFS Ex5, Hyderabad Zone II; spec WP3.4).

N-mm throughout (E = 203 400 MPa = 2 074 000 kgf/cm2, IS 801 6.3; properties from is811_sections in mm; loads in
N/mm from IS 875 kN/m2 pressures).  FAIL-CLOSED: no load_plan combinations -> raise; no IS 875-3 pressures
(site.Vb / k2 table / pd) -> raise; no Ah (IS 1893) -> raise; snow only from IS 875-4 (declared, or 0 with found:false);
no ASCE / LRFD / AISI seed anywhere.

Seismic basis (stated in the report): `elastic_R1` -- the cold-formed portal is designed ELASTICALLY for the IS 1893
forces with R = 1.0 (Ah = (Z/2)(I/1.0)(Sa/g)); no ductility is claimed; IS 800 Section 12 is not applicable; wind
governs the frame.  IS 1893 7.11.1.1 drift (0.004 h under VB, gamma 1.0) and IS 800 Table 6 wind sway (Height/150
elastic cladding, read-only retrieval) are both reported.

Frame analysis: planar direct-stiffness model of ONE transverse frame (columns + rafters on nodes at the girt /
purlin stations and at the mezzanine level), linear elastic + P-Delta iteration on the compression members
(no stiffness reduction, no notional loads -- IS 801 is working stress; the sway effective length K comes from
IS 800 Annex D (sway frames) with beta = sum Kc/(sum Kc + sum Kb), C = 1.0).
Members: back-to-back pairs (n_ply 1 or 2, IS 801 7.3 interconnection) of IS 811 lipped channels; checks per
combination: IS 801 6.7.1 (doubly-symmetric pair, Cm 0.85 sway, F'e with the sway KL), 6.3 LTB on the unrestrained
flange between fly braces, 6.4 web shear, 6.5 crippling where a concentrated reaction bears on the web.
Connections: knee / apex / valley bolt groups (IS 801 7.5 on the channel sheet; elastic vector method), column
bases (anchor bolts IS 800 11.6.2 working stress = 0.6 x the 10.3 nominal, plate bending 11.4.1(c) 0.75 fy,
concrete bearing = EOR input, IS 456 not in the corpus).  Longitudinal bracing: declared diagonals checked in
tension (0.6 Fy on the net section, 7.5.2) and compression (6.6).
"""
from __future__ import annotations
import math

import india_cfs_env  # noqa: F401
import is811_sections as S
import is801_members as M
import india_cfs_basis as B
import india_wind_tables as WT
import india_seismic as IS
import india_connections as C8

E = M.E_MPA
SRC = "india_cfs_portal (N-mm; IS 801 / IS 811 / IS 875 / IS 1893; IS 800 Annex D K, Table 6, 11.6.2 / 11.4.1 WSM)"
STATEMENT = ("SEISMIC BASIS -- all-cold-formed portal designed ELASTICALLY for earthquake: R = 1.0 (no ductility claimed), "
             "Ah = (Z/2)(I/1.0)(Sa/g) per IS 1893 (Part 1):2016 6.4.2; IS 800:2007 Section 12 is not applicable to "
             "cold-formed members; the members are proportioned to IS 801:1975 working stress with the +33 1/3 % "
             "allowable of 6.1.2 on the EL / WL combinations; wind governs this frame (Zone II).")


class PortalError(ValueError):
    pass


# ------------------------------------------------------------------------------------------------ planar solver
class Frame2D:
    """Unit-agnostic planar frame (3 dof / node): nodes {tag: (x, y)}, elements [n1, n2, EA, EI, label], supports,
    nodal loads, member uniform loads (local axial p, transverse w) with consistent fixed-end forces."""

    def __init__(self):
        self.nodes, self.elems, self.fix = {}, [], {}
        self.nload, self.mload = {}, {}

    def node(self, tag, x, y):
        self.nodes[tag] = (x, y)

    def elem(self, n1, n2, EA, EI, label):
        self.elems.append([n1, n2, EA, EI, label])

    def support(self, tag, fx=True, fy=True, mz=False):
        self.fix[tag] = (fx, fy, mz)

    def load_node(self, tag, Fx=0.0, Fy=0.0, Mz=0.0):
        a = self.nload.setdefault(tag, [0.0, 0.0, 0.0])
        a[0] += Fx; a[1] += Fy; a[2] += Mz

    def load_member(self, idx, p_axial=0.0, w_perp=0.0):
        a = self.mload.setdefault(idx, [0.0, 0.0])
        a[0] += p_axial; a[1] += w_perp

    def _geom(self, el):
        (x1, y1), (x2, y2) = self.nodes[el[0]], self.nodes[el[1]]
        L = math.hypot(x2 - x1, y2 - y1)
        return L, (x2 - x1) / L, (y2 - y1) / L

    @staticmethod
    def _kel(EA, EI, L):
        a = EA / L; b = 12.0 * EI / L ** 3; c = 6.0 * EI / L ** 2; d = 4.0 * EI / L; e = 2.0 * EI / L
        return [[a, 0, 0, -a, 0, 0], [0, b, c, 0, -b, c], [0, c, d, 0, -c, e],
                [-a, 0, 0, a, 0, 0], [0, -b, -c, 0, b, -c], [0, c, e, 0, -c, d]]

    @staticmethod
    def _T(c, s):
        return [[c, s, 0, 0, 0, 0], [-s, c, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0],
                [0, 0, 0, c, s, 0], [0, 0, 0, -s, c, 0], [0, 0, 0, 0, 0, 1]]

    def solve(self, axials=None):
        tags = sorted(self.nodes)
        dof = {t: (3 * i, 3 * i + 1, 3 * i + 2) for i, t in enumerate(tags)}
        n = 3 * len(tags)
        K = [[0.0] * n for _ in range(n)]
        F = [0.0] * n
        feq = {}
        for idx, el in enumerate(self.elems):
            L, c, s = self._geom(el)
            kl = self._kel(el[2], el[3], L)
            if axials and axials.get(idx, 0.0) > 0.0:
                Ng = axials[idx] / L
                for (i, j, sg) in ((1, 1, 1), (4, 4, 1), (1, 4, -1), (4, 1, -1)):
                    kl[i][j] -= sg * Ng
            T = self._T(c, s)
            Tt = [list(r) for r in zip(*T)]
            kg = [[sum(Tt[i][k] * sum(kl[k][m] * T[m][j] for m in range(6)) for k in range(6)) for j in range(6)] for i in range(6)]
            p, w = self.mload.get(idx, (0.0, 0.0))
            fl = [p * L / 2.0, w * L / 2.0, w * L * L / 12.0, p * L / 2.0, w * L / 2.0, -w * L * L / 12.0]
            feq[idx] = fl
            fg = [sum(Tt[i][j] * fl[j] for j in range(6)) for i in range(6)]
            ed = dof[el[0]] + dof[el[1]]
            for i in range(6):
                F[ed[i]] += fg[i]
                for j in range(6):
                    K[ed[i]][ed[j]] += kg[i][j]
        for t, (Fx, Fy, Mz) in self.nload.items():
            d = dof[t]; F[d[0]] += Fx; F[d[1]] += Fy; F[d[2]] += Mz
        K0 = [r[:] for r in K]; F0 = F[:]
        for t, (fx, fy, mz) in self.fix.items():
            for flag, d in zip((fx, fy, mz), dof[t]):
                if flag:
                    for j in range(n):
                        K[d][j] = 0.0; K[j][d] = 0.0
                    K[d][d] = 1.0; F[d] = 0.0
        u = _gauss(K, F)
        res_u = {t: tuple(u[d] for d in dof[t]) for t in tags}
        end = {}
        for idx, el in enumerate(self.elems):
            L, c, s = self._geom(el)
            T = self._T(c, s)
            ed = dof[el[0]] + dof[el[1]]
            ug = [u[d] for d in ed]
            ul = [sum(T[i][j] * ug[j] for j in range(6)) for i in range(6)]
            kl = self._kel(el[2], el[3], L)
            end[idx] = [sum(kl[i][j] * ul[j] for j in range(6)) - feq[idx][i] for i in range(6)]
        reac = {t: tuple(sum(K0[dd][j] * u[j] for j in range(n)) - F0[dd] for dd in dof[t]) for t in self.fix}
        return {"u": res_u, "end_forces": end, "reactions": reac}


def _gauss(A, b):
    n = len(b)
    M_ = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M_[r][i]))
        if abs(M_[p][i]) < 1e-14:
            raise PortalError("singular stiffness matrix (mechanism?)")
        M_[i], M_[p] = M_[p], M_[i]
        piv = M_[i][i]
        for r in range(i + 1, n):
            f = M_[r][i] / piv
            if f:
                for cidx in range(i, n + 1):
                    M_[r][cidx] -= f * M_[i][cidx]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M_[i][n] - sum(M_[i][j] * x[j] for j in range(i + 1, n))) / M_[i][i]
    return x


# ------------------------------------------------------------------------------------------------ geometry
def _sec(spec):
    n, base = S.parse_designator(spec.get("designator") or spec["section"])
    n = int(spec.get("n_ply") or n)
    return S.built_up(base, n) if n == 2 else S.props(base)


def meta_slope(span, He, Ha):
    return math.atan2(Ha - He, span / 2.0)


def build_frame(po, secs, extra_stations=()):
    """Frame2D of the transverse frame in mm.  po: cfg['portal'] {spans_m, eave_m, apex_m, girt_spacing_m,
    purlin_spacing_m, base}.  Returns (frame, members {label: [elem idx]}, meta)."""
    spans = [float(s) * 1000.0 for s in po["spans_m"]]
    He = float(po["eave_m"]) * 1000.0; Ha = float(po["apex_m"]) * 1000.0
    gt = float(po.get("girt_spacing_m", 1.5)) * 1000.0; pt = float(po.get("purlin_spacing_m", 1.5)) * 1000.0
    fr = Frame2D(); members = {}; tag = [0]

    def stations(L, target, forced=()):
        nseg = max(int(round(L / max(target, 1.0))), 2)
        pts = sorted(set([L * i / nseg for i in range(nseg + 1)] + [f for f in forced if 0 < f < L]))
        return pts

    def chain(x1, y1, x2, y2, sec, label, target, forced=()):
        Lc = math.hypot(x2 - x1, y2 - y1)
        pts = stations(Lc, target, forced)
        tags_ = []
        for d in pts:
            fx, fy = x1 + (x2 - x1) * d / Lc, y1 + (y2 - y1) * d / Lc
            ex = next((t for t, (xx, yy) in fr.nodes.items() if abs(xx - fx) < 1e-6 and abs(yy - fy) < 1e-6), None)
            if ex is None:
                tag[0] += 1; fr.node(tag[0], fx, fy); tags_.append(tag[0])
            else:
                tags_.append(ex)
        members.setdefault(label, [])
        for a, b in zip(tags_, tags_[1:]):
            fr.elem(a, b, E * sec["A"], E * sec["Ix"], label)
            members[label].append(len(fr.elems) - 1)
        return tags_

    xs = [0.0]
    for sp in spans:
        xs.append(xs[-1] + sp)
    cols = []
    forced_c = tuple(extra_stations)
    if po.get("knee_brace"):
        forced_c = forced_c + (He - float(po["knee_brace"]["col_below_eave_m"]) * 1000.0,)
    forced_r = (float(po["knee_brace"]["raf_from_knee_m"]) * 1000.0,) if po.get("knee_brace") else ()
    for k, x in enumerate(xs):
        lab = "col_L" if k == 0 else ("col_R" if k == len(xs) - 1 else "col_I%d" % k)
        cols.append(chain(x, 0.0, x, He, secs["col"], lab, gt, forced=forced_c))
    apex = []
    for k in range(len(spans)):
        xa, xb = xs[k], xs[k + 1]; mid = (xa + xb) / 2.0
        Lh = math.hypot(mid - xa, Ha - He)
        tL = chain(xa, He, mid, Ha, secs["raf"], "raf_%dL" % (k + 1), pt, forced=forced_r)
        chain(mid, Ha, xb, He, secs["raf"], "raf_%dR" % (k + 1), pt, forced=tuple(Lh - f for f in forced_r))
        apex.append(tL[-1])
    kb = po.get("knee_brace")
    if kb and secs.get("kb"):
        # knee braces: pin-ended diagonals from a column station (z_m below the eave) to a rafter station (d_m from the
        # knee along the rafter); modelled with the brace EA and a negligible EI (pinned ends)
        zc = He - float(kb["col_below_eave_m"]) * 1000.0
        dr = float(kb["raf_from_knee_m"]) * 1000.0
        EA_kb = E * secs["kb"]["A"]; EI_kb = E * secs["kb"]["Ix"] * 1e-4
        members.setdefault("knee_brace", [])
        for k, chain in enumerate(cols):
            cn = next((t for t in chain if abs(fr.nodes[t][1] - zc) < 1e-6), None)
            if cn is None:
                raise PortalError("knee brace column station %.0f mm is not a girt station (add it to the girt spacing)" % zc)
            x = xs[k]
            targets = []
            if k < len(spans):
                targets.append((x + dr * math.cos(meta_slope(spans[0], He, Ha)), He + dr * math.sin(meta_slope(spans[0], He, Ha))))
            if k > 0:
                targets.append((x - dr * math.cos(meta_slope(spans[0], He, Ha)), He + dr * math.sin(meta_slope(spans[0], He, Ha))))
            for (tx, ty) in targets:
                rn = next((t for t, (xx, yy) in fr.nodes.items() if abs(xx - tx) < 1.0 and abs(yy - ty) < 1.0), None)
                if rn is None:
                    raise PortalError("knee brace rafter station %.0f mm from the knee is not a purlin station" % dr)
                fr.elem(cn, rn, EA_kb, EI_kb, "knee_brace")
                members["knee_brace"].append(len(fr.elems) - 1)
    fixed = str(po.get("base", "fixed")) == "fixed"
    for c in cols:
        fr.support(c[0], True, True, fixed)
    meta = {"base_nodes": [c[0] for c in cols], "top_nodes": [c[-1] for c in cols], "col_chains": cols, "apex_nodes": apex,
            "xs": xs, "He": He, "Ha": Ha, "slope": math.atan2(Ha - He, spans[0] / 2.0), "fixed_base": fixed,
            "raf_len_half": math.hypot(spans[0] / 2.0, Ha - He), "n_spans": len(spans)}
    return fr, members, meta


# ------------------------------------------------------------------------------------------------ load cases
def _mezz_nodes(fr, meta, y):
    out = []
    for chain in meta["col_chains"]:
        for t in chain:
            if abs(fr.nodes[t][1] - y) < 1e-6:
                out.append(t)
    return out


def elementary_cases(cfg, fr, members, meta, wind):
    """Elementary cases as lists of (kind, target, values): D, Lr, S, mezzD, mezzL, W<pattern>, E."""
    po = cfg["portal"]; ld = cfg["loads"]
    sp = float(po["spacing_m"]) * 1000.0                 # frame spacing mm
    cases = {}
    cs = math.cos(meta["slope"])

    def on_rafters(kNm2, basis, sign=-1.0):
        out = []
        w = kNm2 * 1e-3 * sp                               # N/mm along the member (per horizontal projection when basis)
        for lab, idxs in members.items():
            if not lab.startswith("raf"):
                continue
            for idx in idxs:
                el = fr.elems[idx]
                L, c, s = fr._geom(el)
                wl = w * (abs(c) if basis == "projection" else 1.0)
                # gravity: global -y -> local components (axial along member = -wl*s*..., perpendicular = -wl*c)
                out.append(("m", idx, (sign * wl * s * (1 if el[1] > el[0] else 1), sign * wl * c)))
        return out

    # dead: roof sheeting + purlins (per slope length) + member self-weight (per length)
    cases["D"] = on_rafters(float(ld["D_roof"]), "length")
    for lab, idxs in members.items():
        if lab == "knee_brace":
            continue
        sec = (cfg["_secs"]["col"] if lab.startswith("col") else cfg["_secs"]["raf"])
        wsw = (sec.get("mass_kg_m") or 0.0) * 9.80665 / 1000.0          # N/mm
        for idx in idxs:
            el = fr.elems[idx]; L, c, s = fr._geom(el)
            if lab.startswith("col"):
                cases["D"].append(("m", idx, (-wsw, 0.0)))               # axial along the column (down)
            else:
                cases["D"].append(("m", idx, (-wsw * s, -wsw * c)))
    # wall self-weight / cladding on the columns (girts + sheeting) as axial load along the column
    wall = float(ld.get("clad", 0.0)) * 1e-3 * sp
    for lab, idxs in members.items():
        if lab.startswith("col"):
            for idx in idxs:
                cases["D"].append(("m", idx, (-wall, 0.0)))
    cases["Lr"] = on_rafters(float(ld.get("Lr", 0.0)), "projection")
    snow = float(ld.get("snow", 0.0))
    cases["S"] = on_rafters(snow, "projection") if snow > 0 else []
    # mezzanine: reactions of the mezzanine beams on the columns of the declared span at the mezzanine level
    mz = cfg.get("mezzanine")
    cases["mezzD"], cases["mezzL"] = [], []
    if mz and str(mz.get("support", "portal_columns")) != "independent_posts":
        y = float(mz["height_m"]) * 1000.0
        nodes = _mezz_nodes(fr, meta, y)
        k = int(mz.get("span_index", 0))
        x_a, x_b = meta["xs"][k], meta["xs"][k + 1]
        trib_len = min(float(mz["depth_m"]) * 1000.0, sp)  # along the building: the frame's share of the mezzanine depth
        half = (x_b - x_a) / 2.0 * trib_len                # mm2 tributary to each supporting column
        e = float(mz.get("bracket_e_mm", 0.0))
        for t in nodes:
            x = fr.nodes[t][0]
            if abs(x - x_a) < 1e-6 or abs(x - x_b) < 1e-6:
                sgn = 1.0 if abs(x - x_a) < 1e-6 else -1.0   # bracket moment sign: load inside the bay
                PD = float(mz["D_kNm2"]) * 1e-3 * half; PL = float(mz["L_kNm2"]) * 1e-3 * half
                cases["mezzD"].append(("n", t, (0.0, -PD, sgn * PD * e)))
                cases["mezzL"].append(("n", t, (0.0, -PL, sgn * PL * e)))
    # wind patterns (IS 875-3 Tables 5 / 6 with Cpi): pressure + towards the surface
    for pat in wind["patterns"]:
        out = []
        left = pat["from"] == "L"
        wall_w = pat["wall_windward_kNm2"] * 1e-3 * sp; wall_l = pat["wall_leeward_kNm2"] * 1e-3 * sp
        roof_w = pat["roof_windward_kNm2"] * 1e-3 * sp; roof_l = pat["roof_leeward_kNm2"] * 1e-3 * sp
        for lab, idxs in members.items():
            if lab == ("col_L" if left else "col_R"):
                for idx in idxs:
                    out.append(("m", idx, (0.0, (-wall_w if left else +wall_w))))     # inward on the windward wall
            elif lab == ("col_R" if left else "col_L"):
                for idx in idxs:
                    out.append(("m", idx, (0.0, (+wall_l if left else -wall_l))))     # local +y' points inside for col_R
            elif lab.startswith("raf"):
                # first slope from the wind side = windward (EF); every other slope leeward (GH) -- Table 6 note for
                # multi-span roofs: the remaining slopes take the leeward values (conservative on uplift)
                span_no = int(lab[4]); side = lab[-1]
                windward = (left and span_no == 1 and side == "L") or ((not left) and span_no == meta["n_spans"] and side == "R")
                p = roof_w if windward else roof_l
                for idx in idxs:
                    el = fr.elems[idx]; L, c, s = fr._geom(el)
                    # local +y' of a rafter element drawn left-to-right points to the upper-left (outward for left slopes);
                    # apply pressure as a load towards the surface = against the outward normal
                    outward = +1.0 if side == "L" else -1.0
                    out.append(("m", idx, (0.0, -p * outward)))
        cases[pat["name"]] = out
    # earthquake: Ah x seismic weight at the eave (roof + half walls) and at the mezzanine level (elastic, R = 1)
    Ah = wind["Ah"]
    W_roof = cfg["_W"]["roof_N"]
    W_mezz = 0.0 if (mz and str(mz.get("lateral")) == "own_bracing") else cfg["_W"]["mezz_N"]
    out = []
    tops = meta["top_nodes"]
    for t in tops:
        out.append(("n", t, (Ah * W_roof / len(tops), 0.0, 0.0)))
    if mz and W_mezz:
        nodes = [t for t in _mezz_nodes(fr, meta, float(mz["height_m"]) * 1000.0)]
        for t in nodes:
            out.append(("n", t, (Ah * W_mezz / len(nodes), 0.0, 0.0)))
    cases["E"] = out
    return cases


def _apply(fr, loadlist, f):
    for kind, tgt, val in loadlist:
        if kind == "m":
            fr.load_member(tgt, p_axial=val[0] * f, w_perp=val[1] * f)
        else:
            fr.load_node(tgt, val[0] * f, val[1] * f, val[2] * f)


def solve_combo(cfg, secs, cases, factors, extra_stations, pdelta=True):
    fr, members, meta = build_frame(cfg["portal"], secs, extra_stations)
    for case, f in factors.items():
        if f and cases.get(case):
            _apply(fr, cases[case], f)
    sol = fr.solve()
    pd = {"iters": 0, "converged": True}
    if pdelta:
        prev = max(abs(u[0]) for u in sol["u"].values()) or 1e-9
        for it in range(6):
            ax = {}
            for lab, idxs in members.items():
                if lab.startswith("col"):
                    for idx in idxs:
                        q = sol["end_forces"][idx]
                        N = max(q[0], -q[3])
                        if N > 0:
                            ax[idx] = N
            if not ax:
                break
            sol = fr.solve(axials=ax)
            d = max(abs(u[0]) for u in sol["u"].values()) or 1e-9
            pd["iters"] = it + 1
            if d / prev > 3.0:
                pd["converged"] = False; break
            if abs(d - prev) <= 0.005 * d:
                break
            prev = d
    sol["pdelta"] = pd
    return fr, members, meta, sol


def member_forces(fr, members, sol):
    """Per member group: max |P|, |V|, |M| and the station forces (P, V, M) list."""
    out = {}
    for lab, idxs in members.items():
        st = []
        for idx in idxs:
            q = sol["end_forces"][idx]
            st.append((q[0], q[1], q[2])); st.append((-q[3], -q[4], -q[5]))
        Pmax = max(st, key=lambda r: r[0])       # max compression (local axial +ve = compression at node i)
        Mmax = max(st, key=lambda r: abs(r[2]))
        out[lab] = {"P_N": max(abs(r[0]) for r in st), "V_N": max(abs(r[1]) for r in st), "M_Nmm": max(abs(r[2]) for r in st),
                    "at_Mmax": Mmax, "at_Pmax": Pmax, "stations": st}
    return out


# ------------------------------------------------------------------------------------------------ K (IS 800 Annex D)
def sway_K(Ic, Lc, Ir_over_Lr_sum, fixed_base):
    """IS 800:2007 Annex D sway frame: K = [(1 - 0.2(b1 + b2) - 0.12 b1 b2)/(1 - 0.8(b1 + b2) + 0.6 b1 b2)]^0.5,
    beta = sum Kc/(sum Kc + sum Kb), K = C I/L with C = 1.0 (rigid far ends).  Pinned base: beta1 = 1."""
    Kc = Ic / Lc
    b2 = Kc / (Kc + Ir_over_Lr_sum) if Ir_over_Lr_sum > 0 else 1.0
    b1 = 0.0 if fixed_base else 1.0
    num = 1.0 - 0.2 * (b1 + b2) - 0.12 * b1 * b2
    den = 1.0 - 0.8 * (b1 + b2) + 0.6 * b1 * b2
    if den <= 1e-9:
        return float("inf"), b1, b2
    return math.sqrt(num / den), b1, b2


# ------------------------------------------------------------------------------------------------ wind
def wind_patterns(cfg):
    site = cfg["site"]; po = cfg["portal"]
    H = float(po["eave_m"]); Ha = float(po["apex_m"])
    w_m = sum(float(s) for s in po["spans_m"]); l_m = float(po["length_m"])
    if site.get("cyclone_belt") is None:
        raise PortalError("site.cyclone_belt (true/false + cite) required (D10)")
    req = WT.k4_required(bool(site["cyclone_belt"]), site.get("wind_structure_class"))
    k4 = req["k4"]; Kd = 1.0 if site["cyclone_belt"] else float(site.get("Kd", 0.9))
    tab = site.get("k2_table")
    if not tab:
        raise PortalError("site.k2_table (IS 875-3 Table 2) required -- pressures are never seeded")
    pts = sorted((float(k), float(v)) for k, v in dict(tab).items())
    z = (H + Ha) / 2.0                  # mean roof height for the frame pressures

    def k2(z_):
        if z_ <= pts[0][0]:
            return pts[0][1]
        for (z1, k1), (z2, k2_) in zip(pts, pts[1:]):
            if z1 <= z_ <= z2:
                return k1 + (k2_ - k1) * (z_ - z1) / (z2 - z1)
        return pts[-1][1]
    Vz = float(site["Vb"]) * float(site.get("k1", 1.0)) * k2(max(z, 10.0)) * float(site.get("k3", 1.0)) * k4
    pz = 0.6 * Vz ** 2 / 1000.0
    A = float(po["spacing_m"]) * max(H, w_m / 2.0)
    Ka_rec = WT.resolve_ka(A, site.get("Ka_corpus_hit"))
    if not Ka_rec.get("found"):
        raise PortalError("Ka unresolved: %s" % Ka_rec.get("cite"))
    Ka = float(Ka_rec["Ka"])
    pd = max(Kd * Ka * float(site.get("Kc", 1.0)) * pz, 0.7 * pz)
    pitch = math.degrees(math.atan2(Ha - H, float(po["spans_m"][0]) / 2.0))
    mw = WT.lowrise_member_wind(pd, H, w_m, l_m, pitch, float(po.get("opening_ratio", 0.05)))
    if not isinstance(mw, dict) or not mw.get("found"):
        raise PortalError("IS 875-3 member wind patterns unresolved: %s" % (mw.get("note") if isinstance(mw, dict) else mw))
    mw_cite = mw.get("cite")
    mw = mw["patterns"]
    pats = []
    for p in mw:
        if p.get("direction") != "across_ridge":
            continue
        for side in ("L", "R"):
            pats.append(dict(p, name="%s%s" % (p["name"], side), **{"from": side}))
    along = [p for p in mw if p.get("direction") == "along_ridge"]
    return {"Vz_mps": Vz, "pz_kNm2": pz, "pd_kNm2": pd, "k2": k2(max(z, 10.0)), "k4": k4, "Kd": Kd, "Ka": Ka, "Ka_area_m2": A,
            "Ka_basis": "frame_tributary", "z_ref_m": z, "pitch_deg": pitch, "patterns": pats, "along_ridge": along,
            "Cpi": sorted({p["Cpi"] for p in mw}), "cite": "IS 875-3 6.3, Table 2, 6.3.4, 7.2, Table 4; " + str(mw_cite),
            "Vb_mps": site["Vb"], "terrain_category": site.get("terrain_category"), "cyclone_belt": bool(site["cyclone_belt"]),
            "cyclone_belt_cite": site.get("cyclone_belt_cite"), "k1": site.get("k1", 1.0), "k3": site.get("k3", 1.0),
            "code": "IS 875 (Part 3):2015", "storeys": [{"k": 1, "z_m": H, "k2": round(k2(max(H, 10.0)), 4), "Vz_mps": round(Vz, 3),
                                                         "pz_kNm2": round(pz, 4), "pd_kNm2": round(pd, 4)}]}


# ------------------------------------------------------------------------------------------------ seismic (elastic, R = 1)
def seismic_elastic(cfg, secs, meta):
    site = cfg["site"]; po = cfg["portal"]; ld = cfg["loads"]
    I_rec = IS.importance_factor(cfg.get("occupancy"))
    if not I_rec.get("found"):
        raise PortalError("IS 1893 Table 8 I unresolved: %s" % I_rec.get("note"))
    I = I_rec["I"]
    sp = float(po["spacing_m"]); w_m = sum(float(s) for s in po["spans_m"]); He = float(po["eave_m"])
    n_fr = int(po.get("n_frames", 2))
    area_frame = w_m * sp                                           # m2 roof per frame
    W_roof = float(ld["D_roof"]) * area_frame * 1e3                 # N
    raf_len = 2 * meta["raf_len_half"] * meta["n_spans"]
    W_sw = ((secs["raf"].get("mass_kg_m") or 0.0) * raf_len + (secs["col"].get("mass_kg_m") or 0.0) * He * 1000.0 * (meta["n_spans"] + 1)) * 9.80665 / 1000.0
    W_wall = float(ld.get("clad", 0.0)) * 2 * He * sp * 1e3 / 2.0    # half the wall height to the eave
    W_roof_tot = W_roof + W_sw + W_wall
    snow = float(ld.get("snow", 0.0))
    if snow > 1.5:
        W_roof_tot += 0.2 * snow * area_frame * 1e3
    mz = cfg.get("mezzanine"); W_mezz = 0.0; W_mezz_total = 0.0
    if mz:
        k = int(mz.get("span_index", 0)); span = float(po["spans_m"][k])
        L = float(mz["L_kNm2"]); q = (float(mz["D_kNm2"]) + (0.25 if L <= 3.0 else 0.5) * L) * 1e3
        W_mezz_total = q * span * float(mz["depth_m"])                 # the whole mezzanine (N)
        trib = min(float(mz["depth_m"]), sp)
        W_mezz = q * span * trib                                        # share of one frame when it pushes the portal
    own = bool(mz) and str(mz.get("lateral")) == "own_bracing"
    W_frame = W_roof_tot + (0.0 if own else W_mezz)                     # seismic weight of one transverse frame
    W_portal_total = W_roof_tot * n_fr + (0.0 if own else W_mezz_total)   # whole portal building (longitudinal bracing)
    h = float(po["apex_m"])
    Ta = 0.09 * h / math.sqrt(w_m)                                    # 7.6.2(c)
    R = 1.0
    sa = IS.sa_over_g(Ta, site["soil"], "ESM") if hasattr(IS, "sa_over_g") else 2.5
    Ah = (float(site["Z"]) / 2.0) * (I / R) * sa
    rho_min = {"II": 0.007, "III": 0.011, "IV": 0.016, "V": 0.024}[str(site["zone"]).upper()]
    Ah = max(Ah, rho_min)
    W = W_frame
    return {"Z": site["Z"], "zone": site["zone"], "I": I, "I_cite": I_rec.get("cite"), "I_row": I_rec.get("row"), "R": R,
            "R_cite": "elastic design, R = 1.0 (owner ruling: all-CFS portal, no ductility claimed; IS 800 Section 12 n/a)",
            "soil": site["soil"], "Ta_s": Ta, "Ta_x_s": Ta, "Ta_y_s": Ta, "Ta_formula": "0.09 h/sqrt(d) (7.6.2(c)), h = apex, d = frame width",
            "Sa_g": sa, "Ah": Ah, "Ah_min_table7": rho_min, "W_kN": W / 1e3, "W_frame_roof_kN": W_roof_tot / 1e3,
            "W_frame_mezz_kN": (0.0 if own else W_mezz / 1e3), "W_portal_total_kN": W_portal_total / 1e3,
            "W_mezzanine_total_kN": W_mezz_total / 1e3, "mezzanine_lateral": ("own bracing (not on the portal)" if own else "on the portal frames"),
            "VB_kN": Ah * W / 1e3, "VB_frame_kN": Ah * W / 1e3, "VB_portal_total_kN": Ah * W_portal_total / 1e3,
            "VB_mezzanine_kN": Ah * W_mezz_total / 1e3, "system": "all-CFS portal (elastic, R 1.0)",
            "seismic_basis": "elastic_R1", "statement": STATEMENT, "_W": {"roof_N": W_roof_tot, "mezz_N": W_mezz, "portal_total_N": W_portal_total,
                                                                          "mezz_total_N": W_mezz_total},
            "cite": "IS 1893 6.4.2 Ah = (Z/2)(I/R)(Sa/g); Table 7 minimum; 7.3 / 7.4 W (D + Table 10 IL share); 7.6.2(c) Ta",
            "code": "IS 1893 (Part 1):2016 + Amd 1, 2", "esm_permitted": True,
            "esm_note": "regular single-storey portal, h < 15 m, Zone II: ESM permitted (7.6); no RSA required (7.7.1)"}


# ------------------------------------------------------------------------------------------------ checks
def _mrow(label, name, r, extra=None):
    o = {"combo": label, "check": name, "value": r.get("value"), "limit": r.get("limit"), "dc": r.get("dc"), "ok": r.get("ok"),
         "clause": r.get("clause"), "cite": r.get("cite"), "allowable_increase": r.get("allowable_increase", 1.0),
         "capacity_basis": r.get("capacity_basis", "IS801_allowable"), "source": SRC}
    if r.get("note"):
        o["note"] = r["note"]
    if extra:
        o.update(extra)
    return o


def check_member(cfg, role, sec, fy, forces_by_combo, K, L_col_mm, Lu_mm, wind_eq_by_combo):
    rows = []
    for lab, f in forces_by_combo.items():
        we = wind_eq_by_combo[lab]
        for tagn, (P, V, Mz) in (("at max M", f["at_Mmax"]), ("at max P", f["at_Pmax"])):
            Pc = max(P, 0.0)
            KLx = K * L_col_mm if role == "column" else L_col_mm      # rafters: in-plane KL = member length (K 1)
            r = M.combined_67(sec, fy, Pc, abs(Mz), KLx, Lu_mm, Lu_mm, cm_case="sway" if we else "transverse_restrained",
                              braced_against_twist=(sec.get("n_ply", 1) == 2), wind_eq=we, compression_flange_restrained=False)
            if "checks" not in r:
                rows.append(_mrow(lab, "6.7 %s" % tagn, {"ok": None, "note": r.get("note"), "clause": r.get("clause")}))
                continue
            for nm, ck in r["checks"].items():
                rows.append(_mrow(lab, "%s (%s)" % (nm, tagn), ck, {"P_N": round(Pc, 1), "M_Nmm": round(abs(Mz), 1), "KL_mm": round(KLx, 0),
                                                                    "fa_MPa": round(r["fa_MPa"], 2), "fb_MPa": round(r["fbx_MPa"], 2),
                                                                    "Fa_MPa": round(r["Fa_MPa"], 2), "Fb_MPa": round(r["Fbx_MPa"], 2),
                                                                    "Cm": r["Cm"], "amplification": r.get("amplification")}))
        rows.append(_mrow(lab, "6.4.1 web shear", M.web_shear_64(sec, fy, f["V_N"], wind_eq=we), {"V_N": round(f["V_N"], 1)}))
        if f["V_N"] and f["M_Nmm"]:
            cb = M.web_bending_shear_643(sec, fy, f["M_Nmm"], f["V_N"], wind_eq=we)
            rows.append(_mrow(lab, "6.4.3 web bending + shear", cb["combined"]))
    return rows


def bolt_group_75(fy, t_sheet, bolts, M_Nmm, V_N, N_N, wind_eq, n_ply):
    """Knee / apex bolt group on the channel webs (IS 801 7.5): elastic vector method, max bolt force, checks on the
    thinnest sheet (t per ply; a back-to-back pair has two sheets in bearing per bolt)."""
    rows, cols = int(bolts["rows"]), int(bolts["cols"]); p, g = float(bolts["pitch_mm"]), float(bolts["gauge_mm"])
    d = float(bolts["d_mm"])
    pts = [((c - (cols - 1) / 2.0) * g, (r - (rows - 1) / 2.0) * p) for r in range(rows) for c in range(cols)]
    J = sum(x * x + y * y for x, y in pts); n = len(pts)
    fmax = 0.0
    for x, y in pts:
        fx = -M_Nmm * y / J + V_N / n; fy_ = M_Nmm * x / J + N_N / n
        fmax = max(fmax, math.hypot(fx, fy_))
    P_per_sheet = fmax / max(n_ply, 1)
    out = M.bolted_connection_75(fy, t_sheet, d, P_per_sheet, n, float(bolts.get("edge_mm", 1.5 * d)), g, bolt_class=bolts.get("bolt_class", "4.6"),
                                 wind_eq=wind_eq)
    out.update(F_bolt_max_N=fmax, n_bolts=n, J_mm2=J, method="elastic vector method (M r/J + V/n)")
    return out


IS800_1114_CITE = ("IS 800:2007 11.1.4: permissible stresses may be increased by 33 percent in combinations involving wind or "
                   "seismic loads; anchor bolts limited to 25 percent; no increase when the wind / seismic load is the major load "
                   "(acting with dead load alone)")


def is800_wsm_increase(wind_eq, with_imposed, anchor=False):
    """IS 800:2007 11.1.4 (corpus exact_section 11.1.4): 1.33 members / 1.25 anchor bolts in W / EL combinations that also
    carry imposed load; 1.0 when W / EL acts with dead load alone (the 'major load' rule) and for gravity combinations."""
    if not wind_eq or not with_imposed:
        return 1.0
    return 1.25 if anchor else 1.33


def base_check(cfg, base, R_N, wind_eq, with_imposed=True):
    """Column base under working reactions (H, V, Mz): anchor bolts IS 800 11.6.2 (0.6 x 10.3 nominal), plate bending
    11.4.1(c) 0.75 fy, concrete bearing = EOR input (IS 456 not in the corpus).  Increases per IS 800 11.1.4 (not IS 801
    6.1.2): 33 % plate / 25 % anchors only when W / EL acts together with imposed load."""
    H, V, Mz = R_N
    B_, L_, t = float(base["B_mm"]), float(base["L_mm"]), float(base["t_plate_mm"])
    fyp = float(base["fy_plate_MPa"])
    an = base["anchors"]; n = int(an["n_total"]); nt = int(an["n_tension"]); d = float(an["d_mm"])
    inc = is800_wsm_increase(wind_eq, with_imposed, anchor=False)
    inc_a = is800_wsm_increase(wind_eq, with_imposed, anchor=True)
    checks = {}
    # bearing pressure (linear) on the plate: q = V/(B L) +- 6 M/(B L^2); uplift when V < 0
    q_max = max(V, 0.0) / (B_ * L_) + 6.0 * abs(Mz) / (B_ * L_ ** 2)
    q_min = max(V, 0.0) / (B_ * L_) - 6.0 * abs(Mz) / (B_ * L_ ** 2)
    ea = float(base.get("bearing_permissible_MPa", 0.0))
    if ea > 0:
        checks["concrete bearing"] = M._rec(q_max, ea, "IS 456 (EOR input)", base.get("bearing_cite") or "EOR-supplied permissible bearing",
                                           capacity_basis="EOR_input", allowable_increase=1.0)
    else:
        checks["concrete bearing"] = {"value": q_max, "limit": None, "dc": None, "ok": None, "clause": "IS 456 (not in the corpus)",
                                      "cite": "permissible bearing pressure on the pedestal: EOR input (base.bearing_permissible_MPa + cite)",
                                      "capacity_basis": "EOR_input", "allowable_increase": 1.0, "found": False}
    # anchor tension from the moment (lever arm between the tension bolts and the compression edge) when q_min < 0
    lever = float(an.get("f_mm", L_ / 2.0 - float(an.get("edge_mm", 50.0))))
    T_total = 0.0
    if V < 0:
        T_total = -V + abs(Mz) / (2.0 * lever)
    elif q_min < 0:
        T_total = max((abs(Mz) - V * L_ / 6.0) / (lever + L_ / 3.0), 0.0)
    T_bolt = T_total / max(nt, 1); V_bolt = abs(H) / n
    bc = C8.bolt_capacity_is800(d, an.get("grade", "4.6"), nn=1, ns=0, Anb_mm2=an.get("Anb_mm2"),
                                t_mm=t, fu_plate_MPa=float(base.get("fu_plate_MPa", 410.0)), e_mm=float(an.get("edge_mm", 50.0)),
                                p_mm=float(an.get("pitch_mm", 3 * d)), d0_mm=d + 2.0)
    if bc.get("Tnb_N") and bc.get("Vnsb_N"):
        Asb = bc["Asb_mm2"]
        fatb = 0.60 * bc["Tnb_N"] / Asb * inc_a; fasb = 0.60 * bc["Vnsb_N"] / Asb * inc_a
        checks["anchor tension 11.6.2.3"] = M._rec(T_bolt / Asb, fatb, "IS 800:2007 11.6.2.3", "fatb = 0.60 Tnb/Asb (working stress); " + IS800_1114_CITE,
                                                  capacity_basis="IS800_WSM", allowable_increase=inc_a, T_bolt_N=T_bolt)
        checks["anchor shear 11.6.2.1"] = M._rec(V_bolt / Asb, fasb, "IS 800:2007 11.6.2.1", "fasb = 0.60 Vnsb/Asb (working stress); " + IS800_1114_CITE,
                                                capacity_basis="IS800_WSM", allowable_increase=inc_a, V_bolt_N=V_bolt)
        comb = (T_bolt / Asb / fatb) ** 2 + (V_bolt / Asb / fasb) ** 2
        checks["anchor combined"] = M._rec(comb, 1.0, "IS 800:2007 11.6.3 / 10.3.6 form", "(f/fa)^2 + (v/va)^2 <= 1 at working stress",
                                          capacity_basis="IS800_WSM", allowable_increase=1.0)
    # plate bending: cantilever strip beyond the column flange under q_max (compression side)
    a = float(base.get("a_mm", (L_ - float(base.get("col_d_mm", L_ / 2.0))) / 2.0))
    Mstrip = q_max * a ** 2 / 2.0                                  # N-mm per mm width
    fb = 6.0 * Mstrip / t ** 2
    checks["plate bending 11.4.1(c)"] = M._rec(fb, 0.75 * fyp * inc, "IS 800:2007 11.4.1 (c)", "solid plates bending: fab = 0.75 fy; " + IS800_1114_CITE,
                                              capacity_basis="IS800_WSM", allowable_increase=inc, a_mm=a, q_max_MPa=q_max)
    if T_total > 0:
        # uplift side: plate bending from the anchor pull over the same cantilever (per tension row)
        Mt = T_total * a / (B_)
        checks["plate bending (uplift side)"] = M._rec(6.0 * Mt / t ** 2, 0.75 * fyp * inc, "IS 800:2007 11.4.1 (c)",
                                                      "solid plates bending: fab = 0.75 fy; " + IS800_1114_CITE, capacity_basis="IS800_WSM", allowable_increase=inc)
    dcs = [c["dc"] for c in checks.values() if isinstance(c.get("dc"), (int, float))]
    return {"checks": checks, "dc": max(dcs) if dcs else None, "ok": (None if any(c.get("ok") is None for c in checks.values())
                                                                       else all(c.get("ok") for c in checks.values())),
            "reactions": {"H_N": H, "V_N": V, "M_Nmm": Mz}, "T_total_N": T_total}


def _bracing_block(cfg, bid, lb, F_by_case, fy, L_diag, cos, n_bays, n_sides, note):
    sec = _sec(lb)
    tension_only = bool(lb.get("tension_only", True))
    rows = []
    for lab, F in F_by_case:
        T = F / (n_bays * n_sides) / cos
        An = sec["A"] - float(lb.get("n_bolts_at_section", 1)) * (float(lb.get("d_bolt_mm", 12.0)) + 2.0) * sec["t"]
        rows.append(_mrow(lab, "tension 6.1 / 7.5.2 net section", M._rec(T / An, 0.6 * fy * B.INCREASE_WL_EL, "IS 801 6.1 / 7.5.2",
                                                                          "0.60 Fy on the net section (+33 1/3 %, 6.1.2)", allowable_increase=B.INCREASE_WL_EL),
                          {"T_N": round(T, 1), "An_mm2": An}))
        if not tension_only:
            comp = M.compression_allowable(sec, fy, L_diag, L_diag, wind_eq=True, secondary=True)
            if comp.get("ok") is None:
                rows.append(_mrow(lab, "compression 6.6", {"ok": None, "note": comp.get("note"), "clause": comp.get("clause")}))
            else:
                rows.append(_mrow(lab, "compression 6.6 (both diagonals active)", M._rec(T, comp["Pa_N"], comp["clause"], comp["cite"],
                                                                                        allowable_increase=comp["allowable_increase"])))
    dcs = [r["dc"] for r in rows if isinstance(r.get("dc"), (int, float))]
    return {"id": "%s-%s" % (bid, sec["label"]), "type": "X-bracing (%d bays x %d sides), %s, %s" % (n_bays, n_sides, sec["label"],
                                                                                              "tension diagonals only (the compression diagonal is assumed buckled, IS 801 6.6.2 secondary member)" if tension_only else "both diagonals"),
            "checks": rows, "dc": max(dcs) if dcs else None, "value": max(F for _, F in F_by_case), "limit": None,
            "ok": (None if any(r.get("ok") is None for r in rows) else all(r.get("ok") for r in rows)),
            "forces_N": {lab: F for lab, F in F_by_case}, "note": note,
            "clause": "IS 801 6.1 / 6.6 / 7.5; IS 875-3 Table 5 (theta 90); IS 1893 6.4.2 (R 1)",
            "capacity_basis": "IS801_allowable", "allowable_increase": B.INCREASE_WL_EL, "demand_level": "working"}


def longitudinal_bracing(cfg, wind, seis, fy):
    """Declared diagonal bracing in the side walls / roof for the longitudinal wind (gable) and EQ (elastic R 1) of the
    whole portal building, plus the mezzanine's own bracing when it is self-braced."""
    out = []
    lb = cfg.get("longitudinal_bracing")
    po = cfg["portal"]; He = float(po["eave_m"]); Ha = float(po["apex_m"]); w_m = sum(float(s) for s in po["spans_m"])
    if not lb:
        out.append({"id": "longitudinal-bracing", "type": "bracing", "value": None, "limit": None, "dc": None, "ok": None,
                    "clause": "IS 801 6.6 / 7.5", "note": "cfg['longitudinal_bracing'] not declared -- the gable wind / longitudinal EQ "
                                                            "load path is undesigned", "capacity_basis": "IS801_allowable", "allowable_increase": 1.0})
    else:
        gable = w_m * (He + Ha) / 2.0                                    # m2 one gable
        cpe_net = 0.7 + 0.5                                             # Table 5 theta 90: C windward +0.7, D leeward -0.5 (l/w band 1-1.5, h/w <= 0.5)
        F_w = cpe_net * wind["pd_kNm2"] * gable * 1e3
        F_e = seis["Ah"] * seis["_W"]["portal_total_N"]
        Lb = math.hypot(float(po["spacing_m"]) * 1000.0, He * 1000.0)
        cos = float(po["spacing_m"]) * 1000.0 / Lb
        out.append(_bracing_block(cfg, "longitudinal-bracing", lb, [("DL+1.0WL(gable)", F_w), ("DL+1.0EL(longitudinal)", F_e)], fy, Lb, cos,
                                  int(lb["n_braced_bays"]), 2, lb.get("note")))
    mz = cfg.get("mezzanine")
    if mz and str(mz.get("lateral")) == "own_bracing":
        mb = mz.get("bracing")
        if not mb:
            out.append({"id": "mezzanine-bracing", "type": "bracing", "value": None, "limit": None, "dc": None, "ok": None,
                        "clause": "IS 801 6.1 / 7.5", "note": "mezzanine.bracing not declared although mezzanine.lateral = own_bracing",
                        "capacity_basis": "IS801_allowable", "allowable_increase": 1.0})
        else:
            F_e = seis["Ah"] * seis["_W"]["mezz_total_N"]
            Lb = math.hypot(float(mb["bay_m"]) * 1000.0, float(mz["height_m"]) * 1000.0)
            cos = float(mb["bay_m"]) * 1000.0 / Lb
            for d in ("X", "Y"):
                out.append(_bracing_block(cfg, "mezzanine-bracing-%s" % d, mb, [("DL+IL+1.0EL(mezzanine %s)" % d, F_e)], fy, Lb, cos,
                                          int(mb["n_braced_bays_%s" % d.lower()]), 1, mb.get("note")))
    return out


# ------------------------------------------------------------------------------------------------ run
def run(cfg, root):
    po = cfg.get("portal")
    if not po:
        raise PortalError("cfg['portal'] required")
    plan = cfg.get("load_plan") or {}
    if plan.get("cfs_combinations") not in ("auto",) and not isinstance(plan.get("cfs_combinations"), list):
        raise PortalError("load_plan.cfs_combinations missing (IS 875-5 8.1 set) -- no combinations are invented")
    if plan.get("design_basis") != B.DESIGN_BASIS:
        raise PortalError("load_plan.design_basis must be IS801_WSM")
    cm = cfg["cfs_members"]
    fy = float(cm["Fy_MPa"])
    secs = {"col": _sec(cm["columns"]), "raf": _sec(cm["rafters"])}
    if po.get("knee_brace"):
        secs["kb"] = _sec(cm["knee_braces"])
    cfg["_secs"] = secs
    fr0, members0, meta0 = build_frame(po, secs)
    wind = wind_patterns(cfg)
    seis = seismic_elastic(cfg, secs, meta0)
    cfg["_W"] = seis["_W"]
    wind["Ah"] = seis["Ah"]
    extra = ()
    if cfg.get("mezzanine"):
        extra = (float(cfg["mezzanine"]["height_m"]) * 1000.0,)
    fr0, members0, meta0 = build_frame(po, secs, extra)
    cases = elementary_cases(cfg, fr0, members0, meta0, wind)
    # combinations: IS 875-5 8.1 at 1.0 with the member wind patterns as the WL references
    plan_for_combos = dict(plan, member_wind=[{"name": p["name"]} for p in wind["patterns"]], story_forces={"EL": {"1": [1, 0, 0]}},
                           snow_summary={"applicable": float(cfg["loads"].get("snow", 0.0)) > 0})
    combos = B.cfs_combinations(plan_for_combos, cfg)
    has_mezz = bool(cfg.get("mezzanine"))
    results = {}; wind_eq = {}; with_imposed = {}
    for c in combos:
        fac = {"D": c["fD"], "Lr": c["fL"] if not c.get("fS") else 0.0, "S": c.get("fS", 0.0), "mezzD": c["fD"] if has_mezz else 0.0,
               "mezzL": (c["fL"] if has_mezz else 0.0), "E": c["fE"]}
        if c["fW"] and c.get("lateral_ref") in cases:
            fac[c["lateral_ref"]] = abs(c["fW"])
        elif c["fW"]:
            continue                                                  # pattern-less wind row (WL placeholder) -- skip
        if c["fE"] and c.get("lateral_ref") != "EL":
            continue
        fr, mem, meta, sol = solve_combo(cfg, secs, cases, fac, extra)
        mf = member_forces(fr, mem, sol)
        results[c["label"]] = {"forces": mf, "reactions": sol["reactions"], "u": sol["u"], "pdelta": sol["pdelta"], "factors": fac,
                               "meta": meta}
        wind_eq[c["label"]] = bool(c["wind_eq"])
        with_imposed[c["label"]] = bool(c["fL"]) or bool(c.get("fS"))     # IS 800 11.1.4 'major load' rule for the WSM bases
    # ---- K (IS 800 Annex D, sway) ----
    Lc = meta0["He"]; Lr = meta0["raf_len_half"]
    K_ext, b1, b2 = sway_K(secs["col"]["Ix"], Lc, secs["raf"]["Ix"] / Lr, meta0["fixed_base"])
    K_int, _, b2i = sway_K(secs["col"]["Ix"], Lc, 2 * secs["raf"]["Ix"] / Lr, meta0["fixed_base"])
    # ---- member checks ----
    members = []
    groups = {"column": [l for l in members0 if l.startswith("col")], "rafter": [l for l in members0 if l.startswith("raf")]}
    for role, labs in groups.items():
        sec = secs["col" if role == "column" else "raf"]
        Lu = float(cm["columns" if role == "column" else "rafters"].get("L_unbraced_mm", 1500.0))
        rows = []
        for lab in labs:
            K = (K_int if lab.startswith("col_I") else K_ext) if role == "column" else 1.0
            fb = {cl: r["forces"][lab] for cl, r in results.items()}
            L_mem = Lc if role == "column" else Lr
            rr = check_member(cfg, role, sec, fy, fb, K, L_mem, Lu, wind_eq)
            for r in rr:
                r["member"] = lab
            rows += rr
        if sec.get("n_ply", 1) == 2:
            ic = M.interconnection_73(Lc if role == "column" else Lr, sec["ry"] / math.sqrt(2) if sec.get("ry") else sec["rx"], sec["rx"])
            sp_ = cm["columns" if role == "column" else "rafters"].get("connector_spacing_mm")
            rows.append({"combo": "-", "check": "7.3 (a) interconnection spacing", "value": sp_, "limit": ic["Smax_mm"],
                         "dc": (float(sp_) / ic["Smax_mm"]) if sp_ else None, "ok": (float(sp_) <= ic["Smax_mm"]) if sp_ else None,
                         "clause": ic["clause"], "cite": ic["cite"], "capacity_basis": "IS801_allowable", "allowable_increase": 1.0, "source": SRC})
        dcs = [r["dc"] for r in rows if isinstance(r.get("dc"), (int, float))]
        unev = [r for r in rows if r.get("ok") is None and not r.get("informational")]
        members.append({"id": "%s-%s" % (role, sec.get("designator") or sec["label"]), "role": role, "section": sec["label"],
                        "designator": sec.get("designator") or sec["label"], "n_ply": sec.get("n_ply", 1), "Fy_MPa": fy,
                        "length_mm": L_mem, "K_sway": (K_ext if role == "column" else 1.0), "K_interior": K_int if role == "column" else None,
                        "K_cite": "IS 800:2007 Annex D sway frame, beta1 %.2f (base %s), beta2 %.3f, C 1.0" % (b1, "fixed" if meta0["fixed_base"] else "pinned", b2),
                        "L_unbraced_mm": Lu, "demand_level": "working", "capacity_basis": "IS801_allowable", "design_basis": B.DESIGN_BASIS,
                        "combinations": list(results), "checks": rows, "DC": max(dcs) if dcs else None,
                        "ok": (None if unev else all(r.get("ok") is not False for r in rows)),
                        "limit_state": "IS 801:1975 working stress (is801_members)", "source": SRC})
    # ---- knee braces: pin-ended axial members (6.6 compression / 6.1 tension) ----
    if "knee_brace" in members0:
        ksec = secs["kb"]; rows = []
        Lkb = math.hypot(float(po["knee_brace"]["col_below_eave_m"]) * 1000.0, float(po["knee_brace"]["raf_from_knee_m"]) * 1000.0)
        for cl, r in results.items():
            f = r["forces"]["knee_brace"]
            Pc = max(x[0] for x in f["stations"]); Pt = max(-x[0] for x in f["stations"])
            we = wind_eq[cl]
            if Pc > 0:
                rows.append(_mrow(cl, "6.6 compression (K 1.0)", M.check_compression(ksec, fy, Pc, Lkb, Lkb, wind_eq=we,
                                                                                         braced_against_twist=(ksec.get("n_ply", 1) == 2)), {"P_N": round(Pc, 1)}))
            if Pt > 0:
                inc = B.INCREASE_WL_EL if we else 1.0
                rows.append(_mrow(cl, "6.1 tension 0.6 Fy (gross; net at the bolts per 7.5.2)", M._rec(Pt / ksec["A"], 0.6 * fy * inc, "IS 801 6.1", "F = 0.60 Fy",
                                                                                                          allowable_increase=inc), {"P_N": round(Pt, 1)}))
        dcs = [x["dc"] for x in rows if isinstance(x.get("dc"), (int, float))]
        members.append({"id": "knee-brace-%s" % (ksec.get("designator") or ksec["label"]), "role": "knee brace", "section": ksec["label"],
                        "designator": ksec.get("designator") or ksec["label"], "n_ply": ksec.get("n_ply", 1), "Fy_MPa": fy, "length_mm": Lkb,
                        "demand_level": "working", "capacity_basis": "IS801_allowable", "design_basis": B.DESIGN_BASIS,
                        "combinations": list(results), "checks": rows, "DC": max(dcs) if dcs else None,
                        "ok": (None if any(x.get("ok") is None for x in rows) else all(x.get("ok") for x in rows)),
                        "limit_state": "IS 801:1975 working stress (is801_members)", "source": SRC})
    # ---- mezzanine on independent posts: IS 801 6.6 compression members ----
    mz = cfg.get("mezzanine")
    if mz and str(mz.get("support")) == "independent_posts" and mz.get("posts"):
        ps = mz["posts"]; psec = _sec(ps)
        trib = float(ps["trib_m2"])
        PD = float(mz["D_kNm2"]) * trib * 1e3; PL = float(mz["L_kNm2"]) * trib * 1e3
        Lp = float(mz["height_m"]) * 1000.0
        rows = []
        for lab, P in (("DL", PD), ("DL+IL", PD + PL)):
            r = M.check_compression(psec, fy, P, Lp, Lp, braced_against_twist=(psec.get("n_ply", 1) == 2))
            rows.append(_mrow(lab, "6.6 axial (K 1.0 pinned ends)", r, {"P_N": round(P, 1)}))
        dcs = [r["dc"] for r in rows if isinstance(r.get("dc"), (int, float))]
        members.append({"id": "mezzanine-post-%s" % (psec.get("designator") or psec["label"]), "role": "mezzanine post", "section": psec["label"],
                        "designator": psec.get("designator") or psec["label"], "n_ply": psec.get("n_ply", 1), "Fy_MPa": fy, "length_mm": Lp,
                        "demand_level": "working", "capacity_basis": "IS801_allowable", "design_basis": B.DESIGN_BASIS,
                        "combinations": ["DL", "DL+IL"], "checks": rows, "DC": max(dcs) if dcs else None,
                        "ok": (None if any(r.get("ok") is None for r in rows) else all(r.get("ok") for r in rows)),
                        "note": "mezzanine floor on independent cold-formed posts (pinned); its seismic weight (D + Table 10 share of IL) "
                                "is applied to the portal at the mezzanine level (elastic, R 1.0); mezzanine joists per cfs_members.joists",
                        "limit_state": "IS 801:1975 working stress (is801_members)", "source": SRC})
    # ---- connections ----
    conns = []
    cn = cfg.get("cfs_connections_spec") or {}
    for key, node_fn in (("knee", lambda meta: meta["top_nodes"]), ("apex", lambda meta: meta["apex_nodes"])):
        spec = cn.get(key)
        if not spec:
            conns.append({"id": key, "type": "bolted gusset", "value": None, "limit": None, "dc": None, "ok": None,
                          "clause": "IS 801 7.5", "note": "cfs_connections_spec.%s (bolt rows/cols/pitch/gauge/d) not declared" % key,
                          "capacity_basis": "IS801_allowable", "allowable_increase": 1.0})
            continue
        worst = None
        for cl, r in results.items():
            meta = r["meta"]
            # forces at the joint: take the rafter end at the joint (max over the joint nodes)
            for lab, mf in r["forces"].items():
                if not lab.startswith("raf"):
                    continue
                st = mf["stations"]
                cand = st[0] if key == "knee" and lab.endswith("L") else (st[-1] if key == "knee" else (st[-1] if lab.endswith("L") else st[0]))
                P, V, Mz = cand
                bg = bolt_group_75(fy, secs["raf"]["t"], spec, abs(Mz), abs(V), abs(P), wind_eq[cl], secs["raf"].get("n_ply", 1))
                # governing combination by the force checks (bearing / bolt shear / net section); 7.5.1 is geometry only
                fd = max((v["dc"] for k, v in bg["checks"].items() if not k.startswith("7.5.1") and isinstance(v.get("dc"), (int, float))), default=0.0)
                bg["dc_force"] = fd
                if worst is None or fd > worst[1]["dc_force"]:
                    worst = (cl, bg, (P, V, Mz), lab)
        cl, bg, (P, V, Mz), lab = worst
        conns.append({"id": key + "-bolt-group", "type": "bolted gusset (%dx%d M%d, %s)" % (spec["rows"], spec["cols"], spec["d_mm"], lab),
                      "checks": [_mrow(cl, k, v) for k, v in bg["checks"].items()], "value": bg["F_bolt_max_N"], "limit": None,
                      "dc": bg["dc"], "ok": bg["ok"], "governing_combo": cl, "demand": {"P_N": P, "V_N": V, "M_Nmm": Mz},
                      "clause": "IS 801 7.5 (%s)" % bg["method"], "capacity_basis": "IS801_allowable",
                      "allowable_increase": bg["allowable_increase"], "demand_level": "working"})
    base = cn.get("base")
    if base:
        worst = None
        for cl, r in results.items():
            for t, R_ in r["reactions"].items():
                bc = base_check(cfg, base, R_, wind_eq[cl], with_imposed.get(cl, False))
                if worst is None or (bc["dc"] or 0) > (worst[1]["dc"] or 0):
                    worst = (cl, bc, t)
        cl, bc, t = worst
        conns.append({"id": "column-base", "type": "base plate %sx%sx%s, %d anchors M%d" % (base["B_mm"], base["L_mm"], base["t_plate_mm"], base["anchors"]["n_total"], base["anchors"]["d_mm"]),
                      "checks": [_mrow(cl, k, v) for k, v in bc["checks"].items()], "value": bc["reactions"]["V_N"], "limit": None,
                      "dc": bc["dc"], "ok": bc["ok"], "governing_combo": cl, "reactions": bc["reactions"], "T_uplift_N": bc["T_total_N"],
                      "clause": "IS 800:2007 11.6.2 / 11.4.1 (c) working stress (11.1.4 increases); concrete bearing EOR input", "capacity_basis": "IS800_WSM",
                      "allowable_increase": 1.0, "demand_level": "working"})
    else:
        conns.append({"id": "column-base", "type": "base", "value": None, "limit": None, "dc": None, "ok": None, "clause": "IS 800 11.6.2",
                      "note": "cfs_connections_spec.base not declared", "capacity_basis": "IS800_WSM", "allowable_increase": 1.0})
    conns += longitudinal_bracing(cfg, wind, seis, fy)
    # ---- sway / drift ----
    He = meta0["He"]
    sway_w = 0.0; sway_e = 0.0; gov_w = None
    for cl, r in results.items():
        d = max(abs(r["u"][t][0]) for t in r["meta"]["top_nodes"])
        if r["factors"].get("E") and not any(k.startswith("WM") for k in r["factors"]):
            sway_e = max(sway_e, d)
        elif any(r["factors"].get(k) for k in r["factors"] if k.startswith("WM")):
            if d > sway_w:
                sway_w, gov_w = d, cl
    Hw = max((abs(sum(R_[0] for R_ in r["reactions"].values())) for cl, r in results.items()
              if any(k.startswith("WM") and r["factors"].get(k) for k in r["factors"]) and r["factors"].get("D") == 1.0), default=0.0)
    Heq = max((abs(sum(R_[0] for R_ in r["reactions"].values())) for cl, r in results.items() if r["factors"].get("E")), default=0.0)
    drift = [{"storey": 1, "dir": "X", "drift": sway_e / He, "limit": 0.004, "value": sway_e / He, "sway_mm": sway_e, "dc": (sway_e / He) / 0.004, "ok": sway_e / He <= 0.004,
              "clause": "IS 1893 7.11.1.1: storey drift under VB (gamma 1.0, R 1.0 elastic) <= 0.004 h", "load": "DL+1.0EL"},
             {"storey": 1, "dir": "X", "drift": sway_w / He, "limit": 1.0 / 150.0, "value": sway_w / He, "sway_mm": sway_w, "dc": (sway_w / He) / (1.0 / 150.0),
              "ok": sway_w / He <= 1.0 / 150.0, "clause": "IS 800:2007 Table 6 (read-only): industrial building, no cranes, column, elastic cladding: Height/150 (1.0 W)",
              "load": gov_w}]
    lateral = {"system": "all-CFS portal (elastic, R 1.0)", "R": 1.0, "R_cite": seis["R_cite"], "seismic_basis": "elastic_R1", "statement": STATEMENT,
               "seismic_summary": {k: v for k, v in seis.items() if not k.startswith("_")}, "seismic_analysis": {"method": "ESM (IS 1893 7.6; regular, h < 15 m, Zone II)"},
               "members": [{"id": m["id"], "role": m["role"], "section": m["designator"], "n": len(groups.get(m["role"], [1])), "DC": m["DC"],
                            "governing_combo": max(((r["combo"], r["dc"]) for r in m["checks"] if isinstance(r.get("dc"), (int, float))), key=lambda x: x[1])[0] if m["DC"] else None}
                           for m in members],
               "connections": [{"id": c["id"], "type": c["type"], "DC": c.get("dc"), "not_evaluated": [k["check"] for k in c.get("checks", []) if k.get("ok") is None]}
                               for c in conns],
               "drift_table": drift, "drift_max": sway_e / He, "load_combinations_n": len(results), "status": None,
               "wind_vs_eq": {"H_base_wind_kN": Hw / 1e3, "H_base_eq_kN": Heq / 1e3, "VB_frame_kN": seis["VB_frame_kN"],
                              "eave_sway_wind_mm": sway_w, "eave_sway_eq_mm": sway_e,
                              "governing": "wind" if Hw >= Heq else "seismic", "governing_wind_pattern": gov_w},
               "capacity_design": {"system": "all-CFS portal", "R": 1.0, "n_checks": 0, "n_fail": 0, "n_not_evaluated": 0,
                                   "note": "IS 800 Section 12 not applicable (elastic R 1.0 design, no ductility claimed)"},
               "demand_level": "working", "capacity_basis": "IS801_allowable", "vendored_commit": india_cfs_env.vendored_commit(),
               "pdelta": {cl: r["pdelta"] for cl, r in results.items()}}
    # frame status = member + connection + drift checks (no HR authority here)
    reasons = []
    for m in members:
        if m["ok"] is not True:
            reasons += ["%s: %s / %s dc %s ok %s" % (m["id"], r["combo"], r["check"], r.get("dc"), r.get("ok")) for r in m["checks"] if r.get("ok") is not True][:10]
    for d in drift:
        if not d["ok"]:
            reasons.append("drift %s: %.5f > %.5f (%s)" % (d["load"], d["drift"], d["limit"], d["clause"]))
    lateral["status"] = {"status": "complete" if not reasons else "partial", "reasons": reasons, "n_reasons": len(reasons),
                         "authority": "india_cfs_portal (all-CFS elastic portal: IS 801 members + drift)"}
    combos_out = [c for c in combos if c["label"] in results]
    return {"members": members, "connections": conns, "lateral_summary": lateral, "wind_summary": wind, "seismic_summary": lateral["seismic_summary"],
            "combinations": combos_out, "results_by_combo": {cl: {"forces": {l: {k: v for k, v in f.items() if k != "stations"} for l, f in r["forces"].items()},
                                                                  "reactions": r["reactions"], "pdelta": r["pdelta"]} for cl, r in results.items()},
            "K": {"exterior": K_ext, "interior": K_int, "beta1": b1, "beta2_ext": b2, "beta2_int": b2i}, "statement": STATEMENT,
            "frame_geometry": {"units": "mm", "nodes": {str(t): [x, y] for t, (x, y) in fr0.nodes.items()},
                               "elements": [[str(e[0]), str(e[1]), e[4]] for e in fr0.elems],
                               "supports": {str(t): v for t, v in fr0.fix.items()},
                               "spacing_mm": float(po["spacing_m"]) * 1000.0, "n_frames": int(po.get("n_frames") or 1)}}
