"""X01 (CFS side): the IS 1893 Table 5(ii) (Amd 2) flexible-diaphragm run of the vendored HR engine on the CFS
lateral frame -- lateral_frame keys reach the HR cfg, the JSON frame builder's rigid diaphragms are replaced by the
deck membrane for L-plans (free / grade nodes stay out of the deck), and the diaphragm rows carry the 7.6.4 record.

The engine tests need hr_vendor re-synced from steltic_india (india_flexible_diaphragm, X01); they skip until then."""
from __future__ import annotations
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
sys.path.insert(0, os.path.join(ROOT, "steel_engine", "hr_vendor"))

STIFF = {"type": "metal_deck", "topping_t_mm": 75.0, "fck_MPa": 25.0, "source": "EOR: 75 mm M25 topping on the deck",
         "cite": "EOR deck schedule; Ec per IS 456 6.2.3.1"}
SECS = {"col_sec": {"lateral": {"1-2": "WPB200X200X50.92"}, "gravity": {"1-2": "WPB200X200X42.26"}},
        "beam_sec": {"floor_X": "NPB300X165X39.88", "floor_Y": "NPB300X165X39.88", "roof_X": "NPB300X165X39.88",
                     "roof_Y": "NPB300X165X39.88"}, "brace_sec": {"1-2": "WPB200X200X50.92"}}


def _spec(gold, **kw):
    spec = {"name": "t_x01", "system": "SCBF", "R": 4.5, "Z": 0.16, "I": 1.0, "zone": "III", "soil": "II", "NX": 3, "NY": 3,
            "bay_x_m": 5.0, "bay_y_m": 5.0, "heights_m": [3.0, 3.0], "D_floor": 1.5, "D_roof": 1.0, "L_floor": 2.0, "Lr": 0.75,
            "clad": 0.5, "col": "WPB200X200X50.92", "beam": "NPB300X165X39.88", "brace": "WPB200X200X50.92", "braced_bays": [],
            "base": "fixed", "occupancy": {"use": "residential", "persons": 40},
            "load_plan": {"jurisdiction": "india", "retrieval": []}, "gold": gold, "custom_build_module": "india_cfs_frame_build"}
    spec.update(kw)
    return spec


def _Lgold(**extra):
    # L-plan: the 2 x 2 bay corner of a 3 x 3 bay grid removed at every level (nodes i, j >= 2)
    L2 = [[i, j] for i in range(4) for j in range(4) if not (i >= 2 and j >= 2)]
    g = dict(SECS, present={"default": L2}, gravity_base="pinned",
             xbays={"1-2": [["X", 0, 0], ["X", 0, 3], ["Y", 0, 0], ["Y", 0, 2], ["Y", 3, 0], ["X", 2, 0]]})
    g.update(extra)
    return g


def test_spec_keys_reach_the_hr_cfg():
    import hr_vendor_runner as RN
    cfg, _ = RN.build_cfg(_spec(_Lgold(), diaphragm_stiffness=STIFF, flexible_diaphragm_analysis=True))
    assert cfg["diaphragm_stiffness"] == STIFF and cfg["flexible_diaphragm_analysis"] is True
    cfg2, _ = RN.build_cfg(_spec(_Lgold()))
    assert "diaphragm_stiffness" not in cfg2 and "flexible_diaphragm_analysis" not in cfg2


def test_build_hr_spec_passes_the_lateral_frame_keys():
    src = open(os.path.join(ROOT, "steel_engine", "india_cfs_lateral.py"), encoding="utf-8").read()
    body = src[src.index("def build_hr_spec"):src.index("def run_lateral")]
    for k in ("diaphragm_stiffness", "flexible_diaphragm_analysis", "flexible_diaphragm_eor"):
        assert 'lf.get("%s")' % k in body


def test_diaphragm_rows_carry_the_flexible_764_record():
    import india_cfs_lateral as L
    lat = {"diaphragm_7_6_4": {"flexible_run": {"levels": {"X": [{"level": 1, "delta_max_from_chord_mm": 0.4,
                                                                    "avg_storey_drift_mm": 2.0, "ratio": 0.2,
                                                                    "limit": 1.2, "classification": "rigid"}]}}}}
    assert L._flexible_764(lat, "X", 1)["ratio"] == 0.2
    assert L._flexible_764(lat, "Y", 1) is None and L._flexible_764({}, "X", 1) is None


@pytest.fixture(scope="module")
def FD():
    pytest.importorskip("openseespy.opensees")
    return pytest.importorskip("india_flexible_diaphragm", reason="hr_vendor not yet re-synced with the HR X01 engine")


def test_lplan_flexible_run_on_the_json_builder(FD):
    import hr_vendor_runner as RN
    import engine3d as E
    cfg, _ = RN.build_cfg(_spec(_Lgold(), diaphragm_stiffness=STIFF))
    E.clear_caches()
    assert FD.trigger(cfg)[0] is True                                         # 2 of 3 bays = 67 % > 15 %
    f = FD.rsa_flexible(cfg)
    assert f["deck"][1]["panels"] == 5 and f["deck"][2]["panels"] == 5       # 9 bays less the 2 x 2 corner
    r = E.rsa_analysis(cfg)
    for d in ("X", "Y"):
        assert f[d]["VB_scaled_N"] == pytest.approx(r[d]["VB_scaled_N"], rel=1e-6)
        assert f[d]["mass_participation"] >= 0.90
    # a very stiff deck reproduces the rigid-diaphragm periods of the CFS builder's model
    cfg["diaphragm_stiffness"] = {"type": "custom", "G_eff_MPa": 1.0e6, "t_mm": 150.0, "source": "test: stiff deck"}
    fs = FD.rsa_flexible(cfg)
    for a, b in zip([m["T"] for m in r["modes"][:3]], [m["T"] for m in fs["modes"][:3]]):
        assert b == pytest.approx(a, rel=0.03)


def test_split_level_grade_nodes_stay_out_of_the_deck(FD):
    """Split-level site (as test_wp6_frame_build): the level-1 plate is the south half only -- the grade nodes of the
    north half are fixed and outside the level-1 diaphragm, so they get no deck panel."""
    import hr_vendor_runner as RN
    south = [[i, j] for i in range(3) for j in range(2)]
    full = [[i, j] for i in range(3) for j in range(3)]
    gold = dict(SECS, present={"0": full, "1": south, "2": full}, stepped_bases={"1": [[i, 2] for i in range(3)]},
                omit_beams_at={"1": [[i, 2] for i in range(3)]}, xbays={"1-2": [["X", 0, 0], ["Y", 0, 0]]},
                gravity_base="fixed")
    cfg, _ = RN.build_cfg(_spec(gold, NX=2, NY=2, bay_x_m=6.0, bay_y_m=4.0, diaphragm_stiffness=STIFF))
    m = FD.build_flexible(cfg, "Linear", 2)
    assert m["deck"][1]["panels"] == 2 and m["deck"][2]["panels"] == 4
