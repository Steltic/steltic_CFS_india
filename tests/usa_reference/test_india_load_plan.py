"""India CFS load_plan: refuse ASCE hardcoding; require RAG-backed combinations."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "steel_engine"))

import india_loads as IL
import pytest


def test_missing_load_plan_errors():
    findings = IL.validate_load_plan({})
    assert any(s == "ERROR" for s, _ in findings)


def test_rag_backed_plan_builds_cases():
    cfg = {
        "seis": {"SDS": 0.1},
        "load_plan": {
            "jurisdiction": "india",
            "retrieval": [
                {"stem": "IS_875_Part_2_1987", "query": "imposed loads residential",
                 "found": True, "cite": "Table 1"},
                {"stem": "IS_1893_Part_1_2016", "query": "seismic zone factor",
                 "found": True, "cite": "Table 3"},
                {"stem": "IS_801_1975", "query": "member design",
                 "found": True, "cite": "5.2"},
            ],
            "combinations": [
                {"label": "1.5DL+1.5LL", "fD": 1.5, "fL": 1.5, "fLr": 0.0,
                 "lateral": {}, "cite": "IS RAG"},
                {"label": "1.2DL+1.2EQ_X", "fD": 1.2, "fL": 0.0, "fLr": 0.0,
                 "lateral": {"1": [10.0, 0.0, 0.0]}, "cite": "IS 1893"},
            ],
        },
    }
    findings = IL.validate_load_plan(cfg)
    assert not any(s == "ERROR" for s, _ in findings)
    cases = IL.cases_from_load_plan(cfg)
    assert len(cases) == 2
    assert cases[0][0] == "1.5DL+1.5LL"
    assert cases[1][4][1][0] == 10.0
    dicts = IL.combo_dicts_from_load_plan(cfg)
    assert dicts[0]["label"] == "1.5DL+1.5LL"


def test_asce_flag_forbidden():
    cfg = {
        "use_asce7_engine_loads": True,
        "load_plan": {
            "jurisdiction": "india",
            "retrieval": [
                {"stem": "IS_875_Part_1_2026", "query": "dead", "found": True, "cite": "1"},
                {"stem": "IS_1893_Part_1_2016", "query": "Z", "found": True, "cite": "3"},
            ],
            "combinations": [
                {"label": "1.5D", "fD": 1.5, "fL": 0, "fLr": 0, "cite": "x"},
            ],
        },
    }
    findings = IL.validate_load_plan(cfg)
    assert any("use_asce7_engine_loads" in m for s, m in findings if s == "ERROR")


def test_wind_story_forces_disabled():
    import cfs_pipeline as CP
    with pytest.raises(RuntimeError, match="disabled|load_plan"):
        CP.wind_story_forces({"wind": {"V": 100, "exposure": "C"}, "stories": 1,
                              "heights_ft": [10], "plan_ft": [40, 30]}, "X")


def test_engine3d_wind_forces_disabled():
    import engine3d as E
    with pytest.raises(RuntimeError, match="disabled|load_plan"):
        E.wind_forces({"wind": {"V": 100, "exposure": "C"}, "heights": [120],
                       "NX": 1, "NY": 1, "SX": 300, "SY": 300}, "X")


def test_preflight_requires_load_plan():
    import preflight as PF
    findings = PF.check({"heights": [120, 120], "SX": 240, "SY": 240, "system": "wsp_shearwall",
                         "seis": {"SDS": 0.5, "SD1": 0.2, "R": 6.5, "Cd": 4, "Ie": 1.0},
                         "model": {"bases": "pinned", "joints": "pinned", "gravity": "framed"},
                         "diaphragm": "flexible"})
    assert any("load_plan" in m for s, m in findings if s == "ERROR")
