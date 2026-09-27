"""RR-BUG-6 (CFS part): wind_story_forces resolves Ka per direction with the direction's own frame tributary area;
a single declared site.Ka_corpus_hit is not applied to a direction whose Table 4 Ka is higher (report: Ka 0.9467 for
A = 18 m2 used at A = 15.75 m2 where Table 4 gives 0.9617), and element Ka (purlins / studs) is area-checked too."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_env  # noqa: E402,F401
import india_cfs_lateral as L  # noqa: E402
import india_cfs_members as CM  # noqa: E402
import india_wind_tables as WT  # noqa: E402  (vendored HR)


def _cfg():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex1")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    return Bx.build_cfg()


def test_single_declared_ka_checked_per_direction():
    cfg = _cfg()
    H = max(cfg["geometry"]["heights_m"])
    lf = cfg["lateral_frame"]
    # bay_y > bay_x case of the report: X frames spaced bay_y, Y frames spaced bay_x
    lf["bay_y_m"], lf["bay_x_m"] = 6.0, 5.25
    A_x, A_y = 6.0 * H, 5.25 * H
    ka_x_t4, ka_y_t4 = WT.ka_for_area_m2(A_x)["Ka"], WT.ka_for_area_m2(A_y)["Ka"]
    assert ka_y_t4 > ka_x_t4
    cfg["site"]["Ka_corpus_hit"] = {"found": True, "Ka": ka_x_t4, "cite": "Table 4 at the X-frame area"}
    ws, _f = L.wind_story_forces(cfg)
    assert ws["Ka_X"] == pytest.approx(ka_x_t4) and ws["Ka_Y"] == pytest.approx(ka_y_t4)     # Y not below Table 4
    assert ws["Ka_area_check_Y"]["ok"] is False and "unconservative" in ws["Ka_note_Y"]
    assert ws["Ka"] == pytest.approx(ka_y_t4) and ws["Ka_area_m2"] == pytest.approx(A_y)
    # the HR preflight on the forwarded summary accepts both directions
    errs = [m for s, m in WT.wind_findings({"load_plan": {"wind_summary": ws}}) if s == "ERROR" and "Ka" in m]
    assert errs == []
    # per-direction declaration is honoured where it is not below Table 4
    cfg["site"]["Ka_corpus_hit"] = {"found": True, "Ka_x": 0.99, "Ka_y": 1.0, "cite": "EOR"}
    ws2, _ = L.wind_story_forces(cfg)
    assert ws2["Ka_X"] == 0.99 and ws2["Ka_Y"] == 1.0


def test_element_ka_is_area_checked():
    cfg = _cfg()
    cfg["site"]["Ka_corpus_hit"] = {"found": True, "Ka": 0.9467, "cite": "frame Ka"}
    mw = CM.member_pd(cfg, 0.4 * 3.0, 12.0, "wall", "general")
    assert mw["Ka"] == 1.0                    # 1.2 m2 element: Table 4 1.0, the frame Ka is not applied
