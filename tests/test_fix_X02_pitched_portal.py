"""X02 (CFS-A-15 pitch, HR-E-05): the JSON-declared frame builder (india_cfs_frame_build, gold.roof_planes in metres) and
the regular-grid path of hr_vendor_runner (spec.roof_planes) build a true-slope pitched portal through the vendored HR
engine: apex nodes, sloped rafters, no tie across the span, roof load per plan area, roof dead load in W.

The HR engine part (roof_geometry.py) arrives with the next re-sync of steel_engine/hr_vendor; until then these tests
skip."""
from __future__ import annotations
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
sys.path.insert(0, os.path.join(ROOT, "steel_engine", "hr_vendor"))

pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "steel_engine", "hr_vendor", "roof_geometry.py")),
                                reason="vendored HR engine without roof_geometry (X02) -- re-sync hr_vendor")

COL, RAF, PUR = "WPB600X300X211.92", "NPB600X220X154.47", "NPB300X150X36.53"
PLANE_M = {"axis": "X", "eave_coords_m": [0.0, 24.0], "ridge_coord_m": 12.0, "eave_z_m": 8.0, "ridge_z_m": 11.0,
           "rafter_sec": RAF, "ridge_sec": PUR}


def _spec(gold=None, **kw):
    spec = {"name": "t_portal", "system": "SMRF", "R": 5.0, "Z": 0.24, "I": 1.0, "zone": "IV", "soil": "II", "NX": 1,
            "NY": 2, "bay_x_m": 24.0, "bay_y_m": 7.5, "heights_m": [8.0], "D_floor": 0.0, "D_roof": 0.35, "L_floor": 0.0,
            "Lr": 0.75, "clad": 0.0, "snow": 1.2905, "col": COL, "beam": PUR, "brace": None, "braced_bays": [],
            "moment_lines": [["X", 0], ["X", 1], ["X", 2]], "base": "fixed", "default_strong": "X",
            "occupancy": {"use": "storage", "persons": 5}, "load_plan": {"jurisdiction": "india", "retrieval": []}}
    if gold is not None:
        spec.update(gold=gold, custom_build_module="india_cfs_frame_build")
    spec.update(kw)
    return spec


def _check_portal(cfg):
    import engine3d as E
    import static_model as SM
    import openseespy.opensees as ops
    info = E.build(cfg, "Linear")
    raf = [e for e in info["ele"] if e[1] == "beam" and abs(ops.nodeCoord(e[3])[2] - ops.nodeCoord(e[4])[2]) > 1.0]
    assert len(raf) == 6                                                  # 3 frames x 2 sloped rafters
    assert max(ops.nodeCoord(n)[2] for e in raf for n in e[3:]) == pytest.approx(11000.0)
    assert E.floor_beam_gaps(cfg) == []
    assert not [f for f in SM.pitched_roof_findings(cfg, info) if f[0] == "ERROR"]
    assert E.seismic_weight_components(cfg, 1)["dead"] == pytest.approx(0.35 * 24.0 * 15.0 * 1000.0, rel=1e-9)
    ops.wipe()
    m = SM.build_static(cfg, "Linear", 6)
    ops.timeSeries("Linear", 1); ops.pattern("Plain", 1, 1)
    lev = SM.apply_gravity_state(cfg, m, 1.5, 0.0, 0.0, fS=1.5, self_weight=False)
    assert lev[1] == pytest.approx(1.5 * (0.35 + 1.2905) * 24.0 * 15.0 * 1000.0, rel=0.01)
    assert SM._solve_newton() == 0
    # eaves spread freely (no diaphragm tie across the span) and symmetrically
    ul, ur = ops.nodeDisp(E.ntag(0, 1, 1), 1), ops.nodeDisp(E.ntag(1, 1, 1), 1)
    assert ul < -1.0 and ur == pytest.approx(-ul, rel=1e-6)


def test_gold_frame_build_pitched_portal():
    import hr_vendor_runner as RN
    gold = {"roof_planes": [dict(PLANE_M)], "moment_lines": [["X", 0], ["X", 1], ["X", 2]], "gravity_base": "fixed",
            "col_sec": {"lateral": {"1": COL}, "gravity": {"1": COL}},
            "beam_sec": {"roof_X": RAF, "roof_Y": PUR}}
    cfg, esm = RN.build_cfg(_spec(gold))
    assert cfg["roof_planes"][0]["eave_coords_mm"] == [0.0, 24000.0] and cfg["roof_planes"][0]["ridge_z_mm"] == 11000.0
    cfg["self_weight"] = False
    _check_portal(cfg)


def test_regular_runner_path_pitched_portal():
    import hr_vendor_runner as RN
    cfg, esm = RN.build_cfg(_spec(None, roof_planes=[dict(PLANE_M)]))
    assert esm["seismic_summary"]["W_kN"] > 0.35 * 24.0 * 15.0                   # roof dead load by plan area is in W
    cfg["self_weight"] = False
    _check_portal(cfg)


def test_roof_planes_mm_conversion():
    import india_cfs_frame_build as FB
    out = FB.roof_planes_mm([dict(PLANE_M, lines=[0, 2]), {"axis": "Y", "eave_coords_mm": [0, 6000]}])
    assert out[0]["eave_coords_mm"] == [0.0, 24000.0] and out[0]["ridge_coord_mm"] == 12000.0
    assert out[0]["eave_z_mm"] == 8000.0 and out[0]["lines"] == [0, 2] and "eave_z_m" not in out[0]
    assert out[1] == {"axis": "Y", "eave_coords_mm": [0, 6000]}
