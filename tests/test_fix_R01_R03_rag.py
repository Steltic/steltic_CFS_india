"""R01-R03 (+ R04 rewording, L-08 part) in the CFS standards search tool.

R01  a server / transport error is never "genuinely absent"; not_tabulated and document_not_in_corpus
     pass through.
R02  an exact clause / table hit is final regardless of count (NEW-2: exact-table replies are
     recognised by table_id / matched / type); an explicit type sends the id, not the sentence
     (NEW-4); rung 5 only when everything else is empty, honest provenance; unit tokens are not ids.
R03  rag/ evidence files keyed on collection|clause|type|query + content hash, never overwritten.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from steltic import config                     # noqa: E402
from steltic.job_tools import JobWorkspace     # noqa: E402

C1893 = "engineering_standards_IS1893"


class Wire(JobWorkspace):
    def __init__(self, reply, jobs=None):
        if jobs is not None:
            JobWorkspace.__init__(self, jobs)
        else:
            self.building = False
        self.reply = reply
        self.wire = []
        self._aliases_cache = {}

    def log(self, tool, detail="", result=""):
        return {}

    def _corpus_status(self):
        return {}

    def _rag_post(self, query, collection, clause="", chapter="", type_="", want_commentary=False, neighbors=None):
        self.wire.append({"query": query, "collection": collection, "clause": clause, "type": type_})
        return self.reply(query, collection, clause, type_, len(self.wire)), None


def _hits(n, **kw):
    return [dict({"id": f"h{i}", "source": "IS_1893_Part_1_2016", "text": f"hit {i}"}, **kw) for i in range(n)]


def _run(reply, query, coll=C1893, **kw):
    config.RAG_API_URL = "http://stub"
    ws = Wire(reply)
    return ws, ws.search_engineering_standards(query, coll, **kw)


def test_exact_table_reply_recognised_by_table_id_and_final():
    # the old adapter reports a table hit's section as the citing clause (Table 10 -> 7.3.5)
    def reply(q, c, cl, t, n):
        if cl == "Table 10":
            return {"results": _hits(1, section="7.3.5", table_id="10")}
        return {"results": [{"id": "x", "source": "IS_9595_1996", "section": "Table 10"}] if not c else []}
    ws, out = _run(reply, "Table 10", type="exact_table", doc="IS_1893_Part_1_2016")
    assert len(ws.wire) == 1, ws.wire
    assert out["results"][0]["table_id"] == "10" and "FOUND ONLY" not in str(out.get("note"))


def test_exact_reply_recognised_by_matched_or_type():
    ws, out = _run(lambda q, c, cl, t, n: {"results": _hits(1), "type": "exact_table", "found": True},
                   "Table 10", type="exact_table", doc="IS_1893_Part_1_2016")
    assert len(ws.wire) == 1 and out.get("exact_ids") == ["Table 10"]


def test_explicit_type_sends_the_clause_not_the_sentence():
    ws, out = _run(lambda q, c, cl, t, n: {"results": _hits(1, section="7.3.6") if cl == "7.3.6" else []},
                   "7.3.6 weight of partition walls", type="exact_section", clause="7.3.6")
    assert ws.wire[0]["clause"] == "7.3.6" and len(ws.wire) == 1
    assert "thin" not in out


def test_explicit_type_lifts_the_id_out_of_a_sentence():
    ws, out = _run(lambda q, c, cl, t, n: {"results": _hits(1, table_id="6") if cl == "Table 6" else []},
                   "Table 6 importance factor I", type="exact_table")
    assert ws.wire[0]["clause"] == "Table 6"
    ws, out = _run(lambda q, c, cl, t, n: {"results": []}, "weight of partition walls 7.3.6", type="exact_section")
    assert ws.wire[0]["clause"] == "7.3.6"


def test_unit_tokens_are_not_clause_ids():
    ws = Wire(lambda *a: {"results": []})
    assert ws._query_ids("Steel 78.5 kN/m3 unit weight") == []
    assert ws._query_ids("IS 875-3 basic wind speed 50 m/s") == []


def test_rung5_only_when_everything_else_is_empty():
    ws, out = _run(lambda q, c, cl, t, n: {"results": _hits(1) if c else _hits(5, source="IS_875_Part_3_2015")},
                   "Delhi zone factor")
    assert all(w["collection"] == C1893 for w in ws.wire), ws.wire


def test_rung5_hits_from_the_asked_document_lead():
    def reply(q, c, cl, t, n):
        if c:
            return {"results": []}
        return {"results": [{"id": "a", "source": "IS_875_Part_3_2015"}, {"id": "b", "source": "IS_1893_Part_1_2016"}]}
    ws, out = _run(reply, "Delhi")
    assert out["results"][0]["source"] == "IS_1893_Part_1_2016"
    assert "FOUND ONLY" not in out["note"] and out["also_found_in"] == ["IS_875_Part_3_2015"]


def test_server_error_is_retried_and_never_reported_absent():
    ws, out = _run(lambda q, c, cl, t, n: {"results": [], "note": "server error: SQLite objects created in a thread"},
                   "snow load", coll="engineering_standards_IS875_P4")
    assert out["not_found_kind"] == "server_error" and out["found"] is None
    assert "not evidence of absence" in out["note"] and "genuinely absent" not in out["note"]
    assert ws.wire[0] == ws.wire[1], "an errored rung is retried once"


def test_not_tabulated_passes_through():
    note = "Town not listed in IS 1893 (Part 1) Annex E or IS 875 (Part 3) Annex A: use the zone map"
    ws, out = _run(lambda q, c, cl, t, n: {"results": [], "not_tabulated": True, "note": note}, "Noida")
    assert out["not_found_kind"] == "not_tabulated" and out["note"] == note


def test_document_not_in_corpus_passes_through():
    ws, out = _run(lambda q, c, cl, t, n: {"results": [], "note": "IS_456_2000 is not in the corpus"},
                   "development length anchor bolt", coll="engineering_standards_IS456")
    assert out["not_found_kind"] == "document_not_in_corpus"
    assert all(w["collection"] for w in ws.wire), "no rung 5 once the corpus says the document is absent"


def test_evidence_files_are_never_overwritten(tmp_path):
    config.RAG_API_URL = "http://stub"
    ws = Wire(lambda q, c, cl, t, n: {"results": [{"id": c, "source": c, "text": "Chennai " + c}] * 3}, jobs=tmp_path)
    ws.new_activity_log("b1")
    a = ws.search_engineering_standards("Chennai", C1893, type="fts")
    first = (tmp_path / "b1" / a["saved"]).read_text()
    b = ws.search_engineering_standards("Chennai", "engineering_standards_IS875_P3", type="fts")
    assert a["saved"] != b["saved"]
    assert (tmp_path / "b1" / a["saved"]).read_text() == first


def test_reworded_uses_word_boundaries():
    ws = Wire(lambda *a: {"results": []})
    ws._aliases_cache = {"synonym_groups": [["load combination", "combination of loads"],
                                            ["partial safety factor", "gamma_m0", "gamma_m1"]]}
    assert not any("combinationss" in x for x in ws._reworded("load combinations IS 875 Part 5"))
    assert ws._reworded("partial safety factors for loads") == []
