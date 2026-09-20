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
        pkg["portal"] = por
        pkg["lateral_frame"] = por.get("lateral_summary")
        pkg["cfs_members"] = por.get("members") or []
        pkg["cfs_connections"] = por.get("connections") or []
        cfg["load_plan"]["wind_summary"] = por.get("wind_summary") or cfg["load_plan"].get("wind_summary")
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
        v = os.path.join((pkg.get("lateral_frame") or {}).get("root") or "", "viewer_3d.html")
        if os.path.exists(v):
            shutil.copy(v, os.path.join(root, "viewer_3d.html"))
            vend = os.path.join(os.path.dirname(v), "vendor")
            if os.path.isdir(vend) and not os.path.isdir(os.path.join(root, "vendor")):
                shutil.copytree(vend, os.path.join(root, "vendor"))
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
    with open(os.path.join(root, "STATUS.md"), "w") as f:
        f.write("# %s -- design status: %s\n\nAuthority: %s\nVendored HR engine: %s\n\nOpen reasons (%d):\n%s"
                % (name, st["status"].upper(), st["authority"], (pkg.get("lateral_frame") or {}).get("vendored_commit"),
                   len(st["reasons"]), "".join("- %s\n" % r for r in st["reasons"])))
    print("[%s] status %s (%d reasons)" % (name, st["status"], st["n_reasons"]))
    return out
