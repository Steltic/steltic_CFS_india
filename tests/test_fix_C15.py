"""C15: lipped zed (LZ) bending -- the Sxc expression had identical branches, so a zed got a single-axis x-x Fb with
no principal-axis treatment.  Until principal-axis bending is implemented the engine refuses LZ in bending (found:false,
ok None) and every caller reports the row as not evaluated instead of crashing or passing it."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import is811_sections as S   # noqa: E402
import is801_members as M    # noqa: E402


def test_lz_bending_refused():
    z = S.props("LZ230X75X20X2.55")
    b = M.bending_allowable(z, 240.0, 1500.0)
    assert b["found"] is False and b["ok"] is None and b["Ma_Nmm"] is None and "principal-axis" in b["note"]
    c = M.combined_67(z, 240.0, 1000.0, 1.0e6, 3000.0, 3000.0, 1500.0)
    assert c["ok"] is None and c["dc"] is None and "checks" not in c


def test_channel_bending_unchanged():
    c = S.props("CLR100X50X15X2")
    b = M.bending_allowable(c, 240.0, 1000.0)
    assert b["ok"] is True and b["Sxc_cm3"] == c["Ix"] / 1e4 / (c["h"] / 20.0)


def test_lz_purlin_row_not_evaluated():
    import india_cfs_members as CM
    cfg = {"cfs_members": {"Fy_MPa": 240.0, "joists": {"section": "LZ230X75X20X2.55", "spacing_mm": 400.0, "span_mm": 3000.0}},
           "loads": {"D_floor": 1.0, "L_floor": 2.0}, "load_plan": {}}
    rec = CM.design_joists(cfg)
    rows = [r for r in rec["checks"] if r["check"].startswith("6.1/6.2/6.3")]
    assert rows and all(r["ok"] is None for r in rows) and rec["ok"] is None
