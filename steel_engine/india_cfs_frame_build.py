"""india_cfs_frame_build.py -- the JSON-declared hot-rolled frame builder for CFS jobs whose plan is not a full NX x NY
rectangle (L / Z / T / U / cruciform / split-level / podium) or whose lateral system needs chevron EBF links or moment
lines that the vendored regular-grid builder (example_build) cannot draw.

X06 (E11, HR-B-20): the builder itself now lives in the HR engine as steel_engine/frame_build.py (shared by both
engines; see its docstring for the `gold` block schema).  This module is a thin wrapper that loads that file from the
vendored copy (steel_engine/hr_vendor/frame_build.py) BY PATH -- steel_engine / hr_vendor never enter sys.path here,
so it is safe both in the CFS process (preflight) and across the subprocess boundary of india_cfs_lateral ->
hr_vendor_runner (cfg['lateral_frame']['custom_build_module'] names this module or a job-local .py path).  The public
API is unchanged: make_gold, attach, frame_build, framed_area_m2, framed_area_issues (CFS cfg schema, C06), plus the
private helpers _rng_pick, _cells_area, _xy.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
SHARED_PATH = os.path.join(_HERE, "hr_vendor", "frame_build.py")
_MOD_NAME = "hr_vendor_frame_build"


def _load_shared():
    mod = sys.modules.get(_MOD_NAME)
    if mod is not None:
        return mod
    if not os.path.exists(SHARED_PATH):
        raise ImportError("india_cfs_frame_build: the shared HR frame builder %s is missing -- re-vendor the HR engine "
                          "(steltic_india steel_engine/frame_build.py, X06) into steel_engine/hr_vendor" % SHARED_PATH)
    sp = importlib.util.spec_from_file_location(_MOD_NAME, SHARED_PATH)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[_MOD_NAME] = mod
    sp.loader.exec_module(mod)
    return mod


_FB = _load_shared()
_rng_pick = _FB._rng_pick
make_gold = _FB.make_gold
attach = _FB.attach
_cells_area = _FB._cells_area
framed_area_m2 = _FB.framed_area_m2
_xy = _FB._xy
frame_build = _FB.frame_build


def framed_area_issues(cfg):
    """C06 (CFS-C-05 e): ERROR when the framed floor / roof area of a level (from the model the builder draws) is below
    0.9 x the declared plan area of that level: gold.plan_area_m2 (number or {level: m2}), else geometry plan_x x plan_y
    minus the declared voids (gold.voids_m2 / geometry.voids_m2, number or {level: m2}).  A level the model drops
    silently leaves its gravity load and seismic weight out of the analysis (the Ex10 high-bay roof)."""
    lf = cfg.get("lateral_frame") or {}
    geo = cfg.get("geometry") or {}
    H = list(geo.get("heights_m") or [])
    if not lf or not H or lf.get("NX") is None or lf.get("NY") is None:
        return []
    g = lf.get("gold") if lf.get("custom_build_module") else None
    spec = {"NX": lf["NX"], "NY": lf["NY"], "bay_x_m": lf.get("bay_x_m"), "bay_y_m": lf.get("bay_y_m"), "heights_m": H,
            "gold": g, "col": lf.get("col"), "beam": lf.get("beam"), "brace": lf.get("brace"), "base": lf.get("base"),
            "moment_lines": lf.get("moment_lines")}

    def pick(v, k):
        if isinstance(v, dict):
            return v.get(str(k), v.get(k, _rng_pick(v, k)))
        return v
    out = []
    for k in range(1, len(H) + 1):
        decl = pick((g or {}).get("plan_area_m2"), k)
        src = "gold.plan_area_m2"
        if decl is None:
            if geo.get("plan_x_m") is None or geo.get("plan_y_m") is None:
                continue
            voids = pick((g or {}).get("voids_m2"), k) or pick(geo.get("voids_m2"), k) or 0.0
            decl = float(geo["plan_x_m"]) * float(geo["plan_y_m"]) - float(voids)
            src = "geometry plan_x x plan_y - voids %.1f m2" % float(voids)
        try:
            fa = framed_area_m2(spec, k)
        except Exception as ex:                                     # a malformed gold block is reported, not hidden
            out.append(("ERROR", "framed-area check (C06): level %d not evaluable: %s" % (k, ex)))
            continue
        if fa < 0.9 * float(decl) - 1e-6:
            out.append(("ERROR", "level %d: framed %s area %.1f m2 < 0.9 x declared plan area %.1f m2 (%s) -- part of the plate "
                                 "is not framed by the model, so its gravity load and seismic weight are dropped; frame it (gold "
                                 "present / multi-level columns / free_nodes) or declare the voids" %
                        (k, "roof" if k == len(H) else "floor", fa, float(decl), src)))
    return out

