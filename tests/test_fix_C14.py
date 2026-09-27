"""C14 (CFS-B-09, C-12, D-09, NEW-4): member groups -- joists as a list with per-group loads, eave struts, headers,
purlins with point loads (evaporator units); no float(None) crash for a copied Ex5 purlin block."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_members as CM   # noqa: E402


def _cfg():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex1")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    cfg = Bx.build_cfg()
    cfg["load_plan"]["story_forces"] = {}
    return cfg


def test_joist_groups_with_own_loads():
    cfg = _cfg()
    j = cfg["cfs_members"]["joists"]
    cfg["cfs_members"]["joists"] = [dict(j, name="rooms"), dict(j, name="balcony", L_kNm2=3.0, L_cite="IS 875-2 Table 1 balconies")]
    recs = [r for r in CM.design_all(cfg) if r["role"] == "joist"]
    assert [r["id"] for r in recs] == ["joist-rooms-CLR180X50X20X3.15", "joist-balcony-CLR180X50X20X3.15"]
    assert recs[1]["w_live_N_per_mm"] == pytest.approx(recs[0]["w_live_N_per_mm"] * 1.5)
    assert recs[1]["DC"] > recs[0]["DC"]


def test_eave_strut_and_header():
    cfg = _cfg()
    cfg["cfs_members"]["eave_struts"] = {"section": "CLR150X50X20X3.15", "span_mm": 5000.0, "P_N": 12000.0,
                                         "P_cite": "gable wind share to the eave line (EOR calc)", "L_unbraced_mm": 5000.0}
    cfg["cfs_members"]["headers"] = [{"section": "CLR180X50X20X3.15", "n_ply": 2, "span_mm": 2400.0, "w_dead_kN_per_m": 3.0,
                                      "w_live_kN_per_m": 2.4, "load_cite": "joist reactions", "connector_spacing_mm": 300.0}]
    recs = {r["role"]: r for r in CM.design_all(cfg)}
    es, hd = recs["eave_strut"], recs["header"]
    assert es["DC"] is not None and es["P_N"] == 12000.0 and all(c["allowable_increase"] == pytest.approx(4 / 3) for c in es["checks"])
    b = [c for c in hd["checks"] if c["check"] == "6.1/6.2/6.3 bending" and c["combo"] == "DL+IL"][0]
    assert b["M_Nmm"] == pytest.approx(5.4 * 2400.0 ** 2 / 8.0)
    with pytest.raises(ValueError):
        CM.design_eave_strut(cfg, {"section": "CLR150X50X20X3.15", "span_mm": 5000.0})   # axial force must be declared


def test_point_load_purlin():
    cfg = _cfg()
    base = {"section": "CLR200X80X25X4", "spacing_mm": 1200.0, "span_mm": 5000.0, "L_unbraced_mm": 2500.0}
    cfg["cfs_members"]["purlins"] = [dict(base, name="plain"),
                                     dict(base, name="evap", point_loads=[{"P_kN": 2.0, "a_m": 2.5, "kind": "D", "cite": "evaporator unit (supplier data)"}])]
    recs = [r for r in CM.design_all(cfg) if r["role"] == "purlin"]
    g = lambda r: [c for c in r["checks"] if c["combo"] == "DL" and c["check"].startswith("6.1")][0]["M_Nmm"]
    assert g(recs[1]) - g(recs[0]) == pytest.approx(2000.0 * 2500.0 * 2500.0 / 5000.0)


def test_no_float_none_crash():
    cfg = _cfg()
    cfg["cfs_members"]["girts"] = {"section": "CLR150X50X20X3.15", "spacing_mm": 1500.0, "span_mm": 4000.0,
                                   "wind_suction_kNm2": None, "wind_pressure_kNm2": None, "L_unbraced_mm": None}
    rec = CM.design_purlins(cfg, "girt")
    assert rec["loads_N_per_mm"]["wind_up"] < 0
