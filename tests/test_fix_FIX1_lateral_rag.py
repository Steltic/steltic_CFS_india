"""FIX1: the hot-rolled lateral sub-run (india_cfs_lateral.run_lateral -> hr_vendor_runner, job folder
<job>/lateral/<name>) must see the parent job's stored retrieval hits.  The vendored HR evidence gate (H30,
consistency.rag_evidence_issues) looks for <sub_root>/rag/<hit_file> containing the row's quote; the CFS retrieval row
names its hit as 'file'.  Before the fix the sub-run had no rag/ and no hit_file -> every found:true row was reported
'no stored rag/ hit' and the CFS Ex1 reference went PARTIAL."""
import importlib.util
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
import india_cfs_env  # noqa: E402,F401
import india_cfs_lateral as L  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex1")


def _hr_consistency():
    sp = importlib.util.spec_from_file_location("hr_vendor_consistency_fix1",
                                                os.path.join(india_cfs_env.VENDOR, "consistency.py"))
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod


def _ex1_cfg():
    sys.path.insert(0, FIX)
    sys.modules.pop("build_and_run", None)
    try:
        import build_and_run as Bx
        return Bx.build_cfg()
    finally:
        sys.path.remove(FIX)
        sys.modules.pop("build_and_run", None)


def test_hr_retrieval_rows_map_file_to_hit_file():
    rows = [{"query": "q", "quote": "Delhi IV 0.24", "found": True, "file": "rag/IS1893_annexE_zones.json"},
            {"query": "q2", "found": False},
            {"query": "q3", "found": True, "file": "x.json", "hit_file": "rag/y.json"}, "free text"]
    out = L.hr_retrieval_rows(rows)
    assert out[0]["hit_file"] == "IS1893_annexE_zones.json" and out[0]["found"] is True
    assert "hit_file" not in rows[0]                               # the caller's rows are not mutated
    assert out[1] == {"query": "q2", "found": False}
    assert out[2]["hit_file"] == "rag/y.json"                      # an explicit hit_file is kept
    assert out[3] == "free text" and len(out) == 4


def test_lateral_spec_retrieval_passes_hr_evidence_gate_with_copied_rag(tmp_path):
    cfg = _ex1_cfg()
    spec = L.build_hr_spec(cfg, "ex1_lateral")
    rows = spec["load_plan"]["retrieval"]
    assert rows and all(r.get("hit_file") for r in rows if r.get("found") is True)
    C = _hr_consistency()
    sub = tmp_path / "lateral" / "ex1_lateral"
    sub.mkdir(parents=True)
    # the bug: a sub-run folder without the parent's rag/ -> every found:true row is flagged
    bad = C.rag_evidence_issues({"retrieval": rows}, str(sub))
    assert len(bad) == sum(1 for r in rows if r.get("found") is True) and "no stored rag/ hit" in bad[0]
    n = L.copy_rag_hits(os.path.join(FIX, "rag"), str(sub))
    assert n == len(os.listdir(os.path.join(FIX, "rag")))
    assert C.rag_evidence_issues({"retrieval": rows}, str(sub)) == []
    # the gate is not weakened: a quote absent from the stored hit is still reported
    rows2 = [dict(rows[0], quote="Delhi V 0.36")]
    assert len(C.rag_evidence_issues({"retrieval": rows2}, str(sub))) == 1


def test_run_lateral_copies_parent_rag_into_sub_job(tmp_path, monkeypatch):
    cfg = _ex1_cfg()
    job = tmp_path / "JOB"
    shutil.copytree(os.path.join(FIX, "rag"), str(job / "rag"))
    seen = {}

    class _P:
        stdout, stderr = "", ""

    def fake_run(cmd, **kw):                                       # stand-in for the HR subprocess
        spec_path, jobs_root, name = cmd[2], cmd[3], cmd[4]
        seen["rag"] = sorted(os.listdir(os.path.join(jobs_root, name, "rag")))
        json.dump({"root": os.path.join(jobs_root, name)}, open(os.path.join(jobs_root, name, "lateral_result.json"), "w"))
        return _P()

    monkeypatch.setattr(L.subprocess, "run", fake_run)
    res = L.run_lateral(cfg, str(job / "lateral"), name="ex1_lateral")      # default rag_dir = <job>/rag
    assert seen["rag"] == sorted(os.listdir(os.path.join(FIX, "rag")))
    assert res["name"] == "ex1_lateral"
    spec = json.load(open(res["spec"]))
    assert all(r.get("hit_file") for r in spec["load_plan"]["retrieval"] if r.get("found") is True)
