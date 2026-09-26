#!/usr/bin/env python3
"""hr_vendor_runner.py -- run the vendored HR India pipeline on the hot-rolled lateral frame of a CFS job.

Executed as a SUBPROCESS by india_cfs_lateral.run_lateral (so the HR modules named preflight / consistency /
report / pipeline never collide with the CFS ones):

    python3 hr_vendor_runner.py <spec.json> <jobs_root> <name>

The spec is the declarative frame description written by india_cfs_lateral.build_hr_spec (grid, bays, braced bays
/ moment lines, sections per storey group, grades, loads, connections, site / seismic / wind summaries, retrieval).
This runner turns it into the HR cfg (callables for braces / col_sec / beam_sec / releases / col_strong), recomputes
the IS 1893 seismic weight and ESM story forces from the engine (W = model mass, WP1.6), and calls
pipeline.design_and_report -> design_pipeline.design_india -> report_india -> india_seismic_gates.design_status.
Output: <jobs_root>/<name>/{load_plan.json, design/calc_package.json, report.html, STATUS.md, ...} plus
<jobs_root>/<name>/lateral_result.json (the compact summary the CFS package reads back).
CFS-specific behaviour lives here and in india_cfs_lateral; nothing in hr_vendor/ is edited.
"""
from __future__ import annotations
import json
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "hr_vendor")
sys.path.insert(0, VENDOR)                      # HR modules first (this process runs the HR engine only)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def _callables(spec):
    NX, NY = spec["NX"], spec["NY"]
    NF = len(spec["heights_m"])
    braced = spec.get("braced_bays") or []
    bset = {(b[0], int(b[1]), int(b[2])) for b in braced}
    moment_lines = spec.get("moment_lines") or []          # [("X", j), ("Y", i)] frame lines with rigid beam-column joints
    mset = {(m[0], int(m[1])) for m in moment_lines}
    col_groups = spec.get("col_sec") or {}                  # {"perimeter": {"1-2": sec, "3-4": sec}, "interior": {...}}
    beam_groups = spec.get("beam_sec") or {}                # {"floor": sec, "roof": sec, "floor_X": ..}
    lateral_cols = set()
    for (d, i, j) in bset:
        lateral_cols.add((i, j)); lateral_cols.add((i + 1, j) if d == "X" else (i, j + 1))
    for (d, k) in mset:
        for q in range((NX if d == "X" else NY) + 1):
            lateral_cols.add((q, k) if d == "X" else (k, q))

    def _pick(groups, k):
        for rng, sec in groups.items():
            a, _, b = str(rng).partition("-")
            a = int(a); b = int(b) if b else a
            if a <= k <= b:
                return sec
        return None

    def braces(k, nx, ny):
        return [(d, i, j) for (d, i, j) in bset]

    def col_sec(i, j, k, perim):
        lat = (i, j) in lateral_cols
        grp = col_groups.get("lateral" if lat else "gravity") or col_groups.get("perimeter" if perim else "interior") or {}
        return _pick(grp, k) or spec["col"]

    def beam_sec(i, j, k, dirn):
        roof = (k == NF)
        v = beam_groups.get(("roof" if roof else "floor") + "_" + dirn) or beam_groups.get("roof" if roof else "floor")
        if isinstance(v, dict):                             # C11: storey-ranged beam group {"1-2": sec, "3-8": sec}
            v = _pick(v, k)
        return v or spec["beam"]

    def col_strong(i, j, nx, ny):
        # strong axis in the plane of the frame the column belongs to (moment line first, then braced bay)
        for (d, k) in mset:
            if (d == "X" and j == k) or (d == "Y" and i == k):
                return d
        for (d, bi, bj) in bset:
            if d == "X" and j == bj and i in (bi, bi + 1):
                return "X"
            if d == "Y" and i == bi and j in (bj, bj + 1):
                return "Y"
        return spec.get("default_strong", "X")

    def releases(i, j, k, dirn):
        if (dirn, j if dirn == "X" else i) in mset:
            return ("none", "none")                       # rigid moment connection on a moment-frame line
        return ("both", "none")                           # simple shear connection (gusset + shear tab elsewhere)

    return braces, col_sec, beam_sec, col_strong, releases


def build_cfg(spec):
    import india_units as IU
    import engine3d as E
    import example_build as EB
    braces, col_sec, beam_sec, col_strong, releases = _callables(spec)
    heights = list(spec["heights_m"])
    cfg = {
        "name": spec["name"], "system": spec["system"], "arch": spec["system"], "jurisdiction": "india", "units": "m",
        "metric": True, "si_native": True,
        "NX": spec["NX"], "NY": spec["NY"], "bay_x": spec["bay_x_m"], "bay_y": spec["bay_y_m"], "heights": heights,
        "D_floor": spec["D_floor"], "D_roof": spec["D_roof"], "L_floor": spec["L_floor"], "Lr": spec["Lr"],
        "clad": spec.get("clad", 0.0), "snow": spec.get("snow", 0.0),
        "partition_load_kNm2": spec.get("partition_design_kNm2", 0.0), "partition_seismic_kNm2": (spec["partition_seismic_kNm2"] if spec.get("partition_seismic_kNm2") is not None
                                   else max(0.5, float(spec.get("partition_design_kNm2") or 0.0))),     # H22 / R1: IS 1893 7.3.6
        "partitions": spec.get("partitions", True),
        "E": 200000.0, "base": spec.get("base", "fixed"), "diaphragm": spec.get("diaphragm", "rigid"),
        "floor_system": spec.get("floor_system", "one-way (CFS joists between the hot-rolled beams)"),
        "deck_span": spec.get("deck_span", "Y"),
        "model": {"bases": spec.get("base", "fixed"), "joints": spec.get("joints", "pinned except the designated moment lines"),
                  "gravity": "framed (hot-rolled grid carries the CFS floor joists / roof)"},
        "col": spec["col"], "beam": spec["beam"], "brace": spec.get("brace"),
        "braces": braces if spec.get("braced_bays") else None, "col_sec": col_sec, "beam_sec": beam_sec,
        "col_strong": col_strong, "releases": releases, "custom_build": EB.example_build,
        "steel_grade": spec.get("steel_grade", "E250 B0"), "brace_grade": spec.get("brace_grade", "E250 B0"),
        "brace_process": spec.get("brace_process"), "brace_config": spec.get("brace_config", "X"),
        "sway_frame": bool(spec.get("moment_lines")), "column_lateral_support_both_flanges": True,
        "K_factors": spec.get("K_factors") or {"lateral_col": {"Kz": 1.0, "Ky": 1.0}, "gravity_col": {"Kz": 1.0, "Ky": 1.0},
                                                "brace": {"Kz": 1.0, "Ky": 1.0}, "basis": "IS 800 Table 11 (braced frame, both ends restrained)"},
        "LLT_sag_mm": spec.get("LLT_sag_mm") or {"floor": 600.0, "roof": 600.0},
        "LLT_hog_mm": spec.get("LLT_hog_mm") or {"floor": max(spec["bay_x_m"], spec["bay_y_m"]) * 1000.0,
                                                  "roof": max(spec["bay_x_m"], spec["bay_y_m"]) * 1000.0},
        "occupancy": spec["occupancy"], "drift_limit": 0.004, "analyses": ["RSA"],
        "connections": spec.get("connections") or {}, "apply_is18168": spec.get("apply_is18168"),
        "section12_inputs": spec.get("section12_inputs") or {},
        "notes": spec.get("notes", ""), "collector_basis": spec.get("collector_basis"),
        "seis": {"Z": spec["Z"], "I": spec["I"], "R": spec["R"], "zone": spec["zone"], "soil": spec["soil"]},
        "load_plan": spec["load_plan"],
    }
    # C10: mixed systems / per-direction R -- the HR engine reads cfg R_x / R_y and system_x / system_y (H06)
    for key in ("R_x", "R_y", "system_x", "system_y"):
        if spec.get(key) is not None:
            cfg[key] = spec[key]
            if key.startswith("R_"):
                cfg["seis"][key] = spec[key]
    if spec.get("diaphragm_7_6_4"):
        cfg["diaphragm_7_6_4"] = spec["diaphragm_7_6_4"]
    if spec.get("diaphragm_by_level"):                      # GOLD-COLL: per-level rigid / flexible labels
        cfg["diaphragm_by_level"] = spec["diaphragm_by_level"]
    for key in ("diaphragm_type", "delegated_design"):      # AUD-3 / AUD-4 (7.6.4 deck kind; anchor breakout item)
        if spec.get(key) is not None:
            cfg[key] = spec[key]
    for key in ("diaphragm_stiffness", "flexible_diaphragm_analysis", "flexible_diaphragm_eor"):   # X01 (Table 5(ii))
        if spec.get(key) is not None:
            cfg[key] = spec[key]
    if spec.get("default_strong"):
        cfg["default_strong"] = spec["default_strong"]
    if spec.get("roof_planes"):                             # X02: true-slope pitched roof (metre or mm keys)
        import importlib.util as _ilu
        _sp = _ilu.spec_from_file_location("cfs_frame_build_rp", os.path.join(HERE, "india_cfs_frame_build.py"))
        _m = _ilu.module_from_spec(_sp); _sp.loader.exec_module(_m)
        cfg["roof_planes"] = _m.roof_planes_mm(spec["roof_planes"])
    if spec.get("roof_regions"):                            # X02: roof bays of intermediate levels
        cfg["roof_regions"] = {int(k): [tuple(b) for b in v] for k, v in dict(spec["roof_regions"]).items()}
    cfg.update(spec.get("hr_cfg_extra") or {})              # declared HR cfg keys (WP6 gold packages), verbatim
    for key in ("D_by_level", "L_by_level"):                # per-level pressures (podium / mezzanine): int level keys after JSON
        if cfg.get(key):
            cfg[key] = {int(k): float(v) for k, v in dict(cfg[key]).items()}
    IU.apply_si_geometry(cfg)
    IU.apply_metric_pressures(cfg)
    if cfg.get("SX", 0) < 100:
        cfg["SX"] = float(spec["bay_x_m"]) * 1000.0
        cfg["SY"] = float(spec["bay_y_m"]) * 1000.0
    IU.activate_si()
    E.activate_si_units()
    if spec.get("custom_build_module"):
        # WP6: a job-local builder (irregular plan / EBF links / moment lines) declared by the CFS spec; the module's
        # attach(cfg, spec) wires cfg['custom_build'] / cfg['plan'] / cfg['xcoords'] from the JSON spec['gold'] block
        import importlib.util
        cbm = str(spec["custom_build_module"])
        if not cbm.endswith(".py"):
            cbm = os.path.join(HERE, cbm + ".py")          # e.g. india_cfs_frame_build (CFS-only module, loaded by path:
        sp_ = importlib.util.spec_from_file_location("cfs_job_frame_build", cbm)   # steel_engine must NOT enter sys.path here)
        mod = importlib.util.module_from_spec(sp_); sp_.loader.exec_module(mod)
        mod.attach(cfg, spec)
    # ---- IS 1893 seismic summary from the engine weights (W = model mass, WP1.6) ----
    h = sum(heights)
    dx = float(spec.get("d_x_m") or spec["NX"] * spec["bay_x_m"]); dy = float(spec.get("d_y_m") or spec["NY"] * spec["bay_y_m"])
    Ta = {"X": 0.09 * h / math.sqrt(dx), "Y": 0.09 * h / math.sqrt(dy)}      # 7.6.2(c) all other buildings
    ta_formula = "0.09 h/sqrt(d) (IS 1893 7.6.2(c) all other buildings; braced / CFS-clad frame is not a bare MRF)"
    if spec.get("Ta_override"):                                              # e.g. 7.6.2(a) 0.085 h^0.75 on a moment-frame direction
        to = spec["Ta_override"]
        Ta = {"X": float(to.get("X", Ta["X"])), "Y": float(to.get("Y", Ta["Y"]))}
        ta_formula = str(to.get("formula") or ta_formula)
    r = E.esm_from_model(cfg, Ta, soil=spec["soil"])
    plan = cfg["load_plan"]
    ss = plan.setdefault("seismic_summary", {})
    ss.update(r["seismic_summary"])
    ss.update(system=spec["system"], zone=spec["zone"], Z=spec["Z"], I=spec["I"], R=spec["R"], soil=spec["soil"],
              **{k: spec[k] for k in ("R_x", "R_y") if spec.get(k) is not None},
              Ta_formula=ta_formula, Ta_x_s=Ta["X"], Ta_y_s=Ta["Y"], d_x_m=dx, d_y_m=dy)
    plan.setdefault("story_forces", {})
    for d in ("X", "Y"):
        plan["story_forces"]["EQ_" + d] = r["story_forces"]["EQ_" + d]
    plan["story_forces_units"] = "N"
    plan["combinations"] = "auto"
    plan["jurisdiction"] = "india"
    cfg["seis"].update(Ah=ss.get("Ah"), Ta=max(Ta.values()), Sa_g=ss.get("Sa_g"), VB_kN=ss.get("VB_kN"))
    return cfg, r


def _governing(checks, DC=None):
    """C12 (CFS-A-02): value / limit / check / clause of the governing (max dc) HR check, so a summary D/C is traceable and
    never reads as a literal constant."""
    rows = checks.values() if isinstance(checks, dict) else (checks or [])
    rows = [r for r in rows if isinstance(r, dict) and isinstance(r.get("dc"), (int, float))]
    if not rows:
        return {}
    if isinstance(DC, (int, float)):
        g = min(rows, key=lambda r: abs(r["dc"] - DC))          # the row the stored DC comes from (HR DC may exclude e.g. slenderness)
    else:
        g = max(rows, key=lambda r: r["dc"])
    return {"value": g.get("value"), "limit": g.get("limit"), "governing_check": g.get("name") or g.get("check"),
            "governing_clause": g.get("clause")}


def _summary(cfg, out, root):
    import india_seismic_gates as G
    res = {"root": root, "blocked": bool(out.get("blocked")), "error": out.get("error"), "preflight": out.get("preflight")}
    cp = os.path.join(root, "design", "calc_package.json")
    if not os.path.exists(cp):
        return res
    pkg = json.load(open(cp))
    ss = (cfg.get("load_plan") or {}).get("seismic_summary") or {}
    res.update({
        "status": pkg.get("design_status"), "seismic_calc": pkg.get("seismic_calc"), "seismic_analysis": pkg.get("seismic_analysis"),
        "Ah": ss.get("Ah"), "VB_kN": ss.get("VB_kN"), "W_kN": ss.get("W_kN"), "Ta_s": {"X": ss.get("Ta_x_s"), "Y": ss.get("Ta_y_s")},
        "Sa_g": ss.get("Sa_g"), "I": ss.get("I"), "R": ss.get("R"), "Z": ss.get("Z"), "zone": ss.get("zone"),
        "members": [dict({"id": m["id"], "role": m["inputs"]["role"], "section": m["inputs"]["section"], "DC": m.get("DC"),
                          "governing_combo": m["inputs"].get("governing_combo"), "n": m["inputs"].get("n_elements")},
                         **_governing(m.get("checks"), m.get("DC")))
                    for m in pkg.get("members", [])],
        "connections": [dict({"id": c["id"], "type": c["type"], "DC": c.get("DC"),
                              "not_evaluated": [x["name"] for x in c.get("checks", []) if x.get("ok") is None]},
                             **_governing(c.get("checks"), c.get("DC")))
                        for c in pkg.get("connections", [])],
        "drift_table": pkg.get("drift_table"), "drift_max": max((d["drift"] for d in pkg.get("drift_table") or []), default=None),
        "irregularity": {k: (v.get("irregular") if isinstance(v, dict) else v) for k, v in (pkg.get("irregularity") or {}).items()
                         if isinstance(v, dict) and "irregular" in v},
        "capacity_design": {"system": (pkg.get("capacity_design") or {}).get("system"), "R": (pkg.get("capacity_design") or {}).get("R"),
                            "n_checks": len((pkg.get("capacity_design") or {}).get("checks") or {}),
                            "n_fail": sum(1 for c in ((pkg.get("capacity_design") or {}).get("checks") or {}).values() if c.get("ok") is False),
                            "n_not_evaluated": sum(1 for c in ((pkg.get("capacity_design") or {}).get("checks") or {}).values() if c.get("ok") is None)},
        "collectors": pkg.get("collectors"), "diaphragm_7_6_4": pkg.get("diaphragm_7_6_4"),
        "load_combinations_n": len(pkg.get("load_combinations") or []),
        "gates": pkg.get("gates"), "report_html": out.get("report_html"),
    })
    # base reactions for the CFS package (frame anchors): from the static export when present
    try:
        import static_model as SM  # noqa: F401
        res["base_design"] = [c for c in pkg.get("connections", []) if c["type"].startswith("column")]
    except Exception:
        pass
    return res


def main(spec_path, jobs_root, name):
    spec = json.load(open(spec_path))
    os.environ["STEEL_BUILDER_JOBS"] = jobs_root
    os.environ["STELTIC_TEST_JOBS"] = jobs_root
    os.chdir(os.path.dirname(HERE))
    root = os.path.join(jobs_root, name)
    os.makedirs(root, exist_ok=True)
    try:
        cfg, esm = build_cfg(spec)
        json.dump(cfg["load_plan"], open(os.path.join(root, "load_plan.json"), "w"), indent=1, default=str)
        import pipeline as P
        out = P.design_and_report(name, cfg, do_report=True)
        res = _summary(cfg, out, root)
        res["esm"] = {k: v for k, v in esm.items() if k != "seismic_summary"}
    except Exception as ex:
        res = {"root": root, "error": "%s: %s" % (type(ex).__name__, ex), "traceback": traceback.format_exc()}
    json.dump(res, open(os.path.join(root, "lateral_result.json"), "w"), indent=1, default=str)
    print("[hr_vendor_runner] wrote", os.path.join(root, "lateral_result.json"))
    return 0 if not res.get("error") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
