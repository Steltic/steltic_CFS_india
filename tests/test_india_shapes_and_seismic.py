"""IS 811 dual-path catalog + IS 1893 drift/irregularity helpers (no openseespy)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "steel_engine"))
sys.path.insert(0, str(ROOT / "steltic"))


def test_is811_catalog_row_counts():
    import is811_sections as S
    meta = S.catalog_meta()
    assert meta.get("stem") == "IS_811_1987"
    assert meta.get("n_shapes", 0) >= 100
    labs = S.list_is811()
    assert len(labs) >= 100
    assert any(x.startswith("CWS") for x in labs)
    assert any(x.startswith("LZ") for x in labs)


def test_is811_cws_props_match_pdf():
    import is811_sections as S
    p = S.props("CWS20X20X1.25")
    assert abs(p["A_si_cm2"] - 0.683) < 0.02
    assert abs(p["Ix_si_cm4"] - 0.463) < 0.02
    assert p["A"] > 0 and p["d"] > 0
    assert p["Source"] == "IS_811_1987"


def test_is811_missing_found_false():
    import is811_sections as S
    with pytest.raises(KeyError) as ei:
        S.props("CWS999X999X9.99")
    assert "found:false" in str(ei.value)


def test_cfs_sections_dual_path_is811_then_sfia():
    import cfs_sections as CS
    p = CS.gross_props("EA20X20X1.25")
    assert p.get("_source") == "IS_811_1987"
    assert p["A"] > 0
    # SFIA path still works
    p2 = CS.gross_props("600S162-54")
    assert p2["A"] > 0
    assert p2.get("_source") != "IS_811_1987" or "style" in p2


def test_india_seismic_drift_004():
    import india_seismic as IS
    ratio, rho = IS.drift_allowable({})
    assert abs(ratio - 0.004) < 1e-9
    assert rho is False
    drifts = IS.design_story_drifts([0.1, 0.2], {})
    assert drifts == [0.1, 0.2]  # no Cd/Ie


def test_india_seismic_soft_storey():
    import india_seismic as IS
    # Ki < K(above) at storey 0
    flags = IS.storey_stiffness_soft_flags([10.0, 20.0, 20.0])
    assert flags["soft_storeys"][0] is True
    assert flags["drift_limit_by_storey"][0] == 0.002
    assert flags["asce_Ax"]["found"] is False


def test_india_seismic_plan_irregularity_tir():
    import india_seismic as IS
    out = IS.classify_plan_irregularities({"torsion_ratio": 1.6}, {"reentrant": True})
    types = {i["type"]: i for i in out["items"]}
    assert types["Torsional Irregularity"]["triggered"] is True
    assert types["Re-entrant Corners"]["triggered"] is True


def test_india_collections_hosted_aliases():
    from steltic import india_collections as ic
    assert ic.stem_for_collection("IS-801") == "IS_801_1975"
    assert ic.stem_for_collection("engineering_standards_IS811") == "IS_811_1987"
    payload = ic.hosted_alias_payload()
    assert "IS_801_1975" in payload["stem_to_collection"]
    assert "IS_811_1987" in payload["stem_to_collection"]


def test_india_units_helpers():
    import india_units as IU
    assert abs(IU.metric_length_to_in(1.0, "m") - IU.M_TO_IN) < 1e-9
    assert IU.kn_per_m_to_plf(1.0) > 0
    cfg = {"units": "metric", "bay_x": 6.0, "story_heights": [3.0, 3.0]}
    IU.apply_metric_geometry(cfg)
    assert abs(cfg["SX"] - 6.0 * IU.M_TO_IN) < 1e-6


def test_cfs_systems_india_drift():
    import cfs_systems as SYS
    assert abs(SYS.india_drift_limit({}) - 0.004) < 1e-9
    assert SYS.INDIA_SEISMIC_NOTES["s400_omega_capacity_design"]["found"] is False
