"""C03 (CFS-A-03, CFS-D-12, CFS-B-13, CFS-C-17, E5 residual): diaphragm demands -- one braced line (v = F/B, cantilever
chord), per-storey line counts and capacities, collector rows at declared re-entrant lines."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_lateral as L   # noqa: E402


def _hr_rows(kind, level, d, lines_kN, extent_m):
    """H3: the HR collectors.rows the demand now comes from -- {line coordinate m: R_line kN}."""
    return [{"dir": d, "level": level, "line": float(p) * 1000.0, "beam": 1 + n, "role": "collector", "N_N": 10.0,
             "q_N_per_mm": round(R / extent_m, 4), "R_line_N": R * 1000.0, "kind": kind}
            for n, (p, R) in enumerate(lines_kN.items())]


def _root(tmp_path, nst=1, F=24000.0, rows=None):
    root = tmp_path / "lat"; root.mkdir()
    sf = {"EQ_X": {str(k): [F, 0.0, 0.0] for k in range(1, nst + 1)}, "EQ_Y": {str(k): [0.0, F, 0.0] for k in range(1, nst + 1)}}
    json.dump({"story_forces": sf}, open(root / "load_plan.json", "w"))
    if rows is None:        # H3: default = both directions on their two edge lines, equal shares
        rows = []
        for k in range(1, nst + 1):
            rows += _hr_rows("EQ", k, "X", {0: F / 2e3, 8: F / 2e3}, 12.0) + _hr_rows("EQ", k, "Y", {0: F / 2e3, 12: F / 2e3}, 8.0)
    return {"root": str(root), "collectors": {"rows": rows}}


def test_single_central_line(tmp_path):
    """12 x 8 plate, F = 24 kN along X on ONE central line (j = 1 of NY = 2): the analysed reaction of that line is
    the whole 24 kN -> v = 24/12 = 2.0 kN/m (not 1.0); chord from the reaction: M = (F/L) s^2/2 up to the line at
    s = L/2 -> F L/8 = 24 kN m -> 24/12 = 2.0 kN (H3: the demand is the analysed line reaction / deck length)."""
    cfg = {"geometry": {"plan_x_m": 12.0, "plan_y_m": 8.0, "heights_m": [3.0]},
           "lateral_frame": {"NX": 2, "NY": 2, "bay_x_m": 6.0, "bay_y_m": 4.0, "braced_bays": [["X", 0, 1], ["Y", 0, 0], ["Y", 2, 0]]},
           "diaphragm_capacity": {"v_allow_kN_per_m": 6.0}}
    rows = _hr_rows("EQ", 1, "X", {4: 24.0}, 12.0) + _hr_rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0)
    rx = [r for r in L.diaphragm_demands(cfg, _root(tmp_path, rows=rows)) if r["dir"] == "X"][0]
    assert rx["n_lines"] == 1 and rx["v_unit_kN_per_m"] == pytest.approx(2.0)
    assert rx["chord_force_kN"] == pytest.approx(2.0, rel=1e-3) and rx["ok"] is True


def test_single_edge_line_cantilever(tmp_path):
    cfg = {"geometry": {"plan_x_m": 12.0, "plan_y_m": 8.0, "heights_m": [3.0]},
           "lateral_frame": {"NX": 2, "NY": 2, "bay_x_m": 6.0, "bay_y_m": 4.0, "braced_bays": [["X", 0, 0], ["Y", 0, 0], ["Y", 2, 0]]},
           "diaphragm_capacity": {"v_allow_kN_per_m": 6.0}}
    rows = _hr_rows("EQ", 1, "X", {0: 24.0}, 12.0) + _hr_rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0)
    rx = [r for r in L.diaphragm_demands(cfg, _root(tmp_path, rows=rows)) if r["dir"] == "X"][0]
    assert rx["n_lines"] == 1 and rx["span_m"] == pytest.approx(8.0)
    assert rx["chord_force_kN"] == pytest.approx((24.0 / 8.0) * 64.0 / 2.0 / 12.0)      # F L / 2 / B = 8.0 kN


def test_per_storey_lines_and_capacity(tmp_path):
    cfg = {"geometry": {"plan_x_m": 12.0, "plan_y_m": 8.0, "heights_m": [3.0, 3.0],
                        "diaphragm_lines_X": {"1": 3, "2": 1}},
           "lateral_frame": {"NX": 2, "NY": 2, "bay_x_m": 6.0, "bay_y_m": 4.0},
           "diaphragm_capacity": {"v_allow_kN_per_m": {"1": 6.0, "2": {"value": 1.5, "cite": "roof deck test R-2 (EOR)"}}}}
    rows = (_hr_rows("EQ", 1, "X", {0: 8.0, 4: 8.0, 8: 8.0}, 12.0) + _hr_rows("EQ", 2, "X", {4: 24.0}, 12.0)
            + _hr_rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0) + _hr_rows("EQ", 2, "Y", {0: 12.0, 12: 12.0}, 8.0))
    rows_ = [r for r in L.diaphragm_demands(cfg, _root(tmp_path, nst=2, rows=rows)) if r["dir"] == "X"]
    r1, r2 = rows_
    # storey 1: 8 / 8 / 8 kN + the 7.8.2 torsion on the outer lines, Mt = 24 x 0.05 x 8 = 9.6, J = 2 x 8 x 16 = 256,
    # V_t = 9.6 x 8 x 4 / 256 = 1.2 -> 9.2 / 12; storey 2: one X line -> the torque goes to the Y lines
    assert r1["n_lines"] == 3 and r1["v_unit_kN_per_m"] == pytest.approx(9.2 / 12.0) and r1["limit"] == 6.0
    assert r2["n_lines"] == 1 and r2["v_unit_kN_per_m"] == pytest.approx(2.0)
    assert r2["limit"] == 1.5 and r2["ok"] is False and r2["capacity_cite"].startswith("roof deck")


def test_reentrant_collector(tmp_path):
    cfg = {"geometry": {"plan_x_m": 12.0, "plan_y_m": 8.0, "heights_m": [3.0],
                        "reentrant_lines_X": [{"line": "y = 4 m", "B_short_m": 6.0},
                                              {"line": "y = 6 m", "B_short_m": 9.0, "capacity_kN": 20.0, "cite": "HR strut EOR"}]},
           "lateral_frame": {"NX": 2, "NY": 2, "bay_x_m": 6.0, "bay_y_m": 4.0},
           "diaphragm_capacity": {"v_allow_kN_per_m": 6.0}}
    col = [r for r in L.diaphragm_demands(cfg, _root(tmp_path)) if r.get("kind") == "collector"]
    assert len(col) == 2
    assert col[0]["F_collector_kN"] == pytest.approx(24.0 * (1 - 6.0 / 12.0)) and col[0]["ok"] is None
    assert col[1]["F_collector_kN"] == pytest.approx(6.0) and col[1]["ok"] is True
    import india_cfs_gates as G
    assert any(x.startswith("collector storey 1 X") for x in G.diaphragm_issues({"diaphragm": col}))
