"""india_cfs_members.py -- IS 801:1975 design of the cold-formed GRAVITY / WIND members of an India CFS job (D3 / D5):
wall studs (IS 801 8.1 sheathing-braced, 6.7 combined), floor / roof joists, purlins and girts.

Loads: IS 875 (Part 1 / 2) gravity, IS 875 (Part 3) pressures (pd at the member height x (Cpe - Cpi)), combined with the
IS 875 (Part 5) cl. 8.1 working-stress set from india_cfs_basis.cfs_combinations (factor 1.0; +33 1/3 % allowable and
0.75 f effective widths for the wind / EQ rows, IS 801 6.1.2 / 5.2.1.1).  Every capacity slot carries capacity_basis =
"IS801_allowable" and the allowable_increase actually applied.  Units: N, mm, MPa in / out (kgf/cm2 inside is801_members).

cfg['cfs_members'] = {
   Fy_MPa, grade_cite,
   studs:  {section, n_ply, spacing_mm, height_mm, bearing (bool), axial_N_per_stud (declared reaction when bearing),
            sheathing {both_faces, a_mm, Kw_N_per_mm, source}, cladding_kNm2, Cpe_windward, Cpe_leeward, Cpi},
   joists: {section, n_ply, spacing_mm, span_mm, bearing_mm, compression_flange_restrained, deflection_limit_ratio},
   purlins: {section, n_ply, spacing_mm, span_mm, roof_pitch_deg, L_unbraced_mm, bearing_mm},
   girts:   {section, n_ply, spacing_mm, span_mm, L_unbraced_mm} }
"""
from __future__ import annotations
import math

import india_cfs_env  # noqa: F401
import is811_sections as S
import is801_members as M
import india_cfs_basis as B

E_MPA = M.E_MPA


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


def _wind_pd(cfg, z_m):
    """pd (kN/m2) at height z from load_plan.wind_summary (IS 875-3 7.2), interpolated on the storey table."""
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


def _member_record(role, spec, sec, fy, combos, checks_by_combo, extra=None):
    dcs = [c["dc"] for c in checks_by_combo if isinstance(c.get("dc"), (int, float))]
    unevaluated = [c for c in checks_by_combo if c.get("ok") is None and not c.get("informational")]
    rec = {"id": "%s-%s" % (role, sec.get("designator") or sec["label"]), "role": role, "section": sec["label"],
           "designator": sec.get("designator") or sec["label"], "n_ply": sec.get("n_ply", 1), "Fy_MPa": fy,
           "spacing_mm": spec.get("spacing_mm"), "length_mm": spec.get("span_mm") or spec.get("height_mm"),
           "demand_level": "working", "capacity_basis": "IS801_allowable", "design_basis": B.DESIGN_BASIS,
           "combinations": [c["label"] for c in combos], "checks": checks_by_combo,
           "DC": max(dcs) if dcs else None,
           "ok": (None if unevaluated else (all(c.get("ok") is not False for c in checks_by_combo) if checks_by_combo else None)),
           "limit_state": "IS 801:1975 working stress (is801_members)", "source": M.SRC}
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


# ---------------------------------------------------------------------------------------------------------------
def design_studs(cfg, storey=None):
    """Exterior wall studs of one storey (default: the tallest / ground storey): wind out of plane + axial
    (own wall weight, or the declared bearing reaction); IS 801 8.1 bracing, 6.7 combined, 6.4 shear, 6.5 crippling."""
    cm = cfg["cfs_members"]; st = cm["studs"]
    fy, cite = _grade(cfg)
    sec = _sec(st)
    H = list(cfg["geometry"]["heights_m"])
    k = storey or 1
    L = float(st.get("height_mm") or H[k - 1] * 1000.0)
    s = float(st["spacing_mm"])
    z_top = sum(H[:k])
    pd = _wind_pd(cfg, z_top)
    ws = ((cfg.get("load_plan") or {}).get("wind_summary") or {})
    cpe_w = st.get("Cpe_windward", (ws.get("Cpe_X") or {}).get("windward", 0.7))
    cpe_l = st.get("Cpe_leeward", (ws.get("Cpe_X") or {}).get("leeward", -0.5))
    cpi = float(st.get("Cpi", 0.2))
    p_in = (cpe_w + cpi) * pd            # kN/m2 pressure inward (windward wall, internal suction)
    p_out = (abs(cpe_l) + cpi) * pd      # suction outward (leeward wall, internal pressure)
    p = max(p_in, p_out)
    w = p * 1e-3 * s                     # N/mm  (kN/m2 -> N/mm2 x mm)
    Mw = w * L ** 2 / 8.0; Vw = w * L / 2.0
    clad = float(st.get("cladding_kNm2", 0.5)) * 1e-3 * s * L        # N own weight of one stud strip (wall + cladding)
    P_D = clad + (float(st.get("axial_N_per_stud", 0.0)) if st.get("bearing") else 0.0)
    P_L = float(st.get("axial_live_N_per_stud", 0.0)) if st.get("bearing") else 0.0
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
                             M.web_crippling_65(sec, fy, V + P, float(st.get("bearing_mm", sec["b"])), end=True,
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
    Ix = sec["Ix"]
    defl = 5.0 * w * L ** 4 / (384.0 * E_MPA * Ix)
    crit = st.get("deflection_limit_ratio")
    rows.append({"combo": "DL+1.0WL (service)", "check": "deflection (information)", "value": round(defl, 2),
                 "limit": (L / float(crit)) if crit else None, "dc": (defl / (L / float(crit))) if crit else None,
                 "ok": (defl <= L / float(crit)) if crit else None,
                 "clause": "IS 801 5.1 (no limit; 'conventional methods'); criterion %s"
                           % (("L/%s: %s" % (crit, st.get("deflection_cite"))) if crit else "not declared"),
                 "cite": "IS 801 5.1 deflection determination by conventional methods", "capacity_basis": "IS800_Table6",
                 "allowable_increase": 1.0, "source": M.SRC, "informational": not crit})
    extra = {"storey": k, "height_mm": L, "wind": {"pd_kNm2": pd, "z_m": z_top, "Cpe_windward": cpe_w, "Cpe_leeward": cpe_l, "Cpi": cpi,
                                                   "p_design_kNm2": p, "w_N_per_mm": w,
                                                   "cite": "IS 875-3 7.3.1 F = (Cpe - Cpi) A pd; Table 5 walls; 7.3.2 Cpi"},
             "axial": {"P_dead_N": P_D, "P_live_N": P_L, "bearing": bool(st.get("bearing")),
                       "note": "non-load-bearing infill (joists bear on the hot-rolled grid beams)" if not st.get("bearing")
                       else "bearing stud: declared joist reaction"},
             "bracing_8_1": s81, "braced_against_twist": braced, "grade_cite": cite,
             "clauses": ["IS 801 5.2.1.1", "6.1", "6.1.2", "6.2", "6.4.1", "6.5", "6.6.1.1", "6.6.1.2", "6.7", "8.1"]}
    return _member_record("stud", st, sec, fy, combos, rows, extra)


def design_joists(cfg):
    """Floor joists (simply supported between the hot-rolled grid beams): D + partitions + IL; bending on the
    effective section (compression flange restrained by the deck when declared), 6.4 shear, 6.5 crippling,
    deflection vs the declared criterion."""
    cm = cfg["cfs_members"]; jt = cm["joists"]
    fy, cite = _grade(cfg)
    sec = _sec(jt)
    ld = cfg["loads"]
    span = float(jt["span_mm"]); s = float(jt["spacing_mm"])
    wD = (float(ld["D_floor"]) + float(ld.get("partition_design_kNm2", 0.0))) * 1e-3 * s     # N/mm
    wL = float(ld["L_floor"]) * 1e-3 * s
    rows = []
    combos = [c for c in B.cfs_combinations(cfg.get("load_plan"), cfg) if not c.get("lateral_ref") and not c.get("fS")]
    restr = bool(jt.get("compression_flange_restrained", True))
    for c in combos:
        w = c["fD"] * wD + c["fL"] * wL
        Mx = w * span ** 2 / 8.0; V = w * span / 2.0
        b = M.bending_allowable(sec, fy, float(jt.get("L_unbraced_mm", span)), Cb=1.0, compression_flange_restrained=restr)
        rows.append(_row(c["label"], "6.1/6.2/6.3 bending", M._rec(Mx, b["Ma_Nmm"], b["clause"], b["cite"], allowable_increase=1.0),
                         {"M_Nmm": round(Mx, 1), "Fb_MPa": _rnd(b["Fb_MPa"]), "Sx_eff_cm3": _rnd(b["Sx_eff_cm3"]), "ltb": b["ltb_clause"],
                          **({"note": b["note"]} if b.get("note") else {})}))
        rows.append(_row(c["label"], "6.4.1 web shear", M.web_shear_64(sec, fy, V), {"V_N": round(V, 1)}))
        rows.append(_row(c["label"], "6.5 web crippling (end reaction)",
                         M.web_crippling_65(sec, fy, V, float(jt.get("bearing_mm", 50.0)), end=True, back_to_back=sec.get("n_ply", 1) == 2)))
        # 6.4.3 combined bending + shear at the quarter point (M = 0.75 Mmax, V = 0.5 Vmax) for a UDL
        cb = M.web_bending_shear_643(sec, fy, 0.75 * Mx, 0.5 * V)
        rows.append(_row(c["label"], "6.4.3 web bending + shear (quarter point)", cb["combined"]))
    if sec.get("n_ply", 1) == 2:
        ic = M.interconnection_73(span, sec["ry"], sec["ry"], flexural=True, span_mm=span)
        rows.append({"combo": "-", "check": "7.3 interconnection (flexural)", "value": jt.get("connector_spacing_mm"),
                     "limit": ic["Smax_mm"], "dc": (float(jt["connector_spacing_mm"]) / ic["Smax_mm"]) if jt.get("connector_spacing_mm") else None,
                     "ok": (float(jt["connector_spacing_mm"]) <= ic["Smax_mm"]) if jt.get("connector_spacing_mm") else None,
                     "clause": ic["clause"], "cite": ic["cite"], "capacity_basis": "IS801_allowable", "allowable_increase": 1.0, "source": M.SRC})
    crit = jt.get("deflection_limit_ratio")
    defl = 5.0 * wL * span ** 4 / (384.0 * E_MPA * sec["Ix"])
    rows.append({"combo": "IL (service)", "check": "deflection under imposed load", "value": round(defl, 2),
                 "limit": (span / float(crit)) if crit else None, "dc": (defl / (span / float(crit))) if crit else None,
                 "ok": (defl <= span / float(crit)) if crit else None,
                 "clause": "IS 801 5.1 (no limit); criterion %s" % (("L/%s: %s" % (crit, jt.get("deflection_cite"))) if crit else "not declared"),
                 "cite": "IS 800:2007 Table 6 read-only (serviceability_limits_table6) when cited", "capacity_basis": "IS800_Table6",
                 "allowable_increase": 1.0, "source": M.SRC, "informational": not crit})
    extra = {"span_mm": span, "w_dead_N_per_mm": wD, "w_live_N_per_mm": wL, "grade_cite": cite,
             "clauses": ["IS 801 5.2.1.1", "6.1", "6.2", "6.3", "6.4.1", "6.4.3", "6.5", "7.3"]}
    return _member_record("joist", jt, sec, fy, combos, rows, extra)


def design_purlins(cfg, role="purlin"):
    """Roof purlins (or wall girts with role='girt'): gravity (D + Lr / snow on the projection) and wind (net roof /
    wall pressure x spacing, uplift reversal with 0.9 DL); 6.3 LTB on the unrestrained flange between sag rods."""
    cm = cfg["cfs_members"]; pu = cm[role + "s"]
    fy, cite = _grade(cfg)
    sec = _sec(pu)
    ld = cfg["loads"]
    span = float(pu["span_mm"]); s = float(pu["spacing_mm"])
    pitch = math.radians(float(pu.get("roof_pitch_deg", 0.0)))
    if role == "purlin":
        wD = (float(ld["D_roof"])) * 1e-3 * s
        wL = float(ld.get("Lr", 0.0)) * 1e-3 * s * math.cos(pitch)
        wS = float(ld.get("snow", 0.0)) * 1e-3 * s * math.cos(pitch)
        p_up = float(pu.get("wind_uplift_kNm2", 0.0))       # net (Cpe - Cpi) pd, negative = suction
        p_dn = float(pu.get("wind_pressure_kNm2", 0.0))
    else:
        wD = 0.0; wL = 0.0; wS = 0.0
        p_up = -float(pu.get("wind_suction_kNm2", 0.0)); p_dn = float(pu.get("wind_pressure_kNm2", 0.0))
    wW_up = p_up * 1e-3 * s; wW_dn = p_dn * 1e-3 * s
    Lu_top = float(pu.get("L_unbraced_top_mm", 0.0))        # top flange restrained by sheeting -> 0
    Lu_bot = float(pu.get("L_unbraced_mm", span))             # bottom flange between sag rods
    rows = []
    combos = [c for c in B.cfs_combinations(cfg.get("load_plan"), cfg) if c["fE"] == 0]
    for c in combos:
        w_grav = c["fD"] * wD + c["fL"] * wL + c.get("fS", 0.0) * wS
        w = w_grav + (c["fW"] * (wW_up if c["fW"] * wW_up < 0 or c["fD"] < 1.0 else wW_dn) if c["fW"] else 0.0)
        # wind sign: +fW with the suction pattern gives uplift, -fW the pressure pattern
        if c["fW"] > 0:
            w = w_grav + wW_up
        elif c["fW"] < 0:
            w = w_grav + wW_dn
        Mx = w * span ** 2 / 8.0; V = abs(w) * span / 2.0
        uplift = w < 0
        we = bool(c["wind_eq"])
        b = M.bending_allowable(sec, fy, Lu_bot if uplift else Lu_top, Cb=1.0, wind_eq=we,
                                compression_flange_restrained=(not uplift and Lu_top == 0.0))
        rows.append(_row(c["label"], "6.1/6.2/6.3 bending (%s)" % ("uplift, bottom flange" if uplift else "gravity"),
                         M._rec(abs(Mx), b["Ma_Nmm"], b["clause"], b["cite"], allowable_increase=b["allowable_increase"]),
                         {"M_Nmm": round(Mx, 1), "w_N_per_mm": round(w, 4), "Fb_MPa": _rnd(b["Fb_MPa"]), "ltb": b["ltb_clause"],
                          **({"note": b["note"]} if b.get("note") else {})}))
        rows.append(_row(c["label"], "6.4.1 web shear", M.web_shear_64(sec, fy, V, wind_eq=we), {"V_N": round(V, 1)}))
        rows.append(_row(c["label"], "6.5 web crippling (support)",
                         M.web_crippling_65(sec, fy, V, float(pu.get("bearing_mm", 50.0)), end=False, back_to_back=sec.get("n_ply", 1) == 2, wind_eq=we)))
    crit = pu.get("deflection_limit_ratio")
    defl = 5.0 * max(wL + wS, abs(wW_up)) * span ** 4 / (384.0 * E_MPA * sec["Ix"])
    rows.append({"combo": "service", "check": "deflection (information)", "value": round(defl, 2),
                 "limit": (span / float(crit)) if crit else None, "dc": (defl / (span / float(crit))) if crit else None,
                 "ok": (defl <= span / float(crit)) if crit else None,
                 "clause": "IS 801 5.1 (no limit); criterion %s" % (("L/%s: %s" % (crit, pu.get("deflection_cite"))) if crit else "not declared"),
                 "cite": "IS 800:2007 Table 6 read-only when cited", "capacity_basis": "IS800_Table6", "allowable_increase": 1.0, "source": M.SRC,
                 "informational": not crit})
    extra = {"span_mm": span, "loads_N_per_mm": {"dead": wD, "live": wL, "snow": wS, "wind_up": wW_up, "wind_down": wW_dn},
             "grade_cite": cite, "clauses": ["IS 801 5.2.1.1", "6.1", "6.1.2", "6.2", "6.3", "6.4.1", "6.5"]}
    return _member_record(role, pu, sec, fy, combos, rows, extra)


def design_all(cfg):
    """All declared CFS members -> list of member records."""
    cm = cfg.get("cfs_members") or {}
    out = []
    if cm.get("studs"):
        H = cfg["geometry"]["heights_m"]
        storeys = cm["studs"].get("storeys") or [1 + max(range(len(H)), key=lambda i: H[i])]
        for k in storeys:
            out.append(design_studs(cfg, storey=k))
    if cm.get("joists"):
        out.append(design_joists(cfg))
    if cm.get("purlins"):
        out.append(design_purlins(cfg, "purlin"))
    if cm.get("girts"):
        out.append(design_purlins(cfg, "girt"))
    return out
