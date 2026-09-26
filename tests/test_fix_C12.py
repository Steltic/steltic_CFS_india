"""C12 (CFS-A-02, B-03, C-04, B-02, L-13, NEW-3): summaries carry value / limit / governing check; the literal-D/C rule
applies only to underived rows (tolerance, not exact float); lateral blocking reasons first with a count; CFS
consistency runs the vendored rag_evidence_issues on the CFS retrieval rows (file / quote)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import consistency as CC       # noqa: E402
import india_cfs_gates as G    # noqa: E402


def test_runner_governing_check():
    import importlib.util
    sp = importlib.util.spec_from_file_location("hr_vendor_runner_c12", os.path.join(ROOT, "steel_engine", "hr_vendor_runner.py"))
    RN = importlib.util.module_from_spec(sp); sp.loader.exec_module(RN)
    rows = [{"name": "bolt shear", "value": 650.0, "limit": 650.0, "dc": 1.0, "clause": "IS 800 10.3"},
            {"name": "slenderness", "value": 100.0, "limit": 250.0, "dc": 0.4}]
    g = RN._governing(rows)
    assert g["value"] == 650.0 and g["limit"] == 650.0 and g["governing_check"] == "bolt shear"
    assert RN._governing(rows, 0.4)["governing_check"] == "slenderness"          # the row the stored DC comes from


def test_literal_rule():
    pkg = {"lateral_frame": {"connections": [{"id": "c1", "DC": 1.0, "value": 650.0, "limit": 650.0, "governing_check": "x"}]}}
    assert CC._dc_issues(pkg) == []
    assert CC._dc_issues({"a": {"dc": 0.8000000000000002}})                        # no exact-float escape any more
    assert CC._dc_issues({"a": {"dc": 0.8}})
    assert CC._dc_issues({"a": {"dc": 0.8, "governing_check": "7.5.3 bearing"}}) == []   # derived summary
    assert CC._dc_issues({"a": {"dc": 0.81}}) == []


def test_lateral_reasons_blockers_first_with_count():
    reasons = ["member e%d: D/C %.2f > 1" % (i, 1.0 + i / 1000.0) for i in range(261)]
    reasons.append("IS 1893 Amd 2 Table 9 note: irregular building, RSA required (7.7.1)")
    out = G.lateral_issues({"lateral_frame": {"status": {"status": "partial", "reasons": reasons}}})
    assert "Amd 2" in out[0]
    assert any("similar" in x for x in out)                                        # per-element duplicates grouped
    many = ["reason kind %s" % chr(65 + i % 26) * (1 + i // 26) for i in range(100)]
    out2 = G.lateral_issues({"lateral_frame": {"status": {"status": "partial", "reasons": many}}})
    assert out2[-1].endswith("more (see lateral/STATUS.md)") and len(out2) == 61


def test_rag_evidence_checks_quotes(tmp_path):
    (tmp_path / "rag").mkdir()
    json.dump({"found": True, "query": "q", "hits": [{"text": "Hyderabad | 44 | Imphal | 47"}]}, open(tmp_path / "rag" / "a.json", "w"))
    good = {"load_plan": {"retrieval": [{"query": "Annex A", "found": True, "cite": "Vb 44 m/s", "file": "rag/a.json",
                                         "quote": "Hyderabad | 44"}]}}
    bad = {"load_plan": {"retrieval": [{"query": "Annex A", "found": True, "cite": "Vb 44 m/s", "file": "rag/a.json",
                                        "quote": "Hyderabad | 50"}]}}
    cite_only = {"load_plan": {"retrieval": [{"query": "Table 8", "found": True, "cite": "I = 1.5"}]}}
    assert CC.rag_evidence(str(tmp_path), good) == []
    assert CC.rag_evidence(str(tmp_path), bad)
    assert CC.rag_evidence(str(tmp_path), cite_only)                                # a cite string alone no longer passes
