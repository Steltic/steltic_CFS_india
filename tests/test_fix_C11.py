"""C11 (CFS-A-15, B-04, C-03, D-04, B-14, D-15, C-05 a-d) and C06 (CFS-C-05 e): the JSON-declared frame builder honours
lateral_frame.base / gold.sfrs_base per line, storey-ranged and per-line sections, multi-level columns, consecutive-
node beams with a max span, free nodes; the framed-area check refuses a model that drops part of a declared plate."""
from __future__ import annotations
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
sys.path.insert(0, os.path.join(ROOT, "steel_engine", "hr_vendor"))

FULL = [[i, j] for i in range(3) for j in range(3)]
BEAMS = {"floor_X": "NPB300X165X39.88", "floor_Y": "NPB200X130X27.37", "roof_X": "NPB300X165X39.88", "roof_Y": "NPB200X130X27.37"}
COLS = {"lateral": {"1-2": "WPB200X200X50.92"}, "gravity": {"1-2": "WPB200X200X42.26"}}


def _spec(gold, **kw):
    spec = {"name": "t_frame", "system": "SCBF", "R": 4.5, "Z": 0.16, "I": 1.0, "zone": "III", "soil": "II", "NX": 2, "NY": 2,
            "bay_x_m": 6.0, "bay_y_m": 4.0, "heights_m": [3.0, 3.0], "D_floor": 1.5, "D_roof": 1.0, "L_floor": 2.0, "Lr": 0.75, "clad": 0.5,
            "col": "WPB200X200X50.92", "beam": "NPB300X165X39.88", "brace": "WPB200X200X50.92", "braced_bays": [], "base": "fixed",
            "occupancy": {"use": "residential", "persons": 40}, "load_plan": {"jurisdiction": "india", "retrieval": []},
            "gold": gold, "custom_build_module": "india_cfs_frame_build"}
    spec.update(kw)
    return spec


def _build(gold, **kw):
    import hr_vendor_runner as RN
    import engine3d as E
    cfg, _ = RN.build_cfg(_spec(gold, **kw))
    return E.build(cfg, "Linear")


def test_sfrs_base_pinned_and_per_line():
    g = {"xbays": {"1-2": [["X", 1, 0], ["Y", 2, 0]]}, "brace_sec": {"1-2": "WPB200X200X50.92"}, "col_sec": COLS, "beam_sec": BEAMS}
    info = _build(g, base="pinned")
    assert info["bases"][(1, 0)] == "pinned" and info["bases"][(2, 1)] == "pinned"      # lateral_frame.base honoured
    assert _build(g)["bases"][(1, 0)] == "fixed"                                        # default fixed (unchanged)
    info = _build(dict(g, sfrs_base={"X0": "pinned", "Y2": "fixed", "2,0": "fixed"}))
    assert info["bases"][(1, 0)] == "pinned" and info["bases"][(2, 1)] == "fixed" and info["bases"][(2, 0)] == "fixed"
    with pytest.raises(ValueError):
        _build(dict(g, sfrs_base={"X0": "pinned", "Y2": "fixed"}))                     # (2, 0) on both lines, conflicting


def test_storey_ranged_and_per_line_sections():
    g = {"xbays": {"1-2": [["X", 0, 0]]}, "brace_sec": {"1-2": "WPB200X200X50.92"}, "col_sec": COLS,
         "beam_sec": dict(BEAMS, floor_X={"1": "NPB400X180X66.31"}),
         "beam_sec_by_line": {"Y0": "NPB300X165X39.88"}, "col_sec_by_line": {"X2": {"1-2": "WPB250X250X73.15"}}}
    info = _build(g)
    beams = [e for e in info["ele"] if e[1] == "beam"]
    lvl = lambda e: e[3] // 100000
    import engine3d as E
    bx1 = [e for e in beams if lvl(e) == 1 and e[2] == "NPB400X180X66.31"]
    assert len(bx1) == 6                                                   # the 6 X beams of level 1 (storey-ranged group)
    assert not [e for e in beams if lvl(e) == 2 and e[2] == "NPB400X180X66.31"]
    y0 = [e for e in beams if lvl(e) == 1 and e[3] % 100000 // 100 == 0 and e[4] % 100000 // 100 == 0]
    assert len(y0) == 2 and all(e[2] == "NPB300X165X39.88" for e in y0)  # line Y0 override (floor_Y is NPB200)
    cols = [e for e in info["ele"] if e[1] == "col"]
    assert sum(1 for e in cols if e[2] == "WPB250X250X73.15") == 3 * 2     # the 3 columns of y-line 2, both storeys


def test_multilevel_column_and_consecutive_beams():
    lvl1 = [p for p in FULL if p not in ([1, 0], [1, 1])]                 # high-bay: (1, 0) and (1, 1) absent at level 1
    g = {"present": {"default": FULL, "0": FULL, "1": lvl1}, "xbays": {"1-2": [["Y", 0, 0]]}, "brace_sec": {"1-2": "WPB200X200X50.92"},
         "col_sec": COLS, "beam_sec": BEAMS}
    info = _build(g)
    cols = [e for e in info["ele"] if e[1] == "col"]
    import engine3d as E
    through = [e for e in cols if e[3] == E.ntag(1, 0, 0) and e[4] == E.ntag(1, 0, 2)]
    assert len(through) == 1 and len(cols) == 7 * 2 + 2                   # 7 two-storey stacks + 2 full-height columns
    b1 = [e for e in info["ele"] if e[1] == "beam" and e[3] // 100000 == 1]
    assert not [e for e in b1 if {e[3], e[4]} == {E.ntag(0, 0, 1), E.ntag(2, 0, 1)}]       # 12 m > the 6 m bay: no beam
    info2 = _build(dict(g, max_beam_span_m=12.0))
    b1 = [e for e in info2["ele"] if e[1] == "beam" and e[3] // 100000 == 1]
    assert [e for e in b1 if {e[3], e[4]} == {E.ntag(0, 0, 1), E.ntag(2, 0, 1)}]
    assert info["framed_area_m2"][1] == pytest.approx(0.0) and info["framed_area_m2"][2] == pytest.approx(96.0)


def test_free_nodes_builds():
    g = {"xbays": {"1-2": [["X", 0, 0]]}, "brace_sec": {"1-2": "WPB200X200X50.92"}, "col_sec": COLS, "beam_sec": BEAMS,
         "free_nodes": {"2": [[2, 2]]}}
    info = _build(g)
    assert len(info["present"][2]) == 9


def test_framed_area_check():
    import india_cfs_frame_build as FB
    lvl1 = [[0, 0], [1, 0], [0, 1], [1, 1]]                               # only one 6 x 4 cell framed at level 1
    cfg = {"geometry": {"plan_x_m": 12.0, "plan_y_m": 8.0, "heights_m": [3.0, 3.0]},
           "lateral_frame": {"NX": 2, "NY": 2, "bay_x_m": 6.0, "bay_y_m": 4.0, "custom_build_module": "india_cfs_frame_build",
                             "col": "WPB200X200X50.92", "beam": "NPB300X165X39.88",
                             "gold": {"present": {"default": FULL, "1": lvl1}}}}
    errs = FB.framed_area_issues(cfg)
    assert len(errs) == 1 and errs[0][0] == "ERROR" and errs[0][1].startswith("level 1: framed floor area 24.0")
    cfg["lateral_frame"]["gold"]["plan_area_m2"] = {"1": 24.0, "2": 96.0}
    assert FB.framed_area_issues(cfg) == []
    cfg["lateral_frame"]["gold"].pop("plan_area_m2")
    cfg["geometry"]["voids_m2"] = {"1": 70.0}
    assert FB.framed_area_issues(cfg) == []                               # 24 >= 0.9 x (96 - 70)
