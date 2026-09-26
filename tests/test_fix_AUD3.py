"""AUD-3 (gold audit M2): a CFS board diaphragm of the lateral frame declared rigid with no stiffness basis -> CFS
preflight WARN; the lateral run's 7.6.4 contradiction warning reaches the CFS design_status warnings (non-blocking)."""
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import india_cfs_env  # noqa: E402,F401
import india_cfs_gates as G  # noqa: E402


LF = {"system": "SCBF", "diaphragm": "rigid", "diaphragm_7_6_4": {"declared": "rigid", "plan_aspect_ratio": 1.5}}


def test_cfs_preflight_warns_board_diaphragm_declared_rigid_without_basis():
    msgs = [m for s, m in G.audit_warnings({"lateral_frame": dict(LF)}) if s == "WARN"]
    assert any("7.6.4" in m and "board" in m for m in msgs)
    lf2 = dict(LF, diaphragm_stiffness={"type": "custom", "Gd_kN_per_m": 2500, "source": "EOR", "cite": "test"})
    assert not [m for s, m in G.audit_warnings({"lateral_frame": lf2}) if "7.6.4" in m]
    assert not [m for s, m in G.audit_warnings({"lateral_frame": dict(LF, diaphragm="flexible")}) if "7.6.4" in m]


def test_lateral_warnings_reach_cfs_status_without_blocking():
    pkg = {"lateral_frame": {"status": {"warnings": ["IS 1893 7.6.4: the diaphragm is declared rigid but the analysis "
                                                     "gives flexible (ratio 4.26 vs 1.2)"]}}}
    st = G.design_status({}, pkg)
    assert any("declared rigid" in w for w in st["warnings"])
    assert not any("declared rigid" in r for r in st["reasons"])
