"""India CFS P1: C5 IS 811 retrieval plans, C6 IS 800 ban, S2 drift preflight."""
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "steel_engine"))
sys.path.insert(0, str(ROOT / "steltic"))

import india_is811_retrieval as R811
import india_cfs_gates as ICG
import preflight as PF


def _base_cfg(**extra):
    cfg = {
        "system": "wsp_shearwall",
        "stories": 4,
        "heights": [3600, 3600, 3600, 3600],
        "SX": 6000, "SY": 5000,
        "units": "N-mm",
        "jurisdiction": "india",
        "drift_limit": 0.004,
        "seis": {"SDS": 0.24, "SD1": 0.14, "R": 3.0, "Cd": 1.0, "Ie": 1.0},
        "model": {"bases": "pinned", "joints": "pinned", "gravity": "framed"},
        "diaphragm": "flexible",
        "R_source": "explicit",
        "R_cite": "EOR CFS gap",
        "R_cfs_table9_found": False,
        "wall_vn_plf_asd": 480.0,
        "wall_vn_source": "manufacturer",
        "wall_vn_cite": "Acme WSP Table B",
        "load_plan": {
            "jurisdiction": "india",
            "retrieval": [
                {"stem": "IS_875_Part_3_2015", "query": "wind", "found": True, "cite": "7.2"},
                {"stem": "IS_1893_Part_1_2016", "query": "Table 9 R", "found": True, "cite": "Table 9"},
            ],
            "combinations": [
                {"label": "1.5D", "fD": 1.5, "fL": 0, "fLr": 0, "cite": "IS"},
            ],
        },
        "lines_x": [object()],
    }
    cfg.update(extra)
    return cfg


# ---- C5 ----

def test_c5_seed_clr_plan_has_exact_table_and_sections():
    plan = R811.seed_is811_retrieval_plan("CLR100X50X15X2")
    assert len(plan) >= R811.MIN_EXACT_LOOKUPS
    types = {(r["type"], str(r["query"])) for r in plan}
    assert ("exact_table", "6") in types
    assert ("exact_section", "7") in types
    assert ("exact_section", "7.2.3") in types
    amd = [r for r in plan if "Amd1" in r.get("stem", "") or "Amd1" in r.get("collection", "")]
    assert amd, "Amd1 check must be seeded"
    ok, advice = R811.plan_is_rich_enough(plan)
    assert ok, advice


def test_c5_thin_plan_fails_richness():
    thin = [{"stem": "IS_811_1987", "type": "fts", "query": "cold formed"}]
    ok, advice = R811.plan_is_rich_enough(thin)
    assert ok is False
    assert "C5" in advice
    expanded = R811.expand_thin_plan(thin, "CLR100X50X15X2")
    ok2, _ = R811.plan_is_rich_enough(expanded)
    assert ok2 is True


def test_c5_amd1_honest_empty():
    # Cover-page style FTS hit must not become found:true for property deltas
    fake = {
        "found": True,
        "hits": [{
            "found": True, "kind": "fts",
            "section_id": "spec-page:IS_811_1987_Amd1_2011:standard:1",
            "table_id": "", "title": "amendment cover",
        }],
        "results": [{
            "found": True, "kind": "fts",
            "section_id": "spec-page:IS_811_1987_Amd1_2011:standard:1",
            "table_id": "", "title": "amendment cover",
        }],
    }
    out = R811.amd1_honest_result(fake, purpose="is811_amd1_property_delta")
    assert out["found"] is False
    assert out["amd1_property_delta_found"] is False
    assert out.get("results") == []
    assert "found:false" in (out.get("note") or "").lower() or "found:false" in str(out)


def test_c5_parse_label():
    info = R811.parse_is811_label("CLR100X50X15X2")
    assert info["type"] == "CLR"
    assert info["table"] == "6"
    assert info["in_catalog"] is True


# ---- C6 ----

def test_c6_is800_banned_without_purpose():
    ok, msg = ICG.gate_is800_query(
        collection="engineering_standards_IS800", doc="IS_800_2007", purpose="")
    assert ok is False
    assert "C6" in msg


def test_c6_is800_allowlisted_sfrs_gap():
    ok, msg = ICG.gate_is800_query(
        collection="engineering_standards_IS800", doc="IS_800_2007",
        purpose="sfrs_gap_found_false")
    assert ok is True
    assert "allowlisted" in msg.lower() or "C6" in msg


def test_c6_is801_not_caught_as_is800():
    ok, msg = ICG.gate_is800_query(
        collection="engineering_standards_IS801", doc="IS_801_1975", purpose="")
    assert ok is True
    assert msg == ""


def test_c6_retrieval_log_errors_without_purpose():
    cfg = _base_cfg(load_plan={
        "jurisdiction": "india",
        "retrieval": [
            {"stem": "IS_875_Part_3_2015", "query": "wind", "found": True, "cite": "7.2"},
            {"stem": "IS_1893_Part_1_2016", "query": "Table 9", "found": True, "cite": "Table 9"},
            {"stem": "IS_800_2007", "query": "Table 4", "found": True, "cite": "Table 4",
             "purpose": ""},
        ],
        "combinations": [{"label": "1.5D", "fD": 1.5, "fL": 0, "fLr": 0, "cite": "IS"}],
    })
    findings = ICG.validate_is800_retrieval(cfg)
    assert any(s == "ERROR" and "IS 800" in m for s, m in findings)


def test_c6_refusal_payload_and_gate():
    """Banned IS 800 yields refused found:false payload; allowlisted purpose opens gate."""
    out = ICG.is800_refusal_payload(
        collection="engineering_standards_IS800", purpose="", query="Table 4")
    assert out.get("refused") is True
    assert out.get("found") is False
    assert out.get("results") == []
    assert "C6" in (out.get("note") or "")

    ok, _ = ICG.gate_is800_query(collection="engineering_standards_IS800",
                                 doc="IS_800_2007", purpose="document_absence")
    assert ok is True

    # Search tool wires the same gate (source-level check; no RAG network needed)
    src = (ROOT / "steltic" / "job_tools.py").read_text(encoding="utf-8")
    assert "gate_is800_query" in src
    assert "is800_refusal_payload" in src


# ---- S2 ----

def test_s2_india_preflight_accepts_004_not_asce_rc():
    """Ie=1.5 with drift_limit=0.004 must NOT fire ASCE Table 12.12-1 RC IV ERROR."""
    cfg = _base_cfg()
    cfg["seis"]["Ie"] = 1.5
    cfg["drift_limit"] = 0.004
    findings = PF.check(cfg)
    errs = [m for s, m in findings if s == "ERROR"]
    assert not any("12.12-1" in m for m in errs)
    assert not any("0.010" in m and "RC IV" in m for m in errs)


def test_s2_india_preflight_rejects_025_scaffold():
    cfg = _base_cfg(drift_limit=0.025)
    findings = PF.check(cfg)
    assert any(s == "ERROR" and "0.025" in m or (s == "ERROR" and "12.12-1" in m)
               for s, m in findings)
    assert any(s == "ERROR" and "0.004" in m for s, m in findings)


def test_s2_report_still_strips_025():
    import pytest
    pytest.importorskip("matplotlib")
    import report as R
    ch = R._chapters({"jurisdiction": "india", "load_plan": {"jurisdiction": "india"}})
    blob = " ".join(ch[8][1]) if not isinstance(ch[8][1], str) else ch[8][1]
    assert "0.004" in blob
    assert "0.025" not in blob
