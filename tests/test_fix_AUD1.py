"""AUD-1 (gold audit M5, engine observation 1): the CFS consistency evidence rule (consistency.rag_evidence ->
vendored HR rag_evidence_issues) no longer accepts a quote-less found:true row because an unrelated stored hit contains
the digits: the hit must record the row's own query ('# RAG query:' header / JSON query) or carry hit_file + quote."""
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import india_cfs_env  # noqa: E402,F401
import consistency as CC  # noqa: E402
import india_cfs_gates as G  # noqa: E402


def _hit(path, query, body):
    path.write_text("# RAG query: %s\n# collection: x  |  hits: 1\n\n## Hit 1\n%s\n" % (query, body))


def test_cfs_evidence_rule_needs_the_rows_own_hit(tmp_path):
    (tmp_path / "rag").mkdir()
    _hit(tmp_path / "rag" / "ta.txt", "7.3.6 partition walls seismic weight", "Ta = 0.075 h^0.75")
    row = {"query": "Table 2 imposed loads on roofs", "found": True, "cite": "IS 875-2 Table 2 roof 0.75 kN/m2",
           "file": "rag/ta.txt"}
    iss = CC.rag_evidence(str(tmp_path), {"load_plan": {"retrieval": [dict(row)]}})
    assert len(iss) == 1 and "attach hit_file + quote" in iss[0]
    _hit(tmp_path / "rag" / "roof.txt", "Table 2 imposed loads on roofs", "access not provided: 0.75 kN/m2")
    assert CC.rag_evidence(str(tmp_path), {"load_plan": {"retrieval": [dict(row, file="rag/roof.txt")]}}) == []
