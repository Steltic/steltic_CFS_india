"""India CFS complete-gap wave1: R eor_documented, manufacturer vn, IS811 depth alias.

Toward COMPLETE on IN_CFS_Ex1/Ex2 without inventing IS tables or IS 800 OMRF R.
Amd1 found:false and S400 Ω0 N/A must not alone block COMPLETE.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "steel_engine"))
sys.path.insert(0, str(ROOT / "steltic"))

import india_cfs_gates as ICG
import cfs_systems as CS
import cfs_sections as SEC
import cfs_frame as CF
import is811_sections as IS811
import india_is811_retrieval as R811


def _base_wall(**extra):
    cfg = {
        "system": "wsp_shearwall",
        "stories": 4,
        "heights": [3600, 3600, 3600, 3600],
        "SX": 6000, "SY": 5000,
        "units": "N-mm",
        "jurisdiction": "india",
        "seis": {"SDS": 0.24, "SD1": 0.14, "R": 2.5, "Cd": 1.0, "Ie": 1.0},
        "model": {"bases": "pinned", "joints": "pinned", "gravity": "framed"},
        "diaphragm": "flexible",
        "load_plan": {
            "jurisdiction": "india",
            "retrieval": [
                {"stem": "IS_875_Part_3_2015", "query": "wind", "found": True, "cite": "7.2"},
                {"stem": "IS_1893_Part_1_2016", "query": "Table 9 R",
                 "found": False, "cite": "Table 9 CFS row absent"},
            ],
            "combinations": [
                {"label": "1.5D", "fD": 1.5, "fL": 0, "fLr": 0, "cite": "IS"},
            ],
        },
        "lines_x": [object()],
    }
    cfg.update(extra)
    return cfg


# ---- R EOR-documented path -------------------------------------------------

def test_r_eor_documented_allowlisted_and_complete():
    cfg = _base_wall(
        R=2.5,
        R_source="eor_documented",
        R_cite="EOR: CFS WSP not in IS 1893 Table 9; project R=2.5",
        R_cfs_table9_found=False,
        wall_vn_plf_asd=520.0,
        wall_vn_source="manufacturer",
        wall_vn_cite="Acme WSP Table B — EXAMPLE",
    )
    assert "eor_documented" in ICG.R_OK_SOURCES
    assert "is800_omrf" in ICG.R_PROXY_SOURCES
    assert not any(s == "ERROR" for s, _ in ICG.validate_R(cfg))
    assert ICG.R_is_proxy(cfg) is False
    ok, reasons = ICG.complete_allowed(cfg)
    assert ok is True, reasons
    assert ICG.design_status(cfg)["status"] == "complete"


def test_r_is800_omrf_proxy_still_refuses_complete():
    cfg = _base_wall(
        R=3.0,
        R_source="is800_omrf",
        R_cite="forbidden proxy",
        R_cfs_table9_found=False,
        wall_vn_plf_asd=520.0,
        wall_vn_source="manufacturer",
        wall_vn_cite="Acme",
    )
    assert ICG.R_is_proxy(cfg) is True
    ok, reasons = ICG.complete_allowed(cfg)
    assert ok is False
    assert any("proxy" in r.lower() or "C7" in r for r in reasons)


def test_r_never_autofill_from_is800_missing_source_errors():
    """seis.R present without R_source → ERROR (would have been silent IS 800 path)."""
    cfg = _base_wall()  # seis.R=2.5, no R_source
    findings = ICG.validate_R(cfg)
    assert any(s == "ERROR" and "R_source" in m for s, m in findings)
    assert any("IS 800" in m or "proxy" in m.lower() for s, m in findings)


# ---- Manufacturer vn path + EXAMPLE companion ------------------------------

def test_vn_manufacturer_ok_for_complete():
    cfg = _base_wall(
        R=2.5, R_source="eor_documented", R_cite="EOR",
        R_cfs_table9_found=False,
        wall_vn_plf_asd=480.0,
        wall_vn_source="manufacturer",
        wall_vn_cite="Acme catalog sheet 3",
    )
    assert not any(s == "ERROR" for s, _ in ICG.validate_wall_vn(cfg))
    ok, reasons = ICG.complete_allowed(cfg)
    assert ok is True, reasons


def test_ex1_eor_inputs_example_exercises_complete_gate():
    path = ROOT / "test_buildings" / "IN_CFS_Ex1_EOR_inputs_EXAMPLE.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "EXAMPLE" in data["_label"].upper() or "not-for-construction" in data["_label"].lower()
    assert data["R_source"] == "eor_documented"
    assert data["wall_vn_source"] == "manufacturer"
    assert data["R_cfs_table9_found"] is False
    # Merge EXAMPLE provenance onto a wall cfg scaffold
    cfg = _base_wall(
        R=data["R"],
        R_source=data["R_source"],
        R_cite=data["R_cite"],
        R_cfs_table9_found=data["R_cfs_table9_found"],
        wall_vn_plf_asd=data["wall_vn_plf_asd"],
        wall_vn_source=data["wall_vn_source"],
        wall_vn_cite=data["wall_vn_cite"],
    )
    ok, reasons = ICG.complete_allowed(cfg)
    assert ok is True, reasons
    assert ICG.design_status(cfg)["status"] == "complete"


# ---- IS 811 d → depth for frame_section ------------------------------------

def test_is811_depth_alias_on_props_and_gross_props():
    p = IS811.props("CLR100X50X15X2")
    assert p.get("d") is not None
    assert p.get("depth") == p["d"]
    g = SEC.gross_props("CLR100X50X15X2")
    assert g.get("depth") == g.get("d") == p["d"]
    # J/Cw not invented when absent from catalog
    assert g.get("J") is None
    assert g.get("_J_found") is False
    assert g.get("Cw") is None
    assert g.get("_Cw_found") is False


def test_frame_section_accepts_is811_clr():
    fs = CF.frame_section("CLR100X50X15X2")
    assert fs["depth"] > 0
    assert fs["A"] > 0 and fs["Ix"] > 0
    assert fs["single"] is True
    assert fs.get("_source") == "IS_811_1987"
    # built-up path also gets depth
    bu = CF.frame_section("2xCLR100X50X15X2")
    assert bu["depth"] == fs["depth"]
    assert bu["single"] is False
    assert bu["A"] == 2 * fs["A"]


# ---- Amd1 empty + S400 Ω0 must not alone block COMPLETE --------------------

def test_amd1_found_false_does_not_block_complete():
    cfg = _base_wall(
        R=2.5, R_source="eor_documented", R_cite="EOR",
        R_cfs_table9_found=False,
        wall_vn_plf_asd=520.0,
        wall_vn_source="manufacturer",
        wall_vn_cite="Acme",
        is811_retrieval=[
            {"stem": "IS_811_1987_Amd1_2011", "found": False,
             "purpose": "is811_amd1_property_delta", "query": "property delta"},
        ],
    )
    honest = R811.amd1_honest_result(
        {"found": True, "hits": [{"found": True, "kind": "fts",
                                  "section_id": "spec-page:IS_811_1987_Amd1_2011:standard:1",
                                  "table_id": "", "title": "amendment cover"}]},
        purpose="is811_amd1_property_delta",
    )
    assert honest["found"] is False
    assert ICG.amd1_gap_blocks_complete(cfg) is False
    ok, reasons = ICG.complete_allowed(cfg)
    assert ok is True, reasons


def test_s400_omega0_found_false_documented_na():
    note = CS.INDIA_SEISMIC_NOTES["s400_omega_capacity_design"]
    assert note["found"] is False
    assert note.get("Omega0_found") is False
    assert "N/A" in note["note"] or "no" in note["note"].lower()
    assert ICG.s400_omega0_blocks_complete() is False
    cfg = _base_wall(
        R=2.5, R_source="eor_documented", R_cite="EOR",
        R_cfs_table9_found=False,
        wall_vn_plf_asd=520.0,
        wall_vn_source="test",
        wall_vn_cite="NABL lab 2026",
    )
    ok, reasons = ICG.complete_allowed(cfg)
    assert ok is True, reasons
