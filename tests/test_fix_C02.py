"""C02 (CFS-A-04, B-05, D-08, A-13, C-12, D-09, D-10, C-07): member-level wind for studs, purlins and girts --
Table 4 Ka by ELEMENT area, governing Cpe over every face, local strips (Kd 1.0), Cpi from the opening ratio, every
storey by default with storey-unique ids, purlin / girt pressures on every path (fail closed), member_wind for
single-storey HR lateral runs."""
import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_members as CM   # noqa: E402


def _cfg(ex):
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_" + ex)
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    return Bx.build_cfg()


def test_stud_element_ka_and_governing_face():
    cfg = _cfg("Ex1")
    mw = CM.member_pd(cfg, 0.4 * 3.0, 12.0, "wall", "general")
    assert mw["Ka"] == 1.0                                     # 1.2 m2 element (frame Ka 0.9467 at 18 m2 before)
    assert mw["Cpe_max"] == pytest.approx(0.7) and mw["Cpe_min"] == pytest.approx(-0.6)   # h/w 1.5, l/w 1.5, both angles
    pd = max(0.9 * 1.0 * mw["pz_kNm2"], 0.7 * mw["pz_kNm2"])
    assert mw["p_out_kNm2"] == pytest.approx((0.6 + 0.2) * pd)
    e = CM.member_pd(cfg, 1.2, 12.0, "wall", "edge")
    assert e["edge"]["Cpe_local"] == pytest.approx(-1.1) and e["edge"]["Kd"] == 1.0
    assert e["p_out_kNm2"] == pytest.approx((1.1 + 0.2) * mw["pz_kNm2"])            # 7.2.1 Note 2: Kd 1.0 locally
    assert CM.member_pd(cfg, 1.2, 12.0, "wall", "all")["p_out_kNm2"] == pytest.approx(e["p_out_kNm2"])


def test_cpi_from_opening_ratio():
    cfg = _cfg("Ex1")
    cfg["geometry"]["opening_ratio"] = 0.10
    assert CM.member_pd(cfg, 1.2, 12.0, "wall")["Cpi"] == 0.5          # 7.3.2.2: 5-20 % openings
    cfg["geometry"].pop("opening_ratio")
    assert "VERIFY" in CM.member_pd(cfg, 1.2, 12.0, "wall")["Cpi_basis"]


def test_studs_every_storey_unique_ids():
    cfg = _cfg("Ex1")
    cfg["load_plan"]["story_forces"] = {}
    recs = [r for r in CM.design_all(cfg) if r["role"] == "stud"]
    assert [r["storey"] for r in recs] == [1, 2, 3, 4]
    assert len({r["id"] for r in recs}) == 4 and recs[0]["id"] == "stud-S1-CLR100X50X15X2"
    assert recs[3]["wind"]["member_pd"]["pz_kNm2"] > recs[0]["wind"]["member_pd"]["pz_kNm2"]


def test_purlin_ex5_element_ka_local_strip():
    cfg = _cfg("Ex5")
    cfg["load_plan"]["story_forces"] = {}
    rec = CM.design_purlins(cfg, "purlin")
    mw = rec["wind"]["member_pd"]
    assert mw["A_m2"] == pytest.approx(7.5) and mw["Ka"] == 1.0         # element area, not the 60 m2 frame area (Ka 0.853)
    assert mw["edge"]["Cpe_local"] == pytest.approx(-1.4)               # Table 6 h/w <= 0.5, 13.1 deg: eave strip E
    assert rec["wind"]["p_uplift_kNm2"] == pytest.approx(-(1.4 + 0.2) * mw["pz_kNm2"])
    assert "Table 4 Ka for the element area 7.5 m2" in rec["wind"]["cite"]
    assert CM.roof_local_cpe(7.0 / 24.0, 13.1) == pytest.approx(-1.4)


def test_purlins_on_hot_rolled_path_fail_closed():
    cfg = _cfg("Ex1")
    cfg["load_plan"]["story_forces"] = {}
    cfg["cfs_members"]["purlins"] = {"section": "CLR150X50X20X3.15", "spacing_mm": 1200.0, "span_mm": 4000.0,
                                     "wind_uplift_kNm2": None, "wind_pressure_kNm2": None}          # copied Ex5 block
    rec = CM.design_purlins(cfg, "purlin")
    assert rec["wind"]["p_uplift_kNm2"] < 0 and rec["loads_N_per_mm"]["wind_up"] < 0    # derived, never 0
    c2 = copy.deepcopy(cfg); c2["site"].pop("k2_table"); c2["load_plan"].pop("wind_summary", None)
    errs = [m for s, m in CM.wind_preflight(c2) if s == "ERROR"]
    assert errs and "purlins" in " ".join(errs)
    import preflight as PF
    assert any("member wind pressure not derivable" in m for s, m in PF.check(c2) if s == "ERROR")


def test_member_wind_for_single_storey_hr_run():
    import india_cfs_lateral as L
    cfg = _cfg("Ex1")
    cfg["geometry"]["heights_m"] = [4.0]
    spec = L.build_hr_spec(cfg, "t")
    mw = spec["load_plan"]["member_wind"]
    assert {p["name"] for p in mw} == {"WM0+", "WM0-", "WM90+", "WM90-"}
    assert all(p["wind_axis"] in ("X", "Y") for p in mw)
    assert any(p.get("wall_windward_kNm2") for p in mw)                 # wall columns get the girt reactions
    assert "lowrise_member_wind" in spec["load_plan"]["wind_summary"]["member_wind_basis"]["source"]
    assert "member_wind" not in L.build_hr_spec(_cfg("Ex1"), "t")["load_plan"]     # 4 storeys: not low-rise
