"""2026-10 third wave (CFS): P3 repeatable frame models (sorted iteration in the lateral runner, the stated rule for a
column shared by X- and Y-braced bays, a fixed hash seed for the frame sub-run) and P9 cold-formed leftovers."""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.path.join(ROOT, "steel_engine")
RUNNER = os.path.join(ENG, "hr_vendor_runner.py")
sys.path.insert(0, ENG)


def _runner():
    """hr_vendor_runner loaded by path; the vendored folder it puts on sys.path is taken off again so the CFS modules
    of later tests are not shadowed."""
    saved = list(sys.path)
    try:
        sp = importlib.util.spec_from_file_location("hrv_runner_third_wave", RUNNER)
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
    finally:
        sys.path[:] = saved
    return m


# the Ex7 layout: a 2 x 2 bay plan braced on all four walls -> four corner columns in X- and Y-braced bays
SPEC = {"NX": 2, "NY": 2, "heights_m": [3.2, 3.2],
        "braced_bays": [["X", 0, 0], ["X", 1, 0], ["X", 0, 2], ["X", 1, 2],
                        ["Y", 0, 0], ["Y", 0, 1], ["Y", 2, 0], ["Y", 2, 1]],
        "moment_lines": [], "col": "C", "beam": "B", "default_strong": None}

_PROBE = r"""
import importlib.util, json, sys
sp = importlib.util.spec_from_file_location("r", %(runner)r)
m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
spec = json.loads(%(spec)r)
br, cs, bs, strong, rel = m._callables(spec)
out = {"braces": [list(b) for b in br(1, spec["NX"], spec["NY"])],
       "strong": [[i, j, strong(i, j, spec["NX"], spec["NY"])] for i in range(spec["NX"] + 1) for j in range(spec["NY"] + 1)],
       "orientation": m.column_orientation(spec, {"col_strong": strong})}
print(json.dumps(out, sort_keys=True))
"""


def _probe(spec, seed):
    code = _PROBE % {"runner": RUNNER, "spec": json.dumps(spec)}
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300,
                       env=dict(os.environ, PYTHONHASHSEED=str(seed), PYTHONDONTWRITEBYTECODE="1"))
    assert p.returncode == 0, p.stderr[-2000:]
    return p.stdout.strip().splitlines()[-1]


# ================================================================================================ P3
def test_P3_frame_callables_do_not_depend_on_the_hash_seed():
    outs = {_probe(SPEC, s) for s in (0, 1, 2, 3, 7, 11)}
    assert len(outs) == 1, "brace order / column axis changed with PYTHONHASHSEED"
    out = json.loads(outs.pop())
    assert out["braces"] == sorted(out["braces"])                     # element order: X before Y, then i, j


def test_P3_shared_corner_column_takes_the_bay_listed_first():
    r = _runner()
    _, _, _, strong, _ = r._callables(SPEC)
    assert strong(0, 0, 2, 2) == "X" and strong(2, 2, 2, 2) == "X"   # X bays listed first in the schedule
    assert strong(0, 1, 2, 2) == "Y" and strong(1, 0, 2, 2) == "X"   # mid-wall columns: their own wall
    rev = dict(SPEC, braced_bays=list(reversed(SPEC["braced_bays"])))
    _, _, _, strong2, _ = r._callables(rev)
    assert strong2(0, 0, 2, 2) == "Y"                                 # the rule follows the declared order
    co = r.column_orientation(SPEC, {"col_strong": strong})
    assert co["n_shared"] == 4 and [c["grid"] for c in co["shared_columns"]] == [[0, 0], [0, 2], [2, 0], [2, 2]]
    assert all(c["strong_axis"] == "X" for c in co["shared_columns"])
    assert "listed first" in co["rule"] and "both axes" in co["rule"]


def test_P3_moment_lines_both_directions_take_X_and_unclaimed_columns_the_default():
    r = _runner()
    spec = dict(SPEC, braced_bays=[], moment_lines=[["Y", 0], ["X", 0]])
    _, _, _, strong, _ = r._callables(spec)
    assert strong(0, 0, 2, 2) == "X"                                  # on an X line and a Y line -> X
    assert strong(0, 1, 2, 2) == "Y" and strong(1, 0, 2, 2) == "X"
    assert strong(1, 1, 2, 2) == "X"                                  # default X (was None when the key was null)
    assert r._callables(dict(spec, default_strong="Y"))[3](1, 1, 2, 2) == "Y"


def test_P3_builder_path_column_on_two_moment_lines_is_stable():
    r = _runner()
    calls = []

    def inner(i, j):
        calls.append((i, j))
        return "Y"
    cfg = {"_gold": {"col_strong": inner}}
    r._stable_gold_col_strong(cfg, {"gold": {"moment_lines": [["Y", 0], ["X", 0]]}})
    cs = cfg["_gold"]["col_strong"]
    assert cs(0, 0) == "X" and calls == []                            # X line + Y line: the rule, not the set order
    assert cs(0, 1) == "Y" and calls == [(0, 1)]                      # every other column: the builder's own rule
    cfg2 = {"_gold": {"col_strong": inner}}
    r._stable_gold_col_strong(cfg2, {"gold": {"moment_lines": [["Y", i] for i in range(4)]}})
    assert cfg2["_gold"]["col_strong"] is inner                       # one direction only: nothing to decide


def test_P3_frame_subrun_gets_a_fixed_hash_seed(monkeypatch, tmp_path):
    import india_cfs_lateral as L
    seen = {}

    class _P:
        stdout, stderr = "", ""

    def fake_run(cmd, **kw):
        seen["env"] = kw.get("env")
        raise RuntimeError("stop")
    monkeypatch.setattr(L.subprocess, "run", fake_run)
    monkeypatch.setattr(L, "build_hr_spec", lambda cfg, name: {"name": name})
    monkeypatch.setattr(L, "copy_rag_hits", lambda *a, **k: None)
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    with pytest.raises(RuntimeError):
        L.run_lateral({"name": "j"}, str(tmp_path / "lateral"))
    assert seen["env"]["PYTHONHASHSEED"] == "0"
    monkeypatch.setenv("PYTHONHASHSEED", "5")
    with pytest.raises(RuntimeError):
        L.run_lateral({"name": "j"}, str(tmp_path / "lateral"))
    assert seen["env"]["PYTHONHASHSEED"] == "5"


def test_P3_report_states_the_rule():
    import report_cfs_third_wave as R3
    import report_cfs_second_wave as RS
    r = _runner()
    _, _, _, strong, _ = r._callables(SPEC)
    html_ = R3.column_orientation_html({"column_orientation": r.column_orientation(SPEC, {"col_strong": strong})})
    assert "4 frame column(s) stand in frames of both directions" in html_ and "x-line 0, y-line 2" in html_
    assert "braced bay, x-lines 0-1 on y-line 0" in html_
    assert not RS.leaks(RS.tidy_html(html_))
    none = R3.column_orientation_html({"column_orientation": r.column_orientation(
        dict(SPEC, braced_bays=[["X", 0, 0]]), {"col_strong": strong})})
    assert "No frame column stands in frames of both directions" in none
    assert R3.column_orientation_html({}) == ""


# ================================================================================================ P9 cold-formed leftovers
def _mini_cfg(**over):
    """A minimal cold-store-like cfg (Srinagar-type site, 76 x 21 m, 8 m eave, snow) for the P9 units."""
    cfg = {"site": {"Vb": 39.0, "k2_table": {10: 1.0, 15: 1.05}, "cyclone_belt": False, "k1": 1.0, "k3": 1.0, "Kd": 0.9,
                    "wind_structure_class": "industrial"},
           "geometry": {"heights_m": [8.0], "plan_x_m": 76.0, "plan_y_m": 21.0, "roof_pitch_deg": 5.4, "opening_ratio": 0.10},
           "loads": {"Lr": 0.75, "snow": 4.38, "D_roof": 0.75},
           "load_plan": {"snow_summary": {"applicable": True, "s0_kPa": 5.48}}, "cfs_members": {"Fy_MPa": 350.0}}
    cfg.update(over)
    return cfg


def test_P9_stud_deflection_criterion_default_and_declared():
    import india_cfs_members as CM
    st, src = CM.stud_deflection_criterion({"spacing_mm": 400.0})
    assert st["deflection_limit_ratio"] == 300 and "height/300" in st["deflection_cite"] and src.startswith("stated default")
    assert CM.stud_deflection_criterion({"lining": "brittle"})[0]["deflection_limit_ratio"] == 500
    keep = {"deflection_limit_ratio": 360, "deflection_cite": "job"}
    assert CM.stud_deflection_criterion(keep) == (keep, "declared by the job")
    with pytest.raises(ValueError):
        CM.stud_deflection_criterion({"lining": "glass"})
    r = CM._defl_row("s", "deflection (information)", 9.0, 3000.0, st, "c")
    assert not r["informational"] and r["limit"] == pytest.approx(10.0) and r["ok"] is True


def test_P9_dominant_opening_cpi_envelope_members():
    import india_cfs_members as CM
    base = _mini_cfg()
    dom = _mini_cfg(wind_internal_pressure={"case": "dominant opening", "Cpi_pos": 0.8, "Cpi_neg": -0.7, "cite": "c"})
    a = CM.member_pd(base, 9.0, 8.0, "wall")
    b = CM.member_pd(dom, 9.0, 8.0, "wall")
    pd = b["general"]["pd_kNm2"]
    # suction grows by (0.8 - 0.5) pd, pressure by (0.7 - 0.5) pd (opening ratio 10 % -> +-0.5)
    assert b["general"]["p_out_kNm2"] - a["general"]["p_out_kNm2"] == pytest.approx(0.3 * pd)
    assert b["general"]["p_in_kNm2"] - a["general"]["p_in_kNm2"] == pytest.approx(0.2 * pd)
    assert b["Cpi_pos"] == 0.8 and b["Cpi_neg"] == -0.7 and "enveloped" in b["Cpi_basis"]
    small = _mini_cfg(wind_internal_pressure={"Cpi_pos": 0.3, "Cpi_neg": -0.3})
    assert CM.member_pd(small, 9.0, 8.0, "wall")["general"]["p_out_kNm2"] == pytest.approx(a["general"]["p_out_kNm2"])
    with pytest.raises(CM.MemberWindError):           # a dominant opening and protected openings contradict
        CM.member_pd(dict(dom, opening_protection={"required": True}), 9.0, 8.0, "wall")
    with pytest.raises(CM.MemberWindError):
        CM.internal_pressure_case({"wind_internal_pressure": {"Cpi_pos": -0.2, "Cpi_neg": -0.7}})


def test_P9_dominant_opening_on_frame_patterns():
    import india_cfs_lateral as L
    roof = {"EF": -1.2, "GH": -0.4, "EG": -0.8, "FH": -0.6}
    pd = 1.6
    pats = [{"name": "WM0+", "direction": "across_ridge", "Cpi": 0.2, "roof": roof,
             "roof_windward_kNm2": (-1.2 - 0.2) * pd, "roof_leeward_kNm2": (-0.4 - 0.2) * pd,
             "wall_windward_kNm2": (0.7 - 0.2) * pd, "wall_leeward_kNm2": (-0.25 - 0.2) * pd},
            {"name": "WM90-", "direction": "along_ridge", "Cpi": -0.2, "roof": roof,
             "roof_windward_kNm2": (-0.8 + 0.2) * pd, "roof_leeward_kNm2": (-0.6 + 0.2) * pd,
             "wall_windward_kNm2": (0.7 + 0.2) * pd, "wall_leeward_kNm2": (-0.1 + 0.2) * pd}]
    ip = {"case": "dominant opening", "Cpi_pos": 0.8, "Cpi_neg": -0.7}
    out, rec = L.apply_internal_pressure(pats, ip)
    assert out[0]["roof_windward_kNm2"] == pytest.approx((-1.2 - 0.8) * pd)          # pd recovered from the roof record
    assert out[0]["wall_windward_kNm2"] == pytest.approx((0.7 - 0.8) * pd)
    assert out[1]["roof_leeward_kNm2"] == pytest.approx((-0.6 + 0.7) * pd) and out[1]["Cpi"] == -0.7
    assert [p["name"] for p in rec["patterns"]] == ["WM0+", "WM90-"] and pats[0]["Cpi"] == 0.2   # input untouched
    d, rec2 = L.apply_internal_pressure({"patterns": pats, "pd_kNm2": pd}, {"Cpi_pos": 0.1, "Cpi_neg": -0.1})
    assert d["patterns"][0]["roof_windward_kNm2"] == pats[0]["roof_windward_kNm2"] and not rec2["patterns"]  # never reduced
    with pytest.raises(L.LateralSystemError):
        L.apply_internal_pressure([dict(pats[0], Cpi=None)], ip)


def test_P9_opening_protection_text():
    import report_cfs_third_wave as R3
    import report_cfs_second_wave as RS
    cfg = {"opening_protection": {"required": True, "items": "impact-rated doors, roller shutters and glazing",
                                  "basis": "Chennai is in the cyclone belt.", "Cpi_basis": "IS 875 (Part 3):2015 7.3.2.1: Cpi +0.2 and -0.2."}}
    s = R3.opening_protection_html(cfg, "scope")
    w = R3.opening_protection_html(cfg, "wind")
    assert "Design requirement (design engineer and owner)" in s and "Impact-rated doors" in s
    assert "7.3.2.1" in w and "7.3.2.2" in w and "would not apply" in w
    assert not RS.leaks(RS.tidy_html(s + w))
    assert R3.opening_protection_html({}) == "" and R3.opening_protection_html({"opening_protection": {"required": False}}) == ""


def test_P9_simple_beam_closed_forms():
    import india_cfs_secondary as SEC
    r = SEC.simple_beam(4000.0, 2.0, EI=203400.0 * 1e6)
    assert r["R_left_N"] == pytest.approx(4000.0) and r["M_max_Nmm"] == pytest.approx(4.0e6, rel=1e-6)
    assert r["defl_max_mm"] == pytest.approx(5 * 2 * 4000.0 ** 4 / (384 * 203400.0 * 1e6), rel=1e-4)
    p = SEC.simple_beam(4000.0, 0.0, [(1000.0, 1000.0)])
    assert (p["R_left_N"], p["R_right_N"]) == (pytest.approx(750.0), pytest.approx(250.0))
    assert p["M_max_Nmm"] == pytest.approx(750000.0)
    t = SEC.simple_beam(4000.0, lambda x: 3.0 - 2.0 * x / 4000.0)       # trapezoid 3 -> 1 N/mm
    assert t["R_left_N"] == pytest.approx(4000.0 * 7 / 6, rel=1e-5) and t["R_right_N"] == pytest.approx(4000.0 * 5 / 6, rel=1e-5)
    with pytest.raises(SEC.SecondaryError):
        SEC.simple_beam(4000.0, 0.0, [(1.0, 5000.0)])


def test_P9_snow_drift_is875_part4():
    import india_cfs_secondary as SEC
    d = SEC.snow_drift_multilevel(5.48, 5.0, 76.0, 4.0, 5.4)              # CFS Ex2 vestibule
    assert d["muw_raw"] == pytest.approx(8.0) and d["muw"] == pytest.approx(2 * 5.0 / 5.48) and d["governs"] == "k h/s0"
    assert d["s_step_kPa"] == pytest.approx(10.0) and d["l3_m"] == pytest.approx(10.0)
    assert d["mu_far_edge"] == pytest.approx(d["mu2"] - (d["mu2"] - 0.8) * 0.4)      # Note 2 interpolation at l2 = 4 m
    assert d["mu"](12.0) == 0.8
    assert SEC.snow_drift_multilevel(5.48, 1.0, 10.0, 4.0)["muw"] == 0.8           # k h/s0 0.36 -> 0.80 lower bound
    big = SEC.snow_drift_multilevel(0.5, 9.0, 200.0, 20.0)
    assert big["muw"] == 4.0 and big["l3_m"] == 15.0                               # 4.0 cap, l3 <= 15 m
    assert SEC.snow_drift_multilevel(5.48, 2.0, 30.0, 6.0)["l3_m"] == 5.0          # l3 >= 5 m
    with pytest.raises(SEC.SecondaryError):
        SEC.snow_drift_multilevel(5.48, 5.0, 76.0, 4.0, 20.0)                     # steep upper roof: mus required
    p = SEC.snow_drift_projection(5.48, 1.5)
    assert p["mu2"] == 0.8 and not p["surcharge"] and "no drift surcharge" in p["statement"]
    q = SEC.snow_drift_projection(1.0, 3.0)
    assert q["mu2"] == 2.0 and q["surcharge"] and q["l_m"] == 6.0


def _purlin_rec(cont=None):
    rec = {"id": "purlin-C250X70X20X3.15-G350", "role": "purlin", "designator": "C250X70X20X3.15-G350", "Fy_MPa": 350.0,
           "span_mm": 6000.0, "loads_N_per_mm": {"dead": 0.6, "live": 1.1, "snow": 0.0, "wind_up": -3.0, "wind_down": 0.0}}
    if cont:
        rec["continuity"] = cont
    return rec


CLEAT = {"bolts": {"n": 2, "d_mm": 16.0, "class": "4.6", "edge_mm": 35.0, "pitch_mm": 70.0},
         "cleat": {"t_mm": 10.0, "fy_MPa": 250.0, "width_mm": 150.0, "bolt_height_mm": 100.0, "weld_mm": 6.0},
         "roof_pitch_deg": 10.0}


def test_P9_purlin_cleats():
    import india_cfs_secondary as SEC
    cfg = _mini_cfg(loads={"Lr": 0.75, "D_roof": 0.4})
    c1 = SEC.design_purlin_cleats(cfg, [_purlin_rec(), {"role": "girt"}], CLEAT)
    assert len(c1) == 1 and c1[0]["id"].startswith("purlin-cleat-")
    assert all(r.get("detailing") for r in c1[0]["checks"] if "7.5.1" in r["check"])
    assert "7.5.1" not in str(c1[0]["governing_check"])
    names = {r["check"] for r in c1[0]["checks"]}
    for n in ("bolts in the purlin web: 7.5.3 bearing", "bolts in the purlin web: 7.5.4 bolt shear",
              "cleat compression + minor-axis bending (IS 800 11.5.2)", "cleat tension + minor-axis bending (IS 800 11.5.3)",
              "cleat fillet welds (IS 800 11.6.3.1)"):
        assert n in names
    # gravity row DL+IL: R = (0.6 + 1.1) x 6000 / 2 = 5100 N, 2 bolts -> 2550 N per bolt
    row = next(r for r in c1[0]["checks"] if r["combo"] == "DL+IL" and r["check"].endswith("7.5.4 bolt shear"))
    assert row["P_per_bolt_N"] == pytest.approx(2550.0)
    rods = SEC.design_purlin_cleats(cfg, [_purlin_rec()], dict(CLEAT, downslope="sag rods"))[0]
    g = lambda c: max(r["dc"] for r in c["checks"] if r["check"].startswith("cleat compression"))
    assert g(rods) < g(c1[0]) and "sag-rod" in rods["downslope"]
    lap = SEC.design_purlin_cleats(cfg, [_purlin_rec({"type": "lapped", "n_spans": 5, "lap_mm": 600.0})], CLEAT)[0]
    assert lap["webs"] == 2 and lap["purlin_ends"] == 1 and c1[0]["purlin_ends"] == 2   # simple spans: two ends per cleat
    w = next(r for r in c1[0]["checks"] if r["combo"] == "DL+IL" and r["check"].startswith("cleat fillet"))
    assert w["R_N"] == pytest.approx(5100.0) and w["purlin_ends"] == 2


def test_P9_platform_frame_loads_and_eave_struts():
    import india_cfs_secondary as SEC
    cfg = _mini_cfg(lateral_frame={"NY": 1}, roof_platforms=[{
        "name": "p", "frames": [8, 9], "eave_line": 0, "span_m": 4.75, "posts_from_column_m": [0.3, 1.8],
        "beam_trib_m": 0.75, "deck_kNm2": 0.5, "units": [{"P_kN": 3.0, "a_m": 2.375}], "height_above_roof_m": 1.5,
        "beams": {"section": "C250X70X20X3.15-G350", "n_ply": 2, "deck_restrains_top": True, "deflection_limit_ratio": 240},
        "posts": {"section": "C100X50X15X1.6-G350", "height_mm": 600.0}}])
    loads = SEC.platform_frame_loads(cfg)
    assert [r["node"] for r in loads] == [100800, 100900]
    r = loads[0]
    P = -r["Fz_N"] / 2.0                                                    # two posts per frame, equal reactions
    assert P > 3000.0 / 2.0 and r["Mx_Nmm"] == pytest.approx(-P * (300.0 + 1800.0))
    far = SEC.platform_frame_loads(dict(cfg, roof_platforms=[dict(cfg["roof_platforms"][0], eave_line=1)]))
    assert far[0]["node"] == 100801 and far[0]["Mx_Nmm"] > 0
    recs, plats = SEC.design_roof_platforms(cfg, cfg["roof_platforms"])
    assert [m["role"] for m in recs] == ["platform beam", "platform post"] and not plats[0]["drift"]["surcharge"]
    # eave struts of an all-CFS portal: the governing longitudinal force / 2 side walls
    pc = {"cfs_members": {"eave_struts": {"section": "C200X65X20X2.5-G350", "span_mm": 5000.0, "P_from": "longitudinal_bracing"}}}
    conns = [{"id": "longitudinal-bracing-X", "forces_N": {"DL+1.0WL(gable)": 148000.0, "DL+1.0EL(longitudinal)": -60000.0}}]
    es = SEC.portal_eave_struts(pc, conns)
    assert es[0]["P_N"] == pytest.approx(74000.0) and "2 side walls" in es[0]["P_cite"]
    assert SEC.portal_eave_struts({"cfs_members": {}}, conns) is None
    with pytest.raises(SEC.SecondaryError):
        SEC.portal_eave_struts(pc, [])


def test_P9_lean_to_vestibule():
    import india_cfs_secondary as SEC
    lt = {"name": "vestibule", "width_m": 6.0, "depth_m": 4.0, "roof_z_m": 4.0, "front_wall_height_m": 3.6,
          "upper_roof_z_m": 9.0, "upper_roof_length_m": 76.0, "upper_roof_pitch_deg": 5.4, "D_roof_kNm2": 0.35,
          "wall_kNm2": 0.25,
          "joists": {"section": "C250X70X20X3.15-G350", "spacing_mm": 600.0, "bearing_mm": 75.0, "L_unbraced_mm": 2000.0,
                     "deflection_limit_ratio": 180, "deflection_cite": "c"},
          "door": {"width_m": 3.0, "height_m": 3.0,
                   "header": {"section": "C250X70X20X2.5-G350", "n_ply": 2, "bearing_mm": 100.0},
                   "jambs": {"section": "C150X60X20X1.6-G350", "n_ply": 2, "spacing_mm": 600.0}},
          "back_studs": {"section": "C100X50X15X1.6-G350", "n_ply": 2, "spacing_mm": 600.0}}
    recs, rec = SEC.design_lean_to(_mini_cfg(), lt)
    assert [m["role"] for m in recs] == ["lean-to roof joist", "door header", "door jamb", "back-wall stud"]
    assert all(" " not in m["id"] for m in recs)
    assert rec["snow_drift"]["s_step_kPa"] == pytest.approx(10.0)
    j = recs[0]
    # governing reaction at the wall: DL+SL-W -- the trapezoidal drift 10.0 -> 7.75 kPa x 0.6 m, dead + own weight and
    # the downward wind pressure on the roof (the member pressure record), all on a 4.0 m span
    q0, q1 = 10.0 * 0.6, (rec["snow_drift"]["mu_far_edge"] * 5.48) * 0.6
    sw = j["mass_kg_m"] * 9.80665e-3
    pdn = j["wind"]["p_down_kNm2"] * 0.6
    assert j["R_max_N"] == pytest.approx(4000.0 * (2 * q0 + q1) / 6.0 + (0.35 * 0.6 + sw + pdn) * 2000.0, rel=2e-3)
    assert any(c["check"].startswith("6.5 web crippling") for c in j["checks"])
    with pytest.raises(SEC.SecondaryError):
        SEC.design_lean_to(_mini_cfg(load_plan={}), lt)
