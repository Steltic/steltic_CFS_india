"""PEB (2026-10, owner decision D-T5): lapped (continuous) lipped-zed purlins and girts for the HR PEB golds.

* india_cfs_members.continuous_unit_effects: continuous beam on equal spans, laps at 2 EI -- checked against the
  textbook coefficients of 2- and 3-span continuous beams (no lap);
* is801_members: a lipped zed (LZ) bends only with a declared zed_basis (the C15 refusal stays the default) and
  buckles in compression about its minor principal axis (r_min);
* design_purlins(continuity='lapped') returns the lapped record (span, lap end, support, web checks)."""
import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_members as CM   # noqa: E402
import is801_members as M        # noqa: E402
import is811_sections as S       # noqa: E402

L = 7500.0


def test_two_spans_no_lap_textbook():
    ce = CM.continuous_unit_effects(2, L, 0.0)
    assert ce["M_support"] == pytest.approx(-L * L / 8.0, rel=1e-6)          # -wL^2/8
    assert ce["M_span_end"] == pytest.approx(9.0 / 128.0 * L * L, rel=1e-6)  # at 3L/8
    assert ce["R_end"] == pytest.approx(3.0 / 8.0 * L, rel=1e-6)
    assert ce["R_int"] == pytest.approx(10.0 / 8.0 * L, rel=1e-6)


def test_three_spans_no_lap_textbook():
    ce = CM.continuous_unit_effects(3, L, 0.0)
    assert ce["M_support"] == pytest.approx(-0.100 * L * L, rel=1e-3)
    assert ce["M_span_end"] == pytest.approx(0.080 * L * L, rel=1e-2)
    assert ce["M_span_int"] == pytest.approx(0.025 * L * L, rel=1e-2)


def test_laps_attract_moment_to_the_supports():
    a, b = CM.continuous_unit_effects(10, L, 0.0), CM.continuous_unit_effects(10, L, 600.0)
    assert b["M_support"] < a["M_support"] < 0                                   # stiffer laps: more hogging
    assert b["defl_max_per_EI"] < a["defl_max_per_EI"]
    assert -b["M_lap"] < -b["M_support"]                                          # lap end below the support moment
    assert all(isinstance(v, float) for k, v in b.items() if k.startswith(("M_", "V_", "R_")))


def test_lz_bending_needs_zed_basis():
    z = S.props("LZ230X75X20X2.55")
    assert M.bending_allowable(z, 240.0, 2000.0).get("found") is False          # C15 refusal stays the default
    b = M.bending_allowable(z, 240.0, 2000.0, zed_basis="sheeting through-fastened to the outer flange")
    assert b["Ma_Nmm"] > 0 and any("lipped zed" in n for n in b["notes"])


def test_lz_compression_about_the_minor_principal_axis():
    z = S.props("LZ230X75X20X2.55")
    r = M.compression_allowable(z, 240.0, 3000.0, 3000.0)
    assert r["KLr"] == pytest.approx(3000.0 / z["r_min"], rel=1e-9)           # r_min = r_v < r_y
    assert r["KLr"] > r["KLr_y"]


def _cfg_lapped():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex3")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    cfg = copy.deepcopy(Bx.build_cfg())
    cfg["load_plan"]["story_forces"] = {}
    pu = cfg["cfs_members"]["purlins"]
    pu.update(section="LZ230X75X20X2.55", continuity="lapped", n_spans=6, lap_mm=500.0,
              zed_basis="outer flange through-fastened to the sheeting; free flange held by the sag-rod line")
    return cfg


def test_lapped_purlin_record():
    rec = CM.design_purlins(_cfg_lapped(), "purlin")
    c = rec["continuity"]
    assert c["type"] == "lapped" and c["n_spans"] == 6 and c["lap_mm"] == 500.0
    assert c["coefficients_wL2"]["M_support"] < 0 < c["coefficients_wL2"]["M_span_end"]
    names = {r["name"].split(" (")[0] if "name" in r else r.get("check") for r in rec["checks"]}
    assert any("lap end" in str(n) for n in names) and any("interior support" in str(n) for n in names)
    assert isinstance(rec["DC"], float) and rec["DC"] > 0
