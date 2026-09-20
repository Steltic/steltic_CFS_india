"""WP3.6 -- the assembled agent contract is India-only: US strings appear only inside explicit ban statements, the
worked reference is the pytest-asserted Ex1 / Ex5 pair, the driver's completion gate defers to india_cfs_gates."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from steltic import contract  # noqa: E402

US = re.compile(r"\b(AISI|S100|S240|S400|ASCE|AISC|LRFD|SDPWS|SFIA|ksi|kip|kips|plf|psf|SDS|SD1|hold-?down|W-shape|A992|"
                r"600S162-54|wsp_shearwall|strap-braced|SBMF)\b")
BAN = re.compile(r"refus|fail|never|not (a|the) design basis|\bNOT\b|not loaded|not ingested|no basis|foreign|usa_reference|"
                 r"banned|do not|no sheathed|there are no|is not|are not", re.I)


def _paragraphs(text):
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def test_system_prompt_mentions_us_bases_only_to_ban_them():
    sp = contract.system_prompt()
    bad = [p[:200] for p in _paragraphs(sp) if US.search(p) and not BAN.search(p)]
    assert not bad, bad
    for s in ("IS 801:1975", "IS 811:1987", "IS 875", "IS 1893", "IS 800:2007", "IS 18168", "lateral_frame_is800",
              "elastic_R1", "calc_package_cfs.json", "IN_CFS_Ex1", "IN_CFS_Ex5", "design_status"):
        assert s in sp, s
    assert "cfs_design_examples" not in contract.DRIVER_PREAMBLE
    assert "[missing" not in sp


def test_contract_files_are_india_and_us_material_is_quarantined():
    cdir = os.path.join(ROOT, "contract")
    live = sorted(f for f in os.listdir(cdir) if f.endswith(".md"))
    assert live == ["AGENT_START.md", "CFS_REFERENCE.md", "DESIGN_EG_INDEX.md", "IS801_TOC.md", "IS_COLLECTIONS.md", "README_AGENT.md"]
    assert os.path.exists(os.path.join(cdir, "usa_reference", "AISI_TOC.md"))
    ref = open(os.path.join(cdir, "CFS_REFERENCE.md"), encoding="utf-8").read()
    assert "tests/test_wp3_ex1_ex5.py" in ref and "elastic_R1" in ref
    assert not os.path.exists(os.path.join(ROOT, "rag_v2", "cfs_models.jsonl"))
    assert os.path.exists(os.path.join(ROOT, "rag_v2", "usa_reference", "cfs_models.jsonl"))


def test_driver_completion_gate_uses_india_status(tmp_path):
    from steltic import agent
    jd = tmp_path / "job"
    (jd / "design").mkdir(parents=True)
    pkg = {"design_status": {"status": "complete", "reasons": []}, "lateral_frame": {"status": {"status": "partial", "reasons": ["x"]}},
           "cfs_members": [{"id": "m", "checks": [{"combo": "DL", "check": "c", "value": 1.0, "limit": 2.0, "dc": 0.5, "ok": True,
                                                   "capacity_basis": "IS801_allowable"}]}],
           "cfs_connections": [{"id": "c", "dc": 0.5, "ok": True}], "consistency": [],
           "cfg_snapshot": {"load_plan": {"jurisdiction": "india", "design_basis": "IS801_WSM", "lateral_frame_basis": "IS800_LSD",
                                          "retrieval": [{"stem": "IS_875_Part_3_2015", "found": True, "cite": "x"}]}}}
    (jd / "design" / "calc_package_cfs.json").write_text(json.dumps(pkg))

    class WS:
        def _job_dir(self):
            return str(jd)
    probs = agent._completion_gate(WS())
    assert any("edited by hand" in p for p in probs), probs          # stored 'complete' vs re-derived 'partial'
    assert any("design_status partial" in p for p in probs), probs
    (jd / "design" / "calc_package_cfs.json").unlink()
    (jd / "design" / "calc_package.json").write_text("{}")
    assert any("removed US wall-path" in p for p in agent._completion_gate(WS()))


def test_india_collections_refuse_us_and_gate_is800():
    from steltic import india_collections as IC
    assert IC.is_us_collection("engineering_standards_S100") and IC.is_us_collection("AISI_S400_20") and IC.is_us_collection("ASCE7")
    assert not IC.is_us_collection("engineering_standards_IS801")
    assert IC.stem_for_collection("engineering_standards_IS800") == "IS_800_2007"
    assert IC.stem_for_collection("IS18168") == "IS_18168_2023"
    assert "engineering_standards_IS800" in IC.LATERAL_FRAME_COLLECTIONS and "engineering_standards_IS800" not in IC.DESIGN_COLLECTIONS
