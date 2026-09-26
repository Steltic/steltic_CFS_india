"""india_cfs_members.py -- IS 801:1975 design of the cold-formed GRAVITY / WIND members of an India CFS job (D3 / D5):
wall studs (IS 801 8.1 sheathing-braced, 6.7 combined), floor / roof joists, purlins, girts, eave struts and headers.

Loads: IS 875 (Part 1 / 2) gravity, IS 875 (Part 3) MEMBER-LEVEL pressures (member_pd: pz at the member height, Ka from
the ELEMENT tributary area (Table 4), Table 5 / Table 6 Cpe governing over every face and both wind angles, local
coefficients in the edge zones, Cpi from the opening ratio 7.3.2), combined with the IS 875 (Part 5) cl. 8.1
working-stress set from india_cfs_basis.cfs_combinations (factor 1.0; +33 1/3 % allowable and 0.75 f effective widths
for the wind / EQ rows, IS 801 6.1.2 / 5.2.1.1).  Every capacity slot carries capacity_basis = "IS801_allowable" and
the allowable_increase actually applied.  Units: N, mm, MPa in / out (kgf/cm2 inside is801_members).

cfg['cfs_members'] = {
   Fy_MPa, grade_cite,
   studs:  {section, n_ply, spacing_mm, height_mm, bearing (bool), axial_N_per_stud (declared reaction when bearing),
            sheathing {both_faces, a_mm, Kw_N_per_mm, source}, cladding_kNm2, storeys [k, ...] (default: every storey),
            zone 'all' | 'general' | 'edge', Cpe_windward / Cpe_leeward / Cpe_local (declared; never less severe than Table 5),
            Cpi + Cpi_cite (declared; else from the opening ratio)}  or a list of groups,
   joists: {section, n_ply, spacing_mm, span_mm, bearing_mm, compression_flange_restrained, deflection_limit_ratio,
            name, D_kNm2 / L_kNm2 / partition_kNm2 + L_cite (per-group loads)}  or a LIST of such groups (C14),
   purlins: {section, n_ply, spacing_mm, span_mm, roof_pitch_deg, L_unbraced_mm, bearing_mm, zone,
             point_loads [{P_kN, a_m, kind 'D'|'L', cite}] (e.g. evaporator units), wind_uplift_kNm2 / wind_pressure_kNm2
             (declared: only ever increase the derived member pressure)}  or a list of groups,
   girts:   {section, n_ply, spacing_mm, span_mm, L_unbraced_mm, zone, ...}  or a list,
   eave_struts: {section, n_ply, span_mm, P_N + P_cite (declared axial), L_unbraced_mm}  or a list (C14),
   headers: {section, n_ply, span_mm, w_dead_kN_per_m, w_live_kN_per_m, load_cite, bearing_mm, deflection_limit_ratio} or a list (C14) }
Building data for the member wind: site (Vb, k1, k2_table, k3, cyclone_belt, Kd, Kc), geometry (heights_m, plan_x_m /
plan_y_m, opening_ratio, roof_pitch_deg) or portal (eave_m, apex_m, spans_m, length_m, opening_ratio).
"""
from __future__ import annotations
import math

import india_cfs_env  # noqa: F401
import is811_sections as S
import is801_members as M
import india_cfs_basis as B
import india_wind_tables as WT

E_MPA = M.E_MPA


class MemberWindError(ValueError):
    """IS 875-3 member pressures cannot be derived (fail closed: preflight ERROR, never a 0 pressure)."""


def _sec(spec):
    n, base = S.parse_designator(spec.get("designator") or spec["section"])
    n = int(spec.get("n_ply") or n)
    return S.built_up(base, n) if n == 2 else S.props(base)


def _grade(cfg):
    cm = cfg.get("cfs_members") or {}
    fy = cm.get("Fy_MPa")
    if fy is None:
        raise ValueError("cfs_members.Fy_MPa required: IS 811 sections carry no default grade (IS 1079 / IS 801 Table 2, "
                         "declare it with a cite)")
    return float(fy), cm.get("grade_cite")


def groups(cm, key):
    """C14: a role block is one dict or a list of dicts (groups by zone / span / load)."""
    v = (cm or {}).get(key)
    if not v:
        return []
    return [g for g in (v if isinstance(v, (list, tuple)) else [v]) if isinstance(g, dict)]


def _num(v, default=0.0):
    """float(v) for a declared number; the default for None / '' (C14: no float(None) crash)."""
    if v is None or v == "":
        return default
    return float(v)


# ---------------------------------------------------------------------------------------------------------------
# C02: member-level wind (IS 875-3 7.2 / 7.3)
# ---------------------------------------------------------------------------------------------------------------
# Table 6 LOCAL coefficients (7.3.3.2), transcribed from the corpus (IS_875_Part_3_2015 Table 6, manual transcription
# 2026-09-19): {h/w band: {roof angle: (gable-end strip, eave strip beside E, eave strip beside F, ridge strip)}};
# None = '--' (Note 2: where no local coefficient is given the overall coefficient applies).  Strip width y = min(h, 0.15 w).
TABLE_6_LOCAL = {
    "le_0.5": {0: (-2.0, -2.0, -2.0, None), 5: (-1.4, -1.2, -1.2, -1.0), 10: (-1.4, -1.4, None, -1.2), 20: (-1.0, None, None, -1.2),
               30: (-0.8, None, None, -1.1), 45: (None, None, None, -1.1), 60: (None, None, None, -1.1)},
    "0.5_1.5": {0: (-2.0, -2.0, -2.0, None), 5: (-2.0, -2.0, -1.5, -1.0), 10: (-2.0, -2.0, -1.5, -1.2), 20: (-1.5, -1.5, -1.5, -1.0),
                30: (-1.0, None, None, -1.0), 45: (None, None, None, None), 60: (None, None, None, None)},
    "1.5_6": {0: (-2.0, -2.0, -2.0, None), 5: (-2.0, -2.0, -1.5, -1.0), 10: (-2.0, -2.0, -1.5, -1.2), 20: (-1.5, -1.5, -1.5, -1.2),
              30: (-1.5, None, None, None), 40: (-1.0, None, None, None), 50: (None, None, None, None), 60: (None, None, None, None)},
}
TABLE_6_LOCAL_CITE = ("IS 875 (Part 3):2015 Table 6 local coefficients (gable-end, eave and ridge strips of width y = min(h, 0.15 w)); "
                      "linear in roof angle where both bracketing rows print a value, else the printed value; Note 2 overall otherwise")


def roof_local_cpe(h_over_w, alpha_deg):
    """Most severe Table 6 local Cpe at a roof angle (None when no local value applies)."""
    if h_over_w >= 6:
        return None
    band = "le_0.5" if h_over_w <= 0.5 else ("0.5_1.5" if h_over_w <= 1.5 else "1.5_6")
    tab = TABLE_6_LOCAL[band]
    ks = sorted(tab)
    a = max(min(float(alpha_deg), ks[-1]), ks[0])
    lo = max(k for k in ks if k <= a); hi = min(k for k in ks if k >= a)
    t = 0.0 if hi == lo else (a - lo) / (hi - lo)
    vals = []
    for i in range(4):
        v1, v2 = tab[lo][i], tab[hi][i]
        if v1 is not None and v2 is not None:
            vals.append(v1 + t * (v2 - v1))
        elif v1 is not None and t < 1.0:
            vals.append(v1)
        elif v2 is not None and t > 0.0:
            vals.append(v2)
    return min(vals) if vals else None


def building_wind_geometry(cfg):
    """h (eave, m), w / l (lesser / greater plan dimension, m), roof pitch (deg), mean roof height, opening ratio."""
    po = cfg.get("portal")
    geo = cfg.get("geometry") or {}
    cm = cfg.get("cfs_members") or {}
    pur = (groups(cm, "purlins") or [{}])[0]
    if po:
        h = float(po["eave_m"]); ha = float(po.get("apex_m", h))
        w_, l_ = sum(float(s) for s in po["spans_m"]), float(po.get("length_m") or geo.get("plan_y_m") or 0.0)
        pitch = math.degrees(math.atan2(ha - h, float(po["spans_m"][0]) / 2.0))
        zr = (h + ha) / 2.0
        orat = po.get("opening_ratio", geo.get("opening_ratio"))
    else:
        H = [float(x) for x in geo.get("heights_m") or []]
        if not H or geo.get("plan_x_m") is None or geo.get("plan_y_m") is None:
            raise MemberWindError("geometry.heights_m / plan_x_m / plan_y_m required for the IS 875-3 member pressures")
        h = sum(H)
        a, b = float(geo["plan_x_m"]), float(geo["plan_y_m"])
        w_, l_ = min(a, b), max(a, b)
        pitch = _num(geo.get("roof_pitch_deg"), _num(pur.get("roof_pitch_deg"), 0.0))
        zr = h + (math.tan(math.radians(pitch)) * w_ / 4.0 if pitch else 0.0)
        orat = geo.get("opening_ratio", (cfg.get("site") or {}).get("opening_ratio"))
    if not w_ or not l_:
        raise MemberWindError("building plan dimensions for IS 875-3 Tables 5 / 6 not resolvable")
    return {"h_m": h, "w_m": w_, "l_m": max(l_, w_), "pitch_deg": pitch, "z_roof_m": zr,
            "opening_ratio": (None if orat is None else float(orat))}


def _pz(cfg, z_m):
    """pz = 0.6 Vz^2 (kN/m2) at height z: from the site record (Vb k1 k2(z) k3 k4), else the wind_summary storey table."""
    site = cfg.get("site") or {}
    if site.get("Vb") is not None and site.get("k2_table") and site.get("cyclone_belt") is not None:
        pts = sorted((float(k), float(v)) for k, v in dict(site["k2_table"]).items())
        if z_m <= pts[0][0]:
            k2 = pts[0][1]
        else:
            k2 = pts[-1][1]
            for (z1, a), (z2, b) in zip(pts, pts[1:]):
                if z1 <= z_m <= z2:
                    k2 = a + (b - a) * (z_m - z1) / (z2 - z1)
                    break
        k4 = WT.k4_required(bool(site["cyclone_belt"]), site.get("wind_structure_class"))["k4"]
        Vz = float(site["Vb"]) * _num(site.get("k1"), 1.0) * k2 * _num(site.get("k3"), 1.0) * k4
        return 0.6 * Vz ** 2 / 1000.0, {"Vz_mps": Vz, "k2": k2, "k4": k4, "basis": "site Vb k1 k2(z) k3 k4 (IS 875-3 6.3)"}
    ws = ((cfg.get("load_plan") or {}).get("wind_summary") or {})
    st = [r for r in ws.get("storeys") or [] if r.get("pz_kNm2") is not None]
    if st:
        pts = sorted((float(r["z_m"]), float(r["pz_kNm2"])) for r in st)
        for z, pz in pts:
            if z_m <= z + 1e-9:
                return pz, {"basis": "wind_summary storey pz"}
        return pts[-1][1], {"basis": "wind_summary storey pz"}
    if ws.get("pz_kNm2") is not None:
        return float(ws["pz_kNm2"]), {"basis": "wind_summary pz_kNm2"}
    raise MemberWindError("IS 875-3 pz at z = %.1f m not derivable: declare site.Vb / k2_table / cyclone_belt (6.3) -- member "
                          "wind pressures are never seeded" % z_m)


def _cpi(cfg, spec, bg):
    if (spec or {}).get("Cpi") is not None:
        return abs(float(spec["Cpi"])), "declared Cpi (%s)" % (spec.get("Cpi_cite") or "EOR")
    r = bg.get("opening_ratio")
    if r is None:
        c = WT.cpi_from_openings(0.05)
        return c["Cpi"], "opening ratio not declared (geometry.opening_ratio): %s <= 5 %% assumed, +-%.1f -- VERIFY" % (c["cite"], c["Cpi"])
    c = WT.cpi_from_openings(r)
    return c["Cpi"], "%s: opening ratio %.3f -> Cpi +-%.1f" % (c["cite"], r, c["Cpi"])


def member_pd(cfg, element_area_m2, z_m, face, zone="all", spec=None):
    """C02: IS 875-3 net design pressures on ONE cladding member (stud / purlin / girt):
        pd = max(Kd Ka Kc pz, 0.7 pz), Ka = Table 4 for the ELEMENT tributary area (spacing x span, 7.2.2.1),
        Kd = 1.0 with the local coefficients (7.2.1 Note 2);
        face 'wall': Table 5 Cpe over all four walls at theta 0 and 90 (the governing face), local Cpe in the edge strips;
        face 'roof': Table 6 Cpe over EF / GH / EG / FH at the roof pitch, Table 6 local strips;
        Cpi +- from the opening ratio (7.3.2) or declared; declared Cpe_windward / Cpe_leeward / Cpe_local never reduce.
    zone: 'general' (interior), 'edge' (local strips) or 'all' (the more severe of both, per direction).
    Returns p_in_kNm2 (towards the surface) and p_out_kNm2 (away, suction magnitude), both >= 0, with the record."""
    spec = spec or {}
    site = cfg.get("site") or {}
    bg = building_wind_geometry(cfg)
    pz, pzrec = _pz(cfg, max(float(z_m), 0.0))
    ka = WT.resolve_ka(float(element_area_m2), site.get("Ka_corpus_hit"))
    if not ka.get("found"):
        raise MemberWindError("Ka (Table 4) unresolved for A = %.1f m2: %s" % (element_area_m2, ka.get("cite")))
    Ka = float(ka["Ka"])
    cb = site.get("cyclone_belt")
    Kd = 1.0 if cb else _num(site.get("Kd"), 0.9)
    Kc = _num(site.get("Kc"), 1.0)
    hw, lw = bg["h_m"] / bg["w_m"], bg["l_m"] / bg["w_m"]
    if face == "wall":
        cps, loc = [], []
        for th in (0.0, 90.0):
            r = WT.resolve_cpe_walls(hw, lw, th, site.get("cpe_corpus_hit"))
            if r.get("found") and r.get("Cpe"):
                cps += [float(v) for v in r["Cpe"].values()]
                if r.get("Cpe_local") is not None:
                    loc.append(float(r["Cpe_local"]))
        if not cps and not (spec.get("Cpe_windward") is not None and spec.get("Cpe_leeward") is not None):
            raise MemberWindError("Table 5 wall Cpe unresolved for h/w = %.2f, l/w = %.2f and no declared Cpe_windward / "
                                  "Cpe_leeward" % (hw, lw))
        tab_cite = "IS 875-3 Table 5 (7.3.3.1), all four walls at theta 0 / 90; local Cpe in edge strips of width 0.25 w"
    elif face == "roof":
        r = WT.roof_cpe_pitched(hw, bg["pitch_deg"])
        cps = [float(r[k]) for k in ("EF", "GH", "EG", "FH")] if r.get("found") else []
        lc = roof_local_cpe(hw, bg["pitch_deg"])
        loc = [lc] if lc is not None else []
        if not cps and not (spec.get("Cpe_windward") is not None and spec.get("Cpe_leeward") is not None):
            raise MemberWindError("Table 6 roof Cpe unresolved for h/w = %.2f, roof %.1f deg" % (hw, bg["pitch_deg"]))
        tab_cite = "IS 875-3 Table 6 (7.3.3.2) EF / GH / EG / FH at %.1f deg; %s" % (bg["pitch_deg"], TABLE_6_LOCAL_CITE)
    else:
        raise ValueError("face must be 'wall' or 'roof'")
    if spec.get("Cpe_windward") is not None:
        cps.append(float(spec["Cpe_windward"]))
    if spec.get("Cpe_leeward") is not None:
        cps.append(float(spec["Cpe_leeward"]))
    if spec.get("Cpe_local") is not None:
        loc.append(float(spec["Cpe_local"]))
    cpi, cpi_basis = _cpi(cfg, spec, bg)
    cpe_pos, cpe_neg = max(cps), min(cps)
    out = {"face": face, "zone": zone, "A_m2": float(element_area_m2), "z_m": float(z_m), "pz_kNm2": pz, "pz_basis": pzrec,
           "Ka": Ka, "Ka_cite": ka.get("cite"), "Kc": Kc, "Cpe_max": cpe_pos, "Cpe_min": cpe_neg, "Cpi": cpi, "Cpi_basis": cpi_basis,
           "h_over_w": hw, "l_over_w": lw, "pitch_deg": bg["pitch_deg"]}

    def pset(kd, cneg):
        pd = max(kd * Ka * Kc * pz, 0.7 * pz)
        return pd, max(cpe_pos + cpi, 0.0) * pd, max(-cneg + cpi, 0.0) * pd
    pd_g, pin_g, pout_g = pset(Kd, cpe_neg)
    out.update(general={"Kd": Kd, "pd_kNm2": pd_g, "p_in_kNm2": pin_g, "p_out_kNm2": pout_g, "Cpe_min": cpe_neg})
    if loc:
        cl = min(min(loc), cpe_neg)
        pd_e, pin_e, pout_e = pset(1.0, cl)
        out.update(edge={"Kd": 1.0, "pd_kNm2": pd_e, "p_in_kNm2": pin_e, "p_out_kNm2": pout_e, "Cpe_local": cl})
    else:
        out["edge"] = dict(out["general"], note="no local coefficient applies (Table %s Note: overall coefficient)" % ("5" if face == "wall" else "6"))
    use = [out["general"]] if zone == "general" else ([out["edge"]] if zone == "edge" else [out["general"], out["edge"]])
    out["p_in_kNm2"] = max(u["p_in_kNm2"] for u in use)
    out["p_out_kNm2"] = max(u["p_out_kNm2"] for u in use)
    out["pd_kNm2"] = max(u["pd_kNm2"] for u in use)
    out["cite"] = ("IS 875-3 7.2 pd = max(Kd Ka Kc pz, 0.7 pz), Table 4 Ka for the element area %.1f m2 (7.2.2.1); 7.2.1 Note 2 "
                   "Kd 1.0 with local coefficients; %s; 7.3.2 Cpi; 7.3.1 F = (Cpe - Cpi) A pd" % (element_area_m2, tab_cite))
    return out


def wind_preflight(cfg) -> list:
    """C02 fail-closed: every declared stud / purlin / girt group must get IS 875-3 member pressures."""
    out = []
    cm = cfg.get("cfs_members") or {}
    for key, face in (("studs", "wall"), ("purlins", "roof"), ("girts", "wall")):
        for i, g in enumerate(groups(cm, key)):
            try:
                A = _num(g.get("spacing_mm"), 1000.0) * _num(g.get("span_mm") or g.get("height_mm"), 3000.0) / 1e6
                member_pd(cfg, A, 10.0, face, g.get("zone", "all"), g)
            except MemberWindError as ex:
                out.append(("ERROR", "cfs_members.%s[%d]: member wind pressure not derivable (IS 875-3 7.3.1): %s" % (key, i, ex)))
            except (KeyError, TypeError, ValueError) as ex:
                out.append(("ERROR", "cfs_members.%s[%d]: member wind inputs incomplete: %s" % (key, i, ex)))
    bg = None
    try:
        bg = building_wind_geometry(cfg)
    except Exception:
        pass
    if bg and bg.get("opening_ratio") is None and (groups(cm, "studs") or groups(cm, "purlins") or groups(cm, "girts")):
        out.append(("WARN", "geometry.opening_ratio not declared: member Cpi taken as +-0.2 (IS 875-3 7.3.2.1, openings <= 5 %) -- "
                            "declare the opening ratio (7.3.2.2: 5-20 % -> +-0.5)"))
    return out


def _wind_pd(cfg, z_m):
    """pd (kN/m2) at height z from load_plan.wind_summary (IS 875-3 7.2), interpolated on the storey table (frame Ka;
    kept for callers that need the storey value -- member design uses member_pd)."""
    ws = ((cfg.get("load_plan") or {}).get("wind_summary") or {})
    st = ws.get("storeys") or []
    if st:
        pts = sorted((float(r["z_m"]), float(r["pd_kNm2"])) for r in st)
        for z, pd in pts:
            if z_m <= z + 1e-9:
                return pd
        return pts[-1][1]
    if ws.get("pd_kNm2") is not None:
        return float(ws["pd_kNm2"])
    raise ValueError("load_plan.wind_summary.pd_kNm2 (IS 875-3 7.2) missing -- wind pressures are never seeded")


def _member_record(role, spec, sec, fy, combos, checks_by_combo, extra=None, tag=None):
    dcs = [c["dc"] for c in checks_by_combo if isinstance(c.get("dc"), (int, float))]
    unevaluated = [c for c in checks_by_combo if c.get("ok") is None and not c.get("informational")]
    des = sec.get("designator") or sec["label"]
    rec = {"id": "%s-%s%s" % (role, (str(tag) + "-") if tag not in (None, "") else "", des), "role": role, "section": sec["label"],
           "designator": des, "n_ply": sec.get("n_ply", 1), "Fy_MPa": fy,
           "spacing_mm": spec.get("spacing_mm"), "length_mm": spec.get("span_mm") or spec.get("height_mm"),
           "demand_level": "working", "capacity_basis": "IS801_allowable", "design_basis": B.DESIGN_BASIS,
           "combinations": [c["label"] for c in combos], "checks": checks_by_combo,
           "DC": max(dcs) if dcs else None,
           "ok": (None if unevaluated else (all(c.get("ok") is not False for c in checks_by_combo) if checks_by_combo else None)),
           "limit_state": "IS 801:1975 working stress (is801_members)", "source": M.SRC}
    if spec.get("name"):
        rec["group"] = spec["name"]
    if extra:
        rec.update(extra)
    return rec


def _rnd(x, n=2):
    return round(x, n) if isinstance(x, (int, float)) else x


def _row(label, name, r, extra=None):
    o = {"combo": label, "check": name, "value": r.get("value"), "limit": r.get("limit"), "dc": r.get("dc"), "ok": r.get("ok"),
         "clause": r.get("clause"), "cite": r.get("cite"), "allowable_increase": r.get("allowable_increase", 1.0),
         "capacity_basis": "IS801_allowable", "source": M.SRC}
    if r.get("note"):
        o["note"] = r["note"]
    if extra:
        o.update(extra)
    return o


def _defl_row(combo, check, defl, span, spec, cite):
    crit = spec.get("deflection_limit_ratio")
    return {"combo": combo, "check": check, "value": round(defl, 2),
            "limit": (span / float(crit)) if crit else None, "dc": (defl / (span / float(crit))) if crit else None,
            "ok": (defl <= span / float(crit)) if crit else None,
            "clause": "IS 801 5.1 (no limit); criterion %s" % (("L/%s: %s" % (crit, spec.get("deflection_cite"))) if crit else "not declared"),
            "cite": cite, "capacity_basis": "IS800_Table6", "allowable_increase": 1.0, "source": M.SRC,
            "informational": not crit}


# ---------------------------------------------------------------------------------------------------------------
def design_studs(cfg, storey=None, spec=None, tag=None):
    """Exterior wall studs of one storey: member-level wind out of plane (C02: element Ka, governing face, local zones)
    + axial (own wall weight, or the declared bearing reaction); IS 801 8.1 bracing, 6.7 combined, 6.4 shear, 6.5
    crippling."""
    cm = cfg["cfs_members"]; st = spec or groups(cm, "studs")[0]
    fy, cite = _grade(cfg)
    sec = _sec(st)
    H = list(cfg["geometry"]["heights_m"])
    k = storey or 1
    L = float(st.get("height_mm") or H[k - 1] * 1000.0)
    s = float(st["spacing_mm"])
    z_top = sum(H[:k])
    mw = member_pd(cfg, s * L / 1e6, z_top, "wall", st.get("zone", "all"), st)
    p = max(mw["p_in_kNm2"], mw["p_out_kNm2"])
    w = p * 1e-3 * s                     # N/mm  (kN/m2 -> N/mm2 x mm)
    Mw = w * L ** 2 / 8.0; Vw = w * L / 2.0
    clad = _num(st.get("cladding_kNm2"), 0.5) * 1e-3 * s * L        # N own weight of one stud strip (wall + cladding)
    P_D = clad + (_num(st.get("axial_N_per_stud")) if st.get("bearing") else 0.0)
    P_L = _num(st.get("axial_live_N_per_stud")) if st.get("bearing") else 0.0
    sh = st.get("sheathing") or {}
    braced = bool(sh.get("both_faces"))
    s81 = None
    if braced:
        s81 = M.wall_stud_81(sec, fy, L, float(sh["a_mm"]), float(sh["Kw_N_per_mm"]), P_D + P_L, both_faces=True)
        braced = bool(s81.get("braced_against_twist"))
    KLy = float(sh.get("a_mm")) if braced else L
    combos = [c for c in B.cfs_combinations(cfg.get("load_plan"), cfg) if c["fE"] == 0 and not c.get("fS")]
    rows = []
    for c in combos:
        P = c["fD"] * P_D + c["fL"] * P_L
        Mx = abs(c["fW"]) * Mw
        V = abs(c["fW"]) * Vw
        we = bool(c["wind_eq"])
        r = M.combined_67(sec, fy, P, Mx, L, KLy, 0.0 if braced else L, cm_case="transverse_unrestrained",
                          braced_against_twist=braced, wind_eq=we, compression_flange_restrained=braced,
                          e_side="away_from_shear_centre" if not braced else None)
        if r.get("ok") is None and "checks" not in r:
            rows.append(_row(c["label"], "6.6/6.7", {"ok": None, "note": r.get("note"), "clause": r.get("clause")}))
            continue
        for nm, ck in r["checks"].items():
            rows.append(_row(c["label"], nm, ck, {"P_N": round(P, 1), "M_Nmm": round(Mx, 1), "fa_MPa": round(r["fa_MPa"], 2),
                                                 "fb_MPa": round(r["fbx_MPa"], 2), "Cm": r["Cm"], "amplification": r.get("amplification")}))
        if V > 0:
            rows.append(_row(c["label"], "6.4.1 web shear", M.web_shear_64(sec, fy, V, wind_eq=we), {"V_N": round(V, 1)}))
            rows.append(_row(c["label"], "6.5 web crippling at track (end reaction)",
                             M.web_crippling_65(sec, fy, V + P, _num(st.get("bearing_mm"), sec["b"]), end=True,
                                                back_to_back=sec.get("n_ply", 1) == 2, wind_eq=we)))
    if s81:
        for nm, ck in s81["checks"].items():
            if nm.startswith("(d)"):
                cap = sh.get("fastener_lateral_capacity_N")
                if cap and ck.get("value") is not None:
                    ck = dict(ck, limit=float(cap), dc=ck["value"] / float(cap), ok=ck["value"] <= float(cap),
                              capacity_basis="test", note="attachment lateral capacity from the declared fastener test / product data (%s)"
                              % sh.get("fastener_source", "EOR input"))
                    rows.append(_row("8.1 bracing", nm + " vs attachment capacity", ck, {"capacity_basis": "test"}))
                    continue
                ck = dict(ck, note=(ck.get("note") or "") + " | attachment lateral capacity not declared (sheathing.fastener_lateral_capacity_N)")
            rows.append(_row("8.1 bracing", nm, ck))
    # deflection at working wind (information: IS 801 5.1 has no limit; the declared criterion is the EOR's)
    defl = 5.0 * w * L ** 4 / (384.0 * E_MPA * sec["Ix"])
    rows.append(_defl_row("DL+1.0WL (service)", "deflection (information)", defl, L, st, "IS 801 5.1 deflection determination by conventional methods"))
    extra = {"storey": k, "height_mm": L,
             "wind": {"z_m": z_top, "member_pd": mw, "p_design_kNm2": p, "w_N_per_mm": w, "cite": mw["cite"]},
             "axial": {"P_dead_N": P_D, "P_live_N": P_L, "bearing": bool(st.get("bearing")),
                       "note": "non-load-bearing infill (joists bear on the hot-rolled grid beams)" if not st.get("bearing")
                       else "bearing stud: declared joist reaction"},
             "bracing_8_1": s81, "braced_against_twist": braced, "grade_cite": cite,
             "clauses": ["IS 801 5.2.1.1", "6.1", "6.1.2", "6.2", "6.4.1", "6.5", "6.6.1.1", "6.6.1.2", "6.7", "8.1"]}
    return _member_record("stud", st, sec, fy, combos, rows, extra, tag=tag if tag is not None else "S%d" % k)


def design_joists(cfg, spec=None, tag=None):
    """Floor joists (simply supported between the hot-rolled grid beams): D + partitions + IL (per group, C14); bending
    on the effective section (compression flange restrained by the deck when declared), 6.4 shear, 6.5 crippling,
    6.4.3 web bending + shear, deflection vs the declared criterion."""
    cm = cfg["cfs_members"]; jt = spec or groups(cm, "joists")[0]
    fy, cite = _grade(cfg)
    sec = _sec(jt)
    ld = cfg["loads"]
    span = float(jt["span_mm"]); s = float(jt["spacing_mm"])
    D = _num(jt.get("D_kNm2"), _num(ld.get("D_floor")))
    part = _num(jt.get("partition_kNm2"), _num(ld.get("partition_design_kNm2")))
    Lq = _num(jt.get("L_kNm2"), _num(ld.get("L_floor")))
    wD = (D + part) * 1e-3 * s     # N/mm
    wL = Lq * 1e-3 * s
    rows = []
    combos = [c for c in B.cfs_combinations(cfg.get("load_plan"), cfg) if not c.get("lateral_ref") and not c.get("fS")]
    restr = bool(jt.get("compression_flange_restrained", True))
    for c in combos:
        w = c["fD"] * wD + c["fL"] * wL
        Mx = w * span ** 2 / 8.0; V = w * span / 2.0
        b = M.bending_allowable(sec, fy, _num(jt.get("L_unbraced_mm"), span), Cb=1.0, compression_flange_restrained=restr)
        rows.append(_row(c["label"], "6.1/6.2/6.3 bending", M._rec(Mx, b["Ma_Nmm"], b["clause"], b["cite"], allowable_increase=1.0),
                         {"M_Nmm": round(Mx, 1), "Fb_MPa": _rnd(b["Fb_MPa"]), "Sx_eff_cm3": _rnd(b["Sx_eff_cm3"]), "ltb": b["ltb_clause"],
                          **({"note": b["note"]} if b.get("note") else {})}))
        rows.append(_row(c["label"], "6.4.1 web shear", M.web_shear_64(sec, fy, V), {"V_N": round(V, 1)}))
        rows.append(_row(c["label"], "6.5 web crippling (end reaction)",
                         M.web_crippling_65(sec, fy, V, _num(jt.get("bearing_mm"), 50.0), end=True, back_to_back=sec.get("n_ply", 1) == 2)))
        # 6.4.3 combined bending + shear at the quarter point (M = 0.75 Mmax, V = 0.5 Vmax) for a UDL
        cb = M.web_bending_shear_643(sec, fy, 0.75 * Mx, 0.5 * V)
        rows.append(_row(c["label"], "6.4.3 web bending + shear (quarter point)", cb["combined"]))
    if sec.get("n_ply", 1) == 2:
        ic = M.interconnection_73(span, sec["ry"], sec["ry"], flexural=True, span_mm=span)
        rows.append({"combo": "-", "check": "7.3 interconnection (flexural)", "value": jt.get("connector_spacing_mm"),
                     "limit": ic["Smax_mm"], "dc": (float(jt["connector_spacing_mm"]) / ic["Smax_mm"]) if jt.get("connector_spacing_mm") else None,
                     "ok": (float(jt["connector_spacing_mm"]) <= ic["Smax_mm"]) if jt.get("connector_spacing_mm") else None,
                     "clause": ic["clause"], "cite": ic["cite"], "capacity_basis": "IS801_allowable", "allowable_increase": 1.0, "source": M.SRC})
    defl = 5.0 * wL * span ** 4 / (384.0 * E_MPA * sec["Ix"])
    rows.append(_defl_row("IL (service)", "deflection under imposed load", defl, span, jt,
                          "IS 800:2007 Table 6 read-only (serviceability_limits_table6) when cited: other buildings, floor, "
                          "span/300 (not susceptible to cracking) / span/360 (susceptible)"))
    extra = {"span_mm": span, "w_dead_N_per_mm": wD, "w_live_N_per_mm": wL, "grade_cite": cite,
             "loads_kNm2": {"D": D, "partition": part, "L": Lq, "L_cite": jt.get("L_cite")},
             "clauses": ["IS 801 5.2.1.1", "6.1", "6.2", "6.3", "6.4.1", "6.4.3", "6.5", "7.3"]}
    return _member_record("joist", jt, sec, fy, combos, rows, extra, tag=tag)


def _point_load_effects(pls, span, kind):
    """Max moment (N-mm) and max end shear (N) of the declared point loads of one kind on a simple span."""
    Ms, Ra, Rb = [], 0.0, 0.0
    loads = [(float(p["P_kN"]) * 1e3, float(p["a_m"]) * 1e3) for p in pls if str(p.get("kind", "D")).upper() == kind]
    for P, a in loads:
        Ra += P * (span - a) / span; Rb += P * a / span
    for x in [a for _, a in loads]:
        Ms.append(Ra * x - sum(P * (x - a) for P, a in loads if a < x))
    return (max([abs(m) for m in Ms] or [0.0]), max(Ra, Rb))


def design_purlins(cfg, role="purlin", spec=None, tag=None):
    """Roof purlins (or wall girts with role='girt'): gravity (D + Lr / snow on the projection, declared point loads)
    and member-level wind (C02: element Ka, Table 6 / Table 5 governing Cpe, local strips, Cpi from openings;
    derived on every path, declared values only increase it); 6.3 LTB on the unrestrained flange between sag rods."""
    cm = cfg["cfs_members"]; pu = spec or groups(cm, role + "s")[0]
    fy, cite = _grade(cfg)
    sec = _sec(pu)
    ld = cfg["loads"]
    span = float(pu["span_mm"]); s = float(pu["spacing_mm"])
    pitch = math.radians(_num(pu.get("roof_pitch_deg")))
    bg = building_wind_geometry(cfg)
    if role == "purlin":
        wD = _num(ld.get("D_roof")) * 1e-3 * s
        wL = _num(ld.get("Lr")) * 1e-3 * s * math.cos(pitch)
        wS = _num(ld.get("snow")) * 1e-3 * s * math.cos(pitch)
        mw = member_pd(cfg, s * span / 1e6, bg["z_roof_m"], "roof", pu.get("zone", "all"), pu)
        p_up = -max(mw["p_out_kNm2"], abs(_num(pu.get("wind_uplift_kNm2"))))      # net suction (negative = uplift)
        p_dn = max(mw["p_in_kNm2"], _num(pu.get("wind_pressure_kNm2")))
    else:
        wD = 0.0; wL = 0.0; wS = 0.0
        mw = member_pd(cfg, s * span / 1e6, bg["h_m"], "wall", pu.get("zone", "all"), pu)
        p_up = -max(mw["p_out_kNm2"], abs(_num(pu.get("wind_suction_kNm2"))))
        p_dn = max(mw["p_in_kNm2"], _num(pu.get("wind_pressure_kNm2")))
    wW_up = p_up * 1e-3 * s; wW_dn = p_dn * 1e-3 * s
    pls = pu.get("point_loads") or []
    MpD, VpD = _point_load_effects(pls, span, "D")
    MpL, VpL = _point_load_effects(pls, span, "L")
    Lu_top = _num(pu.get("L_unbraced_top_mm"), 0.0)        # top flange restrained by sheeting -> 0
    Lu_bot = _num(pu.get("L_unbraced_mm"), span)             # bottom flange between sag rods
    rows = []
    combos = [c for c in B.cfs_combinations(cfg.get("load_plan"), cfg) if c["fE"] == 0]
    for c in combos:
        w_grav = c["fD"] * wD + c["fL"] * wL + c.get("fS", 0.0) * wS
        # wind sign: +fW with the suction pattern gives uplift, -fW the pressure pattern
        w = w_grav
        if c["fW"] > 0:
            w = w_grav + wW_up
        elif c["fW"] < 0:
            w = w_grav + wW_dn
        Mp = c["fD"] * MpD + c["fL"] * MpL
        Vp = c["fD"] * VpD + c["fL"] * VpL
        Mx = w * span ** 2 / 8.0 + Mp; V = abs(w) * span / 2.0 + Vp
        uplift = Mx < 0
        we = bool(c["wind_eq"])
        b = M.bending_allowable(sec, fy, Lu_bot if uplift else Lu_top, Cb=1.0, wind_eq=we,
                                compression_flange_restrained=(not uplift and Lu_top == 0.0))
        rows.append(_row(c["label"], "6.1/6.2/6.3 bending (%s)" % ("uplift, bottom flange" if uplift else "gravity"),
                         M._rec(abs(Mx), b["Ma_Nmm"], b["clause"], b["cite"], allowable_increase=b["allowable_increase"]),
                         {"M_Nmm": round(Mx, 1), "w_N_per_mm": round(w, 4), "Fb_MPa": _rnd(b["Fb_MPa"]), "ltb": b["ltb_clause"],
                          **({"M_point_Nmm": round(Mp, 1)} if pls else {}), **({"note": b["note"]} if b.get("note") else {})}))
        rows.append(_row(c["label"], "6.4.1 web shear", M.web_shear_64(sec, fy, V, wind_eq=we), {"V_N": round(V, 1)}))
        rows.append(_row(c["label"], "6.5 web crippling (support)",
                         M.web_crippling_65(sec, fy, V, _num(pu.get("bearing_mm"), 50.0), end=False, back_to_back=sec.get("n_ply", 1) == 2, wind_eq=we)))
    defl = 5.0 * max(wL + wS, abs(wW_up), wW_dn) * span ** 4 / (384.0 * E_MPA * sec["Ix"])
    rows.append(_defl_row("service", "deflection (information)", defl, span, pu, "IS 800:2007 Table 6 read-only when cited"))
    extra = {"span_mm": span, "loads_N_per_mm": {"dead": wD, "live": wL, "snow": wS, "wind_up": wW_up, "wind_down": wW_dn},
             "wind": {"member_pd": mw, "p_uplift_kNm2": p_up, "p_down_kNm2": p_dn, "cite": mw["cite"],
                      "declared": {k: pu.get(k) for k in ("wind_uplift_kNm2", "wind_suction_kNm2", "wind_pressure_kNm2") if pu.get(k) is not None}},
             "point_loads": pls or None, "zone": pu.get("zone", "all"),
             "grade_cite": cite, "clauses": ["IS 801 5.2.1.1", "6.1", "6.1.2", "6.2", "6.3", "6.4.1", "6.5"]}
    return _member_record(role, pu, sec, fy, combos, rows, extra, tag=tag)


def design_eave_strut(cfg, spec, tag=None):
    """C14: eave strut -- the longitudinal strut at the eave carrying the declared axial force (gable wind / EQ into the
    bracing, P_N + P_cite) with its own-weight bending; IS 801 6.6 / 6.7 with the 6.1.2 increase (W / EL force)."""
    fy, cite = _grade(cfg)
    sec = _sec(spec)
    L = float(spec["span_mm"])
    if spec.get("P_N") is None:
        raise ValueError("cfs_members.eave_struts: declared axial force P_N (+ P_cite) required -- the strut force of the "
                         "longitudinal bracing load path")
    P = float(spec["P_N"])
    wsw = (sec.get("mass_kg_m") or 0.0) * 9.80665 / 1000.0 + _num(spec.get("w_dead_kN_per_m"))
    Mx = wsw * L ** 2 / 8.0
    Lu = _num(spec.get("L_unbraced_mm"), L)
    r = M.combined_67(sec, fy, P, Mx, L, Lu, Lu, cm_case="transverse_unrestrained",
                      braced_against_twist=(sec.get("n_ply", 1) == 2) or bool(spec.get("braced_against_twist")), wind_eq=True)
    rows = []
    lab = "DL+1.0WL/EL (strut)"
    if "checks" not in r:
        rows.append(_row(lab, "6.6/6.7", {"ok": None, "note": r.get("note"), "clause": r.get("clause")}))
    else:
        for nm, ck in r["checks"].items():
            rows.append(_row(lab, nm, ck, {"P_N": round(P, 1), "M_Nmm": round(Mx, 1), "fa_MPa": round(r["fa_MPa"], 2),
                                           "fb_MPa": round(r["fbx_MPa"], 2)}))
    combos = [{"label": lab}]
    return _member_record("eave_strut", spec, sec, fy, combos, rows,
                          {"span_mm": L, "P_N": P, "P_cite": spec.get("P_cite"), "grade_cite": cite,
                           "clauses": ["IS 801 6.1.2", "6.6.1.1", "6.6.1.2", "6.7"]}, tag=tag)


def design_header(cfg, spec, tag=None):
    """C14: header over a wall opening -- simply supported beam under the declared dead / imposed line loads."""
    fy, cite = _grade(cfg)
    sec = _sec(spec)
    span = float(spec["span_mm"])
    if spec.get("w_dead_kN_per_m") is None:
        raise ValueError("cfs_members.headers: w_dead_kN_per_m (+ w_live_kN_per_m, load_cite) required")
    wD = float(spec["w_dead_kN_per_m"]); wL = _num(spec.get("w_live_kN_per_m"))
    combos = [c for c in B.cfs_combinations(cfg.get("load_plan"), cfg) if not c.get("lateral_ref") and not c.get("fS")]
    rows = []
    restr = bool(spec.get("compression_flange_restrained", False))
    for c in combos:
        w = c["fD"] * wD + c["fL"] * wL
        Mx = w * span ** 2 / 8.0; V = w * span / 2.0
        b = M.bending_allowable(sec, fy, _num(spec.get("L_unbraced_mm"), span), Cb=1.0, compression_flange_restrained=restr)
        rows.append(_row(c["label"], "6.1/6.2/6.3 bending", M._rec(Mx, b["Ma_Nmm"], b["clause"], b["cite"], allowable_increase=1.0),
                         {"M_Nmm": round(Mx, 1), "Fb_MPa": _rnd(b["Fb_MPa"]), "ltb": b["ltb_clause"],
                          **({"note": b["note"]} if b.get("note") else {})}))
        rows.append(_row(c["label"], "6.4.1 web shear", M.web_shear_64(sec, fy, V), {"V_N": round(V, 1)}))
        rows.append(_row(c["label"], "6.5 web crippling (end reaction)",
                         M.web_crippling_65(sec, fy, V, _num(spec.get("bearing_mm"), 50.0), end=True, back_to_back=sec.get("n_ply", 1) == 2)))
        rows.append(_row(c["label"], "6.4.3 web bending + shear (quarter point)", M.web_bending_shear_643(sec, fy, 0.75 * Mx, 0.5 * V)["combined"]))
    defl = 5.0 * wL * span ** 4 / (384.0 * E_MPA * sec["Ix"])
    rows.append(_defl_row("IL (service)", "deflection under imposed load", defl, span, spec, "IS 800:2007 Table 6 read-only when cited"))
    return _member_record("header", spec, sec, fy, combos, rows,
                          {"span_mm": span, "w_dead_N_per_mm": wD, "w_live_N_per_mm": wL, "load_cite": spec.get("load_cite"),
                           "grade_cite": cite, "clauses": ["IS 801 6.1", "6.2", "6.3", "6.4.1", "6.4.3", "6.5"]}, tag=tag)


def _tag(g, i, n):
    return g.get("name") or (("G%d" % (i + 1)) if n > 1 else None)


def design_all(cfg):
    """All declared CFS members -> list of member records (groups per role, C14)."""
    cm = cfg.get("cfs_members") or {}
    out = []
    H = (cfg.get("geometry") or {}).get("heights_m") or []
    st_groups = groups(cm, "studs")
    for i, st in enumerate(st_groups):
        # C02: every storey by default (the top storey carries the highest pz; equal storeys no longer pick storey 1 only)
        storeys = st.get("storeys") or list(range(1, len(H) + 1))
        for k in storeys:
            t = "S%d" % int(k)
            if len(st_groups) > 1:
                t = "%s-%s" % (_tag(st, i, len(st_groups)), t)
            out.append(design_studs(cfg, storey=int(k), spec=st, tag=t))
    for key, fn in (("joists", lambda g, t: design_joists(cfg, g, t)),
                    ("purlins", lambda g, t: design_purlins(cfg, "purlin", g, t)),
                    ("girts", lambda g, t: design_purlins(cfg, "girt", g, t)),
                    ("eave_struts", lambda g, t: design_eave_strut(cfg, g, t)),
                    ("headers", lambda g, t: design_header(cfg, g, t))):
        gs = groups(cm, key)
        for i, g in enumerate(gs):
            out.append(fn(g, _tag(g, i, len(gs))))
    return out
