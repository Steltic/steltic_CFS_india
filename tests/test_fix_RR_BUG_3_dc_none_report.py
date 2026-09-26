"""RR-BUG-3: an all-CFS portal with a mezzanine but no mezzanine.beams (C07 row with DC None) crashed the report step
(india_cfs_pipeline._portal_viewer '%.2f' % None) before the consistency check and the final status (CFS Ex5 pass 1).
The viewer / report show 'not evaluated' and the job is PARTIAL with a reason naming what to declare."""
import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_env  # noqa: E402,F401


def _bx():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex5")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    return Bx


def test_viewer_formats_none_dc_as_not_evaluated(tmp_path):
    import india_cfs_pipeline as CP
    pkg = {"portal_frame_geometry": {"nodes": {"a": [0, 0], "b": [0, 5000], "c": [12000, 6000]},
                                     "elements": [["a", "b", "col"], ["b", "c", "raf"]], "supports": {"a": 1},
                                     "n_frames": 5, "spacing_mm": 6000.0},
           "cfs_members": [{"role": "column", "section": "2xCLR250X80X25X5", "n_ply": 2, "DC": 0.939},
                           {"role": "mezzanine beam", "section": None, "DC": None}]}
    p = CP._portal_viewer("t", pkg, str(tmp_path / "v.html"))
    html = open(p).read()
    assert "not evaluated" in html and "0.94" in html and "not declared" in html


def test_portal_without_mezzanine_beams_reports_partial_with_reason(tmp_path):
    Bx = _bx()
    cfg = copy.deepcopy(Bx.build_cfg())
    assert cfg.get("mezzanine") and cfg["mezzanine"].pop("beams")
    import india_cfs_pipeline as CP
    out = CP.design_and_report(Bx.NAME, cfg, outdir=str(tmp_path / "job"), do_report=True)   # TypeError before
    assert out["status"] == "partial"
    why = [r for r in out["reasons"] if "mezzanine-beam" in r or "mezzanine beam" in r]
    assert why and any("declare cfg['mezzanine']['beams']" in r for r in why)
    root = tmp_path / "job"
    assert "not evaluated" in (root / "viewer_3d.html").read_text()
    assert "not evaluated" in (root / "report.html").read_text()
    st = (root / "STATUS.md").read_text()
    assert "PARTIAL" in st and "mezzanine']['beams']" in st
