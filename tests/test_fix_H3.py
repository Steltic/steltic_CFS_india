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
    (equal shares would be 12 / 12).  7.8.2: Mt = 24 x 0.05 x 8 = 9.6 kN m; k ~ R: CR at s = 2 m, J = 18 x 4 + 6 x 36
    = 288 -> V_t = 9.6 x 18 x 2 / 288 = 1.2 kN on y = 0.  Deck along each X line = 12 m -> v = (18 + 1.2) / 12 = 1.6 kN/m
    (F / (n B) = 1.0), D/C 1.6 / 1.2 = 1.33 FAIL.  Chord from the same reactions, adverse torsion variant R = 19.2 / 4.8:
    w = 3 kN/m, M(s) = 1.5 s^2 - 19.2 s, max |M| = 61.44 kN m at s = 6.4 -> 61.44 / 12 = 5.12 kN.  W (12 kN: 9 / 3) does
    not govern; Y: 12 + 12 on 8 m, Mt = 24 x 0.05 x 12 = 14.4 -> V_t = 14.4 / 12 = 1.2 -> 13.2 / 8 = 1.65."""
    hr = (rows("EQ", 1, "X", {0: 18.0, 8: 6.0}, 12.0) + rows("W", 1, "X", {0: 9.0, 8: 3.0}, 12.0)
          + rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0) + rows("W", 1, "Y", {0: 3.0, 12: 3.0}, 8.0))
    out = L.diaphragm_demands(plate(), lateral(tmp_path, SF, hr))
    rx = _row(out, "X")
    assert rx["demand_evaluated"] is True and rx["n_lines"] == 2
    assert rx["v_unit_kN_per_m"] == pytest.approx(1.6)
    assert rx["governing_case"] == "EQ rigid +7.8.2" and rx["governing_line_m"] == 0.0 and rx["governing_deck_length_m"] == 12.0
    assert {x["line_m"]: x for x in rx["lines"]}[0.0]["R_kN"]["EQ rigid"] == pytest.approx(18.0)
    assert rx["dc"] == pytest.approx(1.6 / 1.2) and rx["ok"] is False
    assert rx["superseded_equal_share"]["v_kN_per_m"] == pytest.approx(1.0)
    assert rx["chord_force_kN"] == pytest.approx(5.12, rel=1e-3)
    ry = _row(out, "Y")
    assert ry["v_unit_kN_per_m"] == pytest.approx(1.65) and ry["governing_deck_length_m"] == 8.0
    assert any("diaphragm storey 1 X: D/C 1.33" in m for m in G.diaphragm_issues({"diaphragm": out}))


def _lplan_cfg():
    # L-plan on a 3 x 3 grid of 5 m bays: the 2 x 2 bay corner (nodes i, j >= 2) removed.  Deck cells (0,0) (1,0) (2,0)
    # (0,1) (0,2): the X line y = 15 m has deck only over x = 0-5 (5 m), not the 15 m bounding box.
    L2 = [[i, j] for i in range(4) for j in range(4) if not (i >= 2 and j >= 2)]
    return {"geometry": {"plan_x_m": 15.0, "plan_y_m": 15.0, "heights_m": [3.0]},
            "lateral_frame": {"NX": 3, "NY": 3, "bay_x_m": 5.0, "bay_y_m": 5.0, "custom_build_module": "india_cfs_frame_build",
                              "gold": {"present": {"default": L2}}},
            "diaphragm_capacity": {"v_allow_kN_per_m": 2.0, "cite": "deck test (EOR)"}}, L2


def test_lplan_deck_length_along_the_line(tmp_path):
    """L-plan: R(y = 15) = 8 kN on 5 m of deck (8 / 15 over the bounding box would be 0.53); y = 5: 6 kN / 15 m;
    y = 0: 10 kN / 15 m.  7.8.2: Mt = 24 x 0.05 x 15 = 18 kN m, CR at y = (6 x 5 + 8 x 15) / 24 = 6.25 m,
    J = 10 x 6.25^2 + 6 x 1.25^2 + 8 x 8.75^2 = 1012.5 -> V_t(15) = 18 x 8 x 8.75 / 1012.5 = 1.2444 kN ->
    v = 9.2444 / 5 = 1.849 kN/m.  Y line x = 15 (the bar end): 7 kN on 5 m; CR x = 105 / 24 = 4.375 m,
    J = 17 x 4.375^2 + 7 x 10.625^2 = 1115.6 -> V_t = 18 x 7 x 10.625 / 1115.6 = 1.2 kN -> 8.2 / 5 = 1.64 kN/m."""
    cfg, L2 = _lplan_cfg()
    sf = {"EQ_X": {"1": [24000.0, 0, 0]}, "EQ_Y": {"1": [0, 24000.0, 0]}}
    hr = (rows("EQ", 1, "X", {0: 10.0, 5: 6.0}, 15.0) + rows("EQ", 1, "X", {15: 8.0}, 5.0)
          + rows("EQ", 1, "Y", {0: 17.0}, 15.0) + rows("EQ", 1, "Y", {15: 7.0}, 5.0))
    out = L.diaphragm_demands(cfg, lateral(tmp_path, sf, hr))
    rx = _row(out, "X")
    by = {x["line_m"]: x for x in rx["lines"]}
    assert by[15.0]["deck_length_m"] == pytest.approx(5.0) and by[5.0]["deck_length_m"] == pytest.approx(15.0)
    assert rx["v_unit_kN_per_m"] == pytest.approx(9.244444 / 5.0, rel=1e-5) and rx["governing_line_m"] == 15.0
    assert rx["dc"] == pytest.approx(9.244444 / 10.0, rel=1e-5)
    ry = _row(out, "Y")
    assert ry["v_unit_kN_per_m"] == pytest.approx(8.2 / 5.0, rel=1e-4) and ry["governing_line_m"] == 15.0
    assert {x["line_m"]: x["deck_length_m"] for x in ry["lines"]}[15.0] == pytest.approx(5.0)
    # the same footprint read back from the HR sub-run model (design/cfg_snapshot.json) gives the same deck lengths
    d_ = tmp_path / "lat" / "design"; d_.mkdir()
    json.dump({"NX": 3, "NY": 3, "units": "N-mm", "xcoords": [0, 5000, 10000, 15000], "ycoords": [0, 5000, 10000, 15000],
               "present": {"1": L2}}, open(d_ / "cfg_snapshot.json", "w"))
    cfg2 = dict(cfg, lateral_frame={"NX": 3, "NY": 3, "bay_x_m": 5.0, "bay_y_m": 5.0, "custom_build_module": "job_builder.py"})
    rx2 = _row(L.diaphragm_demands(cfg2, lateral(tmp_path, sf, hr)), "X")
    assert rx2["v_unit_kN_per_m"] == pytest.approx(9.244444 / 5.0, rel=1e-5) and "cfg_snapshot" in rx2["source"]


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
    6 m is used with a WARN.  A declared length longer than the model's deck is not used.  7.8.2: Mt = 9.6 kN m,
    CR y = 1.5 m, J = 18 x 2.25 + 6 x 20.25 = 162 -> V_t = 1.6 kN on both lines: y = 0 (18 + 1.6) / 12 = 1.633 governs,
    y = 6 (6 + 1.6) / 6 = 1.267."""
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
    assert rx["v_unit_kN_per_m"] == pytest.approx(19.6 / 12.0)
    assert by[6.0]["v_kN_per_m"] == pytest.approx(7.6 / 6.0)
    assert any("DECLARED" in w for w in rx["warnings"]) and any("not used" in w for w in rx["warnings"])
    st = G.design_status({"load_plan": {}}, {"diaphragm": out})
    assert any("DECLARED" in w for w in st["warnings"])


def test_split_level_grade_line_is_not_a_deck_line(tmp_path):
    """Split level: the level-1 plate is the south half (j <= 1); the north line y = 8 m is a row of stepped (grade)
    bases -- its reaction goes to the grade, not through the deck: listed apart, not checked.  The Y lines run on
    the level-1 deck for 4 m only, and the analysed line (8 m, grade nodes included) is flagged an upper bound.
    7.8.2 on the deck lines only (b = 4 m): Mt = 4.8 kN m, CR y = 2.4 m, J = 20 x 2.4^2 + 30 x 1.6^2 = 192 ->
    V_t(4) = 4.8 x 30 x 1.6 / 192 = 1.2 -> (30 + 1.2) / 12 = 2.6.  Y: Mt = 14.4, V_t = 1.2 -> 13.2 / 4 = 3.3."""
    south = [[i, j] for i in range(3) for j in range(2)]
    cfg = plate(custom_build_module="india_cfs_frame_build",
                gold={"present": {"1": south, "0": [[i, j] for i in range(3) for j in range(3)]},
                      "stepped_bases": {"1": [[i, 2] for i in range(3)]}})
    hr = (rows("EQ", 1, "X", {0: 20.0, 4: 30.0}, 12.0) + rows("EQ", 1, "X", {8: 26.0}, 12.0)
          + rows("W", 1, "X", {0: 6.0, 4: 6.0}, 12.0)
          + rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0) + rows("W", 1, "Y", {0: 3.0, 12: 3.0}, 8.0))
    rx = _row(L.diaphragm_demands(cfg, lateral(tmp_path, SF, hr)), "X")
    assert [x["line_m"] for x in rx["lines_outside_deck"]] == [8.0]
    assert rx["v_unit_kN_per_m"] == pytest.approx(31.2 / 12.0) and rx["governing_line_m"] == 4.0
    ry = _row(L.diaphragm_demands(cfg, lateral(tmp_path, SF, hr)), "Y")
    assert ry["v_unit_kN_per_m"] == pytest.approx(13.2 / 4.0)
    assert all(x.get("upper_bound") for x in ry["lines"])


def test_x01_flexible_envelope(tmp_path):
    """X01 ran (seismic_analysis.flexible_diaphragm_run): the flexible-diaphragm line shears enter the envelope.
    Three X lines y = 0 / 4 / 8, rigid R = 10 / 4 / 10 kN; flexible (deck area, simple spans): 6 / 12 / 6 kN ->
    the middle line governs at 12 / 12 = 1.0 kN/m (rigid alone with 7.8.2: V_t = 9.6 x 10 x 4 / 320 = 1.2 ->
    11.2 / 12 = 0.93; the flexible half takes no torsion)."""
    hr = (rows("EQ", 1, "X", {0: 10.0, 4: 4.0, 8: 10.0}, 12.0) + rows("W", 1, "X", {0: 4.0, 4: 4.0, 8: 4.0}, 12.0)
          + rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0) + rows("W", 1, "Y", {0: 3.0, 12: 3.0}, 8.0))
    cfg = plate(braced_bays=[["X", 0, 0], ["X", 0, 1], ["X", 0, 2], ["Y", 0, 0], ["Y", 2, 0]])
    rx = _row(L.diaphragm_demands(cfg, lateral(tmp_path, SF, hr)), "X")
    assert rx["v_unit_kN_per_m"] == pytest.approx(11.2 / 12.0)
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


def test_accidental_torsion_782_hand_values(tmp_path):
    """IS 1893 7.8.2 accidental eccentricity on the rigid reactions (separate commit after H3).
    (a) Two X lines y = 0 / 8 m, direct R = 12 / 12 kN, F = 24 kN, b = 8 m: Mt = 24 x 0.05 x 8 = 9.6 kN m, CR at 4 m,
        V_t = Mt k r / J = 9.6 x 12 x 4 / (2 x 12 x 16) = 1.2 kN (= Mt / 8) -> (12 + 1.2) / 12 = 1.1 kN/m.
    (b) One central X line (y = 4, R = 24 kN): it lies on the CR and takes no torque; the torque goes to the Y lines
        x = 0 / 12 (R 12 / 12 under EQ_Y): V_t = 9.6 x 12 x 6 / (2 x 12 x 36) = 0.8 kN (= Mt / 12) on each, a case of
        the Y rows (0.8 / 8 = 0.1 kN/m, below the Y lines' own 13.2 / 8).
    (c) The flexible (tributary) half takes no torsion; W takes none."""
    sf = {"EQ_X": {"1": [24000.0, 0, 0]}, "EQ_Y": {"1": [0, 24000.0, 0]}, "W_X": {"1": [12000.0, 0, 0]}}
    hr = (rows("EQ", 1, "X", {0: 12.0, 8: 12.0}, 12.0) + rows("W", 1, "X", {0: 6.0, 8: 6.0}, 12.0)
          + rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0))
    rx = _row(L.diaphragm_demands(plate(), lateral(tmp_path, sf, hr)), "X")
    t = rx["torsion_7_8_2"]
    assert t["Mt_kNm"] == pytest.approx(9.6) and t["centre_of_rigidity_m"] == pytest.approx(4.0)
    assert t["V_t_kN"] == {0.0: pytest.approx(1.2), 8.0: pytest.approx(1.2)}
    by = {x["line_m"]: x for x in rx["lines"]}
    assert by[0.0]["R_kN"]["EQ rigid +7.8.2"] == pytest.approx(13.2) and by[0.0]["R_kN"]["W rigid"] == pytest.approx(6.0)
    assert rx["v_unit_kN_per_m"] == pytest.approx(1.1) and rx["governing_case"] == "EQ rigid +7.8.2"
    # (b) single parallel line
    hr1 = rows("EQ", 1, "X", {4: 24.0}, 12.0) + rows("W", 1, "X", {4: 12.0}, 12.0) + rows("EQ", 1, "Y", {0: 12.0, 12: 12.0}, 8.0)
    out = L.diaphragm_demands(plate(), lateral(tmp_path, sf, hr1))
    rx, ry = _row(out, "X"), _row(out, "Y")
    assert rx["v_unit_kN_per_m"] == pytest.approx(2.0) and rx["torsion_7_8_2"]["V_t_kN"] == {}
    assert "normal to the force" in rx["torsion_7_8_2"]["resisted_by"]
    yl = {x["line_m"]: x for x in ry["lines"]}
    assert yl[0.0]["R_kN"]["EQ_X 7.8.2 torsion"] == pytest.approx(0.8) and yl[12.0]["R_kN"]["EQ_X 7.8.2 torsion"] == pytest.approx(0.8)
    assert ry["v_unit_kN_per_m"] == pytest.approx(13.2 / 8.0)
    # (c) flexible tributary half: no torsion added to it
    cfg = plate(braced_bays=[["X", 0, 0], ["X", 0, 2], ["Y", 0, 0], ["Y", 2, 0]])
    rx = _row(L.diaphragm_demands(cfg, lateral(tmp_path, sf, hr, seismic_analysis={"flexible_diaphragm_run": True})), "X")
    assert {x["line_m"]: x for x in rx["lines"]}[0.0]["R_kN"]["EQ flexible tributary"] == pytest.approx(12.0)
