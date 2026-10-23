"""Check fixes (2026-10-23, CFS): report-only fixes after the independent check of the second-wave publish.

Finding 5   no code module names, engine table names, JSON keys or internal words in the printed CFS reports (Ex3:
            'owner decision (2026-10)'); the lateral (hot-rolled frame) reports format a per-use occupancy (Ex4, Ex14
            printed a raw list of dicts) -- that report comes from hr_vendor, re-vendored from steltic_india
Finding 6   'EOR' in the clause text that the site index carries (Ex14, Ex15 headline.serviceability.clause)
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
HR_VENDOR = os.path.join(ROOT, "steel_engine", "hr_vendor")

# strings as printed in the second-wave publish (CHECK2_RESULT findings 5 and 6)
PUBLISHED = [
    "Design note: fixed bases kept by owner decision (2026-10): the cold-formed portal takes its sway stiffness",
    "IS 801 5.1 (no limit); criterion L/300: IS 800:2007 Table 6 (read-only, serviceability_limits_table6): other "
    "buildings, lateral, wind, elastic cladding height/300 applied to the stud span (EOR choice; stricter than the "
    "industrial girt row span/150)",
    "COMPLETE (cold-formed design status (india_cfs_gates) including the hot-rolled frame status)",
    "PASS (IS 875 (Part 4):2021 4.4 ponding screen (HR india_loads.ponding_screen_4_4, engineering practice: the",
    "roof D 1.5 via hr_cfg_extra D_by_level / L_by_level; roof",
    "| plate bending (uplift side) | IS800_WSM | PASS |",
    "| IS801_allowable | PASS | IS 801 6.1 / 6.6 / 7.5",
    "criterion L/150: IS 800:2007 Table 6 (serviceability_limits_table6): industrial, purlins and girts",
    "criterion L/300: IS 800:2007 Table 6 (read-only): other buildings, floor",
    "criterion L/360: IS 800:2007 Table 6 (read-only retrieval, serviceability_limits_table6): other buildings",
    "rod force = 11 members x (P1 2340 N) per line (declared members_per_line); M20",
]


@pytest.mark.parametrize("text", PUBLISHED)
def test_cfs_public_text(text):
    import report_cfs_second_wave as RS
    assert RS.leaks(text), text
    out = RS.public_text(text)
    assert RS.leaks(out) == [], out
    assert RS.public_text(out) == out


def test_cfs_public_text_words():
    import report_cfs_second_wave as RS
    assert "as an adopted design decision" in RS.public_text("fixed bases kept by owner decision (2026-10)")
    assert "(design engineer's choice; stricter" in RS.public_text(PUBLISHED[1])
    assert RS.public_text("Section auto-selected from family thin_C_G350: x") == \
        "Section auto-selected from family thin C sections, G350: x"
    assert RS.public_text("no ratio: column splice: no_splice (PASS)") == "no ratio: column splice: no splice (PASS)"
    assert RS.public_text("IS 456 Table 23 WSM tau_c 0.19 N/mm2") == "IS 456 Table 23 WSM τc 0.19 N/mm2"
    for keep in ("1.5DL+1.5EQ_X", "knee-bolt-group", "bolted gusset (6x2 M16, raf_2R)", "IS 801:1975 6.6.3"):
        assert RS.public_text(keep) == keep


def test_tidy_html_applies_the_pass():
    import report_cfs_second_wave as RS
    out = RS.tidy_html("<p class='rs'>Design note: fixed bases kept by owner decision (2026-10).</p><td>EOR input</td>")
    assert "class='rs'" in out and RS.leaks(out) == [] and "design engineer's input" in out


def test_headline_clause_has_no_eor_or_engine_names():
    """Finding 6: headline.serviceability.clause goes to cfs/index.json."""
    import report_cfs_second_wave as RS
    pkg = {"cfs_members": [{"id": "stud-1", "designator": "C100", "checks": [
        {"check": "deflection (wind)", "dc": 0.5, "value": 5.0, "limit": 10.0, "capacity_basis": "IS800_Table6",
         "clause": PUBLISHED[1]},
        {"check": "6.1 bending", "dc": 0.7, "value": 70.0, "limit": 100.0, "clause": "IS 801 6.1"}]}]}
    h = RS.headline(pkg)
    cl = h["serviceability"]["clause"]
    assert "EOR" not in cl and "serviceability_limits_table6" not in cl and "design engineer's choice" in cl
    assert h["strength"]["dc"] == 0.7


def test_vendored_lateral_report_formats_per_use_occupancy():
    """Finding 5 (CFS Ex4 / Ex14 lateral reports): a per-use occupancy list is formatted, one use per line, and a
    ruling keeps its id with its meaning (hr_vendor report_first_wave + report_public, from steltic_india)."""
    code = (
        "import sys, json; sys.path.insert(0, %r)\n"
        "import report_first_wave as FW, report_second_wave as RS2, report_public as P\n"
        "cfg = {'occupancy': [{'use': 'residential', 'area_m2': 4800.0, 'note': 'persons not stated (brief); owner "
        "ruling D8: floor area > 2,000 m2 as the proxy'}, {'use': 'retail', 'note': 'podium retail; D8 area proxy'}]}\n"
        "t = RS2.tidy_html('<td>' + FW.occupancy_text(cfg) + '</td>')\n"
        "print(json.dumps({'t': t, 'leaks': P.leaks(t)}))\n" % HR_VENDOR)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=HR_VENDOR,
                       env=dict(os.environ, MPLBACKEND="Agg"))
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert "[{" not in out["t"] and "residential" in out["t"] and "retail" in out["t"] and "<br>" in out["t"]
    assert "Steltic design ruling D8" in out["t"] and "owner ruling" not in out["t"] and out["leaks"] == []
