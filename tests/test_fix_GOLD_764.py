"""GOLD-764 (IN_CFS_Ex9, lead decision 1): the CFS diaphragm rows carry the HR flexible run's IS 1893 (Part 1):2016
7.6.4 record on the code-literal ratio -- deviation from the chord / average displacement of the entire diaphragm
(limit 1.2); the deviation / average storey drift is informative only (not the IS 1893 criterion)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))


def _lat(row):
    return {"diaphragm_7_6_4": {"flexible_run": {"levels": {"Y": [row]}}}}


def test_literal_ratio_classifies_ex9_level6():
    """CFS Ex9 level 6 Y: deviation 3.7 mm, average displacement of the diaphragm 10 mm -> 0.37 (rigid); the storey
    drift 1.76 mm gives 2.10 -- recorded as informative, it does not classify."""
    import india_cfs_lateral as L
    row = {"level": 6, "delta_max_from_chord_mm": 3.7, "delta_avg_diaphragm_mm": 10.0, "ratio": 0.37,
           "ratio_vs_avg_displacement": 0.37, "ratio_basis": "IS 1893 (Part 1):2016 7.6.4 literal: ...",
           "avg_storey_drift_mm": 1.76, "ratio_vs_storey_drift": 2.10, "limit": 1.2, "classification": "rigid"}
    r = L._flexible_764(_lat(row), "Y", 6)
    assert r["ratio"] == 0.37 and r["classification"] == "rigid" and "7.6.4 literal" in r["ratio_basis"]
    assert r["ratio_vs_storey_drift"] == 2.10 and r["ratio_vs_storey_drift_note"].startswith("informative")
    assert r["delta_avg_diaphragm_mm"] == 10.0


def test_old_hr_record_is_read_through_its_literal_field():
    import india_cfs_lateral as L
    row = {"level": 7, "delta_max_from_chord_mm": 3.4, "delta_avg_diaphragm_mm": 10.0, "ratio": 3.5,
           "ratio_vs_avg_displacement": 0.34, "avg_storey_drift_mm": 0.97, "limit": 1.2, "classification": "flexible"}
    r = L._flexible_764(_lat(row), "Y", 7)
    assert r["ratio"] == 0.34 and r["classification"] == "rigid" and r["ratio_vs_storey_drift"] == 3.5
    hi = dict(row, ratio_vs_avg_displacement=1.49)
    assert L._flexible_764(_lat(hi), "Y", 7)["classification"] == "flexible"
