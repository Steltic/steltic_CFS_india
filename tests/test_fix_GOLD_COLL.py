"""GOLD-COLL (IN_CFS_Ex9, lead decision 2): lateral_frame.diaphragm_by_level (per-level rigid / flexible labels, e.g.
a composite podium rigid under flexible CFS floors) reaches the HR run, whose flexible levels accumulate the deck shear
along each braced line into the braced bays (IS 1893 (Part 1):2016 7.6.4 tributary distribution)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_lateral as L   # noqa: E402


def _cfg():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex1")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    return Bx.build_cfg()


def test_diaphragm_by_level_reaches_the_hr_cfg():
    import hr_vendor_runner as RN
    cfg = _cfg()
    cfg["lateral_frame"]["diaphragm"] = "flexible"
    cfg["lateral_frame"]["diaphragm_by_level"] = {"1": "rigid"}
    spec = L.build_hr_spec(cfg, "t")
    assert spec["diaphragm_by_level"] == {"1": "rigid"}
    hr, _ = RN.build_cfg(spec)
    assert hr["diaphragm_by_level"] == {"1": "rigid"} and hr["diaphragm"] == "flexible"
    import india_diaphragm as D                           # vendored HR engine
    if hasattr(D, "diaphragm_labels"):                    # hr_vendor re-synced with HR GOLD-COLL
        labels, errs = D.diaphragm_labels(hr)
        assert not errs and labels[1] == "rigid" and all(v == "flexible" for k, v in labels.items() if k > 1)
    # absent -> not passed (backward compatible)
    cfg["lateral_frame"].pop("diaphragm_by_level")
    hr2, _ = RN.build_cfg(L.build_hr_spec(cfg, "t"))
    assert "diaphragm_by_level" not in hr2
