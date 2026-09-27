"""RR-BUG-4 (CFS part): the CFS status is built from the HR lateral package status.  With the per-element rows first
and a cut at 200 the Table 5(ii) flexible-diaphragm blocker and the H30 evidence reasons were lost (CFS Ex9: 229
lateral reasons, Ex12: 435; the CFS STATUS showed only 'Table 2 (+N similar)').  The HR status_record now keeps every
reason class; lateral_issues ranks by the HR reason class, keeps the first row of every class under its cap and
reports the full HR count."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_env  # noqa: E402,F401
import india_cfs_gates as G  # noqa: E402
import india_seismic_gates as HG  # noqa: E402  (vendored HR)

T5 = ("Amd 2 Table 5(ii): re-entrant plan requires a flexible-diaphragm 3D dynamic analysis in addition to the "
      "rigid case -- not performed")
EV = ("consistency: load_plan.retrieval[12] (Noida): found:false without EOR assumption -- record the value used "
      "with {value, source, cite, verify: True} on the row or in cfg['eor_assumptions']")


def _hr_reasons_400():
    rs = ["capacity_design.checks.is18168_table2_column@e%d fails (pass/ok false)" % i for i in range(1, 231)]
    rs += ["capacity_design.checks.is18168_table2_beam@e%d fails (pass/ok false)" % i for i in range(300, 468)]
    return rs + [EV, T5]


def test_hr_package_status_keeps_blockers_and_cfs_shows_them():
    rs = _hr_reasons_400()
    assert len(rs) == 400
    st = HG.status_record({"status": "partial", "reasons": rs, "authority": "HR"})
    assert st["n_reasons"] == 400
    out = G.lateral_issues({"lateral_frame": {"status": st}})
    txt = "\n".join(out)
    assert T5 in txt and EV in txt
    assert out[0].endswith(T5) and out[1].endswith(EV)                 # irregularity, evidence before element rows
    assert any("is18168_table2_column fails (pass/ok false) on 230 elements" in x for x in out)
    st_cfs = G.design_status({}, {"lateral_frame": {"status": st}})
    assert any(T5 in r for r in st_cfs["reasons"]) and any(EV in r for r in st_cfs["reasons"])


def test_cfs_cap_keeps_every_class_and_reports_the_total():
    names = ["%s%s" % (chr(65 + i // 26), chr(65 + i % 26)) for i in range(300)]     # 300 distinct checks
    many = ["member 'm%s' / check %s: ok:false" % (n, n) for n in names]
    rs = many + [EV, T5]
    out = G.lateral_issues({"lateral_frame": {"status": {"status": "partial", "reasons": rs, "n_reasons": 750}}})
    assert len(out) == 61
    assert out[0].endswith(T5) and out[1].endswith(EV)
    assert "750 reasons in total" in out[-1] and out[-1].endswith("more (see lateral/STATUS.md)")
