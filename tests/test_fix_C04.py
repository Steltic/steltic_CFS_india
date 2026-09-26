"""C04 (CFS-D-07): snow combinations appear when the snow load is declared under loads.snow (the documented key)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_basis as B   # noqa: E402


def _labels(plan, cfg):
    return {c["label"] for c in B.cfs_combinations(plan, cfg)}


def test_loads_snow_gives_dl_sl_rows():
    labs = _labels({}, {"loads": {"snow": 2.63}})
    assert "DL+SL" in labs and any(l.startswith("DL+SL+1.0") for l in labs)


def test_other_snow_sources_and_absence():
    assert "DL+SL" in _labels({}, {"snow": 1.2})
    assert "DL+SL" in _labels({"snow_summary": {"applicable": True}}, {})
    assert "DL+SL" not in _labels({}, {"loads": {"snow": 0.0}})
    assert "DL+SL" not in _labels({}, {})
