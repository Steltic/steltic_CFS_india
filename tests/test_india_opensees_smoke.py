"""Minimal India CFS OpenSees smoke: metric brief → N-mm + IS 811 section + eigen.

Requires project venv with openseespy (CPython <3.13). Skip cleanly if unavailable.
Does NOT invent design loads — placeholder mass only; load_plan RAG gate is separate.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "steel_engine"))
sys.path.insert(0, str(ROOT / "steltic"))

openseespy = pytest.importorskip(
    "openseespy.opensees", reason="openseespy not installed in this interpreter"
)


def test_india_cfs_metric_is811_eigen_smoke():
    import openseespy.opensees as ops
    import india_units as IU
    import is811_sections as S811
    import cfs_sections as CS
    import engine3d as eng

    IU.activate_si()
    p = S811.props("CWS80X80X3.15")
    assert p["A"] > 500 and p["Ix"] > 0
    assert p.get("_units") == "mm"

    p2 = CS.gross_props("CWS80X80X3.15")
    assert p2.get("_source") == "IS_811_1987"
    assert p2["A"] > 500

    cfg = {
        "name": "IN_CFS_smoke_2storey",
        "units": "metric",
        "NX": 1,
        "NY": 1,
        "bay_x": 4.0,
        "bay_y": 4.0,
        "story_heights": [3.0, 3.0],
        "jurisdiction": "india",
    }
    IU.apply_si_geometry(cfg)
    assert abs(cfg["SX"] - 4000.0) < 1e-6
    assert cfg["units"] == "N-mm"
    assert eng.unit_system() == "N-mm"
    H = float(cfg["heights"][0])

    ops.wipe()
    ops.model("basic", "-ndm", 2, "-ndf", 3)
    A, E, I = float(p["A"]), eng.E, float(p["Ix"])
    ops.node(1, 0.0, 0.0)
    ops.node(2, 0.0, H)
    ops.fix(1, 1, 1, 1)
    ops.geomTransf("Linear", 1)
    ops.element("elasticBeamColumn", 1, 1, 2, A, E, I, 1)
    ops.mass(2, 0.5, 0.5, 0.0)  # tonne-ish placeholder
    ops.wipeAnalysis()
    lam = ops.eigen("-fullGenLapack", 1)
    assert lam and float(lam[0]) > 0
    T1 = 2 * 3.141592653589793 / (float(lam[0]) ** 0.5)
    assert T1 > 0.0
