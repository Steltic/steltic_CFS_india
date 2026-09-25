"""WP6: the JSON-declared custom frame builder (irregular plans / EBF links / moment lines) and the declared HR cfg keys
that hr_vendor_runner passes into the vendored HR engine for a CFS job's lateral frame."""
from __future__ import annotations
import os
import sys

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


def test_present_sets_xbays_and_per_level_loads():
    import hr_vendor_runner as RN
    import engine3d as E
    gold = {"present": {"default": [[i, j] for i in range(3) for j in range(3)], "2": [[i, j] for i in range(3) for j in range(3) if not (i == 2 and j == 2)]},
            "xbays": {"1-2": [["X", 0, 0], ["Y", 0, 0]]}, "brace_sec": {"1-2": "WPB200X200X50.92"}, "gravity_base": "fixed",
            "col_sec": {"lateral": {"1-2": "WPB200X200X50.92"}, "gravity": {"1-2": "WPB200X200X42.26"}},
            "beam_sec": {"floor_X": "NPB300X165X39.88", "floor_Y": "NPB200X130X27.37", "roof_X": "NPB300X165X39.88", "roof_Y": "NPB200X130X27.37"}}
    cfg, esm = RN.build_cfg(_spec(gold, hr_cfg_extra={"L_by_level": {"1": 4.0}, "D_by_level": {"1": 3.0}}))
    assert cfg["L_by_level"] == {1: 4.0} and cfg["D_by_level"] == {1: 3.0}      # int keys after the JSON hop
    assert cfg["custom_build"] is not None and cfg["braces"] is None
    info = E.build(cfg, "Linear")
    assert len(info["present"][2]) == 8 and len(info["present"][1]) == 9        # corner column removed at the roof
    braces = [e for e in info["ele"] if e[1] == "brace"]
    assert len(braces) == 2 * 2 * 2                                               # 2 X-braced bays x 2 diagonals x 2 storeys
    assert info["bases"][(0, 0)] == "fixed"
    assert esm["seismic_summary"]["W_kN"] > 0


def test_ebf_links_and_moment_lines():
    import hr_vendor_runner as RN
    import engine3d as E
    gold = {"ebf_bays": {"1-2": [["X", 0, 0]]}, "e_link_mm": 900.0, "ebf_beam_sec": {"X": {"1-2": "NPB400X180X66.31"}},
            "ebf_link_sec": {"X": {"1-2": "NPB400X180X66.31"}}, "ebf_brace_sec": {"1-2": "WPB200X200X50.92"},
            "moment_lines": [["Y", 2]], "gravity_base": "pinned",
            "col_sec": {"lateral": {"1-2": "WPB250X250X73.15"}, "gravity": {"1-2": "WPB200X200X42.26"}},
            "beam_sec": {"floor_X": "NPB300X165X39.88", "floor_Y": "NPB300X165X39.88", "roof_X": "NPB300X165X39.88", "roof_Y": "NPB300X165X39.88"}}
    cfg, _ = RN.build_cfg(_spec(gold, system="EBF", R=5.0))
    info = E.build(cfg, "Linear")
    assert len(info["links"]) == 2 and all(abs(l["e_mm"] - 900.0) < 1e-9 for l in info["links"])
    assert cfg["sway_frame"] is True and cfg["brace_config"] == "chevron"
    assert info["bases"][(1, 1)] == "pinned" and info["bases"][(0, 0)] == "fixed"    # SFRS column fixed, gravity column pinned


def test_builder_module_load_does_not_shadow_hr_modules(tmp_path):
    """The runner runs the HR engine only; loading the CFS builder by name must not put steel_engine on sys.path
    (the CFS preflight / pipeline would shadow the HR ones)."""
    import hr_vendor_runner as RN
    gold = {"col_sec": {"lateral": {"1-2": "WPB200X200X50.92"}, "gravity": {"1-2": "WPB200X200X42.26"}},
            "beam_sec": {"floor_X": "NPB300X165X39.88", "floor_Y": "NPB200X130X27.37", "roof_X": "NPB300X165X39.88", "roof_Y": "NPB200X130X27.37"},
            "xbays": {"1-2": [["X", 0, 0]]}, "brace_sec": {"1-2": "WPB200X200X50.92"}}
    before = list(sys.path)
    RN.build_cfg(_spec(gold))
    assert os.path.join(ROOT, "steel_engine") not in [p for p in sys.path if p not in before]


def test_split_level_stepped_bases():
    """Split-level site: the north half (j = 2) is founded on the grade at level 1; its columns start there (fixed), the level-1
    floor plate is the south half only, and the grade nodes stay outside the level-1 diaphragm constraint."""
    import hr_vendor_runner as RN
    import engine3d as E
    south = [[i, j] for i in range(3) for j in range(2)]
    full = [[i, j] for i in range(3) for j in range(3)]
    gold = {"present": {"0": full, "1": south, "2": full}, "stepped_bases": {"1": [[i, 2] for i in range(3)]}, "omit_beams_at": {"1": [[i, 2] for i in range(3)]},
            "xbays": {"1-2": [["X", 0, 0]]}, "brace_sec": {"1-2": "WPB200X200X50.92"}, "gravity_base": "fixed",
            "col_sec": {"lateral": {"1-2": "WPB200X200X50.92"}, "gravity": {"1-2": "WPB200X200X42.26"}},
            "beam_sec": {"floor_X": "NPB300X165X39.88", "floor_Y": "NPB200X130X27.37", "roof_X": "NPB300X165X39.88", "roof_Y": "NPB200X130X27.37"}}
    cfg, _ = RN.build_cfg(_spec(gold))
    info = E.build(cfg, "Linear")
    assert len(info["present"][1]) == 6 and len(info["present"][2]) == 9
    assert info["bases"][(0, 2)] == "fixed@L1" and info["bases"][(0, 0)] == "fixed"
    cols = [e for e in info["ele"] if e[1] == "col"]
    assert len(cols) == 9 + 9                      # storey 1: south half + the three retained basement stubs; storey 2: all nine
    beams1 = [e for e in info["ele"] if e[1] == "beam" and e[3] // 100000 == 1]
    assert len(beams1) == 3 + 4                    # level 1: south plate only (3 X beams + 4 Y beams), none into the grade nodes
