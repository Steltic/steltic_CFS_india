"""O3 (owner ruling 2026-09-26): the C06 framed-area check falls back to geometry.floor_area_m2 before the plan_x x
plan_y bounding box.  floor_area_m2 is the plan area of ONE framed level (number = every level, or {level: m2}; the
CFS gold cfgs declare it per floor, e.g. IN_CFS_Ex6 A_FLOOR = 1558 m2 'per floor'); a value above the bounding box
(a total over storeys) is refused; voids are not subtracted from it."""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

FULL = [[i, j] for i in range(3) for j in range(3)]
LPLAN = [p for p in FULL if p != [2, 2]]          # 12 x 8 m bounding box, cell (1, 1) missing: L-plan 72 m2 of 96 m2


def _cfg(present=None, **geo):
    g = {"plan_x_m": 12.0, "plan_y_m": 8.0, "heights_m": [3.0, 3.0]}
    g.update(geo)
    return {"geometry": g,
            "lateral_frame": {"NX": 2, "NY": 2, "bay_x_m": 6.0, "bay_y_m": 4.0,
                              "custom_build_module": "india_cfs_frame_build",
                              "col": "WPB200X200X50.92", "beam": "NPB300X165X39.88",
                              "gold": {"present": present or {"default": LPLAN}}}}


def test_lplan_bbox_fallback_fails_without_floor_area():
    import india_cfs_frame_build as FB
    errs = FB.framed_area_issues(_cfg())
    assert len(errs) == 2 and all("plan_x x plan_y" in m for _s, m in errs)      # 72 < 0.9 x 96 on both levels


def test_lplan_passes_with_only_geometry_floor_area():
    import india_cfs_frame_build as FB
    assert FB.framed_area_issues(_cfg(floor_area_m2=72.0)) == []                 # scalar: every level
    assert FB.framed_area_issues(_cfg(floor_area_m2={"1": 72.0, "2": 72.0})) == []
    assert FB.framed_area_issues(_cfg(floor_area_m2={1: 72.0, 2: 72.0})) == []


def test_bogus_small_framed_area_still_fails():
    import india_cfs_frame_build as FB
    lvl1 = [[0, 0], [1, 0], [0, 1], [1, 1]]                                        # level 1 frames one 24 m2 cell only
    errs = FB.framed_area_issues(_cfg({"default": LPLAN, "1": lvl1}, floor_area_m2=72.0))
    assert len(errs) == 1 and errs[0][0] == "ERROR"
    m = errs[0][1]
    assert m.startswith("level 1: framed floor area 24.0") and "geometry.floor_area_m2" in m
    assert "not a total over storeys" in m                                        # interpretation stated in src


def test_total_over_storeys_is_refused_and_gold_still_wins():
    import india_cfs_frame_build as FB
    errs = FB.framed_area_issues(_cfg(floor_area_m2=144.0))                       # 2 x 72: gross over the storeys
    assert len(errs) == 2 and all("exceeds the plan bounding box" in m and "ONE level" in m for _s, m in errs)
    c = _cfg(floor_area_m2=144.0)
    c["lateral_frame"]["gold"]["plan_area_m2"] = 72.0                             # gold.plan_area_m2 takes precedence
    assert FB.framed_area_issues(c) == []
    # a per-level dict naming one level only: the other level falls back to the bounding box
    errs = FB.framed_area_issues(_cfg(floor_area_m2={"1": 72.0}))
    assert len(errs) == 1 and errs[0][1].startswith("level 2:") and "plan_x x plan_y" in errs[0][1]
