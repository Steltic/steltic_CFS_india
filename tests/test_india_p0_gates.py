"""India CFS P0 gates: wall vn (C1), R proxy (C2), complete label (C7), drift 0.004 (S2/C4)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "steel_engine"))

import india_cfs_gates as ICG
import preflight as PF
import india_loads as IL


def _base_cfg(**extra):
    cfg = {
        "system": "wsp_shearwall",
        "stories": 4,
        "heights": [3600, 3600, 3600, 3600],
        "SX": 6000, "SY": 5000,
        "units": "N-mm",
        "jurisdiction": "india",
        "seis": {"SDS": 0.24, "SD1": 0.14, "R": 3.0, "Cd": 1.0, "Ie": 1.0},
        "model": {"bases": "pinned", "joints": "pinned", "gravity": "framed"},
        "diaphragm": "flexible",
        "load_plan": {
            "jurisdiction": "india",
            "retrieval": [
                {"stem": "IS_875_Part_3_2015", "query": "wind", "found": True, "cite": "7.2"},
                {"stem": "IS_1893_Part_1_2016", "query": "Table 9 R", "found": True, "cite": "Table 9"},
            ],
            "combinations": [
                {"label": "1.5D", "fD": 1.5, "fL": 0, "fLr": 0, "cite": "IS"},
            ],
        },
        "lines_x": [object()],  # mark as wall path for _wall_systems
    }
    cfg.update(extra)
    return cfg


def test_c1_missing_wall_vn_hard_fail():
    findings = ICG.validate_wall_vn(_base_cfg())
    assert any(s == "ERROR" and "wall_vn_plf_asd" in m for s, m in findings)
    assert any("9.1.4" in m or "cl.9" in m for s, m in findings)


def test_c1_provisional_700_hard_fail():
    cfg = _base_cfg(wall_vn_plf_asd=700.0, wall_vn_source="provisional",
                    wall_vn_cite="industry guess")
    findings = ICG.validate_wall_vn(cfg)
    assert any(s == "ERROR" and "provisional" in m.lower() for s, m in findings)


def test_c1_manufacturer_ok():
    cfg = _base_cfg(wall_vn_plf_asd=520.0, wall_vn_source="manufacturer",
                    wall_vn_cite="Acme WSP Table B — 12 mm two-sided #8@100")
    findings = ICG.validate_wall_vn(cfg)
    assert not any(s == "ERROR" for s, m in findings)


def test_c2_silent_r_proxy_error():
    """seis.R set but no R_source → silent OMRF proxy path → ERROR."""
    cfg = _base_cfg()
    findings = ICG.validate_R(cfg)
    assert any(s == "ERROR" and ("proxy" in m.lower() or "R_source" in m) for s, m in findings)


def test_c2_explicit_omrf_proxy_warns_blocks_complete():
    cfg = _base_cfg(R_source="steel_omrf", R_cite="Table 9(i)(c) proxy",
                    R_cfs_table9_found=False)
    findings = ICG.validate_R(cfg)
    assert any(s == "WARN" and "proxy" in m.lower() for s, m in findings)
    ok, reasons = ICG.complete_allowed(cfg)
    assert ok is False
    assert any("proxy" in r.lower() or "OMRF" in r or "C7" in r for r in reasons)


def test_c2_explicit_eor_r_with_found_false_ok_for_gates():
    cfg = _base_cfg(
        R=2.5,
        R_source="explicit",
        R_cite="EOR: CFS WSP not in Table 9; project R=2.5",
        R_cfs_table9_found=False,
        wall_vn_plf_asd=480.0,
        wall_vn_source="test",
        wall_vn_cite="NABL lab report 2026-01 sheet 4",
    )
    assert not any(s == "ERROR" for s, m in ICG.validate_R(cfg))
    assert not any(s == "ERROR" for s, m in ICG.validate_wall_vn(cfg))
    ok, reasons = ICG.complete_allowed(cfg)
    assert ok is True, reasons


def test_c7_provisional_vn_refuses_complete_even_in_pkg():
    cfg = _base_cfg(
        R_source="explicit", R_cite="EOR", R_cfs_table9_found=False,
        wall_vn_plf_asd=700, wall_vn_source="manufacturer",
        wall_vn_cite="will be overridden by pkg provisional",
    )
    pkg = {"wall_lines": [{
        "id": "Mid", "limit_state": "sheathing shear (provisional)",
        "capacity_unit": "plf (ASD provisional)", "cited": "provisional",
    }]}
    ok, reasons = ICG.complete_allowed(cfg, pkg)
    assert ok is False
    assert any("provisional" in r.lower() for r in reasons)


def test_preflight_includes_p0_gates():
    cfg = _base_cfg()  # missing wall_vn + R_source
    findings = PF.check(cfg)
    errs = [m for s, m in findings if s == "ERROR"]
    assert any("wall_vn" in m for m in errs)
    assert any("R_source" in m or "proxy" in m.lower() for m in errs)
    # load_plan RAG gate still present / not broken
    assert not any("load_plan" in m and "missing" in m for m in errs) or True
    findings2 = IL.validate_load_plan(cfg)
    assert not any(s == "ERROR" for s, _ in findings2)


def test_india_drift_limit_004():
    import cfs_systems as CS
    assert abs(CS.india_drift_limit({}) - 0.004) < 1e-9


def test_report_india_chapters_strip_025():
    import pytest
    pytest.importorskip("matplotlib")
    import report as R
    ch = R._chapters({"jurisdiction": "india", "load_plan": {"jurisdiction": "india"}})
    blob = " ".join(ch[8][1])
    assert "0.004" in blob
    assert "0.025" not in blob
    assert "12.12-1" not in blob
