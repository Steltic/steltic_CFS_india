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
    assert any("only IS 801 allowables" in x for x in B.basis_issues(pkg2))
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
