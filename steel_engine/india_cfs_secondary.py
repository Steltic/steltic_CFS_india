"""india_cfs_secondary.py -- 2026-10 third wave (handoff P9): the cold-formed secondary items the reports listed as
outside the design, designed where the Indian Standards in the corpus give a basis.

* simple_beam                       a simply supported beam under distributed and point loads: reactions, M, V and the
                                    mid-span deflection (numerical, any load shape)
* snow_drift_multilevel             IS 875 (Part 4):2021 5.2.4 -- drift on a lower roof against a higher one
* snow_drift_projection             IS 875 (Part 4):2021 5.2.6 -- drift against a local projection on a roof
* design_beam_is801                 IS 801 6.1-6.5 checks of a simply supported cold-formed beam under combination load
                                    cases (bending with the declared restraint, 6.4.1 shear, 6.4.3 web bending + shear,
                                    6.5 crippling at the supports, deflection against the declared criterion)
* design_post_is801                 IS 801 6.6 / 6.7 checks of a post or jamb (axial + wind bending)
* design_lean_to                    a lean-to (vestibule) against a higher wall: drift-loaded roof joists, the header
                                    over the door (a framed opening), the door jambs and the back-wall studs
* design_roof_platforms             an equipment platform on the roof: its beams and posts, the drift around it, and the
                                    dead loads it puts on the hot-rolled frame (platform_frame_loads)
* design_purlin_cleats              purlin-to-rafter cleats: bolts in the purlin web (IS 801 7.5), the welded plate
                                    cleat (IS 800:2007 11.2.1, 11.3.1, 11.4.1 (c), 11.5.2, 11.5.3, 11.6.3.1 working
                                    stress, 11.1.4 increases)
* portal_eave_struts                the eave-strut force of an all-cold-formed portal from its longitudinal bracing
                                    (IS 801 6.6 / 6.7 by india_cfs_members.design_eave_strut)

Screwed connections are not designed here: IS 801:1975 has bolt (7.5) and weld (7.2) provisions only, so a screw
capacity is a tested or manufacturer value (SCREW_SCOPE).
"""
from __future__ import annotations

import math

import india_cfs_env  # noqa: F401
import is801_members as M
import india_cfs_basis as B
import india_cfs_members as CM

K_SNOW = 2.0                         # kN/m2, IS 875 (Part 4):2021 5.2.4 / 5.2.6 ('k = 2 kN/m2')
MU1 = 0.80                           # 5.2.4 / 5.2.6 mu1
SNOW_CITE_524 = ("IS 875 (Part 4):2021 5.2.4 multilevel roofs: mu1 = 0.80; mu2 = mus + muw; muw = (l1 + l2)/2h <= k h/s0, "
                 "0.80 <= muw <= 4.0, k = 2 kN/m2; l3 = 2h, 5 m <= l3 <= 15 m; mus = 0 for an upper roof of 15 deg or less; "
                 "Note 2: l2 < l3 -> interpolate between mu1 and mu2")
SNOW_CITE_526 = ("IS 875 (Part 4):2021 5.2.6 roofs with local projections and obstructions: mu1 = 0.80; mu2 = k h/s0, "
                 "0.8 <= mu2 <= 2.0, k = 2 kN/m2; l = 2h, 5 m <= l <= 15 m")
SCREW_SCOPE = ("IS 801:1975 gives provisions for welds (7.2) and bolts (7.5) only, none for screws: screwed connections "
               "(sheeting, stud-to-track, clip angles, board fixings) are designed from the screw maker's tested values or "
               "a test programme, and are the design engineer's items")
IS800_WSM_CITE = ("IS 800:2007 Section 11 working stress: 11.4.1 (c) plates bending about the minor axis 0.75 fy, 11.4.2 "
                  "shear 0.40 fy, 11.6.3.1 fillet welds faw = 0.4 fy; 11.1.4 increase 33 percent only when wind acts with "
                  "imposed load")


class SecondaryError(ValueError):
    pass


def _num(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


# ================================================================================================= beam mechanics
def simple_beam(L_mm, q_N_per_mm=None, points=(), EI=None, n=400):
    """Simply supported beam of span L (mm): q(x) in N/mm (callable or number, + downwards), points [(P_N, a_mm)].
    Returns {R_left_N, R_right_N, M_max_Nmm (signed, largest |M|), x_Mmax_mm, V_max_N (largest |V| at a support),
    defl_max_mm (when EI is given, + downwards), M(x) / V(x) samples}.  Numerical: n equal segments, trapezoid rule."""
    L = float(L_mm)
    if L <= 0:
        raise SecondaryError("span must be positive")
    q = q_N_per_mm if callable(q_N_per_mm) else (lambda x, _q=float(q_N_per_mm or 0.0): _q)
    xs = [L * i / n for i in range(n + 1)]
    qs = [q(x) for x in xs]
    # total load and moment about the left support
    W = sum(0.5 * (qs[i] + qs[i + 1]) * (xs[i + 1] - xs[i]) for i in range(n))
    Mx0 = sum(0.5 * (qs[i] * xs[i] + qs[i + 1] * xs[i + 1]) * (xs[i + 1] - xs[i]) for i in range(n))
    for P, a in points:
        if not 0.0 <= float(a) <= L:
            raise SecondaryError("point load at %.0f mm is off the span %.0f mm" % (a, L))
        W += float(P)
        Mx0 += float(P) * float(a)
    Rr = Mx0 / L
    Rl = W - Rr
    V, Mv = [], []
    cum_q, cum_qx = 0.0, 0.0
    for i, x in enumerate(xs):
        if i:
            dx = xs[i] - xs[i - 1]
            cum_q += 0.5 * (qs[i - 1] + qs[i]) * dx
            cum_qx += 0.5 * (qs[i - 1] * xs[i - 1] + qs[i] * xs[i]) * dx
        pl = [(float(P), float(a)) for P, a in points if float(a) <= x + 1e-9]
        Vx = Rl - cum_q - sum(P for P, _ in pl)
        Mxx = Rl * x - (x * cum_q - cum_qx) - sum(P * (x - a) for P, a in pl)
        V.append(Vx)
        Mv.append(Mxx)
    k = max(range(len(Mv)), key=lambda i: abs(Mv[i]))
    out = {"R_left_N": Rl, "R_right_N": Rr, "W_N": W, "M_max_Nmm": Mv[k], "x_Mmax_mm": xs[k],
           "V_max_N": max(abs(Rl), abs(Rr)), "x": xs, "M": Mv, "V": V}
    if EI:
        # deflection by the unit-load method: delta(x0) = integral M(x) m(x) dx / EI, m = unit load at x0
        best = 0.0
        for j in range(0, n + 1, max(1, n // 40)):
            x0 = xs[j]
            acc = 0.0
            for i in range(n):
                xa, xb = xs[i], xs[i + 1]
                ma = (1 - x0 / L) * xa if xa <= x0 else x0 * (1 - xa / L)
                mb = (1 - x0 / L) * xb if xb <= x0 else x0 * (1 - xb / L)
                acc += 0.5 * (Mv[i] * ma + Mv[i + 1] * mb) * (xb - xa)
            if abs(acc) > abs(best):
                best = acc
        out["defl_max_mm"] = best / EI
    return out


# ================================================================================================= snow drift
def snow_drift_multilevel(s0_kPa, h_m, l1_m, l2_m, beta_upper_deg=0.0, mu_s=None):
    """IS 875 (Part 4):2021 5.2.4: the shape coefficient on a lower roof of width l2 against an upper roof of width l1,
    height difference h.  mus = 0 for an upper roof slope of 15 deg or less; steeper upper roofs need the declared mus
    (50 percent of the upper slope load, 5.2.4) -- refused when not given.  Returns the profile record: mu(x) from the
    step, mu2 at the step, l3, the value at the far edge when l2 < l3 (Note 2)."""
    s0, h, l1, l2 = float(s0_kPa), float(h_m), float(l1_m), float(l2_m)
    if s0 <= 0 or h <= 0 or l2 <= 0:
        raise SecondaryError("snow drift: s0, h and l2 must be positive")
    if float(beta_upper_deg) > 15.0 and mu_s is None:
        raise SecondaryError("snow drift 5.2.4: the upper roof is steeper than 15 deg -- declare mus (sliding, 50 percent of "
                             "the upper-slope load distributed over l3)")
    mus = 0.0 if float(beta_upper_deg) <= 15.0 else float(mu_s)
    raw = (l1 + l2) / (2.0 * h)
    cap = K_SNOW * h / s0
    muw = max(0.80, min(4.0, min(raw, cap)))
    mu2 = mus + muw
    l3_raw = 2.0 * h
    l3 = min(15.0, max(5.0, l3_raw))

    def mu(x_m):
        x = max(0.0, float(x_m))
        return (mu2 - (mu2 - MU1) * x / l3) if x < l3 else MU1
    far = mu(min(l2, l3)) if l2 < l3 else MU1
    return {"clause": "IS 875 (Part 4):2021 5.2.4", "cite": SNOW_CITE_524, "s0_kPa": s0, "h_m": h, "l1_m": l1, "l2_m": l2,
            "beta_upper_deg": float(beta_upper_deg), "mu1": MU1, "mus": mus, "muw_raw": raw, "muw_cap_kh_s0": cap,
            "muw": muw, "mu2": mu2, "l3_raw_m": l3_raw, "l3_m": l3, "mu_far_edge": far,
            "s_step_kPa": mu2 * s0, "s_far_edge_kPa": far * s0, "mu": mu,
            "governs": ("k h/s0" if cap < raw and muw == cap else ("0.80 lower bound" if muw == 0.80 else
                        ("4.0 upper bound" if muw == 4.0 else "(l1 + l2)/2h")))}


def snow_drift_projection(s0_kPa, h_m):
    """IS 875 (Part 4):2021 5.2.6: the shape coefficient against a local projection of height h on a roof."""
    s0, h = float(s0_kPa), float(h_m)
    raw = K_SNOW * h / s0
    mu2 = max(0.80, min(2.0, raw))
    l_raw = 2.0 * h
    lx = min(15.0, max(5.0, l_raw))
    return {"clause": "IS 875 (Part 4):2021 5.2.6", "cite": SNOW_CITE_526, "s0_kPa": s0, "h_m": h, "mu1": MU1,
            "mu2_raw": raw, "mu2": mu2, "l_raw_m": l_raw, "l_m": lx, "s_peak_kPa": mu2 * s0,
            "surcharge": mu2 > MU1 + 1e-9,
            "statement": ("drift surcharge: mu2 = %.2f at the projection over %.1f m" % (mu2, lx)) if mu2 > MU1 + 1e-9 else
                         ("no drift surcharge: k h/s0 = %.2f is below the 0.80 lower bound, so the roof's uniform mu1 = 0.80 "
                          "load governs around the projection" % raw)}


# ================================================================================================= combinations
def gravity_wind_cases(cfg, include_snow=True):
    """The IS 875 (Part 5) 8.1 cold-formed rows without earthquake, reduced to distinct (fD, fL, fS, sign fW) cases --
    the first label of each case is kept (the wind patterns repeat the same factors)."""
    seen, out = set(), []
    for c in B.cfs_combinations(cfg.get("load_plan"), cfg):
        if c.get("fE"):
            continue
        fS = float(c.get("fS") or 0.0) if include_snow else 0.0
        key = (float(c["fD"]), float(c["fL"]), fS, (c["fW"] > 0) - (c["fW"] < 0))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(c, fS=fS))
    return out


def _sec_fy(cfg, spec):
    sec = CM._sec(spec)
    fy, cite = CM._grade(cfg, sec)
    return sec, fy, cite


# ================================================================================================= IS 801 beam
def design_beam_is801(cfg, spec, role, load_case_fn, *, span_mm, Lu_gravity_mm, Lu_uplift_mm, restrained_top,
                      defl_case_fn=None, tag=None, bearing_mm=None, extra=None, restraint_text=None, cases=None):
    """A simply supported cold-formed beam (C / 2-ply C) checked to IS 801 under load_case_fn(case) ->
    (q(x) N/mm callable or number, [(P_N, a_mm)]).  Gravity puts the top flange in compression (restrained by the
    sheeting / deck when restrained_top, else braced at Lu_gravity_mm); a net upward load puts the bottom flange in
    compression, braced at Lu_uplift_mm.  defl_case_fn() -> the service load for the deflection row (criterion
    spec['deflection_limit_ratio'] + cite)."""
    sec, fy, gcite = _sec_fy(cfg, spec)
    L = float(span_mm)
    nb = _num(bearing_mm if bearing_mm is not None else spec.get("bearing_mm"), 50.0)
    b2b = sec.get("n_ply", 1) == 2
    rows = []
    cases = cases if cases is not None else gravity_wind_cases(cfg)
    Rmax = 0.0
    for c in cases:
        q, pts = load_case_fn(c)
        r = simple_beam(L, q, pts)
        Mx = r["M_max_Nmm"]
        V = r["V_max_N"]
        Rmax = max(Rmax, abs(r["R_left_N"]), abs(r["R_right_N"]))
        we = bool(c.get("wind_eq"))
        up = Mx < 0
        b = M.bending_allowable(sec, fy, Lu_uplift_mm if up else (0.0 if restrained_top else Lu_gravity_mm), Cb=1.0,
                                wind_eq=we, compression_flange_restrained=(not up and restrained_top))
        lab = "uplift, bottom flange in compression" if up else "gravity, top flange in compression"
        if b.get("ok") is None:
            rows.append(CM._row(c["label"], "6.1/6.2/6.3 bending (%s)" % lab, {"ok": None, "note": b.get("note"), "clause": b.get("clause")}))
        else:
            rows.append(CM._row(c["label"], "6.1/6.2/6.3 bending (%s)" % lab,
                                M._rec(abs(Mx), b["Ma_Nmm"], b["clause"], b["cite"], allowable_increase=b["allowable_increase"]),
                                {"M_Nmm": round(Mx, 1), "x_mm": round(r["x_Mmax_mm"], 1), "Fb_MPa": round(b["Fb_MPa"], 2),
                                 "ltb": b.get("ltb_clause")}))
        rows.append(CM._row(c["label"], "6.4.1 web shear", M.web_shear_64(sec, fy, V, wind_eq=we), {"V_N": round(V, 1)}))
        rows.append(CM._row(c["label"], "6.5 web crippling (end reaction)",
                            M.web_crippling_65(sec, fy, V, nb, end=True, back_to_back=b2b, wind_eq=we)))
        # 6.4.3 at the section of largest moment with the shear there (the moment-shear pair along the span)
        i = r["M"].index(r["M_max_Nmm"])
        rows.append(CM._row(c["label"], "6.4.3 web bending + shear",
                            M.web_bending_shear_643(sec, fy, abs(r["M"][i]), abs(r["V"][i]), wind_eq=we)["combined"]))
    if defl_case_fn is not None:
        q, pts = defl_case_fn()
        d = simple_beam(L, q, pts, EI=M.E_MPA * sec["Ix"])
        rows.append(CM._defl_row("service", "deflection", abs(d["defl_max_mm"]), L, spec,
                                 "IS 801 5.1 deflection by conventional methods"))
    rows += CM.geometry_rows(sec)
    if restraint_text:
        CM._stamp_restraint(rows, restraint_text)
    ext = {"span_mm": L, "grade_cite": gcite, "material": CM.material_statement(cfg, sec), "R_max_N": Rmax,
           "clauses": ["IS 801 5.2.1.1", "6.1", "6.1.2", "6.2", "6.3", "6.4.1", "6.4.3", "6.5"]}
    ext.update(extra or {})
    if restraint_text:
        ext["restraint_basis"] = {"text": restraint_text}
    rec = CM._member_record(role, spec, sec, fy, cases, rows, ext, tag=tag)
    rec["id"] = rec["id"].replace(" ", "-")
    return rec


def design_post_is801(cfg, spec, role, P_case_fn, *, height_mm, w_wind_N_per_mm=0.0, braced_mm=None, tag=None,
                      extra=None, restraint_text=None, cases=None, wind_cite=None):
    """A post / jamb / bearing stud: axial P_case_fn(case) (N, + compression) with wind bending w L^2/8 (simply
    supported over height_mm) -- IS 801 6.6 / 6.7 (6.7.2 (b) refused for a channel loaded away from its shear centre and
    not braced against twisting), 6.4.1 shear, 6.5 crippling at the track, deflection under wind (stud criterion)."""
    sec, fy, gcite = _sec_fy(cfg, spec)
    L = float(height_mm)
    Lb = float(braced_mm) if braced_mm else L
    braced_twist = sec.get("n_ply", 1) == 2 or bool(spec.get("braced_against_twist"))
    rows = []
    cases = cases if cases is not None else gravity_wind_cases(cfg)
    Mw = w_wind_N_per_mm * L ** 2 / 8.0
    Vw = w_wind_N_per_mm * L / 2.0
    for c in cases:
        P = float(P_case_fn(c))
        Mx = abs(c["fW"]) * Mw
        V = abs(c["fW"]) * Vw
        we = bool(c.get("wind_eq"))
        r = M.combined_67(sec, fy, max(P, 0.0), Mx, L, Lb, Lb, cm_case="transverse_unrestrained" if Mx else "braced",
                          braced_against_twist=braced_twist, wind_eq=we,
                          e_side=("away_from_shear_centre" if (Mx and not braced_twist) else None))
        if r.get("ok") is None and "checks" not in r:
            rows.append(CM._row(c["label"], "6.6/6.7", {"ok": None, "note": r.get("note"), "clause": r.get("clause")}))
            continue
        for nm, ck in r["checks"].items():
            rows.append(CM._row(c["label"], nm, ck, {"P_N": round(P, 1), "M_Nmm": round(Mx, 1),
                                                     "KL_r": (round(float(r["compression"]["KLr"]), 1)
                                                              if isinstance((r.get("compression") or {}).get("KLr"), (int, float))
                                                              else None)}))
        if V > 0:
            rows.append(CM._row(c["label"], "6.4.1 web shear", M.web_shear_64(sec, fy, V, wind_eq=we), {"V_N": round(V, 1)}))
    if w_wind_N_per_mm:
        defl = 5.0 * w_wind_N_per_mm * L ** 4 / (384.0 * M.E_MPA * sec["Ix"])
        sd, src = CM.stud_deflection_criterion(spec)
        rows.append(CM._defl_row("DL+1.0WL (service)", "deflection under wind", defl, L, sd,
                                 "IS 801 5.1 deflection by conventional methods"))
        rows[-1]["criterion_source"] = src
    rows += CM.geometry_rows(sec)
    if restraint_text:
        CM._stamp_restraint(rows, restraint_text)
    ext = {"height_mm": L, "grade_cite": gcite, "material": CM.material_statement(cfg, sec),
           "clauses": ["IS 801 6.6.1.1", "6.6.1.2", "6.6.3", "6.7", "6.4.1"], "wind_N_per_mm": w_wind_N_per_mm,
           "wind_cite": wind_cite}
    ext.update(extra or {})
    if restraint_text:
        ext["restraint_basis"] = {"text": restraint_text}
    rec = CM._member_record(role, spec, sec, fy, cases, rows, ext, tag=tag)
    rec["id"] = rec["id"].replace(" ", "-")
    return rec


def _auto(cfg, spec, fn):
    """The lightest passing section of spec['auto_select'] (india_cfs_members.auto_select), else the declared one."""
    if spec.get("auto_select"):
        return CM.auto_select(cfg, spec, lambda g: [fn(g)])[0]
    return fn(spec)


# ================================================================================================= lean-to / vestibule
def design_lean_to(cfg, lt):
    """A lean-to (vestibule / airlock) against a higher wall of the building (cfg['lean_to'], one dict):
        {name, width_m (along the wall), depth_m (joist span, away from the wall), roof_z_m (at the wall), upper_roof_z_m
         (highest roof edge of the main building over the lean-to), upper_roof_length_m (l1), upper_roof_pitch_deg,
         D_roof_kNm2 + D_cite, wall_kNm2, joists {section | auto_select, spacing_mm, bearing_mm, deflection_limit_ratio +
         cite}, door {width_m, height_m, header {...}, jambs {...}}, back_studs {...}, front_wall_height_m}.
    The roof snow is the IS 875-4 5.2.4 drift profile from the wall (mu2) to the front edge; it replaces the roof imposed
    load (IS 875-5 8.1 Note 1).  Returns (member records, record)."""
    s0 = _num(((cfg.get("load_plan") or {}).get("snow_summary") or {}).get("s0_kPa"))
    if s0 <= 0:
        raise SecondaryError("lean_to: the job's snow_summary.s0_kPa is required for the IS 875-4 5.2.4 drift")
    D = _num(lt.get("D_roof_kNm2"))
    depth = float(lt["depth_m"]) * 1000.0
    width = float(lt["width_m"]) * 1000.0
    h = float(lt["upper_roof_z_m"]) - float(lt["roof_z_m"])
    drift = snow_drift_multilevel(s0, h, float(lt["upper_roof_length_m"]), float(lt["depth_m"]),
                                  lt.get("upper_roof_pitch_deg", 0.0), mu_s=lt.get("mu_s"))
    mu = drift["mu"]
    jt = dict(lt["joists"])
    s = float(jt["spacing_mm"])
    # wind on the lean-to roof: the member pressures of the building roof (Table 6 coefficients, local strips) at the
    # lean-to height -- the lean-to's own Table 7 mono-slope coefficients are not resolved by the engine (stated)
    mwj = CM.member_pd(cfg, s * depth / 1e6, float(lt["roof_z_m"]), "roof", "all", jt)
    p_up, p_dn = -mwj["p_out_kNm2"], mwj["p_in_kNm2"]
    Lr = _num((cfg.get("loads") or {}).get("Lr"))

    def q_joist(c, sw=0.0):
        def q(x):
            g = c["fD"] * (D * 1e-3 * s + sw) + c["fL"] * Lr * 1e-3 * s + c["fS"] * mu(x / 1000.0) * s0 * 1e-3 * s
            if c["fW"] > 0:
                g += p_up * 1e-3 * s           # suction (upward, negative)
            elif c["fW"] < 0:
                g += p_dn * 1e-3 * s
            return g
        return q
    rt_j = ("top flange in compression under gravity, restrained by the roof panels through-fastened to it; under uplift "
            "the bottom flange is braced at %.0f mm (declared bridging)" % _num(jt.get("L_unbraced_mm"), depth))

    def joist(g):
        sec = CM._sec(g)
        sw = (sec.get("mass_kg_m") or 0.0) * 9.80665e-3
        return design_beam_is801(cfg, g, "lean-to roof joist", lambda c: (q_joist(c, sw), []), span_mm=depth,
                                 Lu_gravity_mm=0.0, Lu_uplift_mm=_num(g.get("L_unbraced_mm"), depth), restrained_top=True,
                                 defl_case_fn=lambda: (lambda x: mu(x / 1000.0) * s0 * 1e-3 * s, []),
                                 restraint_text=rt_j,
                                 extra={"snow_drift": {k: v for k, v in drift.items() if k != "mu"},
                                        "load_table": [
                                            {"component": "dead (roof panels, joists, services)", "kNm2": D, "applied": "all rows"},
                                            {"component": "snow at the wall, mu2 s0 (IS 875-4 5.2.4)", "kNm2": drift["s_step_kPa"],
                                             "applied": "snow rows, falling linearly away from the wall"},
                                            {"component": "snow at the front edge", "kNm2": mu(depth / 1000.0) * s0,
                                             "applied": "snow rows"},
                                            {"component": "wind uplift (member pressure)", "kNm2": p_up, "applied": "+W rows"}],
                                        "wind": {"member_pd": mwj, "p_uplift_kNm2": p_up, "p_down_kNm2": p_dn, "cite": mwj["cite"]}})
    jrec = _auto(cfg, jt, joist)
    jsw = (jrec.get("mass_kg_m") or 0.0) * 9.80665e-3
    # joist end reactions per metre of wall (N/mm) for each case: back wall (x = 0) and front wall (x = depth)
    cases = gravity_wind_cases(cfg)

    def reactions(c):
        r = simple_beam(depth, q_joist(c, jsw), [])
        return r["R_left_N"] / s, r["R_right_N"] / s

    recs = [jrec]
    door = lt.get("door") or {}
    wall_kNm2 = _num(lt.get("wall_kNm2"))
    Hf = float(lt.get("front_wall_height_m") or lt["roof_z_m"]) * 1000.0
    if door:
        hd = dict(door["header"])
        span_h = float(door["width_m"]) * 1000.0 + 2.0 * _num(hd.get("bearing_mm"), 50.0)
        above = max(Hf - float(door["height_m"]) * 1000.0, 0.0)

        def q_header(c):
            rb = reactions(c)[1]
            return rb + c["fD"] * wall_kNm2 * 1e-3 * above
        rt_h = ("top flange braced by the joists bearing on it at %.0f mm; bottom flange free" % s)

        def header(g):
            sec = CM._sec(g)
            sw = (sec.get("mass_kg_m") or 0.0) * 9.80665e-3
            return design_beam_is801(cfg, g, "door header", lambda c: (q_header(c) + c["fD"] * sw, []), span_mm=span_h,
                                     Lu_gravity_mm=s, Lu_uplift_mm=span_h, restrained_top=False,
                                     defl_case_fn=lambda: (reactions({"fD": 0.0, "fL": 0.0, "fS": 1.0, "fW": 0.0})[1], []),
                                     restraint_text=rt_h, tag="vestibule",
                                     extra={"opening": "%s m wide x %s m high door in the lean-to front wall"
                                                       % (door["width_m"], door["height_m"]),
                                            "load_basis": "the roof-joist end reactions on the front wall (snow drift profile "
                                                          "included) plus the wall above the opening"})
        hrec = _auto(cfg, hd, header)
        recs.append(hrec)
        hsw = (hrec.get("mass_kg_m") or 0.0) * 9.80665e-3
        jb = dict(door["jambs"])
        trib = float(door["width_m"]) * 1000.0 / 2.0 + _num(jb.get("spacing_mm"), 600.0) / 2.0
        mwjb = CM.member_pd(cfg, trib * Hf / 1e6, float(lt["roof_z_m"]), "wall", "all", jb)
        w_j = max(mwjb["p_in_kNm2"], mwjb["p_out_kNm2"]) * 1e-3 * trib

        def P_jamb(c):
            return ((q_header(c) + c["fD"] * hsw) * span_h / 2.0
                    + reactions(c)[1] * _num(jb.get("spacing_mm"), 600.0) / 2.0 + c["fD"] * wall_kNm2 * 1e-3 * trib * Hf)
        rt_jb = ("door jamb: unbraced over its height %.0f mm (no structural sheathing; IS 801 6.6 / 6.7 over the full "
                 "height)" % Hf)
        jbrec = _auto(cfg, jb, lambda g: design_post_is801(
            cfg, g, "door jamb", P_jamb, height_mm=Hf, w_wind_N_per_mm=w_j, tag="vestibule", restraint_text=rt_jb,
            wind_cite=mwjb["cite"], extra={"wind": {"member_pd": mwjb, "tributary_mm": trib, "cite": mwjb["cite"]},
                                           "axial_basis": "half the header load + the joist beside the jamb + the wall strip"}))
        recs.append(jbrec)
    bs = lt.get("back_studs")
    if bs:
        bs = dict(bs)
        Hb = float(lt["roof_z_m"]) * 1000.0
        sp = float(bs["spacing_mm"])

        def P_back(c):
            return reactions(c)[0] * sp + c["fD"] * wall_kNm2 * 1e-3 * sp * Hb
        rt_b = ("back-wall stud against the building wall: unbraced over its height %.0f mm; sheltered by the building "
                "wall, so axial load only" % Hb)
        brec = _auto(cfg, bs, lambda g: design_post_is801(
            cfg, g, "back-wall stud", P_back, height_mm=Hb, w_wind_N_per_mm=0.0, tag="vestibule", restraint_text=rt_b,
            extra={"axial_basis": "the roof-joist reactions at the wall (drift peak) per stud spacing + the wall"}))
        recs.append(brec)
    rec = {"name": lt.get("name"), "width_m": width / 1000.0, "depth_m": depth / 1000.0, "roof_z_m": lt["roof_z_m"],
           "upper_roof_z_m": lt["upper_roof_z_m"], "snow_drift": {k: v for k, v in drift.items() if k != "mu"},
           "members": [r["id"] for r in recs], "basis": lt.get("basis"), "lateral": lt.get("lateral"),
           "wind_note": ("lean-to roof wind: the building's IS 875-3 Table 6 coefficients with the local strips at the "
                         "lean-to height (the Table 7 mono-slope set is not resolved by the engine)")}
    return recs, rec


# ================================================================================================= roof platforms
def design_roof_platforms(cfg, plats):
    """Equipment platforms on the roof (cfg['roof_platforms'], list): beams spanning between two frames, posts down to
    the rafters, the IS 875-4 5.2.6 drift around the platform, and the platform's dead load on the frame.
        {name, frames [i1, i2] (adjacent frame lines), eave_line j, span_m, posts_from_column_m [a_outer, a_inner],
         beam_trib_m, deck_kNm2 + cite, units [{P_kN, a_m}] (per beam, from frame i1), unit_cite, height_above_roof_m,
         snow_on_platform (bool), beams {...}, posts {..., height_mm}}
    Returns (member records, records)."""
    s0 = _num(((cfg.get("load_plan") or {}).get("snow_summary") or {}).get("s0_kPa"))
    recs, out = [], []
    for k, pl in enumerate(plats or []):
        span = float(pl["span_m"]) * 1000.0
        trib = float(pl["beam_trib_m"]) * 1000.0
        deck = _num(pl.get("deck_kNm2"))
        snow = (MU1 * s0) if (pl.get("snow_on_platform", True) and s0 > 0) else 0.0
        units = [(float(u["P_kN"]) * 1e3, float(u["a_m"]) * 1000.0) for u in pl.get("units") or []]
        bm = dict(pl["beams"])

        def q_beam(c, sw):
            return c["fD"] * (deck * 1e-3 * trib + sw) + c["fS"] * snow * 1e-3 * trib
        rt = ("top flange held by the deck grating fixed to it at %s mm; bottom flange braced at the posts" %
              int(_num(bm.get("L_unbraced_mm"), span))) if bm.get("deck_restrains_top") else \
            ("both flanges unbraced between the posts (%.0f mm)" % span)

        def beam(g):
            sec = CM._sec(g)
            sw = (sec.get("mass_kg_m") or 0.0) * 9.80665e-3
            return design_beam_is801(
                cfg, g, "platform beam", lambda c: (q_beam(c, sw), [(c["fD"] * P, a) for P, a in units]),
                span_mm=span, Lu_gravity_mm=_num(g.get("L_unbraced_mm"), span), Lu_uplift_mm=span,
                restrained_top=bool(g.get("deck_restrains_top")),
                defl_case_fn=lambda: (snow * 1e-3 * trib, [(P, a) for P, a in units]),
                restraint_text=rt, tag=pl.get("name"), cases=[c for c in gravity_wind_cases(cfg) if not c["fW"]],
                extra={"load_table": [{"component": "deck", "kNm2": deck, "applied": "dead"},
                                      {"component": "snow on the platform, mu1 s0 (IS 875-4 4.1)", "kNm2": snow, "applied": "snow rows"},
                                      {"component": "equipment units (per beam)", "kN": [u["P_kN"] for u in pl.get("units") or []],
                                       "applied": "dead, at %s m" % ", ".join("%.2f" % u["a_m"] for u in pl.get("units") or [])}],
                       "unit_cite": pl.get("unit_cite")})
        brec = _auto(cfg, bm, beam)
        recs.append(brec)
        bsw = (brec.get("mass_kg_m") or 0.0) * 9.80665e-3
        cases = [c for c in gravity_wind_cases(cfg) if not c["fW"]]

        def beam_R(c):
            r = simple_beam(span, q_beam(c, bsw), [(c["fD"] * P, a) for P, a in units])
            return max(r["R_left_N"], r["R_right_N"])
        ps = dict(pl["posts"])
        prec = _auto(cfg, ps, lambda g: design_post_is801(
            cfg, g, "platform post", beam_R, height_mm=float(ps["height_mm"]), tag=pl.get("name"), cases=cases,
            restraint_text="short post between the platform beam and the rafter, unbraced over its height"))
        recs.append(prec)
        drift = snow_drift_projection(s0, float(pl["height_above_roof_m"])) if s0 > 0 else None
        dead = simple_beam(span, q_beam({"fD": 1.0, "fS": 0.0}, bsw), list(units))
        psw = (prec.get("mass_kg_m") or 0.0) * 9.80665e-3 * float(ps["height_mm"])
        out.append({"name": pl.get("name"), "frames": list(pl["frames"]), "eave_line": pl.get("eave_line"),
                    "span_m": span / 1000.0, "posts_from_column_m": list(pl["posts_from_column_m"]),
                    "dead_reaction_per_post_N": {"left": dead["R_left_N"] + psw, "right": dead["R_right_N"] + psw},
                    "snow_kNm2": snow, "drift": drift, "members": [brec["id"], prec["id"]],
                    "frame_note": pl.get("frame_note")})
    return recs, out


def platform_frame_loads(cfg):
    """The permanent nodal loads the roof platforms put on the hot-rolled frame: at each knee node (frame line i, eave
    line j, roof level) Fz = -(the post reactions) and the moment of the posts' offsets along the rafter about the knee
    (global X moment for frames spanning Y: a post at +a from the knee gives Mx = -P a; at the far eave the sign flips).
    Only the platform's dead load goes to the frame: its snow replaces the roof snow it shelters."""
    out = []
    try:
        recs, plats = design_roof_platforms(cfg, cfg.get("roof_platforms"))
    except (KeyError, SecondaryError) as ex:
        raise SecondaryError("roof_platforms: %s" % ex)
    lf = cfg.get("lateral_frame") or {}
    NY = int(lf.get("NY") or 1)
    for pl in plats:
        j = int(pl.get("eave_line") or 0)
        sgn = -1.0 if j == 0 else 1.0
        for side, i in zip(("left", "right"), pl["frames"]):
            P = pl["dead_reaction_per_post_N"][side]
            tot = 0.0
            mom = 0.0
            for a in pl["posts_from_column_m"]:
                tot += P
                mom += P * float(a) * 1000.0
            out.append({"node": 100000 + int(i) * 100 + j, "Fz_N": -tot, "Mx_Nmm": sgn * mom, "My_Nmm": 0.0, "level": 1,
                        "note": "%s: dead load of the roof platform (posts at %s m from the column along the rafter), "
                                "applied at the knee with the moment of the post offsets" %
                                (pl.get("name"), ", ".join("%.2f" % float(a) for a in pl["posts_from_column_m"])),
                        "ijk": [int(i), j, 1], "NY": NY})
    return out


# ================================================================================================= purlin cleats
def _purlin_reactions(m, cases):
    """Support reaction (N) per case of a purlin record: simple span w L/2 (+ point loads); lapped continuous: the
    interior-support reaction of the declared continuous span set (laps at 2 EI)."""
    ld = m.get("loads_N_per_mm") or {}
    L = float(m.get("span_mm") or m.get("length_mm"))
    k = 0.5
    cont = m.get("continuity") or {}
    if cont.get("type") == "lapped":
        k = CM.continuous_unit_effects(int(cont["n_spans"]), L, float(cont.get("lap_mm") or 0.0))["R_int"] / L
    pls = m.get("point_loads") or []
    out = []
    for c in cases:
        w = c["fD"] * (_num(ld.get("dead")) + _num(ld.get("collateral")) + _num(ld.get("pv"))) + c["fL"] * _num(ld.get("live")) \
            + float(c.get("fS") or 0.0) * _num(ld.get("snow"))
        if c["fW"] > 0:
            w += _num(ld.get("wind_up"))
        elif c["fW"] < 0:
            w += _num(ld.get("wind_down"))
        R = k * w * L
        for p in pls:
            f = c["fD"] if str(p.get("kind") or "D").upper() == "D" else c["fL"]
            a = float(p["a_m"]) * 1000.0
            R += f * float(p["P_kN"]) * 1e3 * max(a, L - a) / L
        out.append((c, R))
    return out


def design_purlin_cleats(cfg, members, spec):
    """Purlin-to-rafter cleats (cfg['cfs_connections_spec']['purlin_cleat']):
        {bolts {n, d_mm, class, edge_mm, pitch_mm}, cleat {t_mm, fy_MPa, width_mm (along the purlin), bolt_height_mm
         (bolt line above the rafter flange), weld_mm}, roof_pitch_deg, note}
    A plate cleat stands on the rafter flange in the plane of the purlin web, the purlin web bolted to it.  For every
    purlin group and combination: the support reaction R normal to the roof (gravity, snow, uplift; lapped purlins:
    the interior-support reaction) and, under gravity, its downslope component H = R tan(pitch): spec 'downslope'
    = 'cleat' (default, H taken wholly by the cleat) or 'sag rods' (H goes to the declared sag-rod lines tied across
    the ridge and the through-fastened sheeting -- the purlin design's own bracing basis -- not to the cleats).  The
    purlin is fixed with its web on the up-slope face of the cleat, so any H bears the web on the cleat and does not
    pull the bolts (a detailing requirement).
      * bolts in the purlin web, R in shear: IS 801 7.5.1 edge distance, 7.5.3 bearing, 7.5.4 bolt shear (lapped
        purlins: the two nested webs share R);
      * cleat at its base: axial R with minor-axis bending M = H hb + R (t_cleat + t_web)/2 -- uplift: IS 800 11.5.3
        (11.2.1 (a) 0.6 fy, 11.4.1 (c) 0.75 fy); gravity: the IS 800 11.5.2 (a) form with K at its 1 + 0.8 n bound and
        Cm = 1.0 (conservative), fac = 0.6 fcd (11.3.1; 7.1.2.1 class c, the cleat a cantilever K = 2 over hb);
      * fillet welds on both faces along the cleat width: IS 800 11.6.3.1 faw = 0.4 fy on the throat;
      * IS 800 11.1.4: 33 percent only when wind acts with imposed / snow load."""
    import india_cfs_portal as PO
    import india_is800 as HI
    b = spec["bolts"]
    cl = spec["cleat"]
    n = int(b["n"]); d = float(b["d_mm"])
    pitch = math.radians(_num(spec.get("roof_pitch_deg")))
    t_c, w_c = float(cl["t_mm"]), float(cl["width_mm"])
    fy_c = float(cl.get("fy_MPa") or 250.0)
    hb = float(cl["bolt_height_mm"])
    s_w = float(cl["weld_mm"])
    A_c = w_c * t_c
    Z_c = w_c * t_c ** 2 / 6.0
    pd = HI.design_compressive_strength(A_c, fy_c, 2.0 * hb, t_c / math.sqrt(12.0), buckling_class="c")
    fcd = (pd.get("Pd_N") or 0.0) / A_c if pd.get("found") else None
    if not fcd:
        raise SecondaryError("purlin cleat: IS 800 7.1.2.1 fcd not computable (%s)" % pd.get("note"))
    fac = 0.6 * fcd
    to_rods = str(spec.get("downslope") or "cleat").lower().replace("_", " ") == "sag rods"
    out = []
    cases = gravity_wind_cases(cfg)
    for m in members:
        if m.get("role") != "purlin":
            continue
        fy = float(m["Fy_MPa"])
        t = float(CM._sec({"designator": m["designator"]})["t"])
        sheets = 2 if (m.get("continuity") or {}).get("type") == "lapped" else 1
        rows = []
        worst = None
        for c, R in _purlin_reactions(m, cases):
            we = bool(c.get("wind_eq"))
            H = R * math.tan(pitch) if (R > 0 and not to_rods) else 0.0
            Pb = abs(R) / n / sheets
            bolt = M.bolted_connection_75(fy, t, d, Pb, n, float(b["edge_mm"]), float(b["pitch_mm"]),
                                          bolt_class=str(b.get("class", "4.6")), wind_eq=we)
            for nm, ck in bolt["checks"].items():
                rows.append(CM._row(c["label"], "bolts in the purlin web: " + nm,
                                    dict(ck, detailing=True) if nm.startswith("7.5.1") else ck,
                                    {"P_per_bolt_N": round(Pb, 1), "webs": sheets}))
            inc = PO.is800_wsm_increase(we, bool(c["fL"] or c.get("fS")))
            Mc = H * hb + abs(R) * (t_c + t) / 2.0
            fa, fb = abs(R) / A_c, Mc / Z_c
            if R < 0:
                ratio = fa / (0.6 * fy_c * inc) + fb / (0.75 * fy_c * inc)
                rows.append(CM._row(c["label"], "cleat tension + minor-axis bending (IS 800 11.5.3)",
                                    M._rec(ratio, 1.0, "IS 800:2007 11.5.3, 11.2.1 (a), 11.4.1 (c)",
                                           "fa/0.6fy + fb/0.75fy <= 1; " + IS800_WSM_CITE, allowable_increase=inc),
                                    {"fa_MPa": round(fa, 2), "fb_MPa": round(fb, 2), "M_Nmm": round(Mc, 1)}))
            else:
                nn = fa / (fac * inc)
                ratio = nn + (1.0 + 0.8 * nn) * fb / (0.75 * fy_c * inc)
                rows.append(CM._row(c["label"], "cleat compression + minor-axis bending (IS 800 11.5.2)",
                                    M._rec(ratio, 1.0, "IS 800:2007 11.5.2 (a), 11.3.1, 7.1.2.1, 11.4.1 (c)",
                                           "fc/fac + K Cm fb/fab <= 1 with K = 1 + 0.8 n (upper bound), Cm = 1.0; fac = "
                                           "0.6 fcd, fcd class c, KL = 2 hb; " + IS800_WSM_CITE, allowable_increase=inc),
                                    {"fa_MPa": round(fa, 2), "fb_MPa": round(fb, 2), "fac_MPa": round(fac, 2),
                                     "M_Nmm": round(Mc, 1)}))
            a = 0.7 * s_w
            fn = abs(R) / (2.0 * a * w_c) + Mc / (a * w_c * (t_c + a))
            fv = H / (2.0 * a * w_c)
            rows.append(CM._row(c["label"], "cleat fillet welds (IS 800 11.6.3.1)",
                                M._rec(math.hypot(fn, fv), 0.4 * fy_c * inc, "IS 800:2007 11.6.3.1",
                                       "faw = 0.4 fy on the throat; " + IS800_WSM_CITE, allowable_increase=inc),
                                {"R_N": round(R, 1), "H_downslope_N": round(H, 1)}))
            if worst is None or abs(R) > abs(worst[1]):
                worst = (c["label"], R)
        strength = [r for r in rows if isinstance(r.get("dc"), (int, float)) and not r.get("detailing")]
        gov = max(strength, key=lambda r: r["dc"], default={})
        out.append({"id": "purlin-cleat-%s" % m["designator"],
                    "type": "purlin cleat: %d M%d %s bolts in the purlin web, %.0f mm plate cleat %.0f mm wide welded to the "
                            "rafter (%.0f mm fillets both faces)" % (n, d, b.get("class", "4.6"), t_c, w_c, s_w),
                    "member": m["id"], "checks": rows, "dc": gov.get("dc"),
                    "ok": all(r.get("ok") is not False for r in rows) if rows else None,
                    "value": abs(worst[1]) if worst else None, "limit": None, "units": "N",
                    "governing_combo": gov.get("combo"), "governing_check": gov.get("check"),
                    "clause": "IS 801 7.5 (bolts in the purlin web); IS 800:2007 11.2.1, 11.3.1, 11.4.1 (c), 11.5.2, 11.5.3, "
                              "11.6.3.1 (cleat, working stress)",
                    "capacity_basis": "IS801_allowable", "allowable_increase": 1.0, "demand_level": "working",
                    "webs": sheets, "fac_MPa": fac, "note": spec.get("note"),
                    "downslope": ("the downslope component goes to the sag-rod lines tied across the ridge and the "
                                  "through-fastened sheeting, not to the cleat" if to_rods else
                                  "the downslope component R tan(pitch) is taken by the cleat")})
    return out


# ================================================================================================= portal eave struts
def portal_eave_struts(cfg, conns):
    """The eave-strut group(s) of an all-cold-formed portal with the axial force derived from its longitudinal bracing:
    the gable wind / longitudinal earthquake force of one side wall (the bracing block's governing force / 2 sides) is
    collected along the eave into the braced bays -- taken whole through the strut at the braced bay (conservative)."""
    cm = cfg.get("cfs_members") or {}
    gs = CM.groups(cm, "eave_struts")
    if not gs:
        return None
    lb = next((c for c in conns or [] if str(c.get("id") or "").startswith("longitudinal-bracing")), None)
    if not lb or not lb.get("forces_N"):
        raise SecondaryError("eave_struts: the longitudinal bracing forces of the portal are required for the strut force")
    lab, F = max(lb["forces_N"].items(), key=lambda kv: abs(kv[1]))
    P = abs(F) / 2.0
    out = []
    for g in gs:
        if g.get("P_N") is None or str(g.get("P_from") or "") == "longitudinal_bracing":
            g = dict(g, P_N=P, P_cite=("%s: governing longitudinal force %.1f kN (%s) / 2 side walls, taken whole through the "
                                       "strut at the braced bay (conservative)" % (lb["id"], abs(F) / 1e3, lab)))
        out.append(g)
    return out
