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


def _grade(cfg, sec=None):
    """(Fy MPa, grade cite) of a member.  2026-10 first wave: a computed thin section carries its own grade in the label
    (-G350: IS 277 grade 350, Fy 350 MPa inside the IS 801 Table 2 36 kgf/mm2 row); an IS 811 section takes the job
    grade cfs_members.Fy_MPa (IS 811 prints no grade)."""
    if sec is not None and sec.get("generic") and sec.get("Fy"):
        return float(sec["Fy"]), sec.get("grade_cite")
    cm = cfg.get("cfs_members") or {}
    fy = cm.get("Fy_MPa")
    if fy is None:
        raise ValueError("cfs_members.Fy_MPa required: IS 811 sections carry no default grade (IS 1079 / IS 801 Table 2, "
                         "declare it with a cite)")
    return float(fy), cm.get("grade_cite")


def material_statement(cfg, sec) -> str:
    """Grade and coating of a member as printed in the report (review item 8: stated in every report)."""
    if sec.get("generic"):
        return sec.get("material")
    cm = cfg.get("cfs_members") or {}
    mat = cm.get("material") or ("IS 1079 hot-rolled sheet / strip (IS 801 2.1), Fy %s MPa (%s)"
                                 % (_fmt_num(cm.get("Fy_MPa")), cm.get("grade_cite") or "IS 801 Table 2"))
    coat = cm.get("coating") or "coating not declared -- IS 811 sections are formed from uncoated IS 1079 sheet: specify " \
                                "hot-dip galvanising or a paint system (IS 4180) -- design engineer"
    return "%s; %s" % (mat, coat)


def _fmt_num(v, nd=3):
    """A number without float noise (13.799999999999999 -> 13.8)."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return "-" if v is None else str(v)
    s = ("%%.%df" % nd) % float(v)
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return s if s not in ("-0", "") else "0"


# ---------------------------------------------------------------------------------------------------------------
# 2026-10 first wave: restraint basis, IS 801 8.2 bracing of channels / zeds, sag rods, non-permanent dead loads
# ---------------------------------------------------------------------------------------------------------------
BRACE_TYPES = {"sag_rods": "sag-rod line(s)", "bridging": "bridging line(s)", "fly_braces": "fly brace(s)",
               "straps": "strap / flat bracing line(s)", "blocking": "solid blocking line(s)"}
IS801_82_CITE = ("IS 801:1975 8.2 (channel and Z-sections used as beams): 8.2.1 braces at the ends and at intervals not "
                 "greater than one-quarter of the span; 8.2.2 each intermediate brace (top and bottom flange) resists "
                 "P1 = 1.5 K' x the load within 0.5 a each side (uniform load), 1.0 K' P within 0.3 a and (1 - x/a) P K' "
                 "for 0.3 a < x <= a (concentrated loads); end braces one-half; K' = m/d (channels, m per 7.3), Ixy/Ix (Z); "
                 "8.2.3 the bracing interval a replaces L in 6.3")
IS801_82_SCOPE = ("8.2 applies only when neither flange is connected to deck or sheathing (8.2 (a)); with one flange "
                  "sheeted 'bracing may or may not be needed' (8.2 footnote) -- the 8.2.1 spacing is shown for reference "
                  "and the 8.2.2 force is used to size the declared braces")
ROD_PITCH = {10: 1.5, 12: 1.75, 16: 2.0, 20: 2.5, 24: 3.0}          # ISO 261 coarse pitch (mm) -- VERIFY
ROD_CITE = ("sag rod: IS 2062 E250 round bar threaded at the ends (fy 250, fu 410 MPa unless declared); IS 800:2007 "
            "11.2.1 working stress: f_at = 0.6 fy on the gross area and 0.69 Tdn on the thread root, Tdn = 0.9 An fu / "
            "gamma_m1 (6.3.1, gamma_m1 1.25, Table 5); root area at the bottom of the threads (IS 800 10.3.5), "
            "d3 = d - 1.2269 p (ISO 724 basic profile, coarse pitch -- VERIFY); no 11.1.4 increase (wind is the major load)")


def _flange_names(role):
    """(sheeted flange, free flange) names by member role."""
    return ("outer", "inner") if role == "girt" else ("top", "bottom")


def bracing_basis(spec, span, role="purlin"):
    """Declared bracing of the free flange of a purlin / girt / joist (2026-10 first wave, review item 3).
    spec['bracing'] = {type: sag_rods | bridging | fly_braces | straps | blocking, lines: n, spacing_mm (optional,
    default span / (lines + 1)), rod_dia_mm, rod_fy_MPa, rod_fu_MPa, min_rod_dia_mm, members_per_line, capacity_N,
    capacity_source, note}; the legacy spec['sag_rods'] = <number of lines> (PEB secondary jobs) is read as sag rods.
    No declared bracing -> the free flange is unbraced over the span (an L_unbraced_mm without a bracing system is not
    used and the record says so)."""
    span = float(span)
    br = spec.get("bracing")
    rec = {"declared": False, "type": None, "type_text": None, "lines": 0, "spacing_mm": span, "source": None, "spec": None,
           "note": None}
    sr = spec.get("sag_rods")
    if isinstance(br, dict) and str(br.get("type") or "").lower() not in ("", "none"):
        typ = str(br["type"]).lower()
        lines = int(_num(br.get("lines"), 0))
        a = _num(br.get("spacing_mm"), 0.0) or (span / (lines + 1) if lines else 0.0)
        if a and not lines:
            lines = max(int(round(span / a)) - 1, 0)
        if a > 0:
            rec.update(declared=True, type=typ, lines=lines, spacing_mm=min(a, span), source="cfg bracing", spec=dict(br))
    elif isinstance(sr, (int, float)) and not isinstance(sr, bool) and sr > 0:
        lines = int(sr)
        rec.update(declared=True, type="sag_rods", lines=lines, spacing_mm=span / (lines + 1),
                   source="cfg sag_rods = %d line(s)" % lines, spec={"type": "sag_rods", "lines": lines})
    Lu = spec.get("L_unbraced_mm")
    if rec["declared"]:
        if Lu not in (None, "") and float(Lu) > rec["spacing_mm"] + 1e-6:
            rec["note"] = ("declared L_unbraced_mm %.0f mm is longer than the bracing interval %.0f mm: the longer length "
                           "is used (conservative)" % (float(Lu), rec["spacing_mm"]))
            rec["spacing_mm"] = float(Lu)
        rec["type_text"] = BRACE_TYPES.get(rec["type"], rec["type"])
    else:
        if Lu not in (None, "") and float(Lu) < span - 1e-6:
            rec["note"] = ("L_unbraced_mm %.0f mm declared without a bracing system (bracing / sag_rods): not used -- the "
                           "free flange is checked unbraced over the span %.0f mm" % (float(Lu), span))
    return rec


def restraint_text(flange, restrained, L_mm=None, brace=None, span=None, basis=None):
    """One-line compression-flange restraint statement printed with every bending / interaction check."""
    if restrained:
        return "compression flange: %s, continuously restrained by %s" % (flange, basis or "the sheeting fastened to it")
    if brace and brace.get("declared"):
        return ("compression flange: %s (free), braced at a = %.0f mm by %d %s (IS 801 8.2.3: a replaces L in 6.3)"
                % (flange, brace["spacing_mm"], brace["lines"], brace.get("type_text") or brace.get("type")))
    return "compression flange: %s (free), UNBRACED over %.0f mm (no bracing declared)" % (flange, float(L_mm or span or 0.0))


def k_prime_82(sec):
    """IS 801 8.2.2 K' = m / d (channels; m by the 7.3 lipped / plain channel formula) or Ixy / Ix (Z-sections);
    0 for a back-to-back pair (doubly symmetric, no twisting tendency)."""
    if sec.get("n_ply", 1) == 2 or sec.get("doubly_symmetric"):
        return 0.0, "back-to-back pair: doubly symmetric, no twisting tendency (K' = 0)"
    if sec.get("type") == "LZ":
        ixy = sec.get("Ixy")
        if ixy is None:
            return None, "Ixy not available for %s" % sec.get("label")
        return abs(ixy) / sec["Ix"], "K' = Ixy / Ix (Z-section, 8.2.2)"
    d, t = sec["h"], sec["t"]
    wf = sec["b"] - t                                    # projection of the flange from the inside face of the web
    if sec.get("c"):
        d1 = sec["c"]
        m = wf * d * t / (4.0 * sec["Ix"]) * (wf * d + 2.0 * d1 * (d - 4.0 * d1 ** 2 / (3.0 * d)))
        how = ("m = (wf d t / 4 Ix)[wf d + 2 d1 (d - 4 d1^2 / 3d)] (IS 801 7.3, lipped channel; t restored where the corpus "
               "OCR drops it -- dimensional check)")
    else:
        m = wf ** 2 / (2.0 * wf + d / 3.0)
        how = "m = wf^2 / (2 wf + d/3) (IS 801 7.3, channel without lips)"
    return m / d, "K' = m / d = %.1f / %.0f; %s" % (m, d, how)


def brace_force_82(sec, w_N_per_mm, a_mm, span_mm, point_loads=None, P_scale=1.0):
    """IS 801 8.2.2 lateral force P1 (N) on the most loaded intermediate brace and on the end brace."""
    kp, how = k_prime_82(sec)
    if kp is None:
        return {"P1_int_N": None, "P1_end_N": None, "K_prime": None, "K_prime_basis": how}
    P1u = 1.5 * kp * abs(w_N_per_mm) * a_mm
    worst = P1u
    braces = [a_mm * k for k in range(1, int(span_mm / a_mm + 1e-6)) if a_mm * k < span_mm - 1e-6]
    for xb in braces:
        pc = 0.0
        for p in point_loads or []:
            P = abs(float(p["P_kN"])) * 1e3 * P_scale
            x = abs(float(p["a_m"]) * 1e3 - xb)
            if x <= 0.3 * a_mm:
                pc += 1.0 * kp * P
            elif x <= a_mm:
                pc += (1.0 - x / a_mm) * P * kp
        worst = max(worst, P1u + pc)
    return {"P1_int_N": worst, "P1_end_N": 0.5 * worst, "P1_uniform_N": P1u, "K_prime": kp, "K_prime_basis": how,
            "n_intermediate_braces": len(braces)}


def rod_capacity(d_mm, fy=250.0, fu=410.0):
    """Working-stress tension capacity (N) of a threaded round sag rod (ROD_CITE)."""
    p = ROD_PITCH.get(int(round(d_mm)), 0.125 * d_mm)
    Ag = math.pi * d_mm ** 2 / 4.0
    d3 = d_mm - 1.226869 * p
    Ar = math.pi * d3 ** 2 / 4.0
    T1 = 0.6 * fy * Ag
    T2 = 0.69 * 0.9 * Ar * fu / 1.25
    return {"d_mm": d_mm, "pitch_mm": p, "Ag_mm2": Ag, "A_root_mm2": Ar, "T_yield_N": T1, "T_rupture_N": T2,
            "T_allow_N": min(T1, T2)}


def _members_per_line(cfg, spec, role, s_mm, br):
    """Members tied into one brace line (the rod force accumulates over them): declared members_per_line, else the
    purlins on one roof slope (portal half-span along the slope / spacing + 1) or the girts over the eave height."""
    if br.get("spec") and br["spec"].get("members_per_line"):
        return int(br["spec"]["members_per_line"]), "declared members_per_line"
    po = cfg.get("portal") or {}
    geo = cfg.get("geometry") or {}
    if role == "purlin" and po.get("spans_m"):
        pitch = math.radians(_num(spec.get("roof_pitch_deg"), 0.0))
        Ls = float(po["spans_m"][0]) / 2.0 / max(math.cos(pitch), 1e-6) * 1000.0
        return int(Ls // s_mm) + 1, "purlins on one slope: %.2f m along the slope / %.0f mm spacing + 1" % (Ls / 1000.0, s_mm)
    if role == "girt":
        h = _num(po.get("eave_m"), sum(float(x) for x in (geo.get("heights_m") or [0.0]))) * 1000.0
        if h > 0:
            return max(int(h // s_mm), 1), "girts over the %.2f m wall height at %.0f mm" % (h / 1000.0, s_mm)
    return 1, "members per brace line not derivable -- one member (declare bracing.members_per_line)"


def nonpermanent_dead(cfg, spec, collateral_kNm2=None, pv_kNm2=None):
    """Lead requirement (review item 5): named non-permanent dead components -- collateral (services hung from the
    purlins / joists) and rooftop PV.  Keyword argument > member spec key > cfg['loads'] key; default 0.
    Applied only where dead load adds to the effect (gravity combinations); excluded where the dead load resists
    (wind uplift / suction with 0.9 DL or DL)."""
    ld = cfg.get("loads") or {}
    out = {}
    for key, kw in (("collateral_kNm2", collateral_kNm2), ("pv_kNm2", pv_kNm2)):
        v = kw if kw is not None else spec.get(key, ld.get(key))
        out[key] = _num(v, 0.0)
    return out


def _with_nonpermanent(w, w_np):
    """Include the non-permanent dead line load w_np (>= 0, along gravity) only when it increases |w|."""
    if not w_np:
        return w, False
    w2 = w + w_np
    return (w2, True) if abs(w2) >= abs(w) - 1e-12 and w >= 0 else (w, False)


def geometry_rows(sec):
    """IS 801 5.2.3 / 5.2.4 flat-width and web-depth limits as check rows (computed thin sections and IS 811)."""
    rows = []
    t = sec["t"]
    fl = sec.get("flats") or {}
    if fl.get("web"):
        rows.append(("5.2.4(a) web h/t", fl["web"] / t, 150.0, "IS 801 5.2.4 (a)", "(h/t)max = 150 for unstiffened webs"))
    if fl.get("flange") and sec.get("lipped"):
        rows.append(("5.2.3(a) flange w/t (simple-lip stiffened)", fl["flange"] / t, 60.0, "IS 801 5.2.3 (a)",
                     "stiffened compression element, other edge stiffened by a simple lip: 60"))
    if fl.get("lip"):
        rows.append(("5.2.3(c) lip w/t (unstiffened)", fl["lip"] / t, 60.0, "IS 801 5.2.3 (c)", "unstiffened compression element: 60"))
    out = []
    for nm, v, lim, cl, cite in rows:
        out.append({"combo": "geometry", "check": nm, "value": round(v, 2), "limit": lim, "dc": v / lim, "ok": v <= lim + 1e-9,
                    "clause": cl, "cite": cite, "capacity_basis": "IS801_allowable", "allowable_increase": 1.0, "source": M.SRC,
                    "units": "-", "detailing": True})
    return out


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
    # the member D/C is the strength / serviceability ratio; detailing limits (IS 801 5.2.3 / 5.2.4 geometry, 8.2.1 brace
    # spacing) and the brace elements (sag rods, straps) keep their own rows and block when they fail, but do not set the
    # member D/C
    dcs = [c["dc"] for c in checks_by_combo if isinstance(c.get("dc"), (int, float)) and not c.get("informational")
           and not c.get("detailing")]
    unevaluated = [c for c in checks_by_combo if c.get("ok") is None and not c.get("informational")]
    des = sec.get("designator") or sec["label"]
    length = spec.get("span_mm") or spec.get("height_mm") or (extra or {}).get("span_mm") or (extra or {}).get("height_mm")
    rec = {"id": "%s-%s%s" % (role, (str(tag) + "-") if tag not in (None, "") else "", des), "role": role, "section": sec["label"],
           "designator": des, "n_ply": sec.get("n_ply", 1), "Fy_MPa": fy,
           "spacing_mm": spec.get("spacing_mm"), "length_mm": length,
           "demand_level": "working", "capacity_basis": "IS801_allowable", "design_basis": B.DESIGN_BASIS,
           "combinations": [c["label"] for c in combos], "checks": checks_by_combo,
           "DC": max(dcs) if dcs else None,
           "ok": (None if unevaluated else (all(c.get("ok") is not False for c in checks_by_combo if not c.get("informational"))
                                            if checks_by_combo else None)),
           "limit_state": "IS 801:1975 working stress (is801_members)", "source": M.SRC,
           # 2026-10 first wave: section family, mass and material on every record
           "section_family": sec.get("family") or ("IS 811:1987 Table %s" % sec.get("table") if sec.get("table") else "IS 811:1987"),
           "section_source": sec.get("source"),
           "mass_kg_m": (sec.get("mass_kg_m") if sec.get("mass_kg_m") is not None else None)}
    if spec.get("name"):
        rec["group"] = spec["name"]
    if extra:
        rec.update(extra)
    return rec


def _units_for(name):
    """Display units of a check row (the report converts N-mm to kN-m and N to kN)."""
    n = str(name).lower()
    if "web bending + shear" in n or "6.4.3" in n or "interaction" in n or "both faces" in n:
        return "-"
    if "bending" in n:
        return "N-mm"
    if "web shear" in n or n.startswith("stability"):
        return "MPa"
    if "crippling" in n or "pmin" in n or "brace force" in n or "sag rod" in n or "attachment capacity" in n:
        return "N"
    if "deflection" in n or "a <= amax" in n or "interconnection" in n or "spacing" in n:
        return "mm"
    if "kw" in n:
        return "N/mm"
    return "-"


def _rnd(x, n=2):
    return round(x, n) if isinstance(x, (int, float)) else x


def _row(label, name, r, extra=None):
    o = {"combo": label, "check": name, "value": r.get("value"), "limit": r.get("limit"), "dc": r.get("dc"), "ok": r.get("ok"),
         "clause": r.get("clause"), "cite": r.get("cite"), "allowable_increase": r.get("allowable_increase", 1.0),
         "capacity_basis": "IS801_allowable", "source": M.SRC, "units": _units_for(name)}
    if r.get("note"):
        o["note"] = r["note"]
    if extra:
        o.update(extra)
    return o


def _stamp_restraint(rows, text):
    """Every row carries the member's compression-flange restraint basis (rows with their own keep it)."""
    for r in rows:
        r.setdefault("restraint", text)
    return rows


def _defl_row(combo, check, defl, span, spec, cite):
    crit = spec.get("deflection_limit_ratio")
    if crit:                                     # a declared criterion makes it a real check, not information
        check = check.replace(" (information)", "")
    return {"combo": combo, "check": check, "value": round(defl, 2), "units": "mm",
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
    sec = _sec(st)
    fy, cite = _grade(cfg, sec)
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
                                                 "fb_MPa": round(r["fbx_MPa"], 2), "Cm": r["Cm"], "amplification": r.get("amplification"),
                                                 # 2026-10 second wave: KL/r of the stud (IS 801 6.6.3), report-only
                                                 "KL_r": (round(float(r["compression"]["KLr"]), 1)
                                                          if isinstance((r.get("compression") or {}).get("KLr"), (int, float)) else None)}))
        if V > 0:
            rows.append(_row(c["label"], "6.4.1 web shear", M.web_shear_64(sec, fy, V, wind_eq=we), {"V_N": round(V, 1)}))
            rows.append(_row(c["label"], "6.5 web crippling at track (end reaction)",
                             M.web_crippling_65(sec, fy, V + P, _num(st.get("bearing_mm"), sec["b"]), end=True,
                                                back_to_back=sec.get("n_ply", 1) == 2, wind_eq=we)))
    if braced:
        rtext = ("both flanges braced in the plane of the wall by the sheathing on both faces at a = %.0f mm (IS 801 8.1 "
                 "(a)-(c) met); weak-axis and torsional buckling over a" % float(sh["a_mm"]))
    elif sh.get("both_faces"):
        rtext = ("sheathing on both faces declared but IS 801 8.1 (b) / (c) not met: stud UNBRACED over its height %.0f mm "
                 "(weak-axis, torsional-flexural and lateral buckling over L)" % L)
    else:
        rtext = "no sheathing bracing declared: stud UNBRACED over its height %.0f mm" % L
    _stamp_restraint(rows, rtext)
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
    rows += geometry_rows(sec)
    _stamp_restraint(rows, rtext)
    extra = {"storey": k, "height_mm": L, "restraint_basis": {"text": rtext, "sheathing_braced": braced,
                                                              "a_mm": float(sh["a_mm"]) if braced else None},
             "material": material_statement(cfg, sec),
             "wind": {"z_m": z_top, "member_pd": mw, "p_design_kNm2": p, "w_N_per_mm": w, "cite": mw["cite"]},
             "axial": {"P_dead_N": P_D, "P_live_N": P_L, "bearing": bool(st.get("bearing")),
                       "note": "non-load-bearing infill (joists bear on the hot-rolled grid beams)" if not st.get("bearing")
                       else "bearing stud: declared joist reaction"},
             "bracing_8_1": s81, "braced_against_twist": braced, "grade_cite": cite,
             "clauses": ["IS 801 5.2.1.1", "6.1", "6.1.2", "6.2", "6.4.1", "6.5", "6.6.1.1", "6.6.1.2", "6.7", "8.1"]}
    return _member_record("stud", st, sec, fy, combos, rows, extra, tag=tag if tag is not None else "S%d" % k)


def design_joists(cfg, spec=None, tag=None, *, collateral_kNm2=None, pv_kNm2=None):
    """Floor joists (simply supported between the hot-rolled grid beams): D + partitions + IL (per group, C14); bending
    on the effective section, 6.4 shear, 6.5 crippling, 6.4.3 web bending + shear, deflection vs the declared criterion.
    2026-10 first wave: the compression (top) flange is restrained only when the job declares it
    (compression_flange_restrained: true + restraint_basis text, e.g. the floor board / deck screwed to it); otherwise
    the joist is checked unbraced over the bridging interval (spec['bracing']) or the span.  collateral_kNm2 /
    pv_kNm2 (keyword, spec or cfg['loads']) are non-permanent dead loads added to the gravity combinations."""
    cm = cfg["cfs_members"]; jt = spec or groups(cm, "joists")[0]
    sec = _sec(jt)
    fy, cite = _grade(cfg, sec)
    ld = cfg["loads"]
    span = float(jt["span_mm"]); s = float(jt["spacing_mm"])
    D = _num(jt.get("D_kNm2"), _num(ld.get("D_floor")))
    part = _num(jt.get("partition_kNm2"), _num(ld.get("partition_design_kNm2")))
    Lq = _num(jt.get("L_kNm2"), _num(ld.get("L_floor")))
    npd = nonpermanent_dead(cfg, jt, collateral_kNm2, pv_kNm2)
    wD = (D + part) * 1e-3 * s     # N/mm
    wL = Lq * 1e-3 * s
    wNP = (npd["collateral_kNm2"] + npd["pv_kNm2"]) * 1e-3 * s
    rows = []
    combos = [c for c in B.cfs_combinations(cfg.get("load_plan"), cfg) if not c.get("lateral_ref") and not c.get("fS")]
    declared = jt.get("compression_flange_restrained")
    restr = bool(declared)
    br = bracing_basis(jt, span, "joist")
    Lb = br["spacing_mm"] if br["declared"] else span
    basis = jt.get("restraint_basis") or "the floor deck / board fastened to it (declared compression_flange_restrained)"
    rtext = restraint_text("top", restr, Lb, br, span, basis=basis)
    if declared is None:
        rtext += " -- compression_flange_restrained not declared, so no deck restraint is assumed"
    zb = jt.get("zed_basis") if sec.get("type") == "LZ" else None
    for c in combos:
        w, inc_np = _with_nonpermanent(c["fD"] * wD + c["fL"] * wL, c["fD"] * wNP)
        Mx = w * span ** 2 / 8.0; V = w * span / 2.0
        b = M.bending_allowable(sec, fy, Lb, Cb=1.0, compression_flange_restrained=restr, zed_basis=zb)
        if b.get("ok") is None:
            rows.append(_row(c["label"], "6.1/6.2/6.3 bending", {"ok": None, "note": b.get("note"), "clause": b.get("clause")}))
            continue
        rows.append(_row(c["label"], "6.1/6.2/6.3 bending", M._rec(Mx, b["Ma_Nmm"], b["clause"], b["cite"], allowable_increase=1.0),
                         {"M_Nmm": round(Mx, 1), "Fb_MPa": _rnd(b["Fb_MPa"]), "Sx_eff_cm3": _rnd(b["Sx_eff_cm3"]), "ltb": b["ltb_clause"],
                          "L_unbraced_mm": 0.0 if restr else Lb, "restraint": rtext, "nonpermanent_dead_included": inc_np,
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
                     "clause": ic["clause"], "cite": ic["cite"], "capacity_basis": "IS801_allowable", "allowable_increase": 1.0, "source": M.SRC,
                     "units": "mm"})
    if not restr:
        rows += bracing_rows(cfg, jt, sec, "joist", span, s, br, w_max=max(wD + wL + wNP, 0.0), w_par=0.0,
                             sheeted=False)
    defl = 5.0 * wL * span ** 4 / (384.0 * E_MPA * sec["Ix"])
    rows.append(_defl_row("IL (service)", "deflection under imposed load", defl, span, jt,
                          "IS 800:2007 Table 6 read-only (serviceability_limits_table6) when cited: other buildings, floor, "
                          "span/300 (not susceptible to cracking) / span/360 (susceptible)"))
    rows += geometry_rows(sec)
    _stamp_restraint(rows, rtext)
    load_table = [
        {"component": "dead (permanent: deck, finishes, joist)", "kNm2": D, "kN_per_m": D * s / 1000.0, "applied": "every combination"},
        {"component": "partitions (IS 875-2 3.1.2)", "kNm2": part, "kN_per_m": part * s / 1000.0, "applied": "with dead load"},
        {"component": "collateral (services hung below; non-permanent dead)", "kNm2": npd["collateral_kNm2"],
         "kN_per_m": npd["collateral_kNm2"] * s / 1000.0, "applied": "gravity combinations only (adds to the effect)"},
        {"component": "imposed (IS 875-2)", "kNm2": Lq, "kN_per_m": Lq * s / 1000.0, "applied": "DL+IL", "cite": jt.get("L_cite")},
    ]
    if npd["pv_kNm2"]:
        load_table.insert(3, {"component": "rooftop PV (non-permanent dead)", "kNm2": npd["pv_kNm2"],
                              "kN_per_m": npd["pv_kNm2"] * s / 1000.0, "applied": "gravity combinations only (adds to the effect)"})
    extra = {"span_mm": span, "w_dead_N_per_mm": wD, "w_live_N_per_mm": wL, "w_nonpermanent_dead_N_per_mm": wNP, "grade_cite": cite,
             "loads_kNm2": {"D": D, "partition": part, "L": Lq, "L_cite": jt.get("L_cite"), **npd},
             "load_table": load_table, "material": material_statement(cfg, sec),
             "restraint_basis": {"text": rtext, "compression_flange_restrained": restr, "declared": declared is not None,
                                 "bracing": br},
             "clauses": ["IS 801 5.2.1.1", "5.2.3", "5.2.4", "6.1", "6.2", "6.3", "6.4.1", "6.4.3", "6.5", "7.3", "8.2"]}
    return _member_record("joist", jt, sec, fy, combos, rows, extra, tag=tag)


def bracing_rows(cfg, spec, sec, role, span, s, br, w_max, w_par=0.0, sheeted=True, point_loads=None, w_vert_member=0.0):
    """IS 801 8.2 rows for a channel / Z beam with declared intermediate bracing (2026-10 first wave, review item 3):
    8.2.1 spacing (blocking when neither flange is sheeted, reference otherwise), 8.2.2 brace force P1 and -- for sag
    rods -- the rod tension accumulated over the members tied into one line, sized from M10-M24 (IS 800 11.2.1 WSM).
    w_max: the governing line load normal to the member (N/mm, any sign); w_par: the line load along the brace line
    (gravity component down the roof slope for purlins); w_vert_member: own weight + cladding carried by girt rods."""
    rows = []
    if not br.get("declared"):
        if not sheeted:
            rows.append({"combo": "bracing", "check": "8.2.1 brace spacing a <= L/4", "value": span, "limit": span / 4.0,
                         "dc": 4.0, "ok": False, "detailing": True, "clause": "IS 801 8.2.1", "cite": IS801_82_CITE, "units": "mm",
                         "capacity_basis": "IS801_allowable", "allowable_increase": 1.0, "source": M.SRC,
                         "note": "no bracing declared and neither flange is connected to deck / sheathing: 8.2.1 requires braces "
                                 "at the ends and at not more than one-quarter of the span"})
        return rows
    a = br["spacing_mm"]
    info = bool(sheeted)
    # with one flange sheeted the 8.2.1 row is a reference (no D/C: it must never read as a failed check downstream)
    rows.append({"combo": "bracing", "check": "8.2.1 brace spacing a <= L/4", "value": round(a, 1), "limit": span / 4.0,
                 "dc": None if info else a / (span / 4.0), "ok": None if info else a <= span / 4.0 + 1e-6,
                 "a_over_L4": a / (span / 4.0), "clause": "IS 801 8.2.1", "cite": IS801_82_CITE, "detailing": True,
                 "units": "mm", "capacity_basis": "IS801_allowable", "allowable_increase": 1.0, "source": M.SRC,
                 "informational": info, **({"note": IS801_82_SCOPE + " (a / (L/4) = %.2f)" % (a / (span / 4.0))} if info else {})})
    if point_loads:
        tot = abs(w_max) * span + sum(abs(float(p["P_kN"])) * 1e3 for p in point_loads)
        big = max(abs(float(p["P_kN"])) * 1e3 for p in point_loads)
        if tot > 0 and big >= tot / 3.0:
            rows.append({"combo": "bracing", "check": "8.2.1 additional brace at a concentrated load >= 1/3 of the total",
                         "value": round(big / tot, 3), "limit": 1.0 / 3.0, "dc": None, "ok": None, "informational": True,
                         "clause": "IS 801 8.2.1", "cite": IS801_82_CITE, "units": "-", "capacity_basis": "IS801_allowable",
                         "allowable_increase": 1.0, "source": M.SRC,
                         "note": "one-third or more of the load is concentrated: place a brace at or near that load"})
    bf = brace_force_82(sec, w_max, a, span, point_loads)
    if bf["P1_int_N"] is None:
        rows.append({"combo": "bracing", "check": "8.2.2 brace force P1", "value": None, "limit": None, "dc": None, "ok": None,
                     "clause": "IS 801 8.2.2", "cite": IS801_82_CITE, "units": "N", "capacity_basis": "IS801_allowable",
                     "allowable_increase": 1.0, "source": M.SRC, "note": bf["K_prime_basis"]})
        return rows
    rows.append({"combo": "bracing (governing w)", "check": "8.2.2 brace force P1, intermediate brace (per flange)",
                 "value": round(bf["P1_int_N"], 1), "limit": None, "dc": None, "ok": True, "informational": True,
                 "clause": "IS 801 8.2.2", "cite": IS801_82_CITE, "units": "N", "capacity_basis": "IS801_allowable",
                 "allowable_increase": 1.0, "source": M.SRC,
                 "note": "K' = %.4f (%s); w = %.3f kN/m; a = %.0f mm; end braces %.0f N" % (bf["K_prime"], bf["K_prime_basis"],
                                                                                         abs(w_max), a, bf["P1_end_N"])})
    typ = br.get("type")
    bsp = br.get("spec") or {}
    n, n_how = _members_per_line(cfg, spec, role, s, br)
    per_member = bf["P1_int_N"] + abs(w_par) * a + abs(w_vert_member) * a
    F = round(n * per_member, 1)                 # rounded once: value and D/C of the brace rows agree exactly
    if typ == "sag_rods":
        fy_r = _num(bsp.get("rod_fy_MPa"), 250.0); fu_r = _num(bsp.get("rod_fu_MPa"), 410.0)
        dmin = _num(bsp.get("min_rod_dia_mm"), 12.0)
        cands = [float(bsp["rod_dia_mm"])] if bsp.get("rod_dia_mm") else [d for d in (10.0, 12.0, 16.0, 20.0, 24.0) if d >= dmin]
        pick = None
        for d in cands:
            rc = rod_capacity(d, fy_r, fu_r)
            pick = rc
            if F <= rc["T_allow_N"]:
                break
        sized = not bsp.get("rod_dia_mm")
        rows.append({"combo": "bracing (governing w)", "check": "sag rod M%d tension (%s)" % (round(pick["d_mm"]), "sized" if sized else "declared"),
                     "value": round(F, 1), "limit": round(pick["T_allow_N"], 1), "dc": F / pick["T_allow_N"],
                     "ok": F <= pick["T_allow_N"] + 1e-6, "clause": "IS 800:2007 11.2.1 / 6.3.1 (working stress)",
                     "cite": ROD_CITE, "units": "N", "capacity_basis": "IS800_WSM", "allowable_increase": 1.0, "source": M.SRC,
                     "rod": pick, "members_per_line": n, "brace_element": True, "detailing": True,
                     "note": "rod force = %d members x (P1 %.0f N + along-line load %.0f N) per line (%s); M%d: Ag %.0f mm2, "
                             "root %.0f mm2" % (n, bf["P1_int_N"], (abs(w_par) + abs(w_vert_member)) * a, n_how,
                                                round(pick["d_mm"]), pick["Ag_mm2"], pick["A_root_mm2"])})
    elif typ == "straps" and bsp.get("strap_width_mm") and bsp.get("strap_t_mm"):
        # flat strap bridging (tension): IS 801 6.1 F = 0.60 Fy on the net section (one fastener hole), the strap grade
        # declared (default the generic G350 coil); the strap line is anchored to blocking every members_per_line
        fy_s = _num(bsp.get("strap_Fy_MPa"), 350.0)
        An = (float(bsp["strap_width_mm"]) - _num(bsp.get("hole_mm"), 5.0)) * float(bsp["strap_t_mm"])
        cap = 0.60 * fy_s * An
        rows.append({"combo": "bracing (governing w)", "check": "strap %sx%s tension (IS 801 6.1, net section)"
                     % (_fmt_num(bsp["strap_width_mm"]), _fmt_num(bsp["strap_t_mm"])),
                     "value": round(F, 1), "limit": round(cap, 1), "dc": F / cap if cap > 0 else None, "ok": F <= cap + 1e-6,
                     "clause": "IS 801 6.1 (F = 0.60 Fy, net section)", "cite": IS801_82_CITE, "units": "N",
                     "capacity_basis": "IS801_allowable", "allowable_increase": 1.0, "source": M.SRC,
                     "brace_element": True, "detailing": True,
                     "note": "strap force = %d members x (P1 %.0f N + along-line load %.0f N) between anchor blocking (%s); "
                             "An = (%s - %s) x %s mm2, Fy %s MPa" % (n, bf["P1_int_N"], (abs(w_par) + abs(w_vert_member)) * a,
                                                                    n_how, _fmt_num(bsp["strap_width_mm"]),
                                                                    _fmt_num(_num(bsp.get("hole_mm"), 5.0)),
                                                                    _fmt_num(bsp["strap_t_mm"]), _fmt_num(fy_s))})
    else:
        cap = bsp.get("capacity_N")
        r = {"combo": "bracing (governing w)", "check": "%s brace force (per brace, %d member(s) per line)" % (typ, n),
             "value": round(F, 1), "limit": float(cap) if cap else None, "units": "N", "brace_element": True, "detailing": True,
             "clause": "IS 801 8.2.2", "cite": IS801_82_CITE, "capacity_basis": "test" if cap else "IS801_allowable",
             "allowable_increase": 1.0, "source": M.SRC}
        if cap:
            r.update(dc=F / float(cap), ok=F <= float(cap), note="declared brace capacity: %s" % (bsp.get("capacity_source") or "design engineer -- VERIFY"))
        else:
            r.update(dc=None, ok=None, note="brace / connection capacity not declared (bracing.capacity_N + capacity_source): "
                                            "the design engineer sizes the %s for this force" % typ)
        rows.append(r)
    return rows


def _point_load_effects(pls, span, kind):
    """Max moment (N-mm) and max end shear (N) of the declared point loads of one kind on a simple span."""
    Ms, Ra, Rb = [], 0.0, 0.0
    loads = [(float(p["P_kN"]) * 1e3, float(p["a_m"]) * 1e3) for p in pls if str(p.get("kind", "D")).upper() == kind]
    for P, a in loads:
        Ra += P * (span - a) / span; Rb += P * a / span
    for x in [a for _, a in loads]:
        Ms.append(Ra * x - sum(P * (x - a) for P, a in loads if a < x))
    return (max([abs(m) for m in Ms] or [0.0]), max(Ra, Rb))


# ---------------------------------------------------------------------------------------------------------------
# PEB (2026-10): lapped (continuous) purlins and girts
# ---------------------------------------------------------------------------------------------------------------
def continuous_unit_effects(n_spans, L, lap, nseg=24):
    """Linear elastic continuous beam on n_spans equal spans L (pinned supports), uniform load w = 1 N/mm, the lap
    zones (lap mm each side of every interior support) at 2 EI (two nested sections), elsewhere EI = 1 (results
    scale with w; deflection with 1/EI).  Returns the moment / shear envelope at the governing positions:
    {M_span_end, M_span_int (sagging +), M_support (hogging -, max over the interior supports), M_lap (moment at the
    lap end, single section, with its sign), x_inflection (from the support), V_support (max), V_lap, R_int, R_end,
    defl_end (x 1/EI), positions}."""
    import numpy as _np
    xs = set()
    for sp in range(n_spans):
        for k in range(nseg + 1):
            xs.add(round(sp * L + L * k / nseg, 6))
    for sp in range(1, n_spans):
        for dx in (-lap, lap):
            xs.add(round(sp * L + dx, 6))
    xs = sorted(xs)
    n = len(xs)

    def EI_at(xm):
        for sp in range(1, n_spans):
            if abs(xm - sp * L) < lap - 1e-9:
                return 2.0
        return 1.0
    K = _np.zeros((2 * n, 2 * n))
    F = _np.zeros(2 * n)
    els = []
    for e in range(n - 1):
        a, b = xs[e], xs[e + 1]
        le = b - a
        EI = EI_at(0.5 * (a + b))
        k = EI / le ** 3 * _np.array([[12, 6 * le, -12, 6 * le], [6 * le, 4 * le ** 2, -6 * le, 2 * le ** 2],
                                      [-12, -6 * le, 12, -6 * le], [6 * le, 2 * le ** 2, -6 * le, 4 * le ** 2]])
        q = -1.0                                                                  # w = 1 N/mm downward (v up +)
        fe = _np.array([q * le / 2.0, q * le ** 2 / 12.0, q * le / 2.0, -q * le ** 2 / 12.0])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i in range(4):
            F[idx[i]] += fe[i]
            for j in range(4):
                K[idx[i], idx[j]] += k[i, j]
        els.append((a, b, le, EI, idx, k, fe))
    sup = [i for i, x in enumerate(xs) if any(abs(x - sp * L) < 1e-6 for sp in range(n_spans + 1))]
    free = [d for d in range(2 * n) if not (d % 2 == 0 and d // 2 in sup)]
    u = _np.zeros(2 * n)
    u[free] = _np.linalg.solve(K[_np.ix_(free, free)], F[free])
    # element end forces f = k u - fe (left end: f[0] shear up +, f[1] moment ccw +); sagging + :
    # M(x) = -f[1] + f[0] x + q x^2 / 2, V(x) = f[0] + q x  (q = -1)
    pts = []
    for (a, b, le, EI, idx, k, fe) in els:
        f = k.dot(u[idx]) - fe
        V0, M0 = f[0], -f[1]
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            x = t * le
            pts.append((a + x, M0 + V0 * x - x * x / 2.0, V0 - x))
    pts.sort()
    out = {"n_spans": n_spans, "L_mm": L, "lap_mm": lap}
    end_span = [p for p in pts if p[0] <= L + 1e-6]
    int_span = [p for p in pts if L - 1e-6 <= p[0] <= 2 * L + 1e-6] if n_spans > 2 else end_span
    out["M_span_end"] = max(p[1] for p in end_span)
    out["M_span_int"] = max(p[1] for p in int_span) if n_spans > 1 else out["M_span_end"]
    if n_spans > 1:
        supm = []
        for sp in range(1, n_spans):
            near = [p for p in pts if abs(p[0] - sp * L) < 1e-6]
            supm.append(min(p[1] for p in near))
        out["M_support"] = min(supm)
        lapm, xinf = [], []
        for sp in range(1, n_spans):
            for sgn in (-1, 1):
                xl = sp * L + sgn * lap
                near = min(pts, key=lambda p: abs(p[0] - xl))
                lapm.append(near[1])
                side = sorted([p for p in pts if (p[0] - sp * L) * sgn > 0 and abs(p[0] - sp * L) <= L / 2.0],
                              key=lambda p: abs(p[0] - sp * L))
                for p in side:
                    if p[1] >= 0:
                        xinf.append(abs(p[0] - sp * L))
                        break
        out["M_lap"] = min(lapm)
        out["M_lap_max"] = max(lapm)
        out["x_inflection_min_mm"] = min(xinf) if xinf else None
        out["x_inflection_max_mm"] = max(xinf) if xinf else None
        out["V_lap"] = max(abs(p[2]) for p in pts if any(abs(abs(p[0] - sp * L) - lap) < 1e-3 for sp in range(1, n_spans)))
    else:
        out.update(M_support=0.0, M_lap=0.0, M_lap_max=0.0, x_inflection_min_mm=None, x_inflection_max_mm=None, V_lap=0.0)
    out["V_support"] = max(abs(p[2]) for p in pts)
    R = []
    for i in sup:
        R.append(sum((k.dot(u[idx]) - fe)[0 if idx[0] == 2 * i else 2] for (a, b, le, EI, idx, k, fe) in els
                     if idx[0] == 2 * i or idx[2] == 2 * i))
    out["R_end"] = abs(R[0])
    out["R_int"] = max(abs(r) for r in R[1:-1]) if len(R) > 2 else abs(R[0])
    out["defl_max_per_EI"] = float(-min(u[0::2]))
    # plain floats (numpy scalars would make the ok flags numpy booleans: 'np.False_ is not False')
    return {k: (float(v) if isinstance(v, (_np.floating, _np.integer)) else v) for k, v in out.items()}


def design_purlins(cfg, role="purlin", spec=None, tag=None, *, collateral_kNm2=None, pv_kNm2=None):
    """Roof purlins (or wall girts with role='girt'): gravity (D + Lr / snow on the projection, declared point loads)
    and member-level wind (C02: element Ka, Table 6 / Table 5 governing Cpe, local strips, Cpi from openings;
    derived on every path, declared values only increase it); 6.3 LTB on the unrestrained flange between braces.

    2026-10 first wave (review item 3 + lead item 5), backward compatible:
      * restraint basis: the sheeted flange (purlin top / girt outer) is restrained by the sheeting (L_unbraced_top_mm
        = 0); the free flange (purlin bottom / girt inner) is braced at the declared bracing interval
        (spec['bracing'] {type, lines, spacing_mm, ...} or the legacy spec['sag_rods'] = number of lines) and is
        checked UNBRACED over the span when no bracing is declared.  Every returned check row carries 'restraint' (the
        compression-flange statement) and the record carries 'restraint_basis'.
      * IS 801 8.2: 8.2.1 spacing (reference when one flange is sheeted, 8.2 (a)), 8.2.2 brace force, sag rods sized.
      * collateral_kNm2 / pv_kNm2 (keyword, spec or cfg['loads']; default 0): non-permanent dead components included
        in the gravity combinations and excluded where the dead load resists wind uplift / suction; shown as separate
        rows of the record's 'load_table'.
      * girts: 'suction' (inner flange in compression) / 'pressure' (outer flange), never 'uplift'."""
    cm = cfg["cfs_members"]; pu = spec or groups(cm, role + "s")[0]
    sec = _sec(pu)
    fy, cite = _grade(cfg, sec)
    ld = cfg["loads"]
    span = float(pu["span_mm"]); s = float(pu["spacing_mm"])
    pitch = math.radians(_num(pu.get("roof_pitch_deg")))
    bg = building_wind_geometry(cfg)
    npd = nonpermanent_dead(cfg, pu, collateral_kNm2, pv_kNm2) if role == "purlin" else {"collateral_kNm2": 0.0, "pv_kNm2": 0.0}
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
    wNP = (npd["collateral_kNm2"] + npd["pv_kNm2"]) * 1e-3 * s
    wW_up = p_up * 1e-3 * s; wW_dn = p_dn * 1e-3 * s
    pls = pu.get("point_loads") or []
    MpD, VpD = _point_load_effects(pls, span, "D")
    MpL, VpL = _point_load_effects(pls, span, "L")
    Lu_top = _num(pu.get("L_unbraced_top_mm"), 0.0)        # sheeted flange restrained by the sheeting -> 0
    br = bracing_basis(pu, span, role)
    Lu_bot = br["spacing_mm"]                                # free flange: bracing interval, or the span (unbraced)
    f_sheet, f_free = _flange_names(role)
    zb = pu.get("zed_basis") if sec.get("type") == "LZ" else None
    if Lu_top == 0.0:
        rt_sheet = restraint_text(f_sheet, True, 0.0, None, span,
                                  basis="the sheeting through-fastened to it" if role == "purlin" else "the wall sheeting fastened to it")
    elif br["declared"]:
        rt_sheet = ("compression flange: %s (not taken as restrained by the sheeting), braced at %.0f mm (declared "
                    "L_unbraced_top_mm; %d %s)" % (f_sheet, Lu_top, br["lines"], br.get("type_text")))
    else:
        rt_sheet = restraint_text(f_sheet, False, Lu_top, None, span)
    rt_free = restraint_text(f_free, False, Lu_bot, br, span)
    if br.get("note"):
        rt_free += " (" + br["note"] + ")"
    rows = []
    combos = [c for c in B.cfs_combinations(cfg.get("load_plan"), cfg) if c["fE"] == 0]
    common = dict(npd=npd, wNP=wNP, br=br, rt_sheet=rt_sheet, rt_free=rt_free, f_sheet=f_sheet, f_free=f_free, zb=zb,
                  pitch=pitch)
    if str(pu.get("continuity") or "").lower() == "lapped":
        return _design_lapped(cfg, role, pu, sec, fy, cite, span, s, wD, wL, wS, wW_up, wW_dn, mw, p_up, p_dn,
                              Lu_top, Lu_bot, combos, tag, **common)
    w_gov, w_par_gov = 0.0, 0.0
    for c in combos:
        w_grav = c["fD"] * wD + c["fL"] * wL + c.get("fS", 0.0) * wS
        # wind sign: +fW with the suction pattern gives uplift / outward suction, -fW the pressure pattern
        w = w_grav
        if c["fW"] > 0:
            w = w_grav + wW_up
        elif c["fW"] < 0:
            w = w_grav + wW_dn
        w, inc_np = _with_nonpermanent(w, c["fD"] * wNP)
        Mp = c["fD"] * MpD + c["fL"] * MpL
        Vp = c["fD"] * VpD + c["fL"] * VpL
        Mx = w * span ** 2 / 8.0 + Mp; V = abs(w) * span / 2.0 + Vp
        free_comp = Mx < 0
        if abs(w) > abs(w_gov):
            w_gov = w
        if role == "purlin" and w > 0:
            w_par_gov = max(w_par_gov, (w_grav + (c["fD"] * wNP if inc_np else 0.0)) * math.sin(pitch))
        we = bool(c["wind_eq"])
        b = M.bending_allowable(sec, fy, Lu_bot if free_comp else Lu_top, Cb=1.0, wind_eq=we,
                                compression_flange_restrained=(not free_comp and Lu_top == 0.0), zed_basis=zb)
        if role == "girt":
            lab = "suction, %s flange in compression" % f_free if free_comp else "pressure, %s flange in compression" % f_sheet
        else:
            lab = "uplift, %s flange in compression" % f_free if free_comp else "gravity, %s flange in compression" % f_sheet
        if b.get("ok") is None:
            rows.append(_row(c["label"], "6.1/6.2/6.3 bending (%s)" % lab, {"ok": None, "note": b.get("note"), "clause": b.get("clause")},
                             {"restraint": rt_free if free_comp else rt_sheet}))
        else:
            rows.append(_row(c["label"], "6.1/6.2/6.3 bending (%s)" % lab,
                             M._rec(abs(Mx), b["Ma_Nmm"], b["clause"], b["cite"], allowable_increase=b["allowable_increase"]),
                             {"M_Nmm": round(Mx, 1), "w_N_per_mm": round(w, 4), "Fb_MPa": _rnd(b["Fb_MPa"]), "ltb": b["ltb_clause"],
                              "L_unbraced_mm": Lu_bot if free_comp else Lu_top, "restraint": rt_free if free_comp else rt_sheet,
                              "nonpermanent_dead_included": inc_np,
                              **({"M_point_Nmm": round(Mp, 1)} if pls else {}), **({"note": b["note"]} if b.get("note") else {})}))
        rows.append(_row(c["label"], "6.4.1 web shear", M.web_shear_64(sec, fy, V, wind_eq=we), {"V_N": round(V, 1)}))
        rows.append(_row(c["label"], "6.5 web crippling (support)",
                         M.web_crippling_65(sec, fy, V, _num(pu.get("bearing_mm"), 50.0), end=False, back_to_back=sec.get("n_ply", 1) == 2, wind_eq=we)))
    w_vert = 0.0
    if role == "girt":
        w_vert = (sec.get("mass_kg_m") or 0.0) * 9.80665e-3 + _num(ld.get("clad")) * 1e-3 * s
    rows += bracing_rows(cfg, pu, sec, role, span, s, br, w_gov, w_par=w_par_gov, sheeted=(Lu_top == 0.0), point_loads=pls,
                         w_vert_member=w_vert)
    defl = 5.0 * max(wL + wS, abs(wW_up), wW_dn) * span ** 4 / (384.0 * E_MPA * sec["Ix"])
    rows.append(_defl_row("service", "deflection (information)", defl, span, pu, "IS 800:2007 Table 6 read-only when cited"))
    rows += geometry_rows(sec)
    _stamp_restraint(rows, "%s; %s" % (rt_sheet, rt_free))
    extra = {"span_mm": span, "loads_N_per_mm": {"dead": wD, "collateral": npd["collateral_kNm2"] * 1e-3 * s,
                                                 "pv": npd["pv_kNm2"] * 1e-3 * s, "live": wL, "snow": wS,
                                                 "wind_up": wW_up, "wind_down": wW_dn},
             "load_table": _purlin_load_table(role, ld, npd, s, pitch, p_up, p_dn, mw),
             "wind": {"member_pd": mw, "p_uplift_kNm2": p_up, "p_down_kNm2": p_dn, "cite": mw["cite"],
                      "declared": {k: pu.get(k) for k in ("wind_uplift_kNm2", "wind_suction_kNm2", "wind_pressure_kNm2") if pu.get(k) is not None}},
             "point_loads": pls or None, "zone": pu.get("zone", "all"), "material": material_statement(cfg, sec),
             "restraint_basis": {"sheeted_flange": f_sheet, "free_flange": f_free, "sheeted_text": rt_sheet, "free_text": rt_free,
                                 "bracing": br, "L_unbraced_free_mm": Lu_bot, "L_unbraced_sheeted_mm": Lu_top},
             "zed_basis": zb,
             "grade_cite": cite, "clauses": ["IS 801 5.2.1.1", "5.2.3", "5.2.4", "6.1", "6.1.2", "6.2", "6.3", "6.4.1", "6.5", "8.2"]}
    return _member_record(role, pu, sec, fy, combos, rows, extra, tag=tag)


def _purlin_load_table(role, ld, npd, s, pitch, p_up, p_dn, mw):
    """Separate rows for every load component of a purlin / girt (kN/m2 and kN/m on the member)."""
    k = s / 1000.0
    if role == "girt":
        return [{"component": "wind suction (member pd, IS 875-3 7.3)", "kNm2": abs(p_up), "kN_per_m": abs(p_up) * k,
                 "applied": "+W rows (inner flange in compression)"},
                {"component": "wind pressure (member pd, IS 875-3 7.3)", "kNm2": p_dn, "kN_per_m": p_dn * k,
                 "applied": "-W rows (outer flange in compression)"}]
    c = math.cos(pitch)
    return [
        {"component": "dead (permanent: sheeting, purlin, insulation)", "kNm2": _num(ld.get("D_roof")),
         "kN_per_m": _num(ld.get("D_roof")) * k, "applied": "every combination (0.9 DL on the uplift rows)"},
        {"component": "collateral (services hung from the purlins; non-permanent dead)", "kNm2": npd["collateral_kNm2"],
         "kN_per_m": npd["collateral_kNm2"] * k, "applied": "gravity combinations only; excluded from uplift"},
        {"component": "rooftop PV (non-permanent dead)", "kNm2": npd["pv_kNm2"], "kN_per_m": npd["pv_kNm2"] * k,
         "applied": "gravity combinations only; excluded from uplift"},
        {"component": "roof imposed load (IS 875-2, on plan)", "kNm2": _num(ld.get("Lr")), "kN_per_m": _num(ld.get("Lr")) * k * c,
         "applied": "DL+IL rows"},
        {"component": "snow (IS 875-4, on plan)", "kNm2": _num(ld.get("snow")), "kN_per_m": _num(ld.get("snow")) * k * c,
         "applied": "DL+SL rows"},
        {"component": "wind uplift (member pd, IS 875-3 7.3)", "kNm2": abs(p_up), "kN_per_m": abs(p_up) * k, "applied": "+W rows"},
        {"component": "wind downward (member pd)", "kNm2": p_dn, "kN_per_m": p_dn * k, "applied": "-W rows"},
    ]


def _design_lapped(cfg, role, pu, sec, fy, cite, span, s, wD, wL, wS, wW_up, wW_dn, mw, p_up, p_dn, Lu_top, Lu_bot,
                   combos, tag, npd=None, wNP=0.0, br=None, rt_sheet=None, rt_free=None, f_sheet="top", f_free="bottom",
                   zb=None, pitch=0.0):
    """PEB (2026-10): lapped (continuous) zed purlins / girts over n_spans equal spans with nested laps of lap_mm each
    side of every interior support (continuous_unit_effects; laps at 2 EI).  Checked per working-stress combination
    (IS 875-5 8.1 / IS 801 6.1.2): span (single section), lap end (single, moment + shear and 6.4.3 web bending +
    shear), interior support (two nested sections: 2 x the single capacity), web crippling at the interior support
    (two webs) and the end support; the flange in compression decides the restraint -- the flange fastened to the
    sheeting is restrained (zed_basis), the free flange buckles over the bracing interval (span, uplift / suction) or over
    the distance from the support to the point of contraflexure (hogging zones; spec 'L_unbraced_hog_mm' overrides).
    2026-10 first wave: restraint text on every row, IS 801 8.2 bracing rows, non-permanent dead (collateral / PV)."""
    n = int(pu.get("n_spans") or 5)
    lap = float(pu.get("lap_mm") or 0.0)
    ce = continuous_unit_effects(n, span, lap)
    zb = pu.get("zed_basis") if sec.get("type") == "LZ" else (pu.get("zed_basis") or "channel")
    L_hog = _num(pu.get("L_unbraced_hog_mm"), ce.get("x_inflection_max_mm") or span / 4.0)
    npd = npd or {"collateral_kNm2": 0.0, "pv_kNm2": 0.0}
    br = br or bracing_basis(pu, span, role)
    rt_sheet = rt_sheet or restraint_text(f_sheet, Lu_top == 0.0, Lu_top, None, span)
    rt_free = rt_free or restraint_text(f_free, False, Lu_bot, br, span)
    rt_hog = ("compression flange: %s (free) in the hogging zone, unbraced from the support to the point of contraflexure, "
              "%.0f mm" % (f_free, L_hog))
    rows = []
    L2 = span ** 2
    w_gov, w_par_gov = 0.0, 0.0
    for c in combos:
        w_grav = c["fD"] * wD + c["fL"] * wL + c.get("fS", 0.0) * wS
        w = w_grav
        if c["fW"] > 0:
            w = w_grav + wW_up
        elif c["fW"] < 0:
            w = w_grav + wW_dn
        w, inc_np = _with_nonpermanent(w, c["fD"] * wNP)
        if abs(w) > abs(w_gov):
            w_gov = w
        if role == "purlin" and w > 0:
            w_par_gov = max(w_par_gov, (w_grav + (c["fD"] * wNP if inc_np else 0.0)) * math.sin(pitch))
        we = bool(c["wind_eq"])
        down = w >= 0
        # continuous_unit_effects is for w = 1 N/mm on the actual spans: scale by w
        Ms = max(ce["M_span_end"], ce["M_span_int"]) * w             # span (sagging for w > 0)
        Ml = ce["M_lap"] * w                                          # lap end (hogging for w > 0)
        Mu = ce["M_support"] * w                                      # support (hogging for w > 0)
        Vs = ce["V_support"] * abs(w)
        Vl = ce["V_lap"] * abs(w)
        Ri = ce["R_int"] * abs(w)
        Re = ce["R_end"] * abs(w)
        if role == "girt":
            lab = "pressure" if down else "suction"
        else:
            lab = "gravity" if down else "uplift"
        # span: sheeted flange in compression when w > 0 (restrained by the sheeting), else the free flange
        b1 = M.bending_allowable(sec, fy, Lu_top if down else Lu_bot, Cb=1.0, wind_eq=we,
                                 compression_flange_restrained=(down and Lu_top == 0.0), zed_basis=zb)
        rows.append(_row(c["label"], "6.1/6.2/6.3 bending, span (single, %s)" % lab,
                         M._rec(abs(Ms), b1["Ma_Nmm"], b1["clause"], b1["cite"], allowable_increase=b1["allowable_increase"]),
                         {"M_Nmm": round(Ms, 1), "w_N_per_mm": round(w, 4), "ltb": b1["ltb_clause"],
                          "L_unbraced_mm": Lu_top if down else Lu_bot, "restraint": rt_sheet if down else rt_free,
                          "nonpermanent_dead_included": inc_np}))
        # lap end and support: hogging for w > 0 -> free flange in compression over the hogging length
        b2 = M.bending_allowable(sec, fy, L_hog if down else Lu_top, Cb=1.0, wind_eq=we,
                                 compression_flange_restrained=(not down and Lu_top == 0.0), zed_basis=zb)
        rows.append(_row(c["label"], "6.1/6.2/6.3 bending, lap end (single)",
                         M._rec(abs(Ml), b2["Ma_Nmm"], b2["clause"], b2["cite"], allowable_increase=b2["allowable_increase"]),
                         {"M_Nmm": round(Ml, 1), "ltb": b2["ltb_clause"], "L_unbraced_mm": L_hog if down else 0.0,
                          "restraint": rt_hog if down else rt_sheet}))
        rows.append(_row(c["label"], "6.1/6.2/6.3 bending, interior support (2 nested sections)",
                         M._rec(abs(Mu), 2.0 * b2["Ma_Nmm"], b2["clause"], b2["cite"] + "; lapped: 2 x single",
                                allowable_increase=b2["allowable_increase"]),
                         {"M_Nmm": round(Mu, 1), "restraint": rt_hog if down else rt_sheet}))
        rows.append(_row(c["label"], "6.4.1 web shear, lap end (single)", M.web_shear_64(sec, fy, Vl, wind_eq=we),
                         {"V_N": round(Vl, 1)}))
        sh2 = M.web_shear_64(sec, fy, Vs / 2.0, wind_eq=we)
        rows.append(_row(c["label"], "6.4.1 web shear, interior support (2 webs, half each)", sh2, {"V_N": round(Vs, 1)}))
        rows.append(_row(c["label"], "6.4.3 web bending + shear, lap end",
                         M.web_bending_shear_643(sec, fy, abs(Ml), Vl, wind_eq=we)["combined"]))
        rows.append(_row(c["label"], "6.5 web crippling, interior support (2 webs, half each)",
                         M.web_crippling_65(sec, fy, Ri / 2.0, _num(pu.get("bearing_mm"), 100.0), end=False,
                                            back_to_back=False, wind_eq=we), {"R_N": round(Ri, 1)}))
        rows.append(_row(c["label"], "6.5 web crippling, end support",
                         M.web_crippling_65(sec, fy, Re, _num(pu.get("bearing_mm"), 100.0), end=True,
                                            back_to_back=False, wind_eq=we), {"R_N": round(Re, 1)}))
    w_vert = 0.0
    if role == "girt":
        w_vert = (sec.get("mass_kg_m") or 0.0) * 9.80665e-3 + _num((cfg.get("loads") or {}).get("clad")) * 1e-3 * s
    rows += bracing_rows(cfg, pu, sec, role, span, s, br, w_gov, w_par=w_par_gov, sheeted=(Lu_top == 0.0),
                         w_vert_member=w_vert)
    I = sec["Ix"]
    wsv = max(wL + wS, abs(wW_up), wW_dn)
    defl = ce["defl_max_per_EI"] * wsv / (E_MPA * I)
    rows.append(_defl_row("service (max of IL, WL)", "deflection, lapped continuous (laps 2 EI)", defl, span, pu,
                          "IS 800:2007 Table 6 purlins / girts span/150 (elastic cladding) when declared"))
    rows += geometry_rows(sec)
    _stamp_restraint(rows, "%s; %s" % (rt_sheet, rt_free))
    extra = {"span_mm": span, "continuity": {"type": "lapped", "n_spans": n, "lap_mm": lap,
                                             "coefficients_wL2": {k: round(ce[k] / L2, 4) for k in
                                                                  ("M_span_end", "M_span_int", "M_support", "M_lap")},
                                             "x_inflection_mm": [ce.get("x_inflection_min_mm"), ce.get("x_inflection_max_mm")],
                                             "L_unbraced_hog_mm": L_hog,
                                             "basis": "continuous beam, equal spans, laps 2 EI (india_cfs_members."
                                                      "continuous_unit_effects)"},
             "zed_basis": pu.get("zed_basis"),
             "loads_N_per_mm": {"dead": wD, "collateral": npd["collateral_kNm2"] * 1e-3 * s, "pv": npd["pv_kNm2"] * 1e-3 * s,
                                "live": wL, "snow": wS, "wind_up": wW_up, "wind_down": wW_dn},
             "load_table": _purlin_load_table(role, cfg.get("loads") or {}, npd, s, pitch, p_up, p_dn, mw),
             "wind": {"member_pd": mw, "p_uplift_kNm2": p_up, "p_down_kNm2": p_dn, "cite": mw["cite"]},
             "zone": pu.get("zone", "all"), "grade_cite": cite, "material": material_statement(cfg, sec),
             "restraint_basis": {"sheeted_flange": f_sheet, "free_flange": f_free, "sheeted_text": rt_sheet, "free_text": rt_free,
                                 "hogging_text": rt_hog, "bracing": br, "L_unbraced_free_mm": Lu_bot,
                                 "L_unbraced_sheeted_mm": Lu_top, "L_unbraced_hog_mm": L_hog},
             "clauses": ["IS 801 5.2.1.1", "5.2.3", "5.2.4", "6.1", "6.1.2", "6.2", "6.3(b) zeds", "6.4.1", "6.4.3", "6.5", "8.2"],
             "mass_kg_per_m": sec.get("mass_kg_m"), "lap_mass_factor": 1.0 + 2.0 * lap * (n - 1) / (n * span)}
    return _member_record(role, pu, sec, fy, combos, rows, extra, tag=tag)


def design_eave_strut(cfg, spec, tag=None):
    """C14: eave strut -- the longitudinal strut at the eave carrying the declared axial force (gable wind / EQ into the
    bracing, P_N + P_cite) with its own-weight bending; IS 801 6.6 / 6.7 with the 6.1.2 increase (W / EL force)."""
    sec = _sec(spec)
    fy, cite = _grade(cfg, sec)
    L = float(spec["span_mm"])
    if spec.get("P_N") is None:
        raise ValueError("cfs_members.eave_struts: declared axial force P_N (+ P_cite) required -- the strut force of the "
                         "longitudinal bracing load path")
    P = float(spec["P_N"])
    wsw = (sec.get("mass_kg_m") or 0.0) * 9.80665 / 1000.0 + _num(spec.get("w_dead_kN_per_m"))
    Mx = wsw * L ** 2 / 8.0
    Lu = _num(spec.get("L_unbraced_mm"), L)
    r = M.combined_67(sec, fy, P, Mx, L, Lu, Lu, cm_case="transverse_unrestrained",
                      braced_against_twist=(sec.get("n_ply", 1) == 2) or bool(spec.get("braced_against_twist")), wind_eq=True,
                      compression_flange_restrained=bool(spec.get("compression_flange_restrained")),
                      zed_basis=spec.get("zed_basis"))
    rows = []
    lab = "DL+1.0WL/EL (strut)"
    if "checks" not in r:
        rows.append(_row(lab, "6.6/6.7", {"ok": None, "note": r.get("note"), "clause": r.get("clause")}))
    else:
        for nm, ck in r["checks"].items():
            rows.append(_row(lab, nm, ck, {"P_N": round(P, 1), "M_Nmm": round(Mx, 1), "fa_MPa": round(r["fa_MPa"], 2),
                                           "fb_MPa": round(r["fbx_MPa"], 2),
                                           "KL_r": (round(float(r["compression"]["KLr"]), 1)       # second wave, report-only
                                                    if isinstance((r.get("compression") or {}).get("KLr"), (int, float)) else None)}))
    combos = [{"label": lab}]
    return _member_record("eave_strut", spec, sec, fy, combos, rows,
                          {"span_mm": L, "P_N": P, "P_cite": spec.get("P_cite"), "grade_cite": cite,
                           "clauses": ["IS 801 6.1.2", "6.6.1.1", "6.6.1.2", "6.7"]}, tag=tag)


def design_header(cfg, spec, tag=None):
    """C14: header over a wall opening -- simply supported beam under the declared dead / imposed line loads."""
    sec = _sec(spec)
    fy, cite = _grade(cfg, sec)
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


# ---------------------------------------------------------------------------------------------------------------
# 2026-10 first wave (review item 2): auto-selection of the lightest passing section from a declared family
# ---------------------------------------------------------------------------------------------------------------
AUTO_FAMILY_NAMES = ("thin_C_G350", "thin_Z_G350", "IS811_CLR", "IS811_CLS", "IS811_LZ")


def family_candidates(family, spec=None):
    """Candidate labels of one family (or a list of families), lightest first: [(label, mass_kg_m, h, t)].
    spec['auto_select'] filters: depth_min_mm / depth_max_mm / t_min_mm / t_max_mm.  Generic thin sections outside
    the IS 801 5.2.3 / 5.2.4 limits are not candidates."""
    import cfs_generic_sections as GS
    asel = (spec or {}).get("auto_select") or {}
    fams = family if isinstance(family, (list, tuple)) else [family]
    out = []
    for f in fams:
        if f in GS.FAMILIES:
            labs = GS.family_labels(f)
        elif str(f).upper().startswith("IS811_"):
            labs = S.list_labels(str(f).split("_", 1)[1].upper())
        else:
            raise ValueError("auto_select.family %r unknown (known: %s)" % (f, ", ".join(AUTO_FAMILY_NAMES)))
        for lab in labs:
            try:
                p = S.props(lab)
            except KeyError:
                continue
            if p.get("generic") and not p.get("is801_geometry_ok"):
                continue
            h, t = p["h"], p["t"]
            if h < _num(asel.get("depth_min_mm"), 0.0) or h > _num(asel.get("depth_max_mm"), 1e9):
                continue
            if t < _num(asel.get("t_min_mm"), 0.0) or t > _num(asel.get("t_max_mm"), 1e9):
                continue
            if p.get("mass_kg_m") is None:
                continue
            out.append((lab, p["mass_kg_m"], h, t))
    return sorted(out, key=lambda r: (r[1], r[2]))


def _first_failure(recs):
    for r in recs:
        for c in r.get("checks") or []:
            if c.get("informational"):
                continue
            if c.get("ok") is None:
                return "not evaluated: %s (%s)" % (c.get("check"), c.get("combo"))
            if c.get("ok") is False:
                return "%s (%s) D/C %s" % (c.get("check"), c.get("combo"), _fmt_num(c.get("dc"), 3))
    return None


def auto_select(cfg, spec, design_group):
    """Pick the lightest section of spec['auto_select']['family'] for which every record of design_group(spec) passes
    every IS 801 check (no D/C > 1, nothing unevaluated).  Returns the records of the chosen section with
    rec['auto_selected'] = {family, criterion, n_candidates, n_tried, lighter_rejected, reference_section, ...}."""
    asel = spec.get("auto_select") or {}
    fam = asel.get("family")
    if not fam:
        raise ValueError("auto_select.family required (one of %s)" % ", ".join(AUTO_FAMILY_NAMES))
    plies = [int(x) for x in (asel.get("n_ply_options") or [int(spec.get("n_ply") or 1)])]
    cands = sorted(((lab, mass * n, h, t, n) for lab, mass, h, t in family_candidates(fam, spec) for n in plies),
                   key=lambda r: (r[1], r[4], r[2]))
    if not cands:
        raise ValueError("auto_select: no candidate in family %r within the declared limits" % (fam,))
    ref = asel.get("reference_section") or (spec.get("section") if str(spec.get("section") or "").lower() not in ("", "auto") else None)
    ref_mass = None
    if ref:
        try:
            n_r, base_r = S.parse_designator(ref)
            ref_mass = (S.props(base_r).get("mass_kg_m") or 0.0) * int(asel.get("reference_n_ply") or n_r)
        except (KeyError, ValueError):
            ref_mass = None
    rejected, chosen, tried = [], None, 0
    for lab, mass, h, t, nply in cands:
        tried += 1
        trial = dict(spec, section=lab, n_ply=nply)
        trial.pop("designator", None)
        nm = ("2x" if nply == 2 else "") + lab
        try:
            recs = design_group(trial)
        except (KeyError, ValueError, ZeroDivisionError) as ex:
            rejected.append({"section": nm, "mass_kg_m": round(mass, 3), "reason": "not designable: %s" % ex})
            continue
        why = _first_failure(recs)
        if why is None:
            chosen = recs
            break
        rejected.append({"section": nm, "mass_kg_m": round(mass, 3), "reason": why})
    meta = {"family": fam, "criterion": "lightest mass per metre (base metal) passing every IS 801 check of the group",
            "n_candidates": len(cands), "n_tried": tried, "lighter_rejected": rejected[-6:],
            "reference_section": ref, "reference_mass_kg_m": ref_mass}
    if chosen is None:
        lab, nply = cands[-1][0], cands[-1][4]
        chosen = design_group(dict(spec, section=lab, n_ply=nply))
        meta["note"] = "no section of family %s passes; the heaviest candidate %s is reported (FAIL)" % (fam, lab)
    for r in chosen:
        r["auto_selected"] = dict(meta, section=r.get("designator"), mass_kg_m=r.get("mass_kg_m"),
                                  n_ply_options=plies)
    return chosen


def design_all(cfg):
    """All declared CFS members -> list of member records (groups per role, C14).  A group with 'auto_select'
    {family, depth / thickness limits, reference_section} gets the lightest passing section of the family."""
    cm = cfg.get("cfs_members") or {}
    out = []
    H = (cfg.get("geometry") or {}).get("heights_m") or []
    st_groups = groups(cm, "studs")
    for i, st in enumerate(st_groups):
        # C02: every storey by default (the top storey carries the highest pz; equal storeys no longer pick storey 1 only)
        storeys = st.get("storeys") or list(range(1, len(H) + 1))

        def _studs(g, i=i, storeys=storeys):
            recs = []
            for k in storeys:
                t = "S%d" % int(k)
                if len(st_groups) > 1:
                    t = "%s-%s" % (_tag(g, i, len(st_groups)), t)
                recs.append(design_studs(cfg, storey=int(k), spec=g, tag=t))
            return recs
        out += auto_select(cfg, st, _studs) if st.get("auto_select") else _studs(st)
    for key, fn in (("joists", lambda g, t: design_joists(cfg, g, t)),
                    ("purlins", lambda g, t: design_purlins(cfg, "purlin", g, t)),
                    ("girts", lambda g, t: design_purlins(cfg, "girt", g, t)),
                    ("eave_struts", lambda g, t: design_eave_strut(cfg, g, t)),
                    ("headers", lambda g, t: design_header(cfg, g, t))):
        gs = groups(cm, key)
        for i, g in enumerate(gs):
            tg = _tag(g, i, len(gs))
            if g.get("auto_select"):
                out += auto_select(cfg, g, lambda gg, fn=fn, tg=tg: [fn(gg, tg)])
            else:
                out.append(fn(g, tg))
    return out
