"""C10 (CFS-A-14, CFS-D-06): mixed lateral systems ('SMF+SCBF', 'EBF+SMF') -- R = min over the components unless
R_x / R_y are declared (validated per direction), declared braced bays kept when SMF is a component, the package /
HR spec names the real system."""
import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_lateral as L   # noqa: E402


def test_resolve_mixed_system():
    assert L.resolve_system("III", "SMF+SCBF") == ("SMF+SCBF", 4.5, L.resolve_system("III", "SMF+SCBF")[2])
    s, R, cite = L.resolve_system("V", "EBF+SMF", 12.0)
    assert s == "EBF+SMF" and R == 5.0 and "min over the components" in cite
    with pytest.raises(L.LateralSystemError):
        L.resolve_system("V", "SMF+SCBF")                 # SCBF banned in Zone V
    with pytest.raises(L.LateralSystemError):
        L.resolve_system("IV", "SMF+SCBF", 18.0)          # SMRF h >= 15 m in Zone IV


def test_per_direction_R():
    r = L.resolve_system_full("III", "SMF+SCBF", 9.0, R_x=5.0, R_y=4.5, system_x="SMF", system_y="SCBF")
    assert r["R"] == 4.5 and r["R_x"] == 5.0 and r["R_y"] == 4.5
    with pytest.raises(L.LateralSystemError):
        L.resolve_system_full("III", "SMF+SCBF", 9.0, R_x=5.0)      # X system = both components -> Table 9 4.5
    assert L.resolve_system_full("III", "SCBF")["R_x"] == 4.5


def _cfg():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex1")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    return Bx.build_cfg()


def test_build_hr_spec_keeps_bays_for_mixed_system():
    cfg = _cfg()
    cfg["site"]["zone"], cfg["site"]["Z"] = "III", 0.16
    cfg["lateral_frame"]["system"] = "SMF+SCBF"
    cfg["lateral_frame"].pop("R", None)
    cfg["lateral_frame"]["braced_bays"] = [["X", 0, 0], ["Y", 0, 0]]
    cfg["lateral_frame"]["moment_lines"] = [["X", 2]]
    spec = L.build_hr_spec(cfg, "t")
    assert spec["system"] == "SMF+SCBF" and spec["R"] == 4.5
    assert spec["braced_bays"] == [["X", 0, 0], ["Y", 0, 0]] and spec["moment_lines"] == [["X", 2]]
    assert spec["load_plan"]["seismic_summary"]["system"] == "SMF+SCBF"
    c2 = copy.deepcopy(cfg); c2["lateral_frame"].update(system="SMF", braced_bays=[["X", 0, 0]])
    assert L.build_hr_spec(c2, "t")["braced_bays"] == []          # pure SMF: no braced bays
    c3 = copy.deepcopy(cfg); c3["lateral_frame"].update(R_x=5.0, system_x="SMF", system_y="SCBF")
    sp3 = L.build_hr_spec(c3, "t")
    assert sp3["R_x"] == 5.0 and sp3["R_y"] is None and sp3["system_x"] == "SMF"
    assert sp3["load_plan"]["seismic_summary"]["R_x"] == 5.0
