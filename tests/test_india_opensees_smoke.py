"""Minimal India CFS OpenSees smoke: metric brief → kip-in + IS 811 section + eigen.

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

    p = S811.props("CWS80X80X3.15")
    assert p["A"] > 0 and p["Ix"] > 0

    p2 = CS.gross_props("CWS80X80X3.15")
    assert p2.get("_source") == "IS_811_1987"

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
    IU.apply_metric_geometry(cfg)
    assert abs(cfg["SX"] - 4.0 * IU.M_TO_IN) < 1e-6
    H = float(cfg["heights"][0])

    ops.wipe()
    ops.model("basic", "-ndm", 2, "-ndf", 3)
    A, E, I = float(p["A"]), 29500.0, float(p["Ix"])
    ops.node(1, 0.0, 0.0)
    ops.node(2, 0.0, H)
    ops.fix(1, 1, 1, 1)  # fix all 3 DOFs at base
    ops.geomTransf("Linear", 1)
    ops.element("elasticBeamColumn", 1, 1, 2, A, E, I, 1)
    ops.mass(2, 0.5, 0.5, 0.0)
    ops.wipeAnalysis()
    lam = ops.eigen("-fullGenLapack", 1)
    assert lam and float(lam[0]) > 0
    T1 = 2 * 3.141592653589793 / (float(lam[0]) ** 0.5)
    assert T1 > 0.0  # smoke only — mass is placeholder
