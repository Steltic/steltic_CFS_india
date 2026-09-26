"""is801_members.py -- IS 801:1975 (working stress) member checks for cold-formed members (WP3.2).

Internal units are the code's own: kgf/cm2 for stresses, cm for lengths, kgf for forces, with
E = 2 074 000 kgf/cm2 and G = 795 000 kgf/cm2 (IS 801 6.3 / 6.6.1.1 / 6.6.1.2 -- read from the PDF pages 15, 18, 20).
Every public function takes and returns SI (MPa, mm, N, N-mm) and reports the kgf/cm2 values it used.

Every constant below was read from the IS 801 PDF page image at 300 dpi (/home/claude/rv/pdfs/INDIA_STEEL/CFS/pdfs/
IS_801_1975.pdf, printed page in brackets):
  5.2.1.1 [p.6]   (w/t)lim = 1435/sqrt(f); b/t = (2120/sqrt(f))[1 - 465/((w/t) sqrt(f))]; tubes 1540 / 420;
                  wind/EQ: b for 0.75 x stress when the 6.1.2 increase is used; deflection 1850, 2710, 600 (tubes 1990, 545)
  5.2.1.2 [p.7]   be/t = b/t - 0.10 (w/t - 60) for w/t > 60
  5.2.2.1 [p.8]   Imin = 1.83 t^4 sqrt((w/t)^2 - 281 200/Fy) >= 9.2 t^4; dmin = 2.8 t (6th root)((w/t)^2 - 281 200/Fy) >= 4.8 t;
                  no simple lip when w/t > 60
  6.1     [p.11]  F = 0.60 Fy (Table 2: Fy 21/24/30/36 kgf/mm2 -> F 1250/1450/1800/2160 kgf/cm2)
  6.1.2   [p.13]  33 1/3 % increase for wind/EQ (alone or combined; section not less than that for DL + LL)
  6.2     [p.13-14] Fc = 0.60 Fy (w/t <= 530/sqrt(Fy)); Fy[0.767 - (3.15/10^4)(w/t) sqrt(Fy)] (<= 1210/sqrt(Fy));
                  562 000/(w/t)^2 (<= 25); 25-60: angle struts 562 000/(w/t)^2, others 1390 - 20 w/t;
                  footnote Fy < 2320: Fc = 0.6 Fy - [(w/t) - 530/sqrt(Fy)](0.6 Fy - 900)/(25[1 - 21.2/sqrt(Fy)])
  6.3     [p.14-15] Fb (I / channel): 2/3 Fy - Fy^2/(5.4 pi^2 E Cb)(L^2 Sxc/(d Iyc)) between 0.36 and 1.8 pi^2 E Cb/Fy;
                  0.6 pi^2 E Cb d Iyc/(L^2 Sxc) beyond; zeds 0.18/0.9, 2.7, 0.3; Cb = 1.75 + 1.05(M1/M2) + 0.3(M1/M2)^2 <= 2.3
  6.4.1   [p.15]  Fv = 1275 sqrt(Fy)/(h/t) <= 0.40 Fy (h/t <= 4590/sqrt(Fy)); 5 850 000/(h/t)^2 beyond
  6.4.2/3 [p.16]  Fbw = 36 560 000/(h/t)^2; sqrt((fbw/Fbw)^2 + (fv/Fv)^2) <= 1
  6.5     [p.16-17] Pmax (single web, R <= t): end 70 t^2 [98 + 4.20 N/t - 0.022 (N/t)(h/t) - 0.011 h/t][1.33 - 0.33 Fy/2320](Fy/2320)
                  x (1.15 - 0.15 R/t) for R up to 4t; interior 70 t^2 [305 + 2.30 N/t - 0.009 (N/t)(h/t) - 0.5 h/t]
                  [1.22 - 0.22 Fy/2320](Fy/2320) x (1.06 - 0.06 R/t); back-to-back: t^2 Fy (4.44 + 0.558 sqrt(N/t)),
                  t^2 Fy (6.66 + 1.146 sqrt(N/t)); N <= h; h/t <= 150
  6.6.1.1 [p.17-18] Fa1 = 0.522 Q Fy - (Q Fy KL/r / 12 500)^2 for KL/r < Cc/sqrt(Q); 10 680 000/(KL/r)^2 beyond; Cc = sqrt(2 pi^2 E/Fy)
  6.6.1.2 [p.19-20] Fa2 = 0.522 Fy - Fy^2/(7.67 sigma_TFO) (sigma_TFO > 0.5 Fy); 0.522 sigma_TFO otherwise;
                  sigma_TFO = (1/2beta)[(sigma_ex + sigma_t) - sqrt((sigma_ex + sigma_t)^2 - 4 beta sigma_ex sigma_t)];
                  sigma_ex = pi^2 E/(KL/rx)^2; sigma_t = (1/(A r0^2))[G J + pi^2 E Cw/(KL)^2]; beta = 1 - (x0/r0)^2;
                  r0^2 = rx^2 + ry^2 + x0^2
  6.6.1.3 [p.20]  Q < 1: replace Fy by Q Fy in 6.6.1.2
  6.6.2   [p.20-21] bracing / secondary members L/r > 120: Fas = Fa/(1.3 - L/(400 r));  6.6.3 KL/r <= 200
  6.7.1   [p.21]  fa/Fa1 + Cmx fbx/((1 - fa/F'ex) Fbx) + Cmy fby/((1 - fa/F'ey) Fby) <= 1 and fa/Fa0 + fbx/Fb1x + fby/Fb1y <= 1;
                  fa/Fa1 < 0.15: fa/Fa1 + fbx/Fbx + fby/Fby <= 1
  6.7.2   [p.21-22] (a) fa/Fa1 + fb1 Cm/(Fb1 [1 - fa/F'e]) <= 1; fa/Fa0 + fb1/Fb1 <= 1  (singly-symmetric, bending in the
                  plane of symmetry); (b) e > 0 (load on the side away from the shear centre): fa <= Fa from sigma_TF
  6.7 defs [p.23-24] Cm = 0.85 (sway); 0.6 - 0.4 M1/M2 >= 0.4 (braced, no transverse load); 0.85 / 1.0 transverse load;
                  F'e = 12 pi^2 E/(23 (K Lb/rb)^2) (may be increased 1/3 per 6.1.2); Fa0 = 6.6.1.1 at L = 0
  7.2.1   [p.26]  fillet / plug weld throat shear 955 / 1100 / 1250 kgf/cm2 for Fy < 2500 / 2500-3500 / > 3500
  7.3     [p.27]  two channels back to back: Smax = L rcy/(2 r1) (compression); L/6 (flexure)
  7.5     [p.29-30] 7.5.1 clear spacing / edge >= 1.5 d and >= P/(0.6 Fy t); 7.5.2 net section (1.0 - 0.9 r + 3 r d/s) 0.6 Fy
                  <= 0.6 Fy; 7.5.3 bearing 2.1 Fy; 7.5.4 bolt shear 970 (precision) / 820 (black) / 1060 (4.6)
  8.1     [p.30-31] sheathing both faces; amax = 8 E I2 Kw/(A^2 Fy^2) and <= L r2/(2 r1); Kw,min = Fy^2 a A^2/(8 E I2);
                  Pmin = Kw Ps (L/240) / (2 sqrt(E I2 Kw/a) - Ps)   [glyph: the '2' printed at the radical is the coefficient
                  of the buckling load of a bar on an elastic foundation, Pcr = 2 sqrt(E I beta); recorded in the result]
"""
from __future__ import annotations
import math

E_KGF = 2074000.0          # kgf/cm2 (IS 801 6.3 / 6.6.1.1)
G_KGF = 795000.0           # kgf/cm2 (IS 801 6.6.1.2)
E_MPA = 203400.0           # = 2 074 000 x 0.0980665
KGF_CM2 = 0.0980665        # MPa per kgf/cm2
MPA_TO_KGF = 1.0 / KGF_CM2  # 10.197 kgf/cm2 per MPa
N_TO_KGF = 1.0 / 9.80665
SRC = "is801_members (IS 801:1975, PDF /home/claude/rv/pdfs/INDIA_STEEL/CFS/pdfs/IS_801_1975.pdf)"
PI2 = math.pi ** 2
INCREASE_WL_EL = 4.0 / 3.0  # IS 801 6.1.2: 33 1/3 percent


def nmm_to_kgfcm(M_Nmm):
    """N-mm -> kgf-cm: 1 N-mm = 0.1 N-cm = 0.1/9.80665 kgf-cm (C01: the demand-stress side used / 1e3, which made fb
    100 x too small; the capacity side Ma = Fb Sx x 98.0665 N-mm per kgf-cm was fixed in WP6 / E6)."""
    return M_Nmm * N_TO_KGF / 10.0


def _rec(value, limit, clause, cite, ok=None, **extra):
    dc = None
    if value is not None and limit not in (None, 0):
        dc = abs(value) / limit
    if ok is None and dc is not None:
        ok = dc <= 1.0 + 1e-9
    r = {"value": value, "limit": limit, "dc": dc, "ok": ok, "clause": clause, "cite": cite, "source": SRC}
    r.update(extra)
    return r


# ---------------------------------------------------------------------------------------------------------------
# 5.2 effective widths (stiffened elements) -- kgf/cm2, cm
# ---------------------------------------------------------------------------------------------------------------
def eff_width_5211(w_cm, t_cm, f_kgf, tube=False, deflection=False):
    """IS 801 5.2.1.1 effective design width b (cm) of a stiffened element of flat width w at stress f (kgf/cm2)."""
    if f_kgf <= 0:
        return w_cm
    wt = w_cm / t_cm
    sf = math.sqrt(f_kgf)
    if deflection:
        lim, c1, c2 = (1990.0 if tube else 1850.0) / sf, 2710.0, (545.0 if tube else 600.0)
    else:
        lim, c1, c2 = (1540.0 if tube else 1435.0) / sf, 2120.0, (420.0 if tube else 465.0)
    if wt <= lim:
        return w_cm
    bt = (c1 / sf) * (1.0 - c2 / (wt * sf))
    return max(min(bt * t_cm, w_cm), 0.0)


def eff_width_5212(w_cm, t_cm, f_kgf):
    """IS 801 5.2.1.2: sub-element / one-edge-connected element with w/t > 60: be/t = b/t - 0.10 (w/t - 60)."""
    b = eff_width_5211(w_cm, t_cm, f_kgf)
    wt = w_cm / t_cm
    if wt <= 60.0:
        return b
    return max((b / t_cm - 0.10 * (wt - 60.0)) * t_cm, 0.0)


def lip_adequacy_5221(w_cm, t_cm, Fy_kgf, d_lip_cm):
    """IS 801 5.2.2.1 simple-lip edge stiffener: dmin = 2.8 t (w/t)^2 - 281200/Fy)^(1/6) >= 4.8 t; w/t <= 60."""
    wt = w_cm / t_cm
    arg = wt ** 2 - 281200.0 / Fy_kgf
    dmin = max(2.8 * t_cm * (arg ** (1.0 / 6.0) if arg > 0 else 0.0), 4.8 * t_cm)
    Imin = max(1.83 * t_cm ** 4 * (math.sqrt(arg) if arg > 0 else 0.0), 9.2 * t_cm ** 4)
    ok = (d_lip_cm >= dmin - 1e-9) and (wt <= 60.0)
    return {"dmin_mm": dmin * 10.0, "d_lip_mm": d_lip_cm * 10.0, "Imin_cm4": Imin, "w_t": wt, "ok": ok,
            "clause": "IS 801 5.2.2.1", "cite": "dmin = 2.8 t (6th root)((w/t)^2 - 281 200/Fy) but not less than 4.8 t"}


# ---------------------------------------------------------------------------------------------------------------
# 6.2 unstiffened elements
# ---------------------------------------------------------------------------------------------------------------
def Fc_unstiffened_62(wt, Fy_kgf, angle_strut=False):
    """IS 801 6.2 allowable compression Fc (kgf/cm2) on a flat unstiffened element of flat-width ratio w/t."""
    sFy = math.sqrt(Fy_kgf)
    if wt <= 530.0 / sFy:
        return 0.60 * Fy_kgf, "6.2(a)"
    if wt <= 1210.0 / sFy:
        if Fy_kgf < 2320.0:
            # footnote: yield < 2320 kgf/cm2, w/t between 530/sqrt(Fy) and 25
            fc = 0.6 * Fy_kgf - (wt - 530.0 / sFy) * (0.6 * Fy_kgf - 900.0) / (25.0 * (1.0 - 21.2 / sFy))
            return fc, "6.2(b) footnote (Fy < 2320)"
        return Fy_kgf * (0.767 - (3.15e-4) * wt * sFy), "6.2(b)"
    if wt <= 25.0:
        if Fy_kgf < 2320.0:
            fc = 0.6 * Fy_kgf - (wt - 530.0 / sFy) * (0.6 * Fy_kgf - 900.0) / (25.0 * (1.0 - 21.2 / sFy))
            return fc, "6.2(c) footnote (Fy < 2320)"
        return 562000.0 / wt ** 2, "6.2(c)"
    if wt <= 60.0:
        if angle_strut:
            return 562000.0 / wt ** 2, "6.2(d) angle strut"
        return 1390.0 - 20.0 * wt, "6.2(d)"
    return None, "6.2: w/t > 60 not covered"


# ---------------------------------------------------------------------------------------------------------------
# section model (IS 811 props -> stiffened / unstiffened elements) and Q
# ---------------------------------------------------------------------------------------------------------------
def _elements(sec):
    """Elements of a lipped / unlipped channel, hat or zed from is811_sections.props (mm):
    returns (stiffened [(w_mm, count)], unstiffened [(w_mm, count)], lip_check_inputs)."""
    fl = sec.get("flats") or {}
    t = sec["t"]
    typ = sec["type"]
    if typ in ("CLS", "CLR", "HS", "HRH", "HRB", "LZ"):
        # web stiffened; flanges stiffened by the lip if 5.2.2.1 is met (checked by caller); lips unstiffened
        nweb = 2 if typ in ("HS", "HRH", "HRB") else 1
        nfl = 1 if typ in ("HS", "HRH", "HRB") else 2
        return ([(fl["web"], nweb), (fl["flange"], nfl)], [(fl["lip"], 2)],
                {"w_flange": fl["flange"], "d_lip": sec.get("c") or 0.0})
    if typ in ("CWS", "CWR"):
        return [(fl["web"], 1)], [(fl["flange"], 2)], None
    if typ in ("EA", "UA"):
        return [], [(fl["leg_h"], 1), (fl["leg_b"], 1)], None
    return [], [], None


def q_factor(sec, Fy_MPa, f_MPa=None, wind_eq=False):
    """IS 801 6.6.1.1 Q = Qs x Qa for an IS 811 section (mm props).  Qs from the weakest unstiffened element (6.2),
    Qa = effective area / gross area with the stiffened elements at stress F (6.1) -- or at the stress Fa used for Qs
    when both element kinds exist (6.6.1.1 (3)); the full area of unstiffened elements is included.
    wind_eq: effective widths for 0.75 x stress (5.2.1.1 note, with the 6.1.2 increase)."""
    Fy = Fy_MPa * MPA_TO_KGF
    t = sec["t"] / 10.0
    stiff, unstiff, lipin = _elements(sec)
    F = 0.60 * Fy
    Qs, Qs_note = 1.0, "no unstiffened elements"
    worst = None
    for w_mm, n in unstiff:
        if w_mm <= 0:
            continue
        wt = w_mm / sec["t"]
        Fc, cl = Fc_unstiffened_62(wt, Fy, angle_strut=sec["type"] in ("EA", "UA"))
        if Fc is None:
            return {"Q": None, "ok": None, "note": "unstiffened element w/t = %.1f > 60 (6.2)" % wt}
        if worst is None or Fc < worst[0]:
            worst = (Fc, wt, cl)
    lip = None
    if lipin is not None:
        lip = lip_adequacy_5221(lipin["w_flange"] / 10.0, t, Fy, lipin["d_lip"] / 10.0)
    if worst is not None:
        Qs = min(worst[0] / F, 1.0)
        Qs_note = "weakest unstiffened element w/t = %.1f: Fc = %.0f kgf/cm2 (%s) / F = %.0f" % (worst[1], worst[0], worst[2], F)
    f_base = (f_MPa * MPA_TO_KGF) if f_MPa else (Qs * F if worst is not None else F)
    if wind_eq:
        f_base = 0.75 * f_base
    A = sec["A"] / 100.0
    Ae = A
    widths = {}
    for w_mm, n in stiff:
        if w_mm <= 0:
            continue
        w = w_mm / 10.0
        if lip is not None and not lip["ok"] and w_mm == lipin["w_flange"]:
            # inadequate lip: flange treated as unstiffened (6.2 stress reduction, no width reduction)
            Fc, cl = Fc_unstiffened_62(w_mm / sec["t"], Fy)
            if Fc is not None:
                Qs = min(Qs, Fc / F)
                Qs_note += "; flange lip inadequate (5.2.2.1) -> flange unstiffened, Fc = %.0f (%s)" % (Fc, cl)
            widths["flange"] = w_mm
            continue
        b = eff_width_5212(w, t, f_base) if (w / t) > 60 else eff_width_5211(w, t, f_base)
        Ae -= (w - b) * t * n
        widths["web" if w_mm == (sec.get("flats") or {}).get("web") else "flange"] = b * 10.0
    Qa = Ae / A
    return {"Q": Qs * Qa, "Qs": Qs, "Qa": Qa, "Ae_mm2": Ae * 100.0, "A_mm2": sec["A"], "f_kgf_cm2": f_base,
            "eff_widths_mm": widths, "lip": lip, "Qs_note": Qs_note, "ok": True,
            "clause": "IS 801 6.6.1.1 (Q = Qs Qa), 5.2.1.1, 6.2, 5.2.2.1", "source": SRC}


# ---------------------------------------------------------------------------------------------------------------
# 6.6 compression
# ---------------------------------------------------------------------------------------------------------------
def Cc(Fy_kgf):
    return math.sqrt(2.0 * PI2 * E_KGF / Fy_kgf)


def fa1_kgf(Fy_kgf, Q, KLr, form_b=False, t_mm=None):
    """IS 801 6.6.1.1 (a): Fa1 = 0.522 Q Fy - (Q Fy KL/r / 12 500)^2 for KL/r < Cc/sqrt(Q), else 10 680 000/(KL/r)^2.
    form_b: 6.6.1.1 (b) (Q = 1, t >= 2.29 mm, KL/r < Cc) alternative."""
    cc = Cc(Fy_kgf)
    if form_b and Q >= 1.0 and t_mm is not None and t_mm >= 2.29 and KLr < cc:
        x = KLr / cc
        return ((1.0 - x ** 2 / 2.0) * Fy_kgf) / (5.0 / 3.0 + 3.0 * x / 8.0 - x ** 3 / 8.0), "6.6.1.1(b)"
    if KLr < cc / math.sqrt(Q):
        return 0.522 * Q * Fy_kgf - (Q * Fy_kgf * KLr / 12500.0) ** 2, "6.6.1.1(a) KL/r < Cc/sqrt(Q)"
    return 10680000.0 / KLr ** 2, "6.6.1.1(a) KL/r >= Cc/sqrt(Q)"


def is801_fa1(Fy_MPa, Q, KLr, form_b=False, t_mm=None):
    """SI wrapper: Fa1 in MPa."""
    fa, cl = fa1_kgf(Fy_MPa * MPA_TO_KGF, Q, KLr, form_b, t_mm)
    return fa * KGF_CM2


def sigma_tfo_kgf(sec, KLx_cm, KLt_cm):
    """IS 801 6.6.1.2 (a) elastic torsional-flexural buckling stress (kgf/cm2) for a singly-symmetric section
    (x-x the axis of symmetry).  sec: is811 props in mm.  Returns None with a reason when x0 / J / Cw are not printed."""
    for k in ("x0", "J", "Cw"):
        if sec.get(k) is None:
            return None, "IS 811 does not print %s for %s (found:false) -- torsional-flexural buckling not evaluable" % (k, sec.get("label"))
    A = sec["A"] / 100.0
    rx, ry, x0 = sec["rx"] / 10.0, sec["ry"] / 10.0, sec["x0"] / 10.0
    J, Cw = sec["J"] / 1e4, sec["Cw"] / 1e6
    r0sq = rx ** 2 + ry ** 2 + x0 ** 2
    beta = 1.0 - x0 ** 2 / r0sq
    s_ex = PI2 * E_KGF / (KLx_cm / rx) ** 2
    s_t = (G_KGF * J + PI2 * E_KGF * Cw / KLt_cm ** 2) / (A * r0sq)
    s = s_ex + s_t
    tfo = (s - math.sqrt(max(s * s - 4.0 * beta * s_ex * s_t, 0.0))) / (2.0 * beta)
    return tfo, {"sigma_ex": s_ex, "sigma_t": s_t, "beta": beta, "r0_cm": math.sqrt(r0sq)}


def fa2_kgf(Fy_kgf, tfo):
    """IS 801 6.6.1.2: Fa2 = 0.522 Fy - Fy^2/(7.67 sigma_TFO) when sigma_TFO > 0.5 Fy; 0.522 sigma_TFO otherwise."""
    if tfo > 0.5 * Fy_kgf:
        return 0.522 * Fy_kgf - Fy_kgf ** 2 / (7.67 * tfo), "6.6.1.2 sigma_TFO > 0.5 Fy"
    return 0.522 * tfo, "6.6.1.2 sigma_TFO <= 0.5 Fy"


def compression_allowable(sec, Fy_MPa, KLx_mm, KLy_mm, KLt_mm=None, braced_against_twist=False, wind_eq=False,
                          secondary=False, form_b=False):
    """Allowable average compression stress Fa (MPa) and load Pa (N) for an IS 811 section (mm props).
    Fa = min(Fa1 about x and y, Fa2 torsional-flexural unless braced against twisting / doubly symmetric).
    Q per 6.6.1.1; 6.6.1.3 replaces Fy by Q Fy in 6.6.1.2 when Q < 1.  wind_eq adds the 6.1.2 increase (x 4/3)
    and uses 0.75 f effective widths.  secondary: 6.6.2 (L/r > 120) reduction."""
    Fy = Fy_MPa * MPA_TO_KGF
    q = q_factor(sec, Fy_MPa, wind_eq=wind_eq)
    if q.get("Q") is None:
        return {"ok": None, "found": False, "note": q.get("note"), "clause": "IS 801 6.6.1.1 / 6.2"}
    Q = q["Q"]
    rx, ry = sec["rx"] / 10.0, sec["ry"] / 10.0
    r_min = (sec.get("r_min") or min(sec["rx"], sec["ry"])) / 10.0
    klr_x, klr_y = KLx_mm / 10.0 / rx, KLy_mm / 10.0 / ry
    klr = max(klr_x, klr_y)
    if sec.get("nonsymmetric"):
        klr = max(klr, max(KLx_mm, KLy_mm) / 10.0 / r_min)
    fa1, cl1 = fa1_kgf(Fy, Q, klr, form_b=form_b, t_mm=sec["t"])
    rec = {"Q": Q, "Qs": q["Qs"], "Qa": q["Qa"], "KLr_x": klr_x, "KLr_y": klr_y, "KLr": klr,
           "Cc": Cc(Fy), "Cc_over_sqrtQ": Cc(Fy) / math.sqrt(Q),
           "Fa1_kgf_cm2": fa1, "Fa1_MPa": fa1 * KGF_CM2, "Fa1_clause": cl1, "eff_widths_mm": q["eff_widths_mm"],
           "lip_5221": q.get("lip"), "Qs_note": q["Qs_note"]}
    Fa = fa1
    governing = cl1
    tfb_applies = (sec.get("singly_symmetric") or sec.get("nonsymmetric")) and not braced_against_twist \
        and not sec.get("doubly_symmetric")
    if tfb_applies:
        KLt = (KLt_mm if KLt_mm is not None else KLy_mm) / 10.0
        tfo, det = sigma_tfo_kgf(sec, KLx_mm / 10.0, KLt)
        if tfo is None:
            rec.update(Fa2_MPa=None, tfb_note=det, ok=None)
            return dict(rec, found=False, note=det, clause="IS 801 6.6.1.2")
        Fy_eff = Q * Fy if Q < 1.0 else Fy               # 6.6.1.3
        fa2, cl2 = fa2_kgf(Fy_eff, tfo)
        rec.update(sigma_TFO_kgf_cm2=tfo, sigma_TFO_MPa=tfo * KGF_CM2, Fa2_kgf_cm2=fa2, Fa2_MPa=fa2 * KGF_CM2,
                   Fa2_clause=cl2 + (" with Q Fy (6.6.1.3)" if Q < 1.0 else ""), tfb_detail=det)
        if fa2 < Fa:
            Fa, governing = fa2, rec["Fa2_clause"]
    else:
        rec["tfb_note"] = ("braced against twisting (8.1 sheathing both faces / bracing)" if braced_against_twist
                           else "doubly symmetric / not subject to torsional-flexural buckling")
    if secondary and klr > 120.0:
        Fa = Fa / (1.3 - klr / 400.0)
        governing += " ; 6.6.2 secondary member L/r > 120: Fa/(1.3 - L/400r)"
    if klr > 200.0:
        rec["slenderness_6_6_3"] = _rec(klr, 200.0, "IS 801 6.6.3", "KL/r of compression members shall not exceed 200")
    inc = INCREASE_WL_EL if wind_eq else 1.0
    A = sec["A"] / 100.0
    rec.update(Fa_kgf_cm2=Fa, Fa_MPa=Fa * KGF_CM2, allowable_increase=inc, Fa_design_MPa=Fa * KGF_CM2 * inc,
               Pa_N=Fa * A * inc * 9.80665, Pa_kN=Fa * A * inc * 9.80665 / 1e3, governing=governing,
               capacity_basis="IS801_allowable", clause="IS 801 6.6.1.1 / 6.6.1.2 / 6.6.1.3 / 6.1.2",
               cite="Fa1 = 0.522 Q Fy - (Q Fy KL/r / 12 500)^2 ...; Fa2 = 0.522 sigma_TFO", source=SRC, ok=True)
    return rec


def check_compression(sec, Fy_MPa, P_N, KLx_mm, KLy_mm, **kw):
    cap = compression_allowable(sec, Fy_MPa, KLx_mm, KLy_mm, **kw)
    if cap.get("ok") is None:
        return dict(cap, value=P_N, limit=None, dc=None)
    r = _rec(P_N, cap["Pa_N"], cap["clause"], cap["cite"])
    r.update({k: v for k, v in cap.items() if k not in r})
    return r


# ---------------------------------------------------------------------------------------------------------------
# 6.3 laterally unbraced beams, 6.1 / 6.4 / 6.5
# ---------------------------------------------------------------------------------------------------------------
def cb_63(M1, M2):
    """Cb = 1.75 + 1.05 (M1/M2) + 0.3 (M1/M2)^2 <= 2.3 (M1 smaller, ratio + for reverse curvature); 1.0 when a
    moment within the unbraced length exceeds both end moments or for combined axial + bending (6.7)."""
    if M2 == 0:
        return 1.0
    r = M1 / M2
    return min(1.75 + 1.05 * r + 0.3 * r * r, 2.3)


def fb_ltb_kgf(Fy_kgf, L_cm, d_cm, Iyc_cm4, Sxc_cm3, Cb=1.0, zed=False):
    """IS 801 6.3 allowable compression stress Fb (kgf/cm2) for a laterally unsupported I / channel (zed) beam."""
    x = L_cm ** 2 * Sxc_cm3 / (d_cm * Iyc_cm4)
    lo, hi, k1, k2 = (0.18, 0.9, 2.7, 0.3) if zed else (0.36, 1.8, 5.4, 0.6)
    pe = PI2 * E_KGF * Cb
    if x <= lo * pe / Fy_kgf:
        return 0.60 * Fy_kgf, "6.3: L^2 Sxc/(d Iyc) <= %.2f pi^2 E Cb/Fy -> F = 0.6 Fy governs" % lo
    if x < hi * pe / Fy_kgf:
        return min(2.0 / 3.0 * Fy_kgf - Fy_kgf ** 2 / (k1 * pe) * x, 0.60 * Fy_kgf), "6.3(%s) inelastic: 2/3 Fy - Fy^2/(%.1f pi^2 E Cb) (L^2 Sxc/(d Iyc))" % ("b" if zed else "a", k1)
    return k2 * pe * d_cm * Iyc_cm4 / (L_cm ** 2 * Sxc_cm3), "6.3(%s) elastic: %.1f pi^2 E Cb d Iyc/(L^2 Sxc)" % ("b" if zed else "a", k2)


def bending_allowable(sec, Fy_MPa, L_unbraced_mm, Cb=1.0, wind_eq=False, compression_flange_restrained=False):
    """Allowable bending stress Fb (MPa) about x-x and moment Ma (N-mm) for an IS 811 channel / zed / hat:
    min(F = 0.6 Fy (6.1), 6.2 Fc of unstiffened compression elements, 6.3 LTB) on the effective section modulus
    (5.2.1.1 widths at the resulting stress).  Iyc = Iy/2 for sections symmetric about x (6.3 definition)."""
    Fy = Fy_MPa * MPA_TO_KGF
    F = 0.60 * Fy
    typ = sec["type"]
    d = sec["h"] / 10.0
    Ix, Iy = sec["Ix"] / 1e4, sec["Iy"] / 1e4
    Sxc = Ix / (d / 2.0) if typ != "LZ" else Ix / (d / 2.0)
    Iyc = Iy / 2.0
    fb1 = F
    notes = []
    # 6.2: unstiffened compression element (lip of a lipped section / flange of an unlipped channel)
    stiff, unstiff, lipin = _elements(sec)
    for w_mm, n in unstiff:
        if w_mm > 0:
            Fc, cl = Fc_unstiffened_62(w_mm / sec["t"], Fy)
            if Fc is not None and Fc < fb1:
                fb1 = Fc
                notes.append("6.2 unstiffened element w/t = %.1f: Fc = %.0f kgf/cm2 (%s)" % (w_mm / sec["t"], Fc, cl))
    lip = lip_adequacy_5221(lipin["w_flange"] / 10.0, sec["t"] / 10.0, Fy, lipin["d_lip"] / 10.0) if lipin else None
    if lip is not None and not lip["ok"]:
        Fc, cl = Fc_unstiffened_62(lipin["w_flange"] / sec["t"], Fy)
        if Fc is not None and Fc < fb1:
            fb1 = Fc
            notes.append("flange lip inadequate (5.2.2.1): flange unstiffened Fc = %.0f (%s)" % (Fc, cl))
    Fb = fb1
    ltb_cl = "6.3 not applicable: compression flange restrained"
    if not compression_flange_restrained and L_unbraced_mm and L_unbraced_mm > 0:
        fb3, ltb_cl = fb_ltb_kgf(Fy, L_unbraced_mm / 10.0, d, Iyc, Sxc, Cb=Cb, zed=(typ == "LZ"))
        Fb = min(Fb, fb3)
    # effective section modulus at the design stress (compression flange stiffened element at f = Fb)
    f_eff = 0.75 * Fb if wind_eq else Fb
    t = sec["t"] / 10.0
    fl = sec.get("flats") or {}
    b_fl = eff_width_5211((fl.get("flange") or 0.0) / 10.0, t, f_eff) if fl.get("flange") else None
    Sx_eff = Sxc
    if b_fl is not None and fl.get("flange"):
        w = fl["flange"] / 10.0
        if b_fl < w - 1e-9:
            # remove (w - b) t from the compression flange at y = d/2 - t/2 and recompute Ix about the shifted centroid
            A = sec["A"] / 100.0
            dA = (w - b_fl) * t
            yf = d / 2.0 - t / 2.0
            ybar = -dA * yf / (A - dA)
            Ix_e = Ix - dA * yf ** 2 - (A - dA) * ybar ** 2
            Sx_eff = Ix_e / (d / 2.0 - ybar)
    inc = INCREASE_WL_EL if wind_eq else 1.0
    return {"Fb_kgf_cm2": Fb, "Fb_MPa": Fb * KGF_CM2, "Fb1_kgf_cm2": fb1, "Fb1_MPa": fb1 * KGF_CM2,
            "Sxc_cm3": Sxc, "Sx_eff_cm3": Sx_eff, "Iyc_cm4": Iyc, "Cb": Cb, "ltb_clause": ltb_cl, "notes": notes,
            "lip_5221": lip, "allowable_increase": inc, "Fb_design_MPa": Fb * KGF_CM2 * inc,
            # kgf/cm2 x cm3 = kgf-cm; 1 kgf-cm = 9.80665 N x 10 mm = 98.0665 N-mm (WP6-fix: the x 1e3 factor gave 100 x Ma)
            "Ma_Nmm": Fb * Sx_eff * inc * 98.0665, "Ma_kNm": Fb * Sx_eff * inc * 98.0665 / 1e6,
            "capacity_basis": "IS801_allowable", "clause": "IS 801 6.1 / 6.2 / 6.3 / 5.2.1.1 / 6.1.2",
            "cite": "Fb = 0.6 pi^2 E Cb d Iyc/(L^2 Sxc) when L^2 Sxc/(d Iyc) >= 1.8 pi^2 E Cb/Fy", "source": SRC, "ok": True}


def web_shear_64(sec, Fy_MPa, V_N, wind_eq=False):
    """IS 801 6.4.1 average shear stress on the flat web(s)."""
    Fy = Fy_MPa * MPA_TO_KGF
    t = sec["t"] / 10.0
    h = (sec.get("flats") or {}).get("web", sec["h"] - 2 * sec["t"]) / 10.0
    nweb = 2 if sec.get("hat") else 1
    ht = h / t
    if ht <= 4590.0 / math.sqrt(Fy):
        Fv = min(1275.0 * math.sqrt(Fy) / ht, 0.40 * Fy); cl = "6.4.1(a)"
    else:
        Fv = 5850000.0 / ht ** 2; cl = "6.4.1(b)"
    inc = INCREASE_WL_EL if wind_eq else 1.0
    fv = V_N * N_TO_KGF / (h * t * nweb)
    r = _rec(fv * KGF_CM2, Fv * inc * KGF_CM2, "IS 801 " + cl, "Fv = 1275 sqrt(Fy)/(h/t) with a maximum of 0.40 Fy",
             h_t=ht, Fv_kgf_cm2=Fv, fv_kgf_cm2=fv, allowable_increase=inc, capacity_basis="IS801_allowable",
             Va_N=Fv * inc * h * t * nweb * 9.80665)
    return r


def web_bending_shear_643(sec, Fy_MPa, M_Nmm, V_N, wind_eq=False):
    """IS 801 6.4.2 / 6.4.3: fbw <= Fbw = 36 560 000/(h/t)^2 and sqrt((fbw/Fbw)^2 + (fv/Fv)^2) <= 1."""
    t = sec["t"] / 10.0
    h = (sec.get("flats") or {}).get("web", sec["h"] - 2 * sec["t"]) / 10.0
    ht = h / t
    Fbw = 36560000.0 / ht ** 2
    Ix = sec["Ix"] / 1e4
    fbw = nmm_to_kgfcm(M_Nmm) * (h / 2.0) / Ix               # kgf-cm x cm / cm4 at the flange-web junction
    sh = web_shear_64(sec, Fy_MPa, V_N, wind_eq=wind_eq)
    Fy = Fy_MPa * MPA_TO_KGF
    Fv_nolim = 1275.0 * math.sqrt(Fy) / ht if ht <= 4590.0 / math.sqrt(Fy) else 5850000.0 / ht ** 2
    inc = INCREASE_WL_EL if wind_eq else 1.0
    comb = math.sqrt((fbw / (Fbw * inc)) ** 2 + (sh["fv_kgf_cm2"] / (Fv_nolim * inc)) ** 2)
    return {"web_bending": _rec(fbw * KGF_CM2, Fbw * inc * KGF_CM2, "IS 801 6.4.2", "Fbw = 36 560 000/(h/t)^2 kgf/cm2",
                                allowable_increase=inc, capacity_basis="IS801_allowable"),
            "web_shear": sh,
            "combined": _rec(comb, 1.0, "IS 801 6.4.3", "sqrt((fbw/Fbw)^2 + (fv/Fv)^2) does not exceed unity",
                             allowable_increase=inc, capacity_basis="IS801_allowable")}


def web_crippling_65(sec, Fy_MPa, P_N, N_bearing_mm, end=True, back_to_back=False, wind_eq=False):
    """IS 801 6.5 allowable concentrated load / reaction Pmax (N) on an unreinforced web."""
    Fy = Fy_MPa * MPA_TO_KGF
    t = sec["t"] / 10.0
    h = (sec.get("flats") or {}).get("web", sec["h"] - 2 * sec["t"]) / 10.0
    ht = h / t
    N = min(N_bearing_mm / 10.0, h)
    Nt = N / t
    R = (sec.get("Ri") or 1.5 * sec["t"]) / 10.0
    Rt = R / t
    if ht > 150.0:
        return {"ok": None, "found": False, "note": "h/t = %.0f > 150: 6.5 requires means of transmitting the load directly into the web" % ht,
                "clause": "IS 801 6.5"}
    if back_to_back:
        if end:
            Pm = t ** 2 * Fy * (4.44 + 0.558 * math.sqrt(Nt)); cl = "6.5(b)(1)"
        else:
            Pm = t ** 2 * Fy * (6.66 + 1.146 * math.sqrt(Nt)); cl = "6.5(b)(2)"
        nweb = 2
    else:
        if Rt > 4.0 + 1e-9:
            return {"ok": None, "found": False, "note": "R/t = %.2f > 4: tests per 9 (6.5(a)(3))" % Rt, "clause": "IS 801 6.5(a)(3)"}
        if end:
            Pm = 70.0 * t ** 2 * (98.0 + 4.20 * Nt - 0.022 * Nt * ht - 0.011 * ht) * (1.33 - 0.33 * Fy / 2320.0) * (Fy / 2320.0)
            Pm *= (1.15 - 0.15 * Rt); cl = "6.5(a)(1)"
        else:
            Pm = 70.0 * t ** 2 * (305.0 + 2.30 * Nt - 0.009 * Nt * ht - 0.5 * ht) * (1.22 - 0.22 * Fy / 2320.0) * (Fy / 2320.0)
            Pm *= (1.06 - 0.06 * Rt); cl = "6.5(a)(2)"
        nweb = 2 if sec.get("hat") else 1
    inc = INCREASE_WL_EL if wind_eq else 1.0
    Pmax_N = Pm * nweb * inc * 9.80665
    return _rec(P_N, Pmax_N, "IS 801 " + cl, "Pmax = 70 t^2 [98 + 4.20 N/t - 0.022 (N/t)(h/t) - 0.011 h/t] ...",
                h_t=ht, N_t=Nt, R_t=Rt, Pmax_per_web_kgf=Pm, n_webs=nweb, allowable_increase=inc,
                capacity_basis="IS801_allowable")


# ---------------------------------------------------------------------------------------------------------------
# 6.7 combined axial and bending
# ---------------------------------------------------------------------------------------------------------------
def cm_67(case="braced", M1_over_M2=None):
    """IS 801 6.7 Cm: 0.85 sway; braced without transverse load 0.6 - 0.4 M1/M2 >= 0.4; braced with transverse load
    0.85 (restrained ends) / 1.0 (unrestrained ends)."""
    if case == "sway":
        return 0.85, "6.7 (a) sway frame Cm = 0.85"
    if case == "braced" and M1_over_M2 is not None:
        return max(0.6 - 0.4 * M1_over_M2, 0.4), "6.7 (b) Cm = 0.6 - 0.4 M1/M2 >= 0.4"
    if case == "transverse_restrained":
        return 0.85, "6.7 (c)(1) transverse load, restrained ends: 0.85"
    return 1.0, "6.7 (c)(2) transverse load, unrestrained ends: 1.0"


def fe_prime_kgf(KLr):
    """F'e = 12 pi^2 E/(23 (K Lb/rb)^2) = 10 680 000/(KL/r)^2 kgf/cm2 (6.7 definitions)."""
    return 12.0 * PI2 * E_KGF / (23.0 * KLr ** 2)


def combined_67(sec, Fy_MPa, P_N, Mx_Nmm, KLx_mm, KLy_mm, L_unbraced_mm, cm_case="braced", M1_over_M2=None,
                braced_against_twist=False, wind_eq=False, KLt_mm=None, Cb=1.0, e_side=None,
                compression_flange_restrained=False, My_Nmm=0.0, Fby_MPa=None):
    """IS 801 6.7 interaction for an IS 811 member (bending about x, the axis of symmetry for channels).
    6.7.1 for doubly-symmetric / braced-against-twist members; 6.7.2 (a) for singly-symmetric members loaded in the
    plane of symmetry; 6.7.2 (b) (positive eccentricity, sigma_TF) is NOT evaluated: ok=None with the reason when
    e_side == 'away_from_shear_centre' and the member is not braced against twisting."""
    comp = compression_allowable(sec, Fy_MPa, KLx_mm, KLy_mm, KLt_mm=KLt_mm, braced_against_twist=braced_against_twist,
                                 wind_eq=wind_eq)
    if comp.get("ok") is None:
        return dict(comp, dc=None, value=None, limit=None)
    bend = bending_allowable(sec, Fy_MPa, L_unbraced_mm, Cb=Cb, wind_eq=wind_eq,
                             compression_flange_restrained=compression_flange_restrained)
    inc = INCREASE_WL_EL if wind_eq else 1.0
    Fy = Fy_MPa * MPA_TO_KGF
    A = sec["A"] / 100.0
    fa = P_N * N_TO_KGF / A
    fbx = nmm_to_kgfcm(Mx_Nmm) / bend["Sx_eff_cm3"]
    Fa1 = comp["Fa1_kgf_cm2"] * inc
    Fa = comp["Fa_kgf_cm2"] * inc                        # min(Fa1, Fa2): the concentric allowable
    Q = comp["Q"]
    Fa0 = 0.522 * Q * Fy * inc                            # 6.6.1.1 at L = 0
    Fbx = bend["Fb_kgf_cm2"] * inc
    Fb1x = bend["Fb1_kgf_cm2"] * inc
    Cm, cm_cite = cm_67(cm_case, M1_over_M2)
    # F'e in the plane of bending (x-x): K Lb / rb about x
    klr_b = KLx_mm / 10.0 / (sec["rx"] / 10.0)
    Fex = fe_prime_kgf(klr_b) * inc
    amp = 1.0 - fa / Fex if fa < Fex else None
    checks = {}
    if amp is None:
        checks["stability"] = _rec(fa * KGF_CM2, Fex * KGF_CM2, "IS 801 6.7", "fa >= F'e: amplification 1/(1 - fa/F'e) undefined",
                                   ok=False)
        i1 = float("inf")
    else:
        i1 = fa / Fa + Cm * fbx / (amp * Fbx)
    fby = nmm_to_kgfcm(My_Nmm) / (sec["Zy"] / 1e3) if My_Nmm and sec.get("Zy") else 0.0
    if fby:
        Fby = (Fby_MPa * MPA_TO_KGF if Fby_MPa else 0.6 * Fy) * inc
        klr_by = KLy_mm / 10.0 / (sec["ry"] / 10.0)
        Fey = fe_prime_kgf(klr_by) * inc
        ampy = 1.0 - fa / Fey if fa < Fey else None
        i1 += (Cm * fby / (ampy * Fby)) if ampy else float("inf")
    i2 = fa / Fa0 + fbx / Fb1x + (fby / (0.6 * Fy * inc) if fby else 0.0)
    ratio = fa / Fa1 if Fa1 else 1.0
    if ratio < 0.15:
        i3 = fa / Fa1 + fbx / Fbx + (fby / (0.6 * Fy * inc) if fby else 0.0)
        cl = "IS 801 6.7.1 (fa/Fa1 < 0.15: fa/Fa1 + fbx/Fbx + fby/Fby)"
        checks["interaction"] = _rec(i3, 1.0, cl, "fa/Fa1 + fbx/Fbx + fby/Fby < 1.0")
    else:
        cl = "IS 801 6.7.1" if (braced_against_twist or sec.get("doubly_symmetric") or not sec.get("singly_symmetric")) \
            else "IS 801 6.7.2 (a)"
        checks["interaction_stability"] = _rec(i1, 1.0, cl, "fa/Fa1 + Cm fb/((1 - fa/F'e) Fb) < 1.0")
        checks["interaction_strength"] = _rec(i2, 1.0, cl, "fa/Fa0 + fb1/Fb1 < 1.0")
    if cl.startswith("IS 801 6.7.2") and e_side == "away_from_shear_centre":
        checks["6.7.2(b)"] = {"value": None, "limit": None, "dc": None, "ok": None, "clause": "IS 801 6.7.2 (b)",
                              "cite": "if e is positive the average compression stress fa shall also not exceed Fa (sigma_TF)",
                              "source": SRC, "found": False,
                              "note": "TODO(verify): 6.7.2 (b) sigma_TF interaction (PDF p.22, OCR unreadable) not implemented; "
                                      "brace the member against twisting (8.1) or load it through the shear centre"}
    for c in checks.values():
        c.setdefault("allowable_increase", inc)
        c.setdefault("capacity_basis", "IS801_allowable")
    dcs = [c["dc"] for c in checks.values() if isinstance(c.get("dc"), (int, float))]
    oks = [c.get("ok") for c in checks.values()]
    out = {"checks": checks, "dc": max(dcs) if dcs else None,
           "ok": (None if any(o is None for o in oks) else all(oks)), "clause": cl,
           "fa_MPa": fa * KGF_CM2, "fbx_MPa": fbx * KGF_CM2, "fby_MPa": fby * KGF_CM2, "Fa1_MPa": Fa1 * KGF_CM2, "Fa_MPa": Fa * KGF_CM2,
           "Fa0_MPa": Fa0 * KGF_CM2, "Fbx_MPa": Fbx * KGF_CM2, "Fb1x_MPa": Fb1x * KGF_CM2, "Fe_prime_MPa": Fex * KGF_CM2,
           "Cm": Cm, "Cm_cite": cm_cite, "amplification": (1.0 / amp) if amp else None, "allowable_increase": inc,
           "capacity_basis": "IS801_allowable", "compression": comp, "bending": bend, "source": SRC}
    return out


# ---------------------------------------------------------------------------------------------------------------
# 8.1 wall studs braced by sheathing
# ---------------------------------------------------------------------------------------------------------------
def wall_stud_81(sec, Fy_MPa, L_mm, a_mm, Kw_N_per_mm, Ps_N, both_faces=True):
    """IS 801 8.1 wall studs braced by wall material on both faces.  sec: is811 props (mm), stud web perpendicular
    to the wall: I1 = Ix (axis parallel to the wall = strong axis of a stud whose flanges face the sheathing?) --
    per 8.1 definitions I1 is about the axis PARALLEL to the wall and I2 about the axis PERPENDICULAR to the wall;
    for a C-stud with its web perpendicular to the wall face, I1 = Ix (bending out of the wall) and I2 = Iy
    (bending in the plane of the wall, the direction the sheathing braces).
    Kw: modulus of elastic support of the wall material per side (N/mm, from tests), a: attachment spacing (mm)."""
    Fy = Fy_MPa * MPA_TO_KGF
    A = sec["A"] / 100.0
    I1, I2 = sec["Ix"] / 1e4, sec["Iy"] / 1e4
    r1, r2 = math.sqrt(I1 / A), math.sqrt(I2 / A)
    L, a = L_mm / 10.0, a_mm / 10.0
    Kw = Kw_N_per_mm * N_TO_KGF * 10.0            # kgf/cm
    Ps = Ps_N * N_TO_KGF
    out = {"clause": "IS 801 8.1", "source": SRC, "checks": {}}
    out["checks"]["(a) both faces"] = {"value": both_faces, "limit": True, "dc": None, "ok": bool(both_faces),
                                       "clause": "IS 801 8.1 (a)", "cite": "attached to both faces or flanges of the studs being braced",
                                       "source": SRC}
    amax1 = 8.0 * E_KGF * I2 * Kw / (A ** 2 * Fy ** 2)
    amax2 = L * r2 / (2.0 * r1)
    amax = min(amax1, amax2)
    out["checks"]["(b) a <= amax"] = _rec(a * 10.0, amax * 10.0, "IS 801 8.1 (b)", "amax = 8 E I2 Kw/(A^2 Fy^2) and L r2/(2 r1)",
                                          amax_Kw_mm=amax1 * 10.0, amax_slenderness_mm=amax2 * 10.0)
    Kw_min = Fy ** 2 * a * A ** 2 / (8.0 * E_KGF * I2)
    out["checks"]["(c) Kw >= Kw,min"] = _rec(Kw_min / (N_TO_KGF * 10.0), Kw_N_per_mm, "IS 801 8.1 (c)",
                                             "Kw = Fy^2 a A^2/(8 E I2)")
    denom = 2.0 * math.sqrt(E_KGF * I2 * Kw / a) - Ps
    if denom <= 0:
        pmin = None
        out["checks"]["(d) Pmin"] = {"value": None, "limit": None, "dc": None, "ok": False, "clause": "IS 801 8.1 (d)",
                                     "cite": "Pmin = Kw Ps (L/240)/(2 sqrt(E I2 Kw/a) - Ps)", "source": SRC,
                                     "note": "Ps >= 2 sqrt(E I2 Kw/a): the sheathing cannot brace this stud load"}
    else:
        pmin = Kw * Ps * (L / 240.0) / denom
        out["checks"]["(d) Pmin"] = {"value": pmin * 9.80665, "limit": None, "dc": None, "ok": None, "clause": "IS 801 8.1 (d)",
                                     "cite": "Pmin = Kw Ps (L/240)/(2 sqrt(E I2 Kw/a) - Ps)", "source": SRC,
                                     "units": "N per attachment (required lateral force each attachment must exert)",
                                     "glyph_note": "PDF p.31: the '2' printed at the radical read as the coefficient 2 sqrt(...) "
                                                   "(Pcr of a bar on an elastic foundation = 2 sqrt(E I beta)); a bare square "
                                                   "root would double Pmin -- Pmin_bare_root_N recorded",
                                     "Pmin_bare_root_N": (Kw * Ps * (L / 240.0) / (math.sqrt(E_KGF * I2 * Kw / a) - Ps) * 9.80665)
                                     if math.sqrt(E_KGF * I2 * Kw / a) > Ps else None}
    out.update(amax_mm=amax * 10.0, Kw_min_N_per_mm=Kw_min / (N_TO_KGF * 10.0), Pmin_N=(pmin * 9.80665) if pmin else None,
               r1_mm=r1 * 10.0, r2_mm=r2 * 10.0,
               braced_against_twist=bool(both_faces) and out["checks"]["(b) a <= amax"]["ok"] and out["checks"]["(c) Kw >= Kw,min"]["ok"])
    oks = [c.get("ok") for c in out["checks"].values() if c.get("ok") is not None]
    out["ok"] = all(oks) if oks else None
    return out


# ---------------------------------------------------------------------------------------------------------------
# 7.2 welds, 7.3 interconnection, 7.5 bolts
# ---------------------------------------------------------------------------------------------------------------
def weld_allowable_721(Fy_MPa):
    """IS 801 7.2.1 permissible shear on the throat of fillet / plug welds (MPa) by the lowest-strength base metal."""
    Fy = Fy_MPa * MPA_TO_KGF
    if Fy < 2500.0:
        v = 955.0
    elif Fy <= 3500.0:
        v = 1100.0
    else:
        v = 1250.0
    return {"Fw_kgf_cm2": v, "Fw_MPa": v * KGF_CM2, "clause": "IS 801 7.2.1",
            "cite": "permissible stress in shear on throat of fillet or plug welds: 955 / 1100 / 1250 kgf/cm2", "source": SRC}


def fillet_weld_721(Fy_MPa, size_mm, length_mm, P_N, wind_eq=False):
    """Fillet weld shear on the throat (0.707 s), IS 801 7.2.1; the 6.1.2 increase applies to connections too."""
    w = weld_allowable_721(Fy_MPa)
    inc = INCREASE_WL_EL if wind_eq else 1.0
    cap = w["Fw_MPa"] * inc * 0.707 * size_mm * length_mm
    return _rec(P_N, cap, w["clause"], w["cite"], throat_mm=0.707 * size_mm, Fw_MPa=w["Fw_MPa"], allowable_increase=inc,
                capacity_basis="IS801_allowable")


def interconnection_73(L_mm, r_cy_mm, r_I_mm, flexural=False, span_mm=None):
    """IS 801 7.3 maximum connector spacing for two channels back to back: L rcy/(2 r1) (compression); L/6 (flexure)."""
    if flexural:
        smax = (span_mm or L_mm) / 6.0
        return {"Smax_mm": smax, "clause": "IS 801 7.3 (b)", "cite": "Smax = L/6 (and not more than 2 g Ts/(m q))", "source": SRC,
                "note": "the 2 g Ts/(m q) limit needs the connector tension strength Ts (EOR / product data)"}
    return {"Smax_mm": L_mm * r_cy_mm / (2.0 * r_I_mm), "clause": "IS 801 7.3 (a)", "cite": "Smax = L rcy/(2 r1)", "source": SRC}


BOLT_SHEAR_754 = {"precision": 970.0, "semi_precision": 970.0, "black": 820.0, "4.6": 1060.0}


def bolted_connection_75(Fy_MPa, t_mm, d_mm, P_per_bolt_N, n_bolts, edge_mm, spacing_perp_mm, T_member_N=None,
                         bolt_class="4.6", Fu_MPa=None, wind_eq=False):
    """IS 801 7.5 checks for a bolted connection in the thinnest sheet t: 7.5.1 spacing / edge, 7.5.2 net section,
    7.5.3 bearing 2.1 Fy, 7.5.4 bolt shear (gross bolt area).  Footnote: Fu/Fy < 1.35 -> use Fu/1.35 for Fy."""
    Fy = Fy_MPa * MPA_TO_KGF
    if Fu_MPa is not None and Fu_MPa / Fy_MPa < 1.35:
        Fy = Fu_MPa * MPA_TO_KGF / 1.35
    inc = INCREASE_WL_EL if wind_eq else 1.0
    t, d = t_mm / 10.0, d_mm / 10.0
    P = P_per_bolt_N * N_TO_KGF
    out = {"clause": "IS 801 7.5", "source": SRC, "checks": {}}
    emin = max(1.5 * d, P / (0.6 * Fy * t * inc))
    out["checks"]["7.5.1 edge / spacing"] = _rec(emin * 10.0, edge_mm, "IS 801 7.5.1", "not less than 1.5 d nor less than P/(0.6 Fy t)")
    out["checks"]["7.5.3 bearing"] = _rec(P / (d * t) * KGF_CM2, 2.1 * Fy * inc * KGF_CM2, "IS 801 7.5.3",
                                          "bearing stress on the area (d x t) shall not exceed 2.1 Fy", allowable_increase=inc)
    fvb = BOLT_SHEAR_754.get(str(bolt_class), 820.0)
    Ab = math.pi * d ** 2 / 4.0
    out["checks"]["7.5.4 bolt shear"] = _rec(P / Ab * KGF_CM2, fvb * inc * KGF_CM2, "IS 801 7.5.4",
                                             "shear stress on the gross cross-sectional area of bolt: 970 / 820 / 1060 kgf/cm2",
                                             allowable_increase=inc, bolt_class=bolt_class)
    if T_member_N:
        r = min(P_per_bolt_N * n_bolts / T_member_N, 1.0)
        if r < 0.2:
            r = 0.0
        s = spacing_perp_mm / 10.0
        Ft = min((1.0 - 0.9 * r + 3.0 * r * d / s), 1.0) * 0.6 * Fy * inc
        An = (spacing_perp_mm - d_mm) * t_mm            # net width per bolt line x t (mm2)
        ft = T_member_N * N_TO_KGF / (An / 100.0) if An > 0 else float("inf")
        out["checks"]["7.5.2 net section"] = _rec(ft * KGF_CM2, Ft * KGF_CM2, "IS 801 7.5.2",
                                                  "tension on the net section shall not exceed (1.0 - 0.9 r + 3 r d/s) 0.6 Fy nor 0.6 Fy",
                                                  r=r, allowable_increase=inc)
    dcs = [c["dc"] for c in out["checks"].values() if isinstance(c.get("dc"), (int, float))]
    out["dc"] = max(dcs) if dcs else None
    out["ok"] = all(c.get("ok") for c in out["checks"].values())
    out["capacity_basis"] = "IS801_allowable"
    out["allowable_increase"] = inc
    return out
