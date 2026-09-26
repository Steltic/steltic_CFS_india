"""X06 (E11, HR-B-20): india_cfs_frame_build is a thin wrapper over the shared HR frame builder (steel_engine/frame_build.py,
loaded from hr_vendor by path).  Parity: the same model (node / element counts, bases, links, framed areas) and the same
linear static response and first period as the pre-X06 CFS module on the frame_build test specs (reference numbers
recorded from india_cfs_frame_build at 62a8245 before the change)."""
from __future__ import annotations
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
sys.path.insert(0, os.path.join(ROOT, "steel_engine", "hr_vendor"))


def _spec(gold, **kw):
    spec = {"name": "t_frame", "system": "SCBF", "R": 4.5, "Z": 0.16, "I": 1.0, "zone": "III", "soil": "II", "NX": 2, "NY": 2,
            "bay_x_m": 6.0, "bay_y_m": 4.0, "heights_m": [3.0, 3.0], "D_floor": 1.5, "D_roof": 1.0, "L_floor": 2.0, "Lr": 0.75, "clad": 0.5,
            "col": "WPB200X200X50.92", "beam": "NPB300X165X39.88", "brace": "WPB200X200X50.92", "braced_bays": [], "base": "fixed",
            "occupancy": {"use": "residential", "persons": 40}, "load_plan": {"jurisdiction": "india", "retrieval": []},
            "gold": gold, "custom_build_module": "india_cfs_frame_build"}
    spec.update(kw)
    return spec


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

CASES = {
 "xbays": (dict(present={"default": FULL, "2": [p for p in FULL if p != [2, 2]]}, xbays={"1-2": [["X", 0, 0], ["Y", 0, 0]]},
               brace_sec={"1-2": "WPB200X200X50.92"}, gravity_base="fixed", col_sec=COLS, beam_sec=BEAMS), {}),
 "ebf_moment": (dict(ebf_bays={"1-2": [["X", 0, 0]]}, e_link_mm=900.0, ebf_beam_sec={"X": {"1-2": "NPB400X180X66.31"}},
               ebf_link_sec={"X": {"1-2": "NPB400X180X66.31"}}, ebf_brace_sec={"1-2": "WPB200X200X50.92"}, moment_lines=[["Y", 2]],
               gravity_base="pinned", col_sec={"lateral": {"1-2": "WPB250X250X73.15"}, "gravity": {"1-2": "WPB200X200X42.26"}},
               beam_sec={k: "NPB300X165X39.88" for k in BEAMS}), dict(system="EBF", R=5.0)),
 "stepped": (dict(present={"0": FULL, "1": [[i, j] for i in range(3) for j in range(2)], "2": FULL}, stepped_bases={"1": [[i, 2] for i in range(3)]},
               omit_beams_at={"1": [[i, 2] for i in range(3)]}, xbays={"1-2": [["X", 0, 0]]}, brace_sec={"1-2": "WPB200X200X50.92"},
               gravity_base="fixed", col_sec=COLS, beam_sec=BEAMS), {}),
 "sfrs_line": (dict(xbays={"1-2": [["X", 1, 0], ["Y", 2, 0]]}, brace_sec={"1-2": "WPB200X200X50.92"}, col_sec=COLS, beam_sec=BEAMS,
               sfrs_base={"X0": "pinned", "Y2": "fixed", "2,0": "fixed"}), {}),
 "sections": (dict(xbays={"1-2": [["X", 0, 0]]}, brace_sec={"1-2": "WPB200X200X50.92"}, col_sec=COLS,
               beam_sec=dict(BEAMS, floor_X={"1": "NPB400X180X66.31"}), beam_sec_by_line={"Y0": "NPB300X165X39.88"},
               col_sec_by_line={"X2": {"1-2": "WPB250X250X73.15"}}), {}),
 "multilevel": (dict(present={"default": FULL, "0": FULL, "1": [p for p in FULL if p not in ([1, 0], [1, 1])]}, xbays={"1-2": [["Y", 0, 0]]},
               brace_sec={"1-2": "WPB200X200X50.92"}, col_sec=COLS, beam_sec=BEAMS, max_beam_span_m=12.0), {}),
 "free": (dict(xbays={"1-2": [["X", 0, 0]]}, brace_sec={"1-2": "WPB200X200X50.92"}, col_sec=COLS, beam_sec=BEAMS, free_nodes={"2": [[2, 2]]},
               xcoords_m=[0.0, 5.0, 12.0], ycoords_m=[0.0, 4.5, 8.0]), {}),
}

REF = {"xbays": {"nodes": 28, "eles": 47, "links": 0, "framed": {"1": 96.0, "2": 72.0}, "disp": [10.085475154, -11.879935672, -0.002488187], "T1": 0.97897132, "W_kN": 473.768, "bases": {"0,1": "fixed", "1,2": "fixed", "2,1": "fixed", "0,0": "fixed", "1,1": "fixed", "2,0": "fixed", "0,2": "fixed", "2,2": "fixed", "1,0": "fixed"}}, "ebf_moment": {"nodes": 33, "eles": 50, "links": 2, "framed": {"1": 96.0, "2": 96.0}, "disp": [104.240398643, 155.365519712, -0.025728872], "T1": 1.27022979, "W_kN": 505.449, "bases": {"0,1": "pinned", "1,2": "pinned", "2,1": "fixed", "0,0": "fixed", "1,1": "pinned", "2,0": "fixed", "0,2": "pinned", "2,2": "fixed", "1,0": "fixed"}}, "stepped": {"nodes": 29, "eles": 41, "links": 0, "framed": {"1": 48.0, "2": 96.0}, "disp": [9.897580201, 58.168640718, -0.002262138], "T1": 0.80193763, "W_kN": 366.658, "bases": {"0,1": "fixed", "1,2": "fixed@L1", "2,1": "fixed", "0,0": "fixed", "1,1": "fixed", "2,0": "fixed", "0,2": "fixed@L1", "2,2": "fixed@L1", "1,0": "fixed"}}, "sfrs_line": {"nodes": 29, "eles": 50, "links": 0, "framed": {"1": 96.0, "2": 96.0}, "disp": [2434.866194085, 3654.192371813, -0.608907498], "T1": 6.37167211, "W_kN": 502.425, "bases": {"0,1": "pinned", "1,2": "pinned", "2,1": "fixed", "0,0": "pinned", "1,1": "pinned", "2,0": "fixed", "0,2": "pinned", "2,2": "pinned", "1,0": "pinned"}}, "sections": {"nodes": 29, "eles": 46, "links": 0, "framed": {"1": 96.0, "2": 96.0}, "disp": [741.51249498, -126.615450882, -0.18506421], "T1": 4.86182538, "W_kN": 509.946, "bases": {"0,1": "pinned", "1,2": "pinned", "2,1": "pinned", "0,0": "fixed", "1,1": "pinned", "2,0": "pinned", "0,2": "pinned", "2,2": "pinned", "1,0": "fixed"}}, "multilevel": {"nodes": 27, "eles": 40, "links": 0, "framed": {"1": 0.0, "2": 96.0}, "disp": [529.271706038, 986.722478338, 0.164328268], "T1": 6.94965895, "W_kN": 248.615, "bases": {"0,1": "fixed", "1,2": "pinned", "2,1": "pinned", "0,0": "fixed", "1,1": "pinned", "2,0": "pinned", "0,2": "pinned", "2,2": "pinned", "1,0": "pinned"}}, "free": {"nodes": 29, "eles": 46, "links": 0, "framed": {"1": 96.0, "2": 96.0}, "disp": [1171.248905704, -415.311834364, -0.280781223], "T1": 5.89705319, "W_kN": 493.246, "bases": {"0,1": "pinned", "1,2": "pinned", "2,1": "pinned", "0,0": "fixed", "1,1": "pinned", "2,0": "pinned", "0,2": "pinned", "2,2": "pinned", "1,0": "fixed"}}}


def test_wrapper_uses_the_shared_hr_module():
    import india_cfs_frame_build as FB
    assert os.path.samefile(FB.SHARED_PATH, os.path.join(ROOT, "steel_engine", "hr_vendor", "frame_build.py"))
    for name in ("make_gold", "attach", "frame_build", "framed_area_m2", "_cells_area", "_rng_pick", "_xy"):
        assert getattr(FB, name) is getattr(FB._FB, name), name
    assert callable(FB.framed_area_issues)


@pytest.mark.parametrize("case", sorted(CASES))
def test_parity_with_pre_x06_builder(case):
    import hr_vendor_runner as RN
    import engine3d as E
    import openseespy.opensees as ops
    g, kw = CASES[case]
    ref = REF[case]
    cfg, esm = RN.build_cfg(_spec(g, **kw))
    assert cfg["custom_build"].__module__ == "hr_vendor_frame_build"
    info = E.build(cfg, "Linear")
    assert len(ops.getNodeTags()) == ref["nodes"] and len(ops.getEleTags()) == ref["eles"]
    assert {"%d,%d" % k: v for k, v in info["bases"].items()} == ref["bases"]
    assert len(info["links"]) == ref["links"]
    assert {str(k): v for k, v in info["framed_area_m2"].items()} == pytest.approx(ref["framed"])
    assert esm["seismic_summary"]["W_kN"] == pytest.approx(ref["W_kN"], rel=1e-9)
    ops.constraints("Transformation"); ops.numberer("RCM"); ops.system("UmfPack"); ops.test("NormDispIncr", 1e-9, 50)
    ops.algorithm("Linear"); ops.integrator("LoadControl", 1.0); ops.analysis("Static")
    ops.timeSeries("Linear", 1); ops.pattern("Plain", 1, 1)
    for k in range(1, info["NF"] + 1):
        ops.load(E.mtag(k), 1.0e5, 0.5e5, 0.0, 0.0, 0.0, 1.0e7)
    assert ops.analyze(1) == 0
    roof = [ops.nodeDisp(E.mtag(info["NF"]), d) for d in (1, 2, 6)]
    assert roof == pytest.approx(ref["disp"], rel=1e-6, abs=1e-9)
    T1 = 6.283185307179586 / ops.eigen("-fullGenLapack", 1)[0] ** 0.5
    assert T1 == pytest.approx(ref["T1"], rel=1e-6)
