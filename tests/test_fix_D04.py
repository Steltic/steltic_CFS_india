"""D04 (CFS-B-12, A-05, B-08, C-13, D-16, A-18): the CFS contract documents the advanced cfg keys agents need, and no
fixture / contract cites span/240 (the IS 800 Table 6 industrial row) for a floor of an ordinary building."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_advanced_keys_documented():
    txt = open(os.path.join(ROOT, "contract", "AGENT_START.md"), encoding="utf-8").read()
    assert "## Advanced cfg keys" in txt
    for key in ("custom_build_module", "gold", "hr_cfg_extra", "diaphragm_depth_X_m", "diaphragm_span_X_m", "diaphragm_lines_X",
                "wind_exposure", "reentrant_lines_X", "composite_scope", "construction_stage", "snow_summary", "Cpe_leeward",
                "Cpe_windward", "member_wind", "deflection_key_roof", "building_type", "SMF+SCBF", "R_x", "R_y", "sfrs_base",
                "col_sec_by_line", "beam_sec_by_line", "max_beam_span_m", "free_nodes", "plan_area_m2", "voids_m2",
                "opening_ratio", "eave_struts", "headers", "point_loads", "embedment_capacity_N", "partition_seismic_kNm2",
                "D_by_level", "quote"):
        assert key in txt, key


def test_build_hr_spec_keys_are_documented():
    """Every lateral_frame key read by build_hr_spec is named in the contract."""
    src = open(os.path.join(ROOT, "steel_engine", "india_cfs_lateral.py"), encoding="utf-8").read()
    body = src[src.index("def build_hr_spec"):src.index("def run_lateral")]
    keys = set(re.findall(r'lf(?:\.get\(|\[)"(\w+)"', body))
    txt = open(os.path.join(ROOT, "contract", "AGENT_START.md"), encoding="utf-8").read()
    missing = sorted(k for k in keys if k not in txt)
    assert not missing, missing


def test_no_floor_span_240():
    for p in ("contract/CFS_REFERENCE.md", "contract/DESIGN_EG_INDEX.md", "tests/fixtures/IN_CFS_Ex1/build_and_run.py",
              "tests/fixtures/IN_CFS_Ex5/build_and_run.py"):
        for line in open(os.path.join(ROOT, p), encoding="utf-8"):
            if re.search(r"(span|L)/240", line, re.I) and re.search(r"floor", line, re.I):
                raise AssertionError("%s: %s" % (p, line.strip()))
