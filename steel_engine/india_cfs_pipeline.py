"""india_cfs_pipeline.py -- the design entry point of an India CFS job (D3 / D5):

    import india_cfs_pipeline as CP
    out = CP.design_and_report(name, cfg, outdir=<job folder>)

  1. preflight.check(cfg) -- schema-aware; any ERROR raises before anything is analysed (WP3.6 / CFSREPO-10)
  2. hot-rolled lateral frame: india_cfs_lateral.run_lateral -> vendored HR India pipeline in a subprocess
     (IS 1893 ESM + RSA, IS 800 Table 4 combinations, IS 800 member checks, Section 12 / IS 18168, connections,
     bases, drift, irregularity, HR design_status, HR report + viewer)        [or the all-CFS portal: india_cfs_portal]
  3. cold-formed members to IS 801 (india_cfs_members) with the IS 875-5 8.1 working-stress set
  4. diaphragm demands to the frame lines (india_cfs_lateral.diaphragm_demands), CFS connections (declared)
  5. package design/calc_package_cfs.json (+ cfg_snapshot.json, load_plan.json), report.html (report_cfs_india),
     viewer_3d.html (the frame viewer from the HR run), consistency.check, india_cfs_gates.design_status, STATUS.md
The package status is `complete` only through india_cfs_gates.design_status.
"""
from __future__ import annotations
import json
import os
import re
import shutil

import india_cfs_env  # noqa: F401
import preflight as PF
import india_cfs_basis as B
import india_cfs_gates as G
import india_cfs_lateral as L
import india_cfs_members as CM
import report_cfs_india as R
import consistency as CC

STEMS = {
    "IS_801_1975": ("IS 801:1975", "cold-formed member allowables (5.2, 6.1-6.7, 7, 8.1)"),
    "IS_811_1987": ("IS 811:1987", "cold-formed section properties (Tables 1-10)"),
    "IS_875_Part_1_2026": ("IS 875 (Part 1):2026", "dead loads"),
    "IS_875_Part_2_1987": ("IS 875 (Part 2):1987", "imposed loads, partitions"),
    "IS_875_Part_3_2015": ("IS 875 (Part 3):2015", "wind: Vb, k2, k4/Kd, Ka, Cpe, Cpi"),
    "IS_875_Part_4_1987": ("IS 875 (Part 4):2021", "snow (where applicable)"),
    "IS_875_Part_5_1987": ("IS 875 (Part 5):1987", "load combinations 8.1 (working stress)"),
    "IS_1893_Part_1_2016": ("IS 1893 (Part 1):2016 + Amd 1, 2", "Z, I, R, Sa/g, Ah, W, Ta, 7.7.1, drift"),
    "IS_800_2007": ("IS 800:2007", "hot-rolled lateral frame: Table 4, members, Section 12, connections"),
    "IS_18168_2023": ("IS 18168:2023", "seismic steel detailing precedence (Zone III-V)"),
}


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o
    return str(o)


def _grounding(cfg, pkg):
    plan = cfg.get("load_plan") or {}
    hits = {}
    for h in plan.get("retrieval") or []:
        if isinstance(h, dict):
            hits.setdefault(h.get("stem"), []).append(h)
    needed = ["IS_801_1975", "IS_811_1987", "IS_875_Part_1_2026", "IS_875_Part_2_1987", "IS_875_Part_3_2015", "IS_875_Part_5_1987",
              "IS_1893_Part_1_2016"]
    if pkg.get("lateral_frame") and not cfg.get("all_cfs_portal"):
        needed += ["IS_800_2007"]
        if str((cfg.get("site") or {}).get("zone")).upper() in ("III", "IV", "V"):
            needed += ["IS_18168_2023"]
    if (cfg.get("loads") or {}).get("snow"):
        needed += ["IS_875_Part_4_1987"]
    rows, missing = [], []
    for s in needed:
        n = len(hits.get(s, [])); ft = sum(1 for h in hits.get(s, []) if h.get("found") is True)
        status = "grounded" if ft else "MISSING"
        if status == "MISSING":
            missing.append(s)
        rows.append((STEMS[s][0], STEMS[s][1], "%d (found:true %d)" % (n, ft), status))
    return rows, missing


def _eor_inputs(cfg, pkg):
    """cfg['eor_inputs'] plus every package check that rests on an EOR / test value (capacity_basis EOR_input or test), so
    EOR_inputs.json is complete even when the cfg forgot to list one (lead ruling L5)."""
    rows = [dict(e) for e in (cfg.get("eor_inputs") or []) if isinstance(e, dict)]
    seen = {(r.get("item"), r.get("value")) for r in rows}

    def walk(obj, path):
        if isinstance(obj, dict):
            cb = obj.get("capacity_basis")
            if cb in ("EOR_input", "test") and ("limit" in obj or "capacity" in obj):
                item = "%s (%s)" % (re.sub(r"\[\d+\]", "", path.split(".")[-1]), obj.get("clause") or cb)
                val = obj.get("limit", obj.get("capacity"))
                key = (item, val, obj.get("cite") or obj.get("source"))
                if key not in seen:
                    seen.add(key)
                    rows.append({"item": item, "value": val, "source": obj.get("cite") or obj.get("source") or "EOR -- VERIFY",
                                 "capacity_basis": cb, "from_package": path})
            for k, v in obj.items():
                if k not in ("cfg_snapshot", "consistency"):
                    walk(v, path + "." + str(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, "%s[%d]" % (path, i))
    walk(pkg, "pkg")
    return rows


def _portal_viewer(name, pkg, path):
    """Self-contained SVG elevation + plan of the all-CFS portal (no HR viewer exists for this path)."""
    g = pkg["portal_frame_geometry"]
    nodes = {k: (float(v[0]), float(v[1])) for k, v in g["nodes"].items()}
    xs = [x for x, y in nodes.values()]; ys = [y for x, y in nodes.values()]
    W_, H_ = 900.0, 420.0; pad = 40.0
    sx = (W_ - 2 * pad) / max(1.0, max(xs) - min(xs)); sy = (H_ - 2 * pad) / max(1.0, max(ys) - min(ys)); sc = min(sx, sy)

    def P(x, y):
        return (pad + (x - min(xs)) * sc, H_ - pad - (y - min(ys)) * sc)
    col = {"col": "#1f4e79", "raf": "#7a1f1f", "knee": "#2e7d32", "mezz": "#8a6d00"}
    lines = []
    for n1, n2, lab in g["elements"]:
        (x1, y1), (x2, y2) = P(*nodes[n1]), P(*nodes[n2])
        c = next((v for k, v in col.items() if k in str(lab).lower()), "#444")
        lines.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="3"><title>%s</title></line>' % (x1, y1, x2, y2, c, lab))
    for t in g.get("supports", {}):
        x, y = P(*nodes[t])
        lines.append('<rect x="%.1f" y="%.1f" width="12" height="8" fill="#000"/>' % (x - 6, y))
    mem = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%.2f</td></tr>" % (m["role"], m["section"], m.get("n_ply", 1), m["DC"])
                  for m in pkg.get("cfs_members", []))
    ss = (pkg.get("lateral_frame") or {}).get("seismic_summary") or {}
    n = int(g.get("n_frames") or 1); sp = float(g.get("spacing_mm") or 0.0) / 1000.0
    html = """<!doctype html><html><head><meta charset="utf-8"><title>%s -- portal frame</title>
<style>body{font-family:system-ui,sans-serif;margin:20px;color:#222}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:3px 8px;font-size:13px}</style></head>
<body><h2>%s -- all-CFS portal (elastic, R = 1.0), transverse frame elevation (mm)</h2>
<p>%d frames at %.1f m; blue = columns, red = rafters, green = knee braces, olive = mezzanine; black = bases. Hover a member for its label.</p>
<svg width="%d" height="%d" viewBox="0 0 %d %d" style="border:1px solid #ccc;background:#fff">%s</svg>
<h3>Members (IS 801 working stress)</h3><table><tr><th>role</th><th>IS 811 section</th><th>n_ply</th><th>D/C</th></tr>%s</table>
<p>Ah = %s; VB (frame) = %s kN; wind governs: %s. Generated by india_cfs_pipeline (SVG elevation; no 3-D solid model on the all-CFS path).</p>
</body></html>""" % (name, name, n, sp, int(W_), int(H_), int(W_), int(H_), "".join(lines), mem, ss.get("Ah"), ss.get("VB_frame_kN"),
                     ((pkg.get("lateral_frame") or {}).get("wind_vs_eq") or {}).get("governing"))
    open(path, "w", encoding="utf-8").write(html)
    return path


def design_and_report(name, cfg, outdir=None, do_report=True):
    root = outdir or os.path.join(os.environ.get("STEEL_BUILDER_JOBS") or os.getcwd(), name)
    os.makedirs(os.path.join(root, "design"), exist_ok=True)
    pf = PF.check(cfg)
    print(PF.render(pf))
    errs = [m for s, m in pf if s == "ERROR"]
    json.dump([{"sev": s, "msg": m} for s, m in pf], open(os.path.join(root, "preflight.json"), "w"), indent=1)
    if errs:
        raise RuntimeError("preflight ERRORs -- fix the cfg before any analysis:\n- " + "\n- ".join(errs))
    pkg = {"building": name, "design_basis": B.DESIGN_BASIS, "lateral_frame_basis": B.LATERAL_FRAME_BASIS,
           "basis_statement": B.BASIS_STATEMENT, "units": {"engine": "N, mm, MPa", "display": "kN, kN-m, m, mm, kN/m2, MPa"},
           "preflight": [{"sev": s, "msg": m} for s, m in pf]}
    # ---- 2 lateral frame ----
    if cfg.get("all_cfs_portal"):
        import india_cfs_portal as PO
        por = PO.run(cfg, root)
        pkg["portal"] = {k: v for k, v in por.items() if k != "frame_geometry"}
        pkg["portal_frame_geometry"] = por.get("frame_geometry")
        pkg["lateral_frame"] = por.get("lateral_summary")
        pkg["cfs_members"] = por.get("members") or []
        pkg["cfs_connections"] = por.get("connections") or []
        ws = por.get("wind_summary") or {}
        cfg["load_plan"]["wind_summary"] = ws
        cfg["load_plan"]["seismic_summary"] = por.get("seismic_summary")
        # secondary members (purlins / girts / mezzanine joists) with the member-level pressures of the portal patterns
        cm = cfg.get("cfs_members") or {}
        pats = ws.get("patterns") or []
        if cm.get("purlins") and pats:
            roof = [p["roof_windward_kNm2"] for p in pats] + [p["roof_leeward_kNm2"] for p in pats]
            cm["purlins"]["wind_uplift_kNm2"] = min(roof)          # most negative net (suction)
            cm["purlins"]["wind_pressure_kNm2"] = max(max(roof), 0.0)
        if cm.get("girts") and pats:
            walls = [p["wall_windward_kNm2"] for p in pats] + [p["wall_leeward_kNm2"] for p in pats]
            cm["girts"]["wind_suction_kNm2"] = -min(min(walls), 0.0)
            cm["girts"]["wind_pressure_kNm2"] = max(walls)
        if cm.get("joists") and cfg.get("mezzanine"):
            cfg["loads"]["D_floor"] = cfg["mezzanine"]["D_kNm2"]; cfg["loads"]["L_floor"] = cfg["mezzanine"]["L_kNm2"]
        pkg["cfs_members"] += CM.design_all(dict(cfg, cfs_members={k: v for k, v in cm.items() if k in ("Fy_MPa", "grade_cite", "purlins", "girts", "joists")}))
        pkg["diaphragm"] = []
    else:
        lat = L.run_lateral(cfg, os.path.join(root, "lateral"), name=name + "_lateral")
        hr_plan = json.load(open(os.path.join(lat["root"], "load_plan.json"))) if os.path.exists(os.path.join(lat["root"], "load_plan.json")) else {}
        cfg["load_plan"]["wind_summary"] = hr_plan.get("wind_summary") or cfg["load_plan"].get("wind_summary")
        cfg["load_plan"]["story_forces"] = hr_plan.get("story_forces")
        cfg["load_plan"]["story_forces_units"] = "N"
        spec = json.load(open(lat["spec"]))
        pkg["lateral_frame"] = {
            "name": lat["name"], "system": spec["system"], "R": spec["R"], "R_cite": L.TABLE9_CITE, "vendored_commit": lat.get("vendored_commit"),
            "root": lat["root"], "report_html": lat.get("report_html"), "status": lat.get("status"), "error": lat.get("error"),
            "seismic_summary": hr_plan.get("seismic_summary"), "seismic_analysis": lat.get("seismic_analysis"), "seismic_calc": lat.get("seismic_calc"),
            "members": lat.get("members"), "connections": lat.get("connections"), "drift_table": lat.get("drift_table"), "drift_max": lat.get("drift_max"),
            "irregularity": lat.get("irregularity"), "capacity_design": lat.get("capacity_design"), "collectors": lat.get("collectors"),
            "diaphragm_7_6_4": lat.get("diaphragm_7_6_4"), "load_combinations_n": lat.get("load_combinations_n"), "gates": lat.get("gates"),
            "demand_level": "LSD", "capacity_basis": "IS800_LSD",
            "note": "hot-rolled IS 800 Section 12 frame designed by the vendored HR India pipeline (IS 800 Table 4 limit state); "
                    "the CFS members claim no seismic force-resisting role (D3)"}
        # ---- 3 CFS members ----
        pkg["cfs_members"] = CM.design_all(cfg)
        # ---- 4 diaphragm + declared CFS connections ----
        pkg["diaphragm"] = L.diaphragm_demands(cfg, lat)
        pkg["cfs_connections"] = list((cfg.get("cfs_connections") or []))
    pkg["cfs_combinations"] = B.cfs_combinations(cfg.get("load_plan"), cfg)
    pkg["grounding"], missing = _grounding(cfg, pkg)
    pkg["grounding_missing"] = missing
    pkg["cfg_snapshot"] = _jsonable({k: v for k, v in cfg.items()})
    st = G.design_status(cfg, pkg)
    pkg["design_status"] = st
    json.dump(_jsonable(pkg), open(os.path.join(root, "design", "calc_package_cfs.json"), "w"), indent=1)
    json.dump(_jsonable(cfg["load_plan"]), open(os.path.join(root, "load_plan.json"), "w"), indent=1)
    json.dump(_jsonable(cfg), open(os.path.join(root, "cfg_snapshot.json"), "w"), indent=1)
    out = {"name": name, "root": root, "status": st["status"], "n_reasons": st["n_reasons"], "reasons": st["reasons"],
           "lateral_status": (pkg.get("lateral_frame") or {}).get("status")}
    if do_report:
        out["report_html"] = R.build_report_cfs_india(name, cfg, pkg, root)
        lroot = (pkg.get("lateral_frame") or {}).get("root")          # HR lateral run (absent on the all-CFS portal path)
        v = os.path.join(lroot, "viewer_3d.html") if lroot else None
        if v and os.path.exists(v):
            shutil.copy(v, os.path.join(root, "viewer_3d.html"))
            vend = os.path.join(os.path.dirname(v), "vendor")
            if os.path.isdir(vend) and not os.path.isdir(os.path.join(root, "vendor")):
                shutil.copytree(vend, os.path.join(root, "vendor"))
        elif pkg.get("portal_frame_geometry"):
            _portal_viewer(name, pkg, os.path.join(root, "viewer_3d.html"))
        issues = CC.check(name, root=root, pkg=pkg, verbose=True)
        pkg["consistency"] = issues
        # the status is re-evaluated with the rendered report (US residue / grounding) and the consistency findings
        if issues:
            pkg["report_us_residue"] = [x for x in issues if x.startswith("report US residue")]
        st = G.design_status(cfg, pkg)
        if issues and st["status"] == "complete":
            st = {"status": "partial", "reasons": ["consistency: " + x for x in issues], "n_reasons": len(issues), "authority": st["authority"]}
        pkg["design_status"] = st
        out.update(status=st["status"], n_reasons=st["n_reasons"], reasons=st["reasons"], consistency=issues)
        json.dump(_jsonable(pkg), open(os.path.join(root, "design", "calc_package_cfs.json"), "w"), indent=1)
        out["report_html"] = R.build_report_cfs_india(name, cfg, pkg, root)
    eor = _eor_inputs(cfg, pkg)
    json.dump(_jsonable(eor), open(os.path.join(root, "EOR_inputs.json"), "w"), indent=1)
    basis_text = B.BASIS_STATEMENT
    if cfg.get("all_cfs_portal"):
        basis_text = ((pkg.get("lateral_frame") or {}).get("statement") or "") + "\n\n" + B.BASIS_STATEMENT.split(" The lateral force-resisting system")[0]
    with open(os.path.join(root, "STATUS.md"), "w") as f:
        f.write("# %s -- design status: %s\n\nAuthority: %s\nVendored HR engine: %s\n\n%s\n\nOpen reasons (%d):\n%s"
                % (name, st["status"].upper(), st["authority"], (pkg.get("lateral_frame") or {}).get("vendored_commit"), basis_text,
                   len(st["reasons"]), "".join("- %s\n" % r for r in st["reasons"])))
        if eor:
            f.write("\nEOR inputs relied upon (EOR_inputs.json, lead ruling L5 -- every number EOR-supplied, VERIFY):\n")
            for e in eor:
                f.write("- %s: %s (%s)\n" % (e.get("item"), e.get("value"), e.get("source")))
    print("[%s] status %s (%d reasons)" % (name, st["status"], st["n_reasons"]))
    return out
