"""report_cfs_india.py -- the HTML report of an India CFS job (spec WP3.6): IS units only (kN, kN/m, kN/m2, m, mm,
MPa), the two labelled combination families, the hot-rolled lateral frame summary (with a link to the vendored HR
report), every IS 801 member check, the diaphragm path, connections, the IS grounding table (IS 801 / 811 / 875 /
1893 / 800 / 18168) and the design status.  No US clause string is written here (india_cfs_gates.US_RE is asserted
by consistency.check on the rendered file).
"""
from __future__ import annotations
import html
import json
import os

import india_cfs_env  # noqa: F401
import india_cfs_basis as B

UNITS = {"force": "kN", "moment": "kN-m", "length": "m", "small_length": "mm", "pressure": "kN/m2", "line_load": "kN/m",
         "stress": "MPa", "engine": "N, mm, MPa (IS 801 kgf/cm2 inside is801_members)"}


def _set_report_units(cfg):
    """WP3.6: the report always displays kN / kN-m / m / mm / kN/m2 / MPa; engine values are N, mm."""
    u = dict(UNITS)
    if str((cfg or {}).get("units") or "m").lower() not in ("m", "mm", "metric", "si", "n-mm"):
        raise ValueError("India report: cfg['units'] must be metric (got %r)" % cfg.get("units"))
    return u


def _kN(v, d=1):
    return "-" if not isinstance(v, (int, float)) else ("%%.%df" % d) % (v / 1e3)


def _kNm(v, d=2):
    return "-" if not isinstance(v, (int, float)) else ("%%.%df" % d) % (v / 1e6)


def _f(v, d=3):
    return "-" if not isinstance(v, (int, float)) else ("%%.%df" % d) % v


def _e(s):
    return html.escape(str(s if s is not None else "-"))


def _t(headers, rows):
    h = "".join("<th>%s</th>" % _e(x) for x in headers)
    b = "".join("<tr>" + "".join("<td>%s</td>" % _e(c) for c in r) + "</tr>" for r in rows)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (h, b)


def _ok(v):
    return {True: "PASS", False: "FAIL", None: "not evaluated"}.get(v, str(v))


CSS = """<style>body{font-family:Georgia,serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#222}
table{border-collapse:collapse;margin:8px 0 16px;font-size:13px}th,td{border:1px solid #bbb;padding:3px 6px;text-align:left}
th{background:#eee}h1{font-size:22px}h2{font-size:18px;margin-top:28px;border-bottom:1px solid #999}.st{padding:8px;border:2px solid #333}
.fail{color:#a00;font-weight:bold}.note{font-size:12px;color:#555}</style>"""


def build_report_cfs_india(name, cfg, pkg, root):
    u = _set_report_units(cfg)
    site = cfg.get("site") or {}; lat = pkg.get("lateral_frame") or {}; lp = cfg.get("load_plan") or {}
    ss = lat.get("seismic_summary") or {}
    st = pkg.get("design_status") or {}
    out = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>%s</title>%s</head><body>" % (_e(name), CSS)]
    out.append("<h1>%s -- India cold-formed steel design report</h1>" % _e(name))
    out.append("<p class='note'>%s</p>" % _e(B.BASIS_STATEMENT))
    out.append("<div class='st'>Design status (%s): <b>%s</b> -- %d open reason(s)</div>"
               % (_e(st.get("authority")), _e(str(st.get("status", "")).upper()), st.get("n_reasons", 0)))
    # ---- 1 building ----
    out.append("<h2>1. Building, site and load path</h2>")
    geo = cfg.get("geometry") or {}
    out.append(_t(["item", "value"], [
        ("brief", cfg.get("brief")), ("site", "%s, IS 1893 Annex E Zone %s (Z = %s), soil type %s" % (site.get("city"), site.get("zone"), site.get("Z"), site.get("soil"))),
        ("plan / heights", "%s m x %s m; storeys %s m" % (geo.get("plan_x_m"), geo.get("plan_y_m"), geo.get("heights_m"))),
        ("lateral system", "%s hot-rolled IS 800:2007 Section 12 frame, R = %s (%s)" % (lat.get("system"), lat.get("R"), lat.get("R_cite"))),
        ("cold-formed members", "IS 801:1975 working stress; IS 811:1987 sections; gravity / wind only (no seismic force-resisting role)"),
        ("importance factor", "I = %s (%s %s)" % (ss.get("I"), ss.get("I_row"), ss.get("I_cite"))),
        ("occupancy", json.dumps(cfg.get("occupancy"), default=str)),
        ("engine units", u["engine"] + "; report in " + ", ".join(u[k] for k in ("force", "moment", "length", "small_length", "pressure", "stress"))),
    ]))
    # ---- 2 loads ----
    out.append("<h2>2. Loads (IS 875 Parts 1-4, IS 1893)</h2>")
    ld = cfg.get("loads") or {}
    out.append(_t(["gravity (kN/m2)", "value"], [(k, ld.get(k)) for k in ("D_floor", "D_roof", "L_floor", "Lr", "clad", "partition_design_kNm2", "partition_seismic_kNm2", "snow")] + [("cite", ld.get("cite"))]))
    ws = lp.get("wind_summary") or {}
    out.append("<p>Wind: IS 875 (Part 3):2015 Vb = %s m/s (%s), terrain category %s, k1 %s, k3 %s, k4 %s, Kd %s, Ka %s (%s), cyclone belt %s -- %s</p>"
               % (ws.get("Vb_mps"), _e(ws.get("Vb_source")), ws.get("terrain_category"), ws.get("k1"), ws.get("k3"), ws.get("k4"), ws.get("Kd"), ws.get("Ka"), ws.get("Ka_basis"), ws.get("cyclone_belt"), _e(ws.get("cyclone_belt_cite"))))
    if ws.get("storeys"):
        out.append(_t(["storey", "z (m)", "k2", "Vz (m/s)", "pz (kN/m2)", "pd (kN/m2)"],
                      [(r["k"], r["z_m"], r["k2"], r["Vz_mps"], r["pz_kNm2"], r["pd_kNm2"]) for r in ws["storeys"]]))
        out.append("<p>Cpe walls (Table 5): X %s; Y %s. Wind base shear X %s kN, Y %s kN.</p>"
                   % (_e(ws.get("Cpe_X")), _e(ws.get("Cpe_Y")), _f(ws.get("VB_x_kN"), 1), _f(ws.get("VB_y_kN"), 1)))
    if lat.get("statement"):
        out.append("<p><b>%s</b></p>" % _e(lat["statement"]))
    if ss:
        out.append("<p>Seismic (IS 1893 (Part 1):2016 + Amd 1, 2): Z %s, I %s, R %s, soil %s, Ta %s / %s s (%s), Sa/g %s, "
                   "<b>Ah = %s</b>, W = %s kN, <b>VB = %s kN</b>; analysis %s%s.</p>"
                   % (ss.get("Z"), ss.get("I"), ss.get("R"), ss.get("soil"), _f(ss.get("Ta_x_s"), 3), _f(ss.get("Ta_y_s"), 3), _e(ss.get("Ta_formula")),
                      ss.get("Sa_g"), ss.get("Ah"), _f(ss.get("W_kN"), 1), _f(ss.get("VB_kN"), 2), _e((lat.get("seismic_analysis") or {}).get("method")),
                      (" (RSA scaled to VB, 7.7.3: %s)" % _e((lat.get("seismic_analysis") or {}).get("scale"))) if (lat.get("seismic_analysis") or {}).get("scale") else ""))
    # ---- 3 combinations ----
    out.append("<h2>3. Load combinations (IS 875 Part 5 working stress per IS 801; IS 800 Table 4 for the hot-rolled frame)</h2>")
    cc = pkg.get("cfs_combinations") or []
    out.append("<p>CFS members -- %s (%d rows, factor 1.0; +33 1/3 %% allowable on the wind / earthquake rows, IS 801 6.1.2):</p>" % (B.DESIGN_BASIS, len(cc)))
    out.append(_t(["label", "DL", "IL", "Lr", "SL", "WL", "EL", "allowable increase", "cite"],
                  [(c["label"], c["fD"], c["fL"], c["fLr"], c.get("fS", 0), c["fW"], c["fE"], _f(c["allowable_increase"], 4), c["cite"][:90]) for c in cc]))
    out.append("<p>Hot-rolled lateral frame -- %s: %s IS 800 Table 4 / IS 1893 6.3 / 7.8.2 / vertical / IS 800 12.2.3 (IS 18168 5.5) combinations "
               "generated by the vendored india_combos (listed in the frame report).</p>" % (B.LATERAL_FRAME_BASIS, lat.get("load_combinations_n")))
    # ---- 4 lateral frame ----
    out.append("<h2>4. Hot-rolled lateral frame (vendored HR India pipeline @ %s)</h2>" % _e(lat.get("vendored_commit")))
    if lat.get("report_html"):
        rel = os.path.relpath(lat["report_html"], root) if os.path.isabs(lat["report_html"]) else lat["report_html"]
        out.append("<p>Full frame report: <a href='%s'>%s</a> (13 chapters: members, Section 12, connections, bases, drift, irregularity).</p>" % (_e(rel), _e(rel)))
    out.append(_t(["member group", "role", "section", "n", "governing combination", "D/C"],
                  [(m["id"], m["role"], m["section"], m.get("n"), m.get("governing_combo"), _f(m.get("DC"))) for m in lat.get("members") or []]))
    out.append(_t(["connection", "type", "D/C", "not evaluated"],
                  [(c["id"], c["type"], _f(c.get("DC")), "; ".join(c.get("not_evaluated") or [])) for c in lat.get("connections") or []]))
    dt = lat.get("drift_table") or []
    out.append(_t(["storey", "dir", "drift", "limit", "ok"], [(d["storey"], d["dir"], _f(d["drift"], 5), d["limit"], _ok(d["ok"])) for d in dt]))
    cd = lat.get("capacity_design") or {}
    out.append("<p>IS 800 Section 12 / IS 18168 checks: %s total, <span class='%s'>%s fail</span>, %s not evaluated. HR authority status: <b>%s</b></p>"
               % (cd.get("n_checks"), "fail" if cd.get("n_fail") else "", cd.get("n_fail"), cd.get("n_not_evaluated"), _e(str((lat.get("status") or {}).get("status", "")).upper())))
    if (lat.get("status") or {}).get("reasons"):
        out.append("<ul class='note'>" + "".join("<li>%s</li>" % _e(r) for r in lat["status"]["reasons"][:40]) + "</ul>")
    # ---- 5 CFS members ----
    out.append("<h2>5. Cold-formed members (IS 801:1975 working stress, IS 811:1987 sections)</h2>")
    for m in pkg.get("cfs_members") or []:
        out.append("<h3>%s -- %s (%s), Fy %s MPa, spacing %s mm, length %s mm, <b>D/C %s</b> (%s)</h3>"
                   % (_e(m["id"]), _e(m["designator"]), _e(m.get("role")), m.get("Fy_MPa"), m.get("spacing_mm"), m.get("length_mm"), _f(m.get("DC")), _ok(m.get("ok"))))
        if m.get("wind"):
            out.append("<p class='note'>wind: %s</p>" % _e(m["wind"]))
        if m.get("axial"):
            out.append("<p class='note'>axial: %s</p>" % _e(m["axial"]))
        if m.get("loads_N_per_mm"):
            out.append("<p class='note'>line loads (kN/m): %s</p>" % _e({k: round(v, 3) for k, v in m["loads_N_per_mm"].items()}))
        out.append(_t(["combination", "check", "value", "limit", "D/C", "increase", "result", "clause"],
                      [(c.get("combo"), c.get("check"), _f(c.get("value")), _f(c.get("limit")), _f(c.get("dc")), _f(c.get("allowable_increase"), 3),
                        _ok(c.get("ok")) + (" (info)" if c.get("informational") else ""), c.get("clause")) for c in m.get("checks") or []]))
    # ---- 6 diaphragm ----
    out.append("<h2>6. Diaphragm path to the frame lines</h2>")
    out.append(_t(["storey", "dir", "F EQ (kN)", "F W (kN)", "governing", "unit shear (kN/m)", "chord (kN)", "capacity", "result"],
                  [(r["storey"], r["dir"], _kN(r["F_EQ_N"]), _kN(r["F_W_N"]), r["governing"], _f(r["v_unit_kN_per_m"], 2), _f(r["chord_force_kN"], 1),
                    r.get("capacity") or "found:false (EOR product / test value)", _ok(r.get("ok")))
                   for r in pkg.get("diaphragm") or [] if r.get("kind") != "collector"]))
    coll = [r for r in pkg.get("diaphragm") or [] if r.get("kind") == "collector"]
    if coll:                                                  # C03: re-entrant collectors
        out.append(_t(["storey", "dir", "re-entrant line", "B_short / B (m)", "collector force (kN)", "capacity (kN)", "result"],
                      [(r["storey"], r["dir"], r.get("line"), "%s / %s" % (_f(r.get("B_short_m"), 2), _f(r.get("B_m"), 2)),
                        _f(r.get("F_collector_kN"), 2), r.get("capacity") or "found:false (EOR input)", _ok(r.get("ok"))) for r in coll]))
    # ---- 7 connections ----
    out.append("<h2>7. Cold-formed connections and anchors (IS 801 7.2 / 7.5)</h2>")
    cn = pkg.get("cfs_connections") or []
    out.append(_t(["id", "type", "demand (kN)", "capacity (kN)", "D/C", "basis", "result", "clause"],
                  [(c["id"], c.get("type"), _kN(c.get("value")), _kN(c.get("limit")), _f(c.get("dc")), c.get("capacity_basis"), _ok(c.get("ok")), c.get("clause")) for c in cn])
               if cn else "<p>none declared</p>")
    # ---- 8 grounding ----
    out.append("<h2>8. Grounding (retrieved standards)</h2>")
    out.append(_t(["standard", "used for", "retrieval hits", "status"], pkg.get("grounding") or []))
    # ---- 9 status ----
    out.append("<h2>9. Design status</h2>")
    out.append("<p><b>%s</b> (%s)</p>" % (_e(str(st.get("status", "")).upper()), _e(st.get("authority"))))
    out.append("<ol>" + "".join("<li>%s</li>" % _e(r) for r in st.get("reasons") or []) + "</ol>")
    out.append("<p class='note'>Vendored shared India engine: work/hr @ %s (steel_engine/hr_vendor/VENDORED_FROM.md).</p>" % _e(lat.get("vendored_commit")))
    out.append("</body></html>")
    path = os.path.join(root, "report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return path
