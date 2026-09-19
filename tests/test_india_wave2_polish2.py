"""India CFS wave2 polish2: practical IS 811 sections, Ix QFM path, native combos, conn D/Cs."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "steel_engine"))
sys.path.insert(0, str(ROOT / "steltic"))

import india_practical_sections as IPS
import india_is811_retrieval as R811
import india_connection_dc as ICD
import cfs_frame as CF
import is811_sections as IS811


def _india_load_plan(combos=True):
    plan = {
        "jurisdiction": "india",
        "retrieval": [
            {"stem": "IS_875_Part_3_2015", "query": "wind", "found": True, "cite": "7.2"},
            {"stem": "IS_875_Part_5_1987", "query": "combinations", "found": True, "cite": "P5"},
        ],
    }
    if combos:
        plan["combinations"] = [
            {"label": "1.5D", "fD": 1.5, "fL": 0, "fLr": 0, "cite": "IS 875 P5 EXAMPLE"},
            {"label": "1.2D+1.5W", "fD": 1.2, "fL": 0, "fLr": 0, "W": 1.5,
             "cite": "IS 875 P5 EXAMPLE wind"},
            {"label": "0.9D+1.5W", "fD": 0.9, "fL": 0, "fLr": 0, "W": 1.5,
             "cite": "IS 875 P5 EXAMPLE uplift", "role": "net uplift"},
        ]
    return plan


# ---- 1. Practical section selection ----------------------------------------

def test_resolve_exact_clr_in_catalog():
    labs = IS811.list_is811("CLR")
    assert labs
    hit = IPS.resolve_is811_label(labs[0])
    assert hit["found"] is True
    assert hit["in_catalog"] is True
    assert hit["label"]


def test_missing_is811_label_found_false():
    hit = IPS.resolve_is811_label("CLR999X99X99X9")
    assert hit["found"] is False
    assert "found:false" in hit["note"].lower() or "not found" in hit["note"].lower()


def test_sfia_without_dims_found_false_lists_candidates():
    out = IPS.prefer_practical_is811("600S162-54", role="stud", jurisdiction="india")
    assert out["found"] is False
    assert out.get("looks_sfia") is True
    assert out.get("candidates")  # listed for EOR, not auto-picked as IS law


def test_nearest_stocked_by_dims():
    out = IPS.prefer_practical_is811(
        None, h_mm=100, b_mm=50, t_mm=2.0, role="portal", jurisdiction="india",
    )
    assert out["found"] is True
    assert out["selection"] == "nearest_stocked"
    assert str(out["label"]).startswith("CLR") or str(out["type"]) in IPS.PORTAL_TYPES


def test_section_selection_for_cfg_exact():
    labs = IS811.list_is811("CLR")
    cfg = {
        "jurisdiction": "india",
        "col_section": labs[0],
        "raf_section": labs[1] if len(labs) > 1 else labs[0],
    }
    st = IPS.section_selection_for_cfg(cfg)
    assert st["found"] is True
    assert not st["missing"]


# ---- 2. Ix OCR → QFM -------------------------------------------------------

def test_ix_qfm_plan_has_hooks():
    labs = IS811.list_is811("CLR")
    plan = R811.seed_ix_qfm_correction_plan(labs[0])
    assert plan
    purposes = [p.get("purpose") for p in plan]
    assert R811.IX_QFM_PURPOSE in purposes
    assert any(p.get("type") == "exact_table" for p in plan)


def test_ix_status_without_qfm_not_applied():
    labs = IS811.list_is811("CLR")
    st = R811.ix_qfm_correction_status(labs[0])
    assert st["correction_applied"] is False
    assert st["found"] is False
    assert st["retrieval_plan"]


def test_apply_ix_requires_cite():
    bad = R811.apply_ix_from_qfm("CLR100X50X15X2", 50.0, cite="")
    assert bad["found"] is False
    ok = R811.apply_ix_from_qfm(
        "CLR100X50X15X2", 50.0,
        cite="IS_811_1987 Table 6 row CLR 100x50x15x2 LIVE QFM EXAMPLE",
    )
    assert ok["found"] is True
    assert ok["correction_applied"] is True
    assert ok["overlay"]["Ix_si_cm4"] == 50.0
    assert ok["overlay"]["_Ix_ocr_corrected"] is True


# ---- 3. Native India combos in cfs_frame ------------------------------------

def test_combo_path_found_false_without_load_plan_combos():
    st = CF.india_combo_path_status({"jurisdiction": "india"})
    assert st["found"] is False
    assert "found:false" in st["note"].lower() or st["n_combos"] == 0


def test_combo_path_found_true_with_load_plan():
    cfg = {"jurisdiction": "india", "load_plan": _india_load_plan(True)}
    st = CF.india_combo_path_status(cfg)
    assert st["found"] is True
    assert st["n_combos"] == 3
    rows = CF.portal_combos_from_load_plan(cfg)
    assert rows[0][0] == "1.5D"
    assert rows[0][1]["D"] == 1.5
    assert rows[1][1]["W"] == 1.5


def test_run_uses_load_plan_combos_not_asce_labels():
    labs = IS811.list_is811("CLR")
    # Tiny portal smoke — use modest dims; analysis_fidelity 0 to avoid heavy iter
    cfg = dict(
        jurisdiction="india",
        span_ft=20.0, eave_ft=10.0, apex_ft=12.0, spacing_ft=10.0,
        col_section=labs[0], raf_section=labs[0],
        base="pinned",
        D_roof=5.0, Lr=10.0, snow_pg=0.0,
        wind=dict(V=90.0, exposure="C", enclosed=True),
        analysis_fidelity=0, direct_analysis=False,
        load_plan=_india_load_plan(True),
    )
    res = CF.run(cfg)
    assert res["india_combo_path"]["found"] is True
    # Combo keys should be India labels, not 1.4D ASCE scaffold
    assert "1.5D" in res["combos"]
    assert "1.4D" not in res["combos"]
    assert "1.2D+1.5W" in res["combos"]


def test_run_scaffolding_when_no_combos():
    labs = IS811.list_is811("CLR")
    cfg = dict(
        jurisdiction="india",
        span_ft=20.0, eave_ft=10.0, apex_ft=12.0, spacing_ft=10.0,
        col_section=labs[0], raf_section=labs[0],
        base="pinned",
        D_roof=5.0, Lr=10.0, snow_pg=0.0,
        wind=dict(V=90.0, exposure="C", enclosed=True),
        analysis_fidelity=0, direct_analysis=False,
        load_plan=_india_load_plan(False),
    )
    res = CF.run(cfg)
    assert res["india_combo_path"]["found"] is False
    assert "1.4D" in res["combos"]  # legacy scaffolding only


# ---- 4. Connection / anchor D/Cs -------------------------------------------

def test_connection_dc_found_false_refuses_aisi():
    st = ICD.connection_dc_status("conn-knee", {"jurisdiction": "india"})
    assert st["found"] is False
    assert st["DC"] is None
    assert "aisi" in st["note"].lower()


def test_connection_dc_aisi_source_refused_even_with_capacity():
    cfg = {
        "jurisdiction": "india",
        "connection_capacities": {
            "conn-knee": dict(capacity=100.0, cited="S100 J3", source="aisi_s100"),
        },
    }
    st = ICD.connection_dc_status("conn-knee", cfg, demand={"M_transfer_kipin": 50})
    assert st["found"] is False


def test_connection_dc_eor_found_true():
    cfg = {
        "jurisdiction": "india",
        "connection_capacities": {
            "conn-knee": dict(
                capacity=200.0, cited="IS 801 cl.7 EXAMPLE manufacturer bracket",
                source="manufacturer", limit_state="bolt shear",
            ),
        },
    }
    st = ICD.connection_dc_status(
        "conn-knee", cfg, demand={"M_transfer_kipin": 100.0},
    )
    assert st["found"] is True
    assert st["DC"] == 0.5
    assert "IS 801" in st["cited"]


def test_apply_stubs_on_portal_package():
    pkg = dict(
        connections=[dict(id="conn-knee", M_transfer_kipin=10.0, note="AGENT")],
        anchorage=[dict(id="base-anchor", V_base_kip=1.0, T_net_uplift_kip=2.0,
                        note="AGENT: 0.9D+1.0W")],
    )
    cfg = {"jurisdiction": "india"}
    ICD.apply_india_connection_stubs(pkg, cfg)
    assert pkg["india_connection_path"]["found"] is False
    assert pkg["connections"][0]["india_dc"]["found"] is False
    assert "aisi" in pkg["anchorage"][0]["note"].lower() or "IS 801" in pkg["anchorage"][0]["note"]
