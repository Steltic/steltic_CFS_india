"""H3 (audit round 5, CFS Ex7 / Ex9 / Ex14): the CFS diaphragm unit shear per frame line = the ANALYSED line reaction of
the HR sub-run (collectors.rows) / the deck length actually present along that line at that level -- enveloped over the
rigid load path and the flexible-diaphragm (X01 / flexible label) line shears, EQ and W -- never F / (n B).  Fail closed
when the reactions are missing; a declared geometry.diaphragm_line_length_m only where the model is ambiguous (WARN)."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_env  # noqa: E402,F401
import india_cfs_gates as G    # noqa: E402
import india_cfs_lateral as L  # noqa: E402


def rows(kind, level, d, lines_kN, extent_m, role="collector", **extra):
    """HR collectors.rows for one level / direction: {line coordinate m: R_line kN}; q = R / line length (N/mm)."""
    return [dict({"dir": d, "level": level, "line": float(p) * 1000.0, "beam": 1000 + n, "role": role, "N_N": 100.0,
                  "q_N_per_mm": round(R * 1000.0 / (extent_m * 1000.0), 4), "R_line_N": R * 1000.0, "kind": kind,
                  "cite": "Diaphragm load path by equilibrium of the analysed model (IS 1893 7.6.4 rigid diaphragm)"},
                 **extra) for n, (p, R) in enumerate(lines_kN.items())]


def lateral(tmp_path, sf, hr_rows, **kw):
    root = tmp_path / "lat"
    root.mkdir(exist_ok=True)
    json.dump({"story_forces": sf}, open(root / "load_plan.json", "w"))
    return dict({"root": str(root), "collectors": {"rows": hr_rows, "error": None}}, **kw)


def plate(**lf):
    """12 m x 8 m plate on a 2 x 2 grid of 6 m x 4 m bays, one storey."""
    return {"geometry": {"plan_x_m": 12.0, "plan_y_m": 8.0, "heights_m": [3.0]},
            "lateral_frame": dict({"NX": 2, "NY": 2, "bay_x_m": 6.0, "bay_y_m": 4.0}, **lf),
            "diaphragm_capacity": {"v_allow_kN_per_m": 1.2, "basis": "test", "cite": "deck test (EOR)"}}


SF = {"EQ_X": {"1": [24000.0, 0.0, 0.0]}, "EQ_Y": {"1": [0.0, 24000.0, 0.0]},
      "W_X": {"1": [12000.0, 0.0, 0.0]}, "W_Y": {"1": [0.0, 6000.0, 0.0]}}


def _row(out, d, k=1):
    return [r for r in out if r.get("kind") != "collector" and r["dir"] == d and r["storey"] == k][0]


def test_two_lines_unequal_stiffness_hand_model(tmp_path):
    """F = 24 kN along X; the analysed rigid diaphragm gives the stiffer line y = 0 R = 18 kN and y = 8 R = 6 kN
    (equal shares would be 12 / 12).  Deck along each X line = 12 m -> v = 18 / 12 = 1.5 kN/m (F / (n B) = 1.0),
    D/C 1.5 / 1.2 = 1.25 FAIL.  Chord from the same reactions: w = 24 / 8 = 3 kN/m, M(s) = 1.5 s^2 - 18 s,
    max |M| = 54 kN m at s = 6 -> 54 / 12 = 4.5 kN.  W (12 kN: 9 / 3) does not govern; Y: 12 + 12 on 8 m -> 1.5."""
    hr = (rows("EQ", 1, "X", {0: 18.0, 8: 6.0}, 12.0) + rows("W", 1, "X", {0: 9.0, 8: 3.0}, 12.0)
          + rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0) + rows("W", 1, "Y", {0: 3.0, 12: 3.0}, 8.0))
    out = L.diaphragm_demands(plate(), lateral(tmp_path, SF, hr))
    rx = _row(out, "X")
    assert rx["demand_evaluated"] is True and rx["n_lines"] == 2
    assert rx["v_unit_kN_per_m"] == pytest.approx(1.5)
    assert rx["governing_case"] == "EQ rigid" and rx["governing_line_m"] == 0.0 and rx["governing_deck_length_m"] == 12.0
    assert rx["dc"] == pytest.approx(1.25) and rx["ok"] is False
    assert rx["superseded_equal_share"]["v_kN_per_m"] == pytest.approx(1.0)
    assert rx["chord_force_kN"] == pytest.approx(4.5, rel=1e-3)
    ry = _row(out, "Y")
    assert ry["v_unit_kN_per_m"] == pytest.approx(1.5) and ry["governing_deck_length_m"] == 8.0
    assert any("diaphragm storey 1 X: D/C 1.25" in m for m in G.diaphragm_issues({"diaphragm": out}))


def _lplan_cfg():
    # L-plan on a 3 x 3 grid of 5 m bays: the 2 x 2 bay corner (nodes i, j >= 2) removed.  Deck cells (0,0) (1,0) (2,0)
    # (0,1) (0,2): the X line y = 15 m has deck only over x = 0-5 (5 m), not the 15 m bounding box.
    L2 = [[i, j] for i in range(4) for j in range(4) if not (i >= 2 and j >= 2)]
    return {"geometry": {"plan_x_m": 15.0, "plan_y_m": 15.0, "heights_m": [3.0]},
            "lateral_frame": {"NX": 3, "NY": 3, "bay_x_m": 5.0, "bay_y_m": 5.0, "custom_build_module": "india_cfs_frame_build",
                              "gold": {"present": {"default": L2}}},
            "diaphragm_capacity": {"v_allow_kN_per_m": 2.0, "cite": "deck test (EOR)"}}, L2


def test_lplan_deck_length_along_the_line(tmp_path):
    """L-plan: R(y = 15) = 8 kN on 5 m of deck -> 1.6 kN/m (8 / 15 over the bounding box would be 0.53);
    y = 5: 6 kN / 15 m; y = 0: 10 kN / 15 m.  Y line x = 15 (the bar end): 7 kN on 5 m -> 1.4 kN/m."""
    cfg, L2 = _lplan_cfg()
    sf = {"EQ_X": {"1": [24000.0, 0, 0]}, "EQ_Y": {"1": [0, 24000.0, 0]}}
    hr = (rows("EQ", 1, "X", {0: 10.0, 5: 6.0}, 15.0) + rows("EQ", 1, "X", {15: 8.0}, 5.0)
          + rows("EQ", 1, "Y", {0: 17.0}, 15.0) + rows("EQ", 1, "Y", {15: 7.0}, 5.0))
    out = L.diaphragm_demands(cfg, lateral(tmp_path, sf, hr))
    rx = _row(out, "X")
    by = {x["line_m"]: x for x in rx["lines"]}
    assert by[15.0]["deck_length_m"] == pytest.approx(5.0) and by[5.0]["deck_length_m"] == pytest.approx(15.0)
    assert rx["v_unit_kN_per_m"] == pytest.approx(1.6) and rx["governing_line_m"] == 15.0
    assert rx["dc"] == pytest.approx(0.8)
    ry = _row(out, "Y")
    assert ry["v_unit_kN_per_m"] == pytest.approx(1.4) and ry["governing_line_m"] == 15.0      # 7 / 5 > 17 / 15
    assert {x["line_m"]: x["deck_length_m"] for x in ry["lines"]}[15.0] == pytest.approx(5.0)
    # the same footprint read back from the HR sub-run model (design/cfg_snapshot.json) gives the same deck lengths
    d_ = tmp_path / "lat" / "design"; d_.mkdir()
    json.dump({"NX": 3, "NY": 3, "units": "N-mm", "xcoords": [0, 5000, 10000, 15000], "ycoords": [0, 5000, 10000, 15000],
               "present": {"1": L2}}, open(d_ / "cfg_snapshot.json", "w"))
    cfg2 = dict(cfg, lateral_frame={"NX": 3, "NY": 3, "bay_x_m": 5.0, "bay_y_m": 5.0, "custom_build_module": "job_builder.py"})
    rx2 = _row(L.diaphragm_demands(cfg2, lateral(tmp_path, sf, hr)), "X")
    assert rx2["v_unit_kN_per_m"] == pytest.approx(1.6) and "cfg_snapshot" in rx2["source"]


def test_fail_closed_without_line_reactions(tmp_path):
    """No collectors.rows (or an HR collector error): the row is NOT evaluated -- no equal-share value is checked."""
    for lat in (lateral(tmp_path, SF, []), dict(lateral(tmp_path, SF, []), collectors={"rows": [], "error": "boom"}),
                {"root": lateral(tmp_path, SF, [])["root"]}):
        out = L.diaphragm_demands(plate(), lat)
        rx = _row(out, "X")
        assert rx["demand_evaluated"] is False and rx["v_unit_kN_per_m"] is None
        assert rx["ok"] is None and rx["dc"] is None and rx["found"] is False
        assert any(m.startswith("diaphragm storey 1 X: demand not evaluated") for m in G.diaphragm_issues({"diaphragm": out}))
    # reactions present for EQ but not for W (F_W > 0): still fail closed
    rx = _row(L.diaphragm_demands(plate(), lateral(tmp_path, SF, rows("EQ", 1, "X", {0: 12.0, 8: 12.0}, 12.0))), "X")
    assert rx["demand_evaluated"] is False and "no analysed W line reactions" in rx["note"]


def test_declared_line_length_only_where_ambiguous(tmp_path):
    """A reaction on an off-grid line (y = 6 m) has no model deck length: not evaluated until declared; the declared
    6 m is used with a WARN (v = 6 / 6 = 1.0).  A declared length longer than the model's deck is not used."""
    hr = (rows("EQ", 1, "X", {0: 18.0, 6: 6.0}, 12.0) + rows("W", 1, "X", {0: 6.0, 6: 6.0}, 12.0)
          + rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0) + rows("W", 1, "Y", {0: 3.0, 12: 3.0}, 8.0))
    rx = _row(L.diaphragm_demands(plate(), lateral(tmp_path, SF, hr)), "X")
    assert rx["demand_evaluated"] is False and "diaphragm_line_length_m" in rx["note"]
    cfg = plate()
    cfg["geometry"]["diaphragm_line_length_m"] = {"1": {"X@6": 6.0, "X@0": 24.0}}
    out = L.diaphragm_demands(cfg, lateral(tmp_path, SF, hr))
    rx = _row(out, "X")
    by = {x["line_m"]: x for x in rx["lines"]}
    assert rx["demand_evaluated"] is True
    assert by[6.0]["deck_length_m"] == 6.0 and "declared" in by[6.0]["deck_length_basis"]
    assert by[0.0]["deck_length_m"] == 12.0                     # 24 m > the model's 12 m: not used
    assert rx["v_unit_kN_per_m"] == pytest.approx(1.5)
    assert any("DECLARED" in w for w in rx["warnings"]) and any("not used" in w for w in rx["warnings"])
    st = G.design_status({"load_plan": {}}, {"diaphragm": out})
    assert any("DECLARED" in w for w in st["warnings"])


def test_split_level_grade_line_is_not_a_deck_line(tmp_path):
    """Split level: the level-1 plate is the south half (j <= 1); the north line y = 8 m is a row of stepped (grade)
    bases -- its reaction goes to the grade, not through the deck: listed apart, not checked.  The Y lines run on
    the level-1 deck for 4 m only, and the analysed line (8 m, grade nodes included) is flagged an upper bound."""
    south = [[i, j] for i in range(3) for j in range(2)]
    cfg = plate(custom_build_module="india_cfs_frame_build",
                gold={"present": {"1": south, "0": [[i, j] for i in range(3) for j in range(3)]},
                      "stepped_bases": {"1": [[i, 2] for i in range(3)]}})
    hr = (rows("EQ", 1, "X", {0: 20.0, 4: 30.0}, 12.0) + rows("EQ", 1, "X", {8: 26.0}, 12.0)
          + rows("W", 1, "X", {0: 6.0, 4: 6.0}, 12.0)
          + rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0) + rows("W", 1, "Y", {0: 3.0, 12: 3.0}, 8.0))
    rx = _row(L.diaphragm_demands(cfg, lateral(tmp_path, SF, hr)), "X")
    assert [x["line_m"] for x in rx["lines_outside_deck"]] == [8.0]
    assert rx["v_unit_kN_per_m"] == pytest.approx(30.0 / 12.0) and rx["governing_line_m"] == 4.0
    ry = _row(L.diaphragm_demands(cfg, lateral(tmp_path, SF, hr)), "Y")
    assert ry["v_unit_kN_per_m"] == pytest.approx(12.0 / 4.0)
    assert all(x.get("upper_bound") for x in ry["lines"])


def test_x01_flexible_envelope(tmp_path):
    """X01 ran (seismic_analysis.flexible_diaphragm_run): the flexible-diaphragm line shears enter the envelope.
    Three X lines y = 0 / 4 / 8, rigid R = 10 / 4 / 10 kN; flexible (deck area, simple spans): 6 / 12 / 6 kN ->
    the middle line governs at 12 / 12 = 1.0 kN/m (rigid alone 10 / 12 = 0.83)."""
    hr = (rows("EQ", 1, "X", {0: 10.0, 4: 4.0, 8: 10.0}, 12.0) + rows("W", 1, "X", {0: 4.0, 4: 4.0, 8: 4.0}, 12.0)
          + rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0) + rows("W", 1, "Y", {0: 3.0, 12: 3.0}, 8.0))
    cfg = plate(braced_bays=[["X", 0, 0], ["X", 0, 1], ["X", 0, 2], ["Y", 0, 0], ["Y", 2, 0]])
    rx = _row(L.diaphragm_demands(cfg, lateral(tmp_path, SF, hr)), "X")
    assert rx["v_unit_kN_per_m"] == pytest.approx(10.0 / 12.0)
    rx = _row(L.diaphragm_demands(cfg, lateral(tmp_path, SF, hr, seismic_analysis={"flexible_diaphragm_run": True})), "X")
    by = {x["line_m"]: x for x in rx["lines"]}
    assert by[4.0]["R_kN"]["EQ flexible tributary"] == pytest.approx(12.0)
    assert by[0.0]["R_kN"]["EQ flexible tributary"] == pytest.approx(6.0)
    assert rx["v_unit_kN_per_m"] == pytest.approx(1.0) and rx["governing_case"] == "EQ flexible tributary"
    # a flexible-labelled level takes the flexible line shears for W as well (tributary width, uniform)
    cfg["lateral_frame"]["diaphragm"] = "flexible"
    rx = _row(L.diaphragm_demands(cfg, lateral(tmp_path, SF, hr)), "X")
    assert {x["line_m"]: x for x in rx["lines"]}[4.0]["R_kN"]["W flexible tributary"] == pytest.approx(6.0)


def test_collector_uses_the_analysed_axial(tmp_path):
    """Re-entrant collector: max(F (1 - B_short / B), the analysed collector axial on that line)."""
    hr = rows("EQ", 1, "X", {0: 12.0, 4: 6.0, 8: 6.0}, 12.0) + rows("W", 1, "X", {0: 6.0, 8: 6.0}, 12.0)
    hr[1]["N_N"] = 15000.0                                    # analysed drag force on the y = 4 m line: 15 kN
    cfg = plate()
    cfg["geometry"]["reentrant_lines_X"] = [{"line": "y = 4 m", "B_short_m": 6.0}]
    col = [r for r in L.diaphragm_demands(cfg, lateral(tmp_path, SF, hr)) if r.get("kind") == "collector"][0]
    assert col["F_collector_formula_kN"] == pytest.approx(12.0) and col["N_collector_analysed_kN"] == pytest.approx(15.0)
    assert col["F_collector_kN"] == pytest.approx(15.0)
