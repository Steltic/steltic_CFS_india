"""AUD-4 (gold audit M3): the lateral-frame anchorage findings (asserted capacity without a derivation, concrete
breakout not delegated) are CFS preflight WARNs; the derived bond form and a delegated breakout item clear them."""
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import india_cfs_env  # noqa: E402,F401
import india_cfs_gates as G  # noqa: E402


LF = {"system": "SCBF", "diaphragm": "rigid", "diaphragm_7_6_4": {"declared": "rigid", "plan_aspect_ratio": 1.5},
      "connections": {"column_base": {"default": {"anchors": {"n_total": 4, "n_tension": 2, "d_mm": 30, "grade": "8.8"},
                                                  "embedment": {"capacity_N": 169646.4, "source": "EOR bond",
                                                                "cite": "IS 456 26.2.1.1 (EOR)"}}}}}


def test_cfs_preflight_warns_anchorage():
    w = G.audit_warnings({"lateral_frame": dict(LF)})
    msgs = [m for s, m in w if s == "WARN"]
    assert any("asserted per-anchor" in m for m in msgs) and any("delegated_design" in m for m in msgs)
    lf2 = dict(LF, diaphragm_stiffness={"type": "custom", "Gd_kN_per_m": 2500, "source": "EOR", "cite": "test"})
    lf2["connections"] = {"column_base": {"default": {"anchors": {"n_total": 4, "n_tension": 2, "d_mm": 30, "grade": "8.8",
                                                                  "embedment": {"method": "bond", "tau_bd_MPa": 1.2,
                                                                                "bar": "plain", "L_mm": 1500.0,
                                                                                "source": "EOR", "cite": "IS 456"}}}}}
    deleg = [{"item": "pedestals and anchor breakout", "criteria": "cone / group breakout per base"}]
    assert G.audit_warnings({"lateral_frame": lf2, "delegated_design": deleg}) == []
