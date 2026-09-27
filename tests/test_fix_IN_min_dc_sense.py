"""IN-MIN-SENSE (gold issues IN_CFS_Ex13 / IN_CFS_Ex7, blocking): the CFS consistency recomputes a minimum-type row
(HR check record with sense '>=' / '>', value >= limit, e.g. IS 1893 7.7.5.2 "at least 90 percent" modal mass of the
Table 5(ii) flexible run) as limit / value; every row without a sense stays a maximum-type row (|value| / limit)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import consistency as CC       # noqa: E402


def _pkg(row):
    return {"lateral_frame": {"seismic_analysis": {"flexible_diaphragm": {"checks": [row]}}}}


def test_ex7_modal_mass_row_with_sense_is_consistent():
    # Ex7 repro numbers: modal mass 0.922 >= 0.90, dc = 0.90 / 0.922 = 0.9761
    row = {"name": "7.7.5.2 modal mass X (flexible run)", "value": 0.922, "limit": 0.9, "dc": 0.9761, "ok": True,
           "sense": ">="}
    assert CC._dc_issues(_pkg(row)) == []
    # Ex13: 0.9455 -> dc 0.9518; scaled base shear row (VB_scaled >= VBbar)
    assert CC._dc_issues(_pkg(dict(row, value=0.9455, dc=0.9518))) == []
    assert CC._dc_issues(_pkg({"name": "7.7.3.1 scaled base shear X (flexible run)", "value": 1002.0,
                               "limit": 1000.0, "dc": 0.998, "ok": True, "sense": ">="})) == []


def test_minimum_row_with_a_wrong_dc_is_still_flagged():
    row = {"name": "7.7.5.2", "value": 0.922, "limit": 0.9, "dc": 1.0244, "ok": True, "sense": ">="}   # value/limit
    iss = CC._dc_issues(_pkg(row))
    assert len(iss) == 1 and "limit/value 0.9761" in iss[0]
    assert CC._dc_issues(_pkg(dict(row, dc=0.5)))


def test_maximum_rows_are_not_relaxed():
    # without a sense the old rule applies unchanged: the Ex7 row (no sense, as the old HR engine wrote it) is flagged
    row = {"name": "7.7.5.2", "value": 0.922, "limit": 0.9, "dc": 0.9761, "ok": True}
    assert CC._dc_issues(_pkg(row))
    # a maximum-type row storing limit / value (unconservative: 0.5 instead of 2.0) is flagged
    assert CC._dc_issues(_pkg({"value": 200.0, "limit": 100.0, "dc": 0.5, "ok": True}))
    # an unknown sense string is not a licence either
    assert CC._dc_issues(_pkg(dict(row, sense="min?")))
    assert CC._dc_issues(_pkg({"value": 50.0, "limit": 100.0, "dc": 0.5})) == []
