"""C05 (CFS-C-06, CFS-B-06): declared storey wind W_X / W_Y (with a cite) survives build_hr_spec; per-level exposed
face width / height (geometry.wind_exposure) for mixed-height buildings."""
import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_lateral as L   # noqa: E402


def _cfg():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex1")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    return Bx.build_cfg()


def test_declared_w_x_survives():
    cfg = _cfg()
    cfg["load_plan"]["story_forces"] = {"W_X": {"1": [10.0, 0, 0], "2": [11.0, 0, 0], "3": [12.0, 0, 0], "4": [7.0, 0, 0]}}
    cfg["load_plan"]["story_forces_units"] = "kN"
    cfg["load_plan"]["wind_story_forces_cite"] = "IS 875-3 7.3.1 by hand, mixed-height faces (EOR calc W-01)"
    spec = L.build_hr_spec(cfg, "t")
    sf = spec["load_plan"]["story_forces"]
    assert sf["W_X"]["2"][0] == pytest.approx(11000.0)                       # kN -> N, not overwritten
    assert sf["W_Y"]["1"][1] > 0                                             # the undeclared direction is generated
    src = spec["load_plan"]["wind_summary"]["story_forces_source"]
    assert src["W_X"].startswith("declared") and src["W_Y"].startswith("IS 875-3")
    c2 = copy.deepcopy(cfg); c2["load_plan"].pop("wind_story_forces_cite")
    with pytest.raises(L.LateralSystemError):
        L.build_hr_spec(c2, "t")


def test_rerun_regenerates_own_forces():
    cfg = _cfg()
    spec = L.build_hr_spec(cfg, "t")
    cfg["load_plan"]["story_forces"] = spec["load_plan"]["story_forces"]
    cfg["load_plan"]["wind_summary"] = spec["load_plan"]["wind_summary"]
    spec2 = L.build_hr_spec(cfg, "t")                                        # no cite needed: our own forces
    assert spec2["load_plan"]["story_forces"]["W_X"] == spec["load_plan"]["story_forces"]["W_X"]


def test_wind_exposure_per_level():
    cfg = _cfg()
    ws0, f0 = L.wind_story_forces(cfg)
    cfg["geometry"]["wind_exposure"] = {"4": {"width_X_m": 4.0, "height_m": 3.0}}
    ws1, f1 = L.wind_story_forces(cfg)
    Ly = cfg["geometry"]["plan_y_m"]
    assert f1["W_X"]["4"][0] == pytest.approx(f0["W_X"]["4"][0] * (4.0 / Ly) * (3.0 / 1.5), rel=1e-9)
    assert f1["W_X"]["3"][0] == pytest.approx(f0["W_X"]["3"][0])
    assert f1["W_Y"]["4"][1] == pytest.approx(f0["W_Y"]["4"][1] * 2.0)       # only the height is declared for Y


def test_ka_per_direction_uses_bay_normal_to_wind():
    cfg = _cfg()
    lf = cfg["lateral_frame"]; H = max(cfg["geometry"]["heights_m"])
    ws, _ = L.wind_story_forces(cfg)
    assert ws["Ka_area_X_m2"] == pytest.approx(float(lf["bay_y_m"]) * H)
    assert ws["Ka_area_Y_m2"] == pytest.approx(float(lf["bay_x_m"]) * H)
    assert ws["Ka"] == max(ws["Ka_X"], ws["Ka_Y"])
