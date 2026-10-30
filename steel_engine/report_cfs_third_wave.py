"""report_cfs_third_wave.py -- report text of the 2026-10 third wave in the CFS reports (handoff P3 and P9).

Every function reads the cfg / calc package and returns a record or an HTML fragment; report_cfs_india.py hooks them
in, and the text passes through the second-wave public-text pass (report_cfs_second_wave.tidy_html) with the rest of
the report.

* column_orientation_html                       P3: the stated rule for the strong axis of a frame column that stands
      in frames of both directions (the corner of two braced walls), with the columns it decides.
"""
from __future__ import annotations

import html
import math


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


# ================================================================================================= P3 column axis
def column_orientation_html(lat):
    """P3: the rule that orients a frame column standing in frames of both directions, and the columns it decides.
    lat = pkg['lateral_frame'] (its 'column_orientation' record comes from the frame sub-run's lateral_result)."""
    co = (lat or {}).get("column_orientation")
    if not isinstance(co, dict) or not co.get("rule"):
        return ""
    rows = co.get("shared_columns") or []
    if not rows:
        return ("<p class='note'><b>Column orientation.</b> No frame column stands in frames of both directions. %s</p>"
                % _e(co["rule"]))
    cells = []
    for r in rows:
        g = r.get("grid") or ["-", "-"]
        fx = "; ".join(r.get("frames_X") or []) or "-"
        fy = "; ".join(r.get("frames_Y") or []) or "-"
        cells.append((_e("x-line %s, y-line %s" % (g[0], g[1])), _e(fx), _e(fy), _e(r.get("strong_axis"))))
    return ("<p class='note'><b>Column orientation.</b> %d frame column(s) stand in frames of both directions. %s</p>"
            % (len(rows), _e(co["rule"]))
            + _t(["column (grid lines, counted from 0)", "X-direction frames", "Y-direction frames",
                  "strong axis in the plane of"], cells))


# ================================================================================================= P9 wind / snow
def internal_pressure_html(cfg, pkg):
    """P9: the declared internal-pressure case (dominant opening) and where it acts."""
    ip = (cfg or {}).get("wind_internal_pressure")
    if not isinstance(ip, dict) or ip.get("Cpi_pos") is None:
        return ""
    ws = ((cfg.get("load_plan") or {}).get("wind_summary") or {})
    rec = ws.get("internal_pressure_case") or {}
    n = len(rec.get("patterns") or [])
    frame = (" The frame's %d member-wind patterns take the same internal pressure." % n) if n else ""
    return ("<p><b>Internal pressure, %s case.</b> %s %s Cpi = %+.1f (internal pressure) and %+.1f (internal suction), "
            "enveloped with the opening-ratio values, for every purlin, girt and stud.%s</p>"
            % (_e(ip.get("case") or "declared"), _e(ip.get("opening") or ""), _e(ip.get("basis") or ""),
               float(ip["Cpi_pos"]), float(ip["Cpi_neg"]), _e(frame)))


def _drift_sentence(d):
    if not d:
        return ""
    if d.get("clause", "").endswith("5.2.4"):
        return ("IS 875 (Part 4):2021 5.2.4 (multilevel roof): s0 = %s kPa, height difference h = %s m, upper roof l1 = %s m, "
                "lower roof l2 = %s m; muw = (l1 + l2)/2h = %s, capped at k h/s0 = %s (k = 2 kN/m2), so muw = %s (%s); "
                "mus = 0 (upper roof %s deg, not steeper than 15 deg); mu2 = %s at the step, i.e. %s kPa, falling to mu1 = "
                "0.80 over l3 = 2h = %s m; the lower roof is %s m deep, so its far edge carries mu = %s (%s kPa) by Note 2."
                % (_f(d["s0_kPa"], 2), _f(d["h_m"], 2), _f(d["l1_m"], 1), _f(d["l2_m"], 2), _f(d["muw_raw"], 2),
                   _f(d["muw_cap_kh_s0"], 3), _f(d["muw"], 3), _e(d.get("governs")), _f(d["beta_upper_deg"], 1),
                   _f(d["mu2"], 3), _f(d["s_step_kPa"], 2), _f(d["l3_m"], 1), _f(d["l2_m"], 2), _f(d["mu_far_edge"], 3),
                   _f(d["s_far_edge_kPa"], 2)))
    return ("IS 875 (Part 4):2021 5.2.6 (local projection): h = %s m above the roof, k h/s0 = %s; mu2 = %s (limits 0.8 to "
            "2.0) over l = %s m: %s." % (_f(d["h_m"], 2), _f(d["mu2_raw"], 3), _f(d["mu2"], 3), _f(d["l_m"], 1),
                                         _e(d.get("statement"))))


def snow_drift_html(pkg):
    """P9: the snow drift on the lean-to and around the roof platforms (IS 875-4 5.2.4 / 5.2.6)."""
    out = []
    lt = (pkg or {}).get("lean_to")
    if isinstance(lt, dict) and lt.get("snow_drift"):
        out.append("<p><b>Snow drift on the %s.</b> %s The drift replaces the roof imposed load on the lean-to (IS 875 "
                   "(Part 5) 8.1 Note 1); it is designed into the lean-to roof joists, the door header and jambs and the "
                   "back-wall studs (chapter 5).</p>" % (_e(lt.get("name") or "lean-to"), _e(_drift_sentence(lt["snow_drift"]))))
    for p in (pkg or {}).get("roof_platforms") or []:
        if p.get("drift"):
            out.append("<p><b>Snow drift around the %s.</b> %s</p>" % (_e(p.get("name") or "roof platform"),
                                                                     _e(_drift_sentence(p["drift"]))))
    return "".join(out)


def platform_frame_html(pkg):
    """P9: what each roof platform puts on the hot-rolled frame."""
    rows = []
    for p in (pkg or {}).get("roof_platforms") or []:
        dl = p.get("dead_reaction_per_post_N") or {}
        rows.append("<p><b>%s on the frame.</b> The platform spans %s m between frame lines %s on eave line %s; its posts "
                    "stand on the rafters %s m from the column. Its dead load (beams, deck, equipment, posts) goes to the "
                    "frame at each knee: %s / %s kN per post, with the moment of the post offsets, and is in the seismic "
                    "weight. Snow on the platform replaces the roof snow it shelters, so the frame's roof snow is unchanged. "
                    "%s</p>" % (_e(p.get("name") or "Roof platform"), _f(p.get("span_m"), 2),
                                _e(" and ".join(str(i) for i in p.get("frames") or [])), _e(p.get("eave_line")),
                                _e(", ".join("%.2f" % float(a) for a in p.get("posts_from_column_m") or [])),
                                _f(_kn(dl.get("left")), 2), _f(_kn(dl.get("right")), 2), _e(p.get("frame_note") or "")))
    return "".join(rows)


def _kn(v):
    return (float(v) / 1e3) if _num(v) else None


# ================================================================================================= P9 connections
def cleat_html(conn):
    """P9: the purlin-cleat check table (bolts in the purlin web, the plate cleat and its welds)."""
    if not str((conn or {}).get("id") or "").startswith("purlin-cleat"):
        return ""
    rows = []
    for k in conn.get("checks") or []:
        if not isinstance(k.get("dc"), (int, float)) and not k.get("detailing"):
            continue
        rows.append((_e(k.get("combo")), _e(k.get("check")), _f(k.get("value"), 2), _f(k.get("limit"), 2),
                     _f(k.get("dc"), 3), _e("PASS" if k.get("ok") else ("FAIL" if k.get("ok") is False else "-")),
                     _e(k.get("clause"))))
    # the governing row per check name (the table would repeat every combination)
    best = {}
    for r, k in zip(rows, [k for k in conn.get("checks") or [] if isinstance(k.get("dc"), (int, float)) or k.get("detailing")]):
        nm = k.get("check")
        if nm not in best or (k.get("dc") or 0.0) > (best[nm][1].get("dc") or 0.0):
            best[nm] = (r, k)
    return ("<p class='rs'>%s (%s): governing combination per check (stresses in MPa, edge distance in mm).</p>" % (_e(conn["id"]), _e(conn.get("type")))
            + _t(["combination", "check", "value", "limit", "D/C", "result", "clause"], [v[0] for v in best.values()]))


def screw_scope_html():
    import india_cfs_secondary as SEC
    return "<p class='note'>Screwed connections: %s.</p>" % _e(SEC.SCREW_SCOPE)
