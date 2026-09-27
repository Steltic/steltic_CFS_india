"""WP3.1 / WP3.5 / WP3.6 -- design basis, COMPLETE authority, lateral-system gate, IS 800 purposes, preflight."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_env  # noqa: E402,F401
import india_cfs_basis as B    # noqa: E402
import india_cfs_gates as G    # noqa: E402
import india_cfs_lateral as L  # noqa: E402
import preflight as PF         # noqa: E402


def _plan(**kw):
    p = {"jurisdiction": "india", "design_basis": "IS801_WSM", "lateral_frame_basis": "IS800_LSD",
         "combinations": "auto", "cfs_combinations": "auto", "retrieval": [{"stem": "IS_875_Part_3_2015", "found": True, "cite": "x"}]}
    p.update(kw)
    return p


def test_wsm_combinations_and_increase():
    rows = B.cfs_combinations(_plan(story_forces={"W_X": {"1": [1, 0, 0]}, "EQ_X": {"1": [1, 0, 0]}}))
    labels = {r["label"] for r in rows}
    assert {"DL", "DL+IL", "DL+1.0W_X", "DL+IL+1.0W_X", "0.9DL+1.0W_X", "DL+1.0EQ_X", "DL+IL+1.0EQ_X", "0.9DL-1.0EQ_X"} <= labels
    for r in rows:
        assert abs(r["fD"]) in (0.9, 1.0) and abs(r["fL"]) in (0.0, 1.0)
        assert r["allowable_increase"] == pytest.approx(4.0 / 3.0 if (r["fW"] or r["fE"]) else 1.0)
        assert r["eff_width_stress_factor"] == (0.75 if (r["fW"] or r["fE"]) else 1.0)


def test_validate_load_plan_refuses_mixed_bases():
    ok = {"load_plan": _plan()}
    assert not [m for s, m in B.validate_load_plan(ok) if s == "ERROR"]
    bad = {"load_plan": _plan(cfs_combinations=[{"label": "1.5DL+1.5LL", "fD": 1.5, "fL": 1.5, "fLr": 0.0}])}
    errs = [m for s, m in B.validate_load_plan(bad) if s == "ERROR"]
    assert any("partial factor" in m for m in errs)
    bad2 = {"load_plan": _plan(design_basis="AISI_LRFD")}
    assert any("IS801_WSM" in m for s, m in B.validate_load_plan(bad2) if s == "ERROR")
    bad3 = {"load_plan": _plan(combinations=[{"label": "DL+LL", "fD": 1.0, "fL": 1.0, "fLr": 0, "design_basis": "IS801_WSM"}])}
    assert any("mixed bases" in m for s, m in B.validate_load_plan(bad3) if s == "ERROR")


def test_capacity_basis_mixing_fails_consistency():
    pkg = {"cfs_members": [{"id": "m", "checks": [{"value": 1.0, "limit": 2.0, "capacity": 2.0, "capacity_basis": "IS800_LSD", "demand_level": "working"}]}]}
    issues = B.basis_issues(pkg)
    assert any("mixed bases" in x for x in issues)
    pkg2 = {"x": {"capacity": 2.0, "capacity_basis": "manufacturer_ASD", "allowable_increase": 1.333, "demand_level": "working"}}
    assert any("none otherwise" in x and "manufacturer_ASD" in x for x in B.basis_issues(pkg2))
    with pytest.raises(B.BasisError):
        B.capacity_slot(1.0, basis="AISI_LRFD")


def test_example_provenance_is_example_only():
    cfg = {"site": {"city": "X"}, "load_plan": _plan(retrieval=[{"stem": "IS_1893_Part_1_2016", "found": True,
                                                                 "cite": "EXAMPLE Acme CFS WSP Table B (not-for-construction)"}])}
    st = G.design_status(cfg, {"lateral_frame": {"status": {"status": "complete", "reasons": []}}, "cfs_members": []})
    assert st["status"] == "example_only"
    assert G.complete_allowed(cfg, {})[0] is False


def test_lateral_system_gate_by_zone():
    assert L.resolve_system("II")[:2] == ("OCBF", 4.0)
    assert L.resolve_system("III")[:2] == ("SCBF", 4.5)
    assert L.resolve_system("IV", "SCBF")[:2] == ("SCBF", 4.5)
    assert L.resolve_system("V")[:2] == ("EBF", 5.0)
    with pytest.raises(L.LateralSystemError):
        L.resolve_system("III", "OCBF")                        # Table 9 Note 1 (D4)
    with pytest.raises(L.LateralSystemError):
        L.resolve_system("V", "SCBF")                          # IS 18168 1.3 (L7)
    with pytest.raises(L.LateralSystemError):
        L.resolve_system("IV", "SMF", height_m=18.0)           # SMRF in Zone IV only < 15 m
    assert L.resolve_system("IV", "SMF", height_m=11.0)[:2] == ("SMF", 5.0)
    with pytest.raises(L.LateralSystemError):
        L.resolve_system("IV", "wsp_shearwall")                # no CFS SFRS (D3)


def test_is800_gate_purposes():
    assert G.gate_is800_query(doc="IS_800_2007", purpose="lateral_frame_is800")[0]
    assert G.gate_is800_query(doc="IS_800_2007", purpose="serviceability_limits_table6")[0]
    assert G.gate_is800_query(doc="IS_18168_2023", purpose="lateral_frame_is800")[0]
    assert not G.gate_is800_query(doc="IS_800_2007", purpose="stud capacity")[0]
    assert G.gate_is800_query(doc="IS_801_1975", purpose="")[0]
    assert G.is800_refusal_payload(collection="engineering_standards_IS800")["refused"]


def test_preflight_refuses_us_keys_walls_and_sfia():
    cfg = {"jurisdiction": "india", "units": "m", "seis": {"SDS": 0.24}, "lines_x": [], "site": {},
           "cfs_members": {"studs": {"section": "600S162-54"}}, "load_plan": _plan()}
    errs = [m for s, m in PF.check(cfg) if s == "ERROR"]
    assert any("ASCE key" in m for m in errs)
    assert any("not a design basis" in m for m in errs)
    assert any("SFIA" in m or "not an IS 811 label" in m for m in errs)
    assert any("drift_limit" in m for s, m in PF.check(dict(cfg, drift_limit=0.025)) if s == "ERROR")


def test_no_waivers_and_dc_recomputed():
    pkg = {"lateral_frame": {"status": {"status": "complete", "reasons": []}},
           "cfs_members": [{"id": "m", "checks": [{"combo": "DL", "check": "x", "value": 3.0, "limit": 2.0, "dc": 0.5, "ok": True,
                                                   "capacity_basis": "IS801_allowable"}]}]}
    cfg = {"load_plan": _plan()}
    st = G.design_status(cfg, pkg)
    assert any("D/C = 1.500" in r for r in st["reasons"])          # recomputed 3/2, not the stored 0.5
    pkg["cfs_members"][0]["waived"] = True
    assert any("waived" in r for r in G.design_status(cfg, pkg)["reasons"])


def _hr_rows(kind, d, lines_kN, extent_m):
    """H3: HR collectors.rows (level 1) -- {line coordinate m: R_line kN}."""
    return [{"dir": d, "level": 1, "line": float(p) * 1000.0, "beam": 1 + n, "role": "collector", "N_N": 10.0,
             "q_N_per_mm": round(R / extent_m, 4), "R_line_N": R * 1000.0, "kind": kind}
            for n, (p, R) in enumerate(lines_kN.items())]


def test_diaphragm_demands_depth_and_span_hand_value(tmp_path):
    """WP6-fix / H3: a 12 m x 8 m plate, storey force 24 kN along X; the analysed reactions of the two lines that run
    along X (deck 12 m each) are 12 / 12 kN: v = 12 / 12 = 1.0 kN/m, chord from the reactions max|M| = F L / 8 = 24 kN m
    -> 24 / 12 = 2.0 kN.  Along Y (lines of deck length 8 m, span 12 m): v = 12 / 8 = 1.5 kN/m, chord = 24 x 12 / (8 x 8)
    = 4.5 kN."""
    import json, os
    import india_cfs_lateral as L
    root = tmp_path / "lat"; root.mkdir()
    json.dump({"story_forces": {"EQ_X": {"1": [24000.0, 0.0, 0.0]}, "EQ_Y": {"1": [0.0, 24000.0, 0.0]},
                                "W_X": {"1": [0.0, 0.0, 0.0]}, "W_Y": {"1": [0.0, 0.0, 0.0]}}}, open(root / "load_plan.json", "w"))
    cfg = {"geometry": {"plan_x_m": 12.0, "plan_y_m": 8.0, "heights_m": [3.0]}, "lateral_frame": {"NX": 2, "NY": 2},
           "diaphragm_capacity": {"v_allow_kN_per_m": 6.0}}
    hr = _hr_rows("EQ", "X", {0: 12.0, 8: 12.0}, 12.0) + _hr_rows("EQ", "Y", {0: 12.0, 12: 12.0}, 8.0)
    rows = L.diaphragm_demands(cfg, {"root": str(root), "collectors": {"rows": hr}})
    rx = [r for r in rows if r["dir"] == "X"][0]; ry = [r for r in rows if r["dir"] == "Y"][0]
    assert abs(rx["v_unit_kN_per_m"] - 1.0) < 1e-9 and abs(rx["chord_force_kN"] - 2.0) < 1e-6
    assert abs(ry["v_unit_kN_per_m"] - 1.5) < 1e-9 and abs(ry["chord_force_kN"] - 4.5) < 1e-6
    assert rx["depth_m"] == 12.0 and rx["span_m"] == 8.0


def test_diaphragm_demands_three_lines(tmp_path):
    """Three braced lines along X (j = 0, 1, 2 of a 12 x 8 plate) with analysed reactions 8 / 8 / 8 kN: v = 8 / 12 kN/m;
    chord from the same reactions (w = 3 kN/m, M(s) = 1.5 s^2 - 8 s - 8 (s - 4)): max |M| = 32/3 kN m at s = 8/3 and
    16/3 -> (32/3) / 12 = 0.889 kN (H3: the chord follows the analysed reactions, not simple spans w s^2 / 8)."""
    import json
    import india_cfs_lateral as L
    root = tmp_path / "lat"; root.mkdir()
    json.dump({"story_forces": {"EQ_X": {"1": [24000.0, 0.0, 0.0]}, "EQ_Y": {"1": [0.0, 0.0, 0.0]}}}, open(root / "load_plan.json", "w"))
    cfg = {"geometry": {"plan_x_m": 12.0, "plan_y_m": 8.0, "heights_m": [3.0]},
           "lateral_frame": {"NX": 2, "NY": 2, "braced_bays": [["X", 0, 0], ["X", 1, 1], ["X", 0, 2], ["Y", 0, 0], ["Y", 2, 1]]},
           "diaphragm_capacity": {"v_allow_kN_per_m": 6.0}}
    hr = _hr_rows("EQ", "X", {0: 8.0, 4: 8.0, 8: 8.0}, 12.0)
    rx = [r for r in L.diaphragm_demands(cfg, {"root": str(root), "collectors": {"rows": hr}}) if r["dir"] == "X"][0]
    assert rx["n_lines"] == 3 and abs(rx["v_unit_kN_per_m"] - 24.0 / 36.0) < 1e-9
    assert abs(rx["chord_force_kN"] - 32.0 / 3.0 / 12.0) < 1e-3


def test_consistency_accepts_mixed_system_label(tmp_path):
    """WP6: an L7 portal declares the least-R system (SCBF 4.5) while the HR package label is 'SMF+SCBF' -- not an issue."""
    import json, os, importlib.util
    sp_ = importlib.util.spec_from_file_location("cfs_consistency_under_test", os.path.join(ROOT, "steel_engine", "consistency.py"))
    CC = importlib.util.module_from_spec(sp_); sp_.loader.exec_module(CC)          # the CFS module by path (not the vendored HR one)
    root = tmp_path / "job"; lat = root / "lateral" / "job_lateral" / "design"; lat.mkdir(parents=True)
    json.dump({"seismic_calc": {"system": "SMF+SCBF", "R": 4.5}, "capacity_design": {"system": "SMF+SCBF", "R": 4.5}}, open(lat / "calc_package.json", "w"))
    pkg = {"lateral_frame": {"name": "job_lateral", "system": "SCBF", "R": 4.5}}
    assert CC._system_issues(pkg, str(root)) == []
    pkg["lateral_frame"]["system"] = "OCBF"
    assert CC._system_issues(pkg, str(root))


def test_wind_summary_carries_the_k4_structure_class():
    """The HR preflight re-derives k4 from the class; the CFS wind summary must carry it (industrial in the belt -> 1.15)."""
    import india_cfs_lateral as L
    cfg = {"site": {"Vb": 50.0, "k2_table": {10: 1.0, 15: 1.05, 20: 1.07}, "cyclone_belt": True, "wind_structure_class": "industrial", "terrain_category": 2},
           "geometry": {"plan_x_m": 48.0, "plan_y_m": 18.0, "heights_m": [6.0]}, "lateral_frame": {"bay_x_m": 6.0, "bay_y_m": 18.0}}
    ws, forces = L.wind_story_forces(cfg)
    assert ws["structure_class"] == "industrial" and abs(ws["k4"] - 1.15) < 1e-9 and ws["Kd"] == 1.0
