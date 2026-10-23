"""report_cfs_second_wave.py -- report-only fixes of the 2026-10 second wave in the CFS reports (items C2, C3).

Nothing here changes a design: every function reads the cfg / calc package and returns text, a record or an HTML
fragment.  report_cfs_india.py hooks them in; india_cfs_pipeline writes design/headline.json.

* row_class, member_ratios, headline, headline_sentence, headline_html, write_headline, member_ratio_text
      C3: the worst cold-formed member STRENGTH ratio is the headline; the slenderness KL/r against the IS 801 6.6.3
      limit (200, from the corpus transcription of IS 801:1975) is printed beside it, and the deflection, stud-bracing,
      detailing, brace-element, connection and hot-rolled-frame ratios are kept apart, each with its own limit.
* soil_html, ta_html, vb_source_text, zone_text                      C3: soil type and basis (as in the HR reports, with
      the next softer type's V_B from the vendored report_second_wave), the moment-frame Ta note, map-reading sources.
* diaphragm_source, diaphragm_notes_html                              C3: whether each diaphragm capacity is sourced.
* scope_html, portal_weight_text                                      C3: what the design covers; the portal W basis.
* base_plate_html                                                     C2: the Ex3 base plate as a design result.
* normalise_citations, tidy_html, codes_table_html                    C3: one citation style for the Indian Standards.
"""
from __future__ import annotations

import html
import json
import math
import os
import re

SLENDER_LIMIT = 200.0
SLENDER_CLAUSE = "IS 801 6.6.3"
SLENDER_TEXT = "the slenderness ratio KL/r of compression members shall not exceed 200 (IS 801:1975 6.6.3)"

CLASS_LABEL = {
    "strength": "Strength, cold-formed members (IS 801 6.1-6.7): the headline",
    "slenderness": "Slenderness, cold-formed compression members (IS 801 6.6.3, KL/r <= 200)",
    "serviceability": "Deflection, cold-formed members (declared IS 800:2007 Table 6 criteria)",
    "bracing_81": "Stud bracing by the sheathing (IS 801 8.1 (a)-(d))",
    "detailing": "Detailing limits (IS 801 5.2.3 / 5.2.4 proportions, 7.3 connector spacing, 7.5.1 edge distance)",
    "brace_element": "Brace elements (sag rods, straps)",
}


def _e(x):
    return html.escape(str(x if x is not None else "-"))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _f(v, d=3):
    return ("%%.%df" % d) % float(v) if _num(v) else "-"


def _t(head, rows):
    h = "".join("<th>%s</th>" % _e(c) for c in head)
    b = "".join("<tr>" + "".join("<td>%s</td>" % c for c in r) + "</tr>" for r in rows)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (h, b)


# ================================================================================================= C3 headline
def row_class(c):
    """The kind of ratio a cold-formed check row carries."""
    n = str(c.get("check") or "").lower()
    cl = str(c.get("clause") or "")
    if c.get("brace_element"):
        return "brace_element"
    if c.get("informational"):
        return "information"
    if c.get("detailing") or n.startswith(("7.3", "7.5.1", "5.2.3", "5.2.4")):
        return "detailing"
    if n.startswith("deflection") or c.get("capacity_basis") == "IS800_Table6":
        return "serviceability"
    if cl.startswith("IS 801 8.1") or c.get("combo") == "8.1 bracing":
        return "bracing_81"
    return "strength"


def _short_check(c):
    return re.sub(r"\s*\((?:at max [MP])\)", "", str(c.get("check") or "")).strip()


def member_ratios(m):
    """{class: {dc, value, limit, units, check, combination, clause}} of one cold-formed member record, plus
    'slenderness': the largest KL/r of its compression rows against the 6.6.3 limit (None when the member carries no
    axial compression in any row)."""
    out = {}
    for c in (m or {}).get("checks") or []:
        if not isinstance(c, dict) or not _num(c.get("dc")):
            continue
        k = row_class(c)
        if k == "information":
            continue
        if k not in out or float(c["dc"]) > out[k]["dc"]:
            out[k] = {"dc": round(float(c["dc"]), 4), "value": c.get("value"), "limit": c.get("limit"),
                      "units": c.get("units"), "check": _short_check(c), "combination": c.get("combo"),
                      "clause": c.get("clause")}
            if c.get("sense"):
                out[k]["sense"] = c["sense"]
    klr = None
    for c in (m or {}).get("checks") or []:
        if isinstance(c, dict) and _num(c.get("KL_r")) and _num(c.get("P_N")) and float(c["P_N"]) > 0:
            if klr is None or float(c["KL_r"]) > klr[0]:
                klr = (float(c["KL_r"]), c.get("combo"))
    if klr:
        out["slenderness"] = {"KL_r": round(klr[0], 1), "limit": SLENDER_LIMIT, "ratio": round(klr[0] / SLENDER_LIMIT, 4),
                              "clause": SLENDER_CLAUSE, "basis": SLENDER_TEXT}
    return out


def _tag(obj, src):
    """Every dict of a headline record names where it comes from (the package consistency check reads a bare D/C
    without value / limit as a literal constant)."""
    if isinstance(obj, dict):
        if "dc" in obj or "ratio" in obj:
            obj.setdefault("derived_from", src)
        for v in obj.values():
            _tag(v, src)
    elif isinstance(obj, list):
        for v in obj:
            _tag(v, src)
    return obj


def tag_frame_headline(fh):
    """The hot-rolled frame's headline record as carried in the CFS package (sources named on every ratio)."""
    if not isinstance(fh, dict):
        return None
    h = json.loads(json.dumps(fh, default=str))
    for r in (h.get("section12") or {}).values():          # value / limit of a Section 12 row may be a minimum-type
        if isinstance(r, dict):                             # pair (dc = limit / value): kept as printed text only
            for k in ("value", "limit"):
                if k in r:
                    r[k + "_shown"] = r.pop(k)
    return _tag(h, "hot-rolled frame report headline (report_second_wave)")


def headline(pkg):
    """The governing ratios of a CFS calc package, kept apart (C3).  strength = the headline (worst cold-formed member
    strength ratio); slenderness = worst KL/r of a cold-formed compression member against 200 (IS 801 6.6.3);
    serviceability, bracing_81, detailing, brace_element, connections; member_dc_max = the old single figure (the
    larger of strength and deflection); frame = the hot-rolled frame's own headline (from its report)."""
    pkg = pkg if isinstance(pkg, dict) else {}
    out = {"strength": None, "slenderness": None, "serviceability": None, "bracing_81": None, "detailing": None,
           "brace_element": None, "connections": None, "member_dc_max": None, "frame": None,
           "slenderness_note": None,
           "basis": ("strength = largest IS 801 6.1-6.7 strength ratio (bending, shear, web crippling, axial, combined) of "
                     "any cold-formed member; slenderness = largest KL/r of a cold-formed compression member over the "
                     "IS 801 6.6.3 limit of 200; deflection, stud bracing (8.1), detailing limits, brace elements and "
                     "connections as their own rows; the hot-rolled frame's ratios from its own report"),
           "source": "steltic_cfs_india report_cfs_second_wave.headline"}
    for m in pkg.get("cfs_members") or []:
        if not isinstance(m, dict):
            continue
        r = member_ratios(m)
        mid = m.get("id")
        sec = m.get("designator") or m.get("section")
        for k in ("strength", "serviceability", "bracing_81", "detailing", "brace_element"):
            if k in r and (out[k] is None or r[k]["dc"] > out[k]["dc"]):
                out[k] = dict(r[k], member=mid, section=sec)
        if "slenderness" in r and (out["slenderness"] is None or r["slenderness"]["ratio"] > out["slenderness"]["ratio"]):
            out["slenderness"] = dict(r["slenderness"], member=mid, section=sec)
        if _num(m.get("DC")) and (out["member_dc_max"] is None or m["DC"] > out["member_dc_max"]["dc"]):
            out["member_dc_max"] = {"dc": round(float(m["DC"]), 4), "member": mid}
    if out["slenderness"] is None:
        comp = any(_num(c.get("P_N")) and float(c["P_N"]) > 0 for m in pkg.get("cfs_members") or [] if isinstance(m, dict)
                   for c in m.get("checks") or [] if isinstance(c, dict))
        out["slenderness_note"] = ("KL/r is not recorded for the compression members of this package (re-run the job)"
                                   if comp else
                                   "no cold-formed member carries axial compression (purlins, girts and joists are "
                                   "flexural members): the IS 801 6.6.3 limit does not apply")
    for c in pkg.get("cfs_connections") or []:
        if isinstance(c, dict) and _num(c.get("dc")) and (out["connections"] is None or c["dc"] > out["connections"]["dc"]):
            out["connections"] = {"dc": round(float(c["dc"]), 4), "id": c.get("id"), "type": c.get("type"),
                                  "value": c.get("value") if _num(c.get("limit")) else None,
                                  "limit": c.get("limit") if _num(c.get("limit")) else None}
    fh = (pkg.get("lateral_frame") or {}).get("headline")
    if isinstance(fh, dict) and (fh.get("strength") or fh.get("slenderness")):
        out["frame"] = {k: fh.get(k) for k in ("strength", "slenderness", "connections", "drift", "section12")}
    return _tag(out, "cfs headline (report_cfs_second_wave)")


def headline_sentence(h):
    """One line for the status block and the site card: strength first, slenderness beside it with its limit."""
    h = h or {}
    st, sl = h.get("strength"), h.get("slenderness")
    parts = []
    if st:
        parts.append("worst cold-formed member strength ratio %s (%s, %s%s)"
                     % (_f(st["dc"]), st["member"], st.get("check") or "IS 801 check",
                        (", " + str(st["combination"])) if st.get("combination") else ""))
    if sl:
        parts.append("slenderness KL/r %s against the IS 801 6.6.3 limit of 200 (ratio %s, %s)"
                     % (_f(sl["KL_r"], 1), _f(sl["ratio"]), sl["member"]))
    elif h.get("slenderness_note"):
        parts.append("slenderness: %s" % h["slenderness_note"])
    return "; ".join(parts)


def _val_lim(r):
    v, l, u = r.get("value"), r.get("limit"), r.get("units")
    if not (_num(v) and _num(l)):
        return ""
    if u == "N-mm":
        return "%.2f / %.2f kN-m" % (v / 1e6, l / 1e6)
    if u == "N":
        return "%.2f / %.2f kN" % (v / 1e3, l / 1e3)
    if u in ("MPa", "mm"):
        return "%.1f / %.1f %s" % (v, l, u)
    return ""                                              # a ratio of ratios, or no unit recorded: the value says it


def headline_html(h):
    """Status block: the headline line and the 'Governing ratios' table (each ratio with its limit and where)."""
    h = h or {}
    rows = []
    st = h.get("strength")
    if st:
        rows.append(["<b>%s</b>" % _e(CLASS_LABEL["strength"]), "<b>%s</b>" % _f(st["dc"]), "1.0",
                     _e(_val_lim(st)), _e("%s: %s" % (st["member"], st.get("check"))), _e(st.get("combination") or "")])
    sl = h.get("slenderness")
    if sl:
        rows.append([_e(CLASS_LABEL["slenderness"]), "KL/r %s / 200 = %s" % (_f(sl["KL_r"], 1), _f(sl["ratio"])), "1.0", "",
                     _e(sl["member"]), _e(sl.get("clause"))])
    else:
        rows.append([_e(CLASS_LABEL["slenderness"]), "-", "1.0", "", _e(h.get("slenderness_note") or "-"), ""])
    for k in ("serviceability", "bracing_81", "detailing", "brace_element"):
        r = h.get(k)
        if r:
            rows.append([_e(CLASS_LABEL[k]), _f(r["dc"]), "1.0", _e(_val_lim(r)), _e("%s: %s" % (r["member"], r.get("check"))),
                         _e(r.get("combination") or r.get("clause") or "")])
    c = h.get("connections")
    if c:
        rows.append([_e("Cold-formed connections, bases and bracing (chapter 7)"), _f(c["dc"]), "1.0", "", _e(c.get("id")),
                     _e(c.get("type") or "")])
    fr = h.get("frame") or {}
    if fr.get("strength"):
        s = fr["strength"]
        rows.append([_e("Hot-rolled frame, member strength (IS 800, its own report)"), _f(s.get("dc")), "1.0", "",
                     _e(s.get("member")), _e(s.get("combination") or "")])
    if fr.get("slenderness"):
        s = fr["slenderness"]
        rows.append([_e("Hot-rolled frame, member slenderness (IS 800 Table 3)"),
                     "KL/r %s / %s = %s" % (_f(s.get("KL_r"), 1), _f(s.get("limit"), 0), _f(s.get("ratio"))), "1.0", "",
                     _e(s.get("member")), _e(s.get("combination") or "")])
    if not rows:
        return ""
    old = h.get("member_dc_max") or {}
    note = ("<p class='note'>The headline is the worst <b>strength</b> ratio of the cold-formed members. Slenderness, "
            "deflection, stud-bracing and detailing ratios are shown beside it with their own limits; each must also be "
            "at most 1.0.%s</p>" % (
                (" The single member D/C used in earlier reports (the larger of the strength and deflection ratios) is "
                 "%s (%s)." % (_f(old.get("dc")), _e(old.get("member")))) if old.get("dc") is not None else ""))
    line = "<p><b>Headline:</b> %s.</p>" % _e(headline_sentence(h))
    return line + "<h3>Governing ratios</h3>" + note + _t(["ratio", "value", "limit", "demand / capacity", "where",
                                                            "combination / clause"], rows)


def write_headline(root, h):
    """design/headline.json (read by the site build and the gold harness)."""
    try:
        os.makedirs(os.path.join(root, "design"), exist_ok=True)
        with open(os.path.join(root, "design", "headline.json"), "w") as f:
            json.dump(h, f, indent=1, default=str)
    except OSError:
        pass
    return h


def member_ratio_text(m):
    """Member header line: strength ratio with its check, then deflection, KL/r and the other limits."""
    r = member_ratios(m)
    bits = []
    if r.get("strength"):
        s = r["strength"]
        bits.append("strength ratio %s (%s%s)" % (_f(s["dc"]), s["check"], (", " + str(s["combination"])) if s.get("combination") else ""))
    else:
        bits.append("strength ratio not evaluated")
    if r.get("serviceability"):
        bits.append("deflection %s" % _f(r["serviceability"]["dc"]))
    if r.get("slenderness"):
        bits.append("KL/r %s / 200 (%s)" % (_f(r["slenderness"]["KL_r"], 1), _f(r["slenderness"]["ratio"])))
    if r.get("bracing_81"):
        bits.append("8.1 bracing %s" % _f(r["bracing_81"]["dc"]))
    if r.get("brace_element"):
        bits.append("brace element %s" % _f(r["brace_element"]["dc"]))
    if r.get("detailing"):
        bits.append("detailing %s" % _f(r["detailing"]["dc"]))
    return "; ".join(bits)


def frame_member_cells(m):
    """Chapter 4 hot-rolled member table: (strength ratio, 'KL/r x / limit (ratio)') from the frame run's record."""
    st = m.get("strength_dc")
    sl, klr, lim = m.get("slenderness_ratio"), m.get("KL_r"), m.get("KL_r_limit")
    s_txt = _f(st) if _num(st) else (_f(m.get("DC")) if _num(m.get("DC")) else "not evaluated")
    if _num(sl) and _num(klr) and _num(lim):
        l_txt = "%s / %s (%s)" % (_f(klr, 1), _f(lim, 0), _f(sl))
    elif _num(sl):
        l_txt = _f(sl)
    else:
        l_txt = "-"
    return s_txt, l_txt


def lateral_member_rows(pkg, portal):
    """Chapter 4 member table rows: strength ratio with its combination and KL/r against its limit, kept apart (C3).
    Hot-rolled frame: from the frame run's per-member record; all-CFS portal: from the IS 801 member records."""
    lat = (pkg or {}).get("lateral_frame") or {}
    recs = {m.get("id"): m for m in (pkg or {}).get("cfs_members") or [] if isinstance(m, dict)}
    rows = []
    for m in lat.get("members") or []:
        if portal and m.get("id") in recs:
            r = member_ratios(recs[m["id"]])
            st = r.get("strength") or {}
            sl = r.get("slenderness")
            other = "; ".join("%s %s" % (lab, _f(r[k]["dc"])) for k, lab in (("detailing", "detailing"),
                                                                           ("serviceability", "deflection")) if r.get(k))
            rows.append((m["id"], m.get("role"), m.get("section"), m.get("n"), _f(st.get("dc")) if st else "not evaluated",
                         st.get("combination") or "-",
                         ("%s / 200 (%s)" % (_f(sl["KL_r"], 1), _f(sl["ratio"]))) if sl else "-", other or "-"))
        else:
            s_txt, l_txt = frame_member_cells(m)
            rows.append((m["id"], m.get("role"), m.get("section"), m.get("n"), s_txt,
                         m.get("strength_combo") or m.get("governing_combo") or "-", l_txt, "-"))
    return rows


def frame_headline_text(lat):
    """The hot-rolled frame's own headline, as its report prints it."""
    h = (lat or {}).get("headline") or {}
    st, sl = h.get("strength"), h.get("slenderness")
    if not (st or sl):
        return ""
    parts = []
    if st:
        parts.append("worst member strength ratio %s (%s%s)" % (_f(st.get("dc")), st.get("member"),
                                                               (", " + str(st["combination"])) if st.get("combination") else ""))
    if sl:
        parts.append("member slenderness KL/r %s against the IS 800 Table 3 limit of %s (ratio %s, %s)"
                     % (_f(sl.get("KL_r"), 1), _f(sl.get("limit"), 0), _f(sl.get("ratio")), sl.get("member")))
    return "Frame headline (its own report): " + "; ".join(parts) + "."


# ================================================================================================= C3 soil / Ta
_SOIL_NAME = {"I": "rock or hard soil", "II": "medium stiff soil", "III": "soft soil"}


def _clean(s):
    try:
        import report_cfs_india as R
        return R.clean(s)
    except Exception:                                      # pragma: no cover - import cycle guard
        return str(s or "")


def soil_basis(cfg, ss):
    site = (cfg or {}).get("site") or {}
    if (cfg or {}).get("soil_basis"):
        return str(cfg["soil_basis"])
    try:
        import india_seismic as IS
        soil = IS.soil_type(ss.get("soil") or site.get("soil") or "II")
    except Exception:
        soil = str(ss.get("soil") or site.get("soil") or "II")
    note = _clean(site.get("soil_note")) if site.get("soil_note") else ""
    assumed = "medium soil" if soil == "II" else ("soft soil" if soil == "III" else "this soil type")
    if note:
        return ("declared in the brief: %s. %s assumed, not from a site investigation; confirm by site investigation "
                "(geotechnical report)" % (note.rstrip("."), assumed[:1].upper() + assumed[1:]))
    return ("%s (Type %s) as declared in the brief: %s assumed, not from a site investigation; confirm by site "
            "investigation (geotechnical report)" % (_SOIL_NAME.get(soil, "soil"), soil, assumed))


def soil_record(cfg, pkg):
    """The HR second-wave soil record (vendored report_second_wave.base_shear_notes) for the CFS frame's seismic
    summary: type, basis and, for Type I / II, the next softer type's Sa/g and V_B ratio at the design Ta."""
    lat = (pkg or {}).get("lateral_frame") or {}
    ss = dict(lat.get("seismic_summary") or {})
    if not ss:
        return None
    if ss.get("rho_min") is None and _num(ss.get("Ah_min_table7")):
        ss["rho_min"] = ss["Ah_min_table7"]
    basis = soil_basis(cfg, ss)
    try:
        import report_second_wave as RS2
        n = RS2.base_shear_notes({"load_plan": {"seismic_summary": ss}, "soil_basis": basis}, {}, dims={})
        return n.get("soil")
    except Exception as ex:                                 # pragma: no cover - vendored HR module missing
        return {"type": ss.get("soil"), "name": None, "basis": basis, "next": None, "rows": [],
                "error": "%s: %s" % (type(ex).__name__, ex)}


def soil_html(cfg, pkg):
    s = soil_record(cfg, pkg)
    if not s:
        return ""
    txt = "<p><b>Soil:</b> Type %s, %s. Basis: %s.</p>" % (_e(s.get("type")), _e(s.get("name") or "-"), _e(s.get("basis")))
    rows = s.get("rows") or []
    if s.get("next") and rows:
        if all(abs((r.get("VB_ratio") or 1.0) - 1.0) < 0.005 for r in rows):
            txt += ("<p class='note'>Note (not a design case): on Type %s soil, Sa/g at the design Ta (%s s) would be the "
                    "same (IS 1893 (Part 1):2016 6.4.2), so V_B would not change.</p>"
                    % (_e(s["next"]), " / ".join(_f(r["Ta_s"]) for r in rows)))
        else:
            txt += ("<p class='note'>Note (not a design case): on Type %s soil the design acceleration at the same Ta would "
                    "be as below (IS 1893 (Part 1):2016 6.4.2, with the 7.2.2 Table 7 minimum). The design here is for Type "
                    "%s.</p>" % (_e(s["next"]), _e(s["type"]))
                    + _t(["dir", "design Ta (s)", "Sa/g Type %s" % s["type"], "Sa/g Type %s" % s["next"], "V_B ratio"],
                         [[_e(r["dir"]), _f(r["Ta_s"]), _f(r["Sa_g"]), _f(r["Sa_g_next"]), _f(r["VB_ratio"], 2)] for r in rows]))
    elif s.get("type") == "III":
        txt += ("<p class='note'>Type III is the softest soil type of IS 1893 (Part 1):2016 6.4.2.1: a firmer soil found by "
                "the site investigation would not raise the design acceleration.</p>")
    return txt


def moment_directions(cfg, pkg):
    """Directions in which the lateral system is a moment frame: the all-CFS portal's frame plane (X), or the
    directions of the declared hot-rolled moment lines."""
    if (cfg or {}).get("all_cfs_portal"):
        return ["X"]
    lf = (cfg or {}).get("lateral_frame") or {}
    sysn = str((lf.get("hr_cfg_extra") or {}).get("system") or lf.get("system") or "").upper()
    dirs = sorted({str(m[0]).upper() for m in lf.get("moment_lines") or [] if m and str(m[0]).upper() in ("X", "Y")})
    if dirs:
        return dirs
    if any(k in sysn for k in ("SMF", "SMRF", "OMF", "OMRF")) and not any(k in sysn for k in ("CBF", "OBF", "SBF", "EBF")):
        return ["X", "Y"]
    return []


def ta_notes(cfg, pkg):
    """Moment-frame directions whose design Ta is the 7.6.2(c) formula 0.09 h/sqrt(d): the bare moment-frame Ta of
    7.6.2(a) and the V_B ratio it would give (report-only; the design keeps its Ta)."""
    lat = (pkg or {}).get("lateral_frame") or {}
    ss = lat.get("seismic_summary") or {}
    if not ss:
        return []
    try:
        import india_seismic as IS
        import report_second_wave as RS2
    except Exception:                                       # pragma: no cover
        return []
    fby = RS2._formula_by_dir(ss.get("Ta_formula"))
    portal = bool((cfg or {}).get("all_cfs_portal"))
    out = []
    for d in moment_directions(cfg, pkg):
        part = fby.get(d, "") or str(ss.get("Ta_formula") or "")
        if RS2._bare_frame(part)[0] or not re.search(r"0\.09\s*h\s*/\s*sqrt", part):
            continue
        T = ss.get("Ta_%s_s" % d.lower(), ss.get("Ta_s"))
        if not _num(T):
            continue
        if portal:
            po = cfg.get("portal") or {}
            h, dd = float(po.get("apex_m")), sum(float(s) for s in po.get("spans_m") or [])
        else:
            dd = ss.get("d_%s_m" % d.lower())
            if not _num(dd):
                continue
            h = float(T) * math.sqrt(float(dd)) / 0.09
        try:
            ta_a = IS.approximate_Ta(h, dd, system="steel MRF", material="steel", infills=False)["Ta_s"]
            soil = IS.soil_type(ss.get("soil") or "II")
            sa0, sa1 = IS.sa_over_g(float(T), soil, "ESM"), IS.sa_over_g(ta_a, soil, "ESM")
        except Exception:
            continue
        out.append({"dir": d, "Ta_s": round(float(T), 4), "h_m": round(h, 2), "d_m": round(float(dd), 2),
                    "Ta_a_s": round(ta_a, 4), "Sa_g": round(sa0, 4), "Sa_g_a": round(sa1, 4),
                    "VB_ratio": round(sa1 / sa0, 4) if sa0 else None})
    return out


def ta_html(cfg, pkg):
    out = []
    for r in ta_notes(cfg, pkg):
        same = abs((r.get("VB_ratio") or 1.0) - 1.0) < 0.005
        out.append("<p class='note'>Ta, %s direction (a moment frame): the design takes IS 1893 (Part 1):2016 7.6.2(c), "
                   "Ta = 0.09 h/&radic;d = 0.09 &times; %s / &radic;%s = %s s. Note (not a design case): the bare "
                   "moment-frame formula of 7.6.2(a), 0.085 h<sup>0.75</sup>, gives %s s and Sa/g %s against %s, %s</p>"
                   % (_e(r["dir"]), _f(r["h_m"], 2), _f(r["d_m"], 2), _f(r["Ta_s"]), _f(r["Ta_a_s"]), _f(r["Sa_g_a"], 2),
                      _f(r["Sa_g"], 2), "so V_B would not change (both periods are on the Sa/g plateau)." if same else
                      "and V_B &times; %s." % _f(r["VB_ratio"], 2)))
    return "".join(out)


def vb_source_text(ws, site):
    """The basic wind speed source in words ('derived_from_map' is the engine's code for a Fig. 1 map reading)."""
    src = (ws or {}).get("Vb_source") or (site or {}).get("Vb_source")
    if src is None:
        return "IS 875 (Part 3):2015 Annex A"
    if str(src).strip().lower() in ("derived_from_map", "map", "fig1", "fig. 1"):
        return ("read from the IS 875 (Part 3):2015 Fig. 1 basic wind speed map at the site, which is not listed in "
                "Annex A; the design engineer's reading, to be confirmed")
    return _clean(src)


def zone_text(site):
    site = site or {}
    if str(site.get("zone_source") or "").lower() in ("derived_from_map", "map"):
        return ("IS 1893 (Part 1):2016 Fig. 1 (seismic zone map) reading at the site, which is not listed in Annex E: "
                "Zone %s (Z = %s)" % (site.get("zone"), site.get("Z")))
    return "IS 1893 (Part 1):2016 Annex E: Zone %s (Z = %s)" % (site.get("zone"), site.get("Z"))


# ================================================================================================= C3 diaphragm sources
_PENDING_RE = re.compile(r"to be filed|VERIFY|required|not declared|pending", re.I)
_CALC_RE = re.compile(r"\bcalc\b|calculation|computed", re.I)


def diaphragm_source(src):
    """('calculated' | 'unsourced' | 'cited', short status) for a declared diaphragm capacity source text."""
    s = str(src or "")
    if not s.strip():
        return "unsourced", "no source given: a test or manufacturer value is required"
    if _CALC_RE.search(s):
        return "calculated", "the design engineer's calculation, given in the source"
    if _PENDING_RE.search(s):
        return "unsourced", ("assumed allowable: no test report or product document is cited yet; confirm with the "
                             "manufacturer's test report before construction")
    return "cited", "as cited"


def diaphragm_notes_html(rows, high=0.90):
    """Diaphragm rows near their limit against a capacity that is not yet sourced (review: Ex13 throat)."""
    flagged = []
    for r in rows or []:
        cap, v = r.get("capacity"), r.get("v_unit_kN_per_m")
        if not (_num(cap) and _num(v) and cap > 0):
            continue
        kind, _ = diaphragm_source(r.get("capacity_source"))
        if kind == "unsourced" and v / cap >= high:
            line = r.get("governing_line_m")
            flagged.append("storey %s, %s direction, line at %s m: %.2f / %.2f kN/m (ratio %.2f)"
                           % (r.get("storey"), r.get("dir"), _f(line, 2) if _num(line) else "-", v, cap, v / cap))
    if not flagged:
        return ""
    return ("<p class='fail'>Diaphragm capacity not yet sourced at a ratio of %.2f or more: %s. The PASS rests on the "
            "assumed allowable shear; the manufacturer's test report must confirm it (or the fastener schedule be "
            "tightened) before the floor is built.</p>" % (high, _e("; ".join(flagged))))


# ================================================================================================= C3 scope
def scope_html(cfg, pkg, kind):
    """What this design covers and what it leaves to the design engineer (one line, chapter 1)."""
    cn = (pkg or {}).get("cfs_connections") or []
    items = ["fire resistance (NBC 2016 Part 4 periods are met by tested lining, ceiling or encasement assemblies)",
             "acoustic performance (sound insulation of separating walls and floors)",
             "corrosion protection beyond the coating class stated in chapter 8"]
    if not cn:
        items.append("the cold-formed connections and screwed fixings (none declared; chapter 7)")
    if kind != "portal_cfs":
        items.append("the floor and roof diaphragm capacities, which are declared values (chapter 6)")
    if kind == "hybrid":
        items.append("load-bearing LGSF walls braced by straps or sheathing as the lateral system: here the hot-rolled "
                     "frame carries all wind and earthquake load and the cold-formed studs and joists carry gravity and "
                     "wind only")
    items.append("foundations, pedestals and anchor embedment beyond the values declared")
    return ("<p class='rs'><b>Scope:</b> this report designs the cold-formed members%s to IS 801:1975 and %s. Outside this "
            "design (the design engineer's items): %s.</p>"
            % (" and the portal frame" if kind == "portal_cfs" else "",
               "the bases and anchors to IS 800:2007 Section 11" if kind == "portal_cfs"
               else "summarises the hot-rolled frame designed to IS 800:2007 in its own report",
               "; ".join(items)))


def portal_weight_text(ss):
    """The all-CFS portal W is ONE transverse frame's seismic weight (review Ex3: 'not stated')."""
    ss = ss or {}
    if not _num(ss.get("W_kN")):
        return ""
    txt = ("W = %s kN is the seismic weight of one transverse frame (roof, frame self-weight and half the wall height over "
           "one bay%s)" % (_f(ss["W_kN"], 1), "; the mezzanine is braced on its own and is not on the frame"
                           if "own bracing" in str(ss.get("mezzanine_lateral") or "") else ""))
    if _num(ss.get("W_portal_total_kN")) and _num(ss.get("VB_portal_total_kN")):
        txt += ("; the whole building, for the longitudinal bracing: W = %s kN, V_B = %s kN"
                % (_f(ss["W_portal_total_kN"], 1), _f(ss["VB_portal_total_kN"], 2)))
    return txt + "."


# ================================================================================================= C2 base plate
def base_plate_html(conn):
    """The column-base plate as a design result (C2): the adopted plate with its governing check and ratio, the
    compared plates that fail (with their ratios) and why the bases are fixed."""
    pdz = (conn or {}).get("plate_design")
    if not isinstance(pdz, dict) or not pdz.get("adopted"):
        return ""
    a = pdz["adopted"]

    def size(r):
        return "%s x %s x %s mm" % (_f(r["B_mm"], 0), _f(r["L_mm"], 0), _f(r["t_mm"], 0))

    def gov(r):
        u = "kN" if str(r.get("governing_check") or "").startswith("anchorage") else "MPa"
        vl = ""
        if _num(r.get("value")) and _num(r.get("limit")):
            vl = (" (%.1f / %.1f kN)" % (r["value"] / 1e3, r["limit"] / 1e3)) if u == "kN" else \
                (" (%.1f / %.1f MPa)" % (r["value"], r["limit"]))
        return "%s, ratio %s%s, %s, base %s" % (_clean(r.get("governing_check")), _f(r.get("dc")), vl, r.get("combination"),
                                                 r.get("support"))

    out = ["<h3>Column base plate: design result</h3>"]
    out.append("<p>Adopted plate <b>%s</b>, %s (%s): governing check %s -- %s.</p>"
               % (_e(size(a)), _e(a.get("anchors")), "IS 800:2007 Section 11 working stress", _e(gov(a)),
                  "PASS" if a.get("ok") else "FAIL"))
    rows = [[_e(size(a)), _e(a.get("anchors")), _e(_clean(a.get("governing_check"))), _f(a.get("dc")), _e(a.get("combination")),
             "PASS (adopted)" if a.get("ok") else "FAIL"]]
    for r in pdz.get("compared") or []:
        rows.append([_e(size(r)), _e(r.get("anchors")), _e(_clean(r.get("governing_check"))), _f(r.get("dc")), _e(r.get("combination")),
                     ("PASS" if r.get("ok") else "<span class='fail'>FAIL</span>") + " (compared)"])
    out.append(_t(["plate B x L x t", "anchors", "governing check", "ratio", "combination", "result"], rows))
    smaller = [r for r in pdz.get("compared") or [] if not r.get("ok")]
    if smaller:
        out.append("<p>%s; the adopted %s plate passes at %s. The adopted plate is therefore a design result of these "
                   "checks (plates between the sizes shown were not checked).</p>"
                   % (_e("; ".join("The smaller %s plate fails on %s at a ratio of %s" % (size(r), _clean(r.get("governing_check")),
                                                                                         _f(r.get("dc"))) for r in smaller)),
                      _e(size(a)), _f(a.get("dc"))))
    fx = pdz.get("fixity") or {}
    if fx.get("base") == "fixed" and _num(fx.get("K_fixed")) and _num(fx.get("K_pinned")):
        klr = ""
        if _num(fx.get("KLr_fixed")) and _num(fx.get("KLr_pinned")):
            klr = (" The in-plane slenderness of the columns would go from KL/r = %s to %s against the IS 801 6.6.3 limit "
                   "of 200%s." % (_f(fx["KLr_fixed"], 0), _f(fx["KLr_pinned"], 0),
                                  " -- over the limit" if fx["KLr_pinned"] > 200.0 else ""))
        out.append("<p><b>Why fixed bases:</b> the portal's sway stiffness comes from its knee and base joints only. With "
                   "fixed bases the exterior column's effective length factor is K = %s (IS 800:2007 Annex D, sway frame, "
                   "&beta;1 = 0, &beta;2 = %s); with pinned bases &beta;1 = 1 and K = %s, %s times the buckling length, "
                   "and the frame would sway more under wind.%s Fixed bases keep the column sections and the frame as "
                   "designed; the cost is a moment-resisting base, the plate and anchors above.%s</p>"
                   % (_f(fx["K_fixed"], 2), _f(fx.get("beta2"), 3), _f(fx["K_pinned"], 2),
                      _f(fx["K_pinned"] / fx["K_fixed"], 1), _e(klr),
                      (" Design note: %s." % _e(_clean(fx["reason"]))) if fx.get("reason") else ""))
    if pdz.get("basis"):
        out.append("<p class='note'>Basis: %s.</p>" % _e(pdz["basis"]))
    return "".join(out)


# ================================================================================================= C3 citations
CODES = [
    ("IS 801:1975", "Code of practice for use of cold-formed light gauge steel structural members in general building "
                    "construction (working stress)", "current edition; reaffirmed 2021 (BIS)", r"IS 801\b"),
    ("IS 811:1987", "Specification for cold formed light gauge structural steel sections", "current edition; reaffirmed 2024 (BIS)",
     r"IS 811\b"),
    ("IS 277", "Galvanized steel strips and sheets (plain and corrugated): the coil of the computed thin sections",
     "grade 350, Z275, by mill certificate", r"IS 277\b"),
    ("IS 875 (Part 1):2026", "Dead loads (unit weights)", "the edition held in the corpus", r"IS 875 \(Part 1\)"),
    ("IS 875 (Part 2):1987", "Imposed loads", "", r"IS 875 \(Part 2\)"),
    ("IS 875 (Part 3):2015", "Wind loads", "", r"IS 875 \(Part 3\)"),
    ("IS 875 (Part 4):2021", "Snow loads", "", r"IS 875 \(Part 4\)"),
    ("IS 875 (Part 5):1987", "Special loads and load combinations (8.1, working stress)", "", r"IS 875 \(Part 5\)"),
    ("IS 1893 (Part 1):2016 with Amendments 1 and 2", "Earthquake resistant design", "in force (BIS withdrew the 2025 "
     "revision in March 2026)", r"IS 1893\b"),
    ("IS 800:2007", "General construction in steel (hot-rolled frame, limit state; Table 6 deflection limits; Section 11 "
                    "working-stress bases of the all-cold-formed portal)", "", r"IS 800\b"),
    ("IS 18168:2023", "Earthquake resistant design and detailing of steel buildings", "", r"IS 18168\b"),
    ("IS 2062 (Part 1):2025", "Hot-rolled structural steel (frame members, plates)", "", r"IS 2062\b"),
    ("IS 4180", "Corrosion protection of light gauge steel sections (paint systems)", "where a paint system is added",
     r"IS 4180\b"),
    ("IS 15961", "Metallic-coated steel sheet, cited for the heavier coating classes (chapter 8)", "where used",
     r"IS 15961\b"),
    ("NBC 2016 Part 4", "Fire and life safety (outside this design)", "", r"NBC 2016"),
]

_CITE_SUBS = [
    (re.compile(r"IS\s*801\s*:\s*1975\s*\(\s*Reaffirmed\s*2021\s*\)", re.I), "IS 801:1975"),
    (re.compile(r"IS\s*811\s*:\s*1987\s*\(\s*Reaffirmed\s*2024\s*\)", re.I), "IS 811:1987"),
    (re.compile(r"IS\s*875\s*\(Part\s*1\)\s*:\s*1987"), "IS 875 (Part 1):2026"),
    (re.compile(r"IS\s*875\s*\(Part\s*4\)\s*:\s*1987"), "IS 875 (Part 4):2021"),
    (re.compile(r"IS\s*2062\s*:\s*(\d{4})"), r"IS 2062 (Part 1):\1"),
    (re.compile(r"IS\s*875\s+Parts\s+1\s*-\s*5"), "IS 875 (Parts 1 to 5)"),
    (re.compile(r"IS\s*875\s+Part\s+(\d)(?=\s*[:)\s,;.]|$)"), r"IS 875 (Part \1)"),
    (re.compile(r"IS\s*875-(\d)\b"), r"IS 875 (Part \1)"),
    (re.compile(r"IS\s*1893\s*\(Part\s*1\)\s*:\s*2016\s*(?:\+|with)\s*Amd\.?\s*1\s*(?:,|and|\+)\s*(?:Amd\.?\s*)?2\b"),
     "IS 1893 (Part 1):2016 with Amendments 1 and 2"),
    (re.compile(r"IS\s*1893\s+Part\s+1\b"), "IS 1893 (Part 1)"),
    (re.compile(r"(?<![(\w])Part\s+([25]):1987"), r"(Part \1):1987"),
]


def normalise_citations(text):
    """One citation style for the Indian Standards in printed text (C3)."""
    for rx, rep in _CITE_SUBS:
        text = rx.sub(rep, text)
    return text


def tidy_html(html_text):
    """Citation style in the text of an HTML document (tags and attributes untouched)."""
    parts = re.split(r"(<[^>]+>)", html_text)
    return "".join(p if p.startswith("<") else normalise_citations(p) for p in parts)


def codes_table_html(report_text):
    """'Standards cited' table: every standard the report text cites, with the edition in the one citation style."""
    text = re.sub(r"<[^>]+>", " ", report_text)
    rows = [[_e(ed), _e(title), _e(status)] for ed, title, status, rx in CODES if re.search(rx, text)]
    if not rows:
        return ""
    return ("<h3>Standards cited (editions)</h3>" + _t(["standard", "subject", "status"], rows))
