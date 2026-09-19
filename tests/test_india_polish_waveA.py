"""CFS India polish Wave A: AISI strip, least-R, podium, perforated, Nx, k4."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "steel_engine"))
sys.path.insert(0, str(ROOT / "steltic"))

import india_practical_sections as IPS
import india_least_r as ILR
import india_podium_two_stage as IPT
import india_perforated_walls as IPW
import india_loads as IL
import is811_sections as IS811
import report as R


# ---- 1. Report AISI boilerplate strip (India) -------------------------------

def test_india_chapters_strip_aisi():
    ch = R._chapters({"jurisdiction": "india"})
    assert "IS 801" in ch[6][0]
    assert "AISI" not in ch[6][0]
    blob = " ".join(ch[1][1] + ch[4][1] + ch[9][1]).lower()
    assert "is 875" in blob or "load_plan" in blob
    assert "not asce 7-22" in blob or "not asce" in blob
    assert "0.004" in " ".join(ch[8][1])


def test_usa_chapters_keep_aisi_when_forced():
    ch = R._chapters({"jurisdiction": "usa", "force_usa_drift_ui": True})
    assert "AISI S100" in ch[6][0]


def test_india_design_basis_codes_is_not_aisi():
    html = R._design_basis_codes(
        {"jurisdiction": "india"},
        {"R": 2.5, "SDS": 0.2, "SD1": 0.1, "Ie": 1.0, "Cd": 1.0, "Om0": 1.0},
    )
    assert "IS 801" in html
    assert "AISI S100" not in html
    assert "ASCE/SEI 7-22" not in html


def test_india_toc_mentions_is801():
    toc = R._toc({"jurisdiction": "india"})
    assert "IS 801" in toc
    assert "AISI S100/S240/S400" not in toc or "not AISI" in toc


# ---- 2. Dual-system least-R -------------------------------------------------

def test_least_r_found_false_without_eor():
    cfg = {
        "jurisdiction": "india",
        "dual_system": True,
        "systems": [
            {"name": "sbmf", "R": 3.0},
            {"name": "strap", "R": 2.5},
        ],
    }
    st = ILR.dual_system_least_R(cfg)
    assert st["dual"] is True
    assert st["least_R"] == 2.5
    assert st["found"] is False
    assert st["require_eor_documented"] is True
    assert st["clause"]["found"] is False
    assert st["asce_12_2_3_refused"] is True


def test_least_r_eor_documented_grounds():
    cfg = {
        "jurisdiction": "india",
        "dual_system": True,
        "R": 2.5,
        "R_source": "eor_documented",
        "R_cite": "EXAMPLE EOR: mixed SBMF+strap; least R=2.5",
        "R_by_system": {"sbmf": 2.5, "strap": 2.5},
    }
    st = ILR.dual_system_least_R(cfg)
    assert st["found"] is True
    assert st["least_R"] == 2.5
    assert st["selection"] == "least_R_eor_documented"
    assert "ASCE" in st["note"] or st["asce_12_2_3_refused"]


def test_least_r_clause_agent_fill():
    cfg = {
        "jurisdiction": "india",
        "dual_system": True,
        "systems": [{"name": "a", "R": 4.0}, {"name": "b", "R": 2.0}],
        "least_R_clause": {
            "found": True,
            "cite": "IS 1893 LIVE RAG EXAMPLE clause",
            "text": "EXAMPLE only — not invented by builder",
        },
    }
    st = ILR.dual_system_least_R(cfg)
    assert st["found"] is True
    assert st["least_R"] == 2.0
    assert st["clause"]["found"] is True


def test_least_r_rag_plan_nonempty():
    plan = ILR.rag_query_plan_least_R({"systems": [{"name": "sbmf"}]})
    assert plan and plan[0]["stem"].startswith("IS_1893")


# ---- 3. Podium / two-stage stubs --------------------------------------------

def test_podium_two_stage_found_false_refuses_asce():
    cfg = {"jurisdiction": "india", "podium": True, "arch": "5over2 podium"}
    st = IPT.podium_package_status(cfg)
    assert st["podium_detected"] is True
    assert st["asce_12_2_3_2_refused"] is True
    assert st["two_stage"]["found"] is False
    assert "12.2.3.2" in st["asce_refuse_note"]
    refuse = IPT.refuse_asce_two_stage_as_india_law(cfg)
    assert refuse["allowed_as_india_law"] is False


def test_podium_agent_fill_requires_cite():
    cfg = {
        "jurisdiction": "india",
        "podium": True,
        "is1893_two_stage": {"found": True},  # missing cite → reverted
    }
    st = IPT.two_stage_analysis_status(cfg)
    assert st["found"] is False


def test_podium_agent_fill_with_cite():
    cfg = {
        "jurisdiction": "india",
        "podium": True,
        "is1893_two_stage": {
            "found": True,
            "cite": "IS 1893 LIVE EXAMPLE",
            "text": "agent-filled",
        },
    }
    st = IPT.two_stage_analysis_status(cfg)
    assert st["found"] is True


# ---- 4. Perforated / Type II stub -------------------------------------------

def test_perforated_is801_found_false():
    cfg = {"jurisdiction": "india", "type_II": True, "feature": "perforated"}
    st = IPW.perforated_wall_rules_status(cfg)
    assert st["found"] is False
    assert st["perforated_detected"] is True
    assert st["s400_type_II_refused_as_india_law"] is True


def test_perforated_practice_ca_disclosure():
    cfg = {
        "jurisdiction": "india",
        "perforated": True,
        "perforated_Ca": 0.72,
        "perforated_Ca_source": "manufacturer",
        "perforated_Ca_cite": "EXAMPLE Acme Table B perforated Ca",
    }
    st = IPW.perforated_wall_rules_status(cfg)
    assert st["found"] is False  # IS rules still false
    assert st["practice_disclosure"]["accepted"] is True
    assert st["practice_disclosure"]["is_is801_law"] is False


# ---- 5. Practical Nx / built-up ---------------------------------------------

def test_parse_nx_pack():
    p = IPS.parse_nx_pack("8xCLR250X80X25X5")
    assert p["n_ply"] == 8
    assert p["bare"].startswith("CLR250")
    assert p["is_nx_pack"] is True
    p2 = IPS.parse_nx_pack("2xCLR100X50X15X2")
    assert p2["n_ply"] == 2 and p2["is_built_up"] and not p2["is_nx_pack"]


def test_nx_pack_found_false_with_candidates():
    labs = IS811.list_is811("CLR")
    # Prefer a CLR250 if present else any
    bare = next((x for x in labs if x.startswith("CLR250")), labs[0])
    req = "8x" + bare
    out = IPS.prefer_portal_stock_or_built_up(req, jurisdiction="india")
    assert out["found"] is False
    assert out.get("is_nx_pack") is True
    assert out.get("bare_in_catalog") is True
    assert out.get("candidates") or out.get("built_up_candidate")
    assert "found:false" in (out.get("note") or "").lower() or "NOT a stocked" in (out.get("note") or "")


def test_2x_built_up_found_true():
    labs = IS811.list_is811("CLR")
    req = "2x" + labs[0]
    hit = IPS.resolve_is811_label(req)
    assert hit["found"] is True
    assert hit["built_up"] is True
    assert hit["n_ply"] == 2


def test_section_selection_cfg_nx_missing():
    labs = IS811.list_is811("CLR")
    bare = next((x for x in labs if "250" in x), labs[0])
    cfg = {
        "jurisdiction": "india",
        "col_section": "32x" + bare,
        "raf_section": "32x" + bare,
    }
    st = IPS.section_selection_for_cfg(cfg)
    assert st["found"] is False
    assert "col_section" in st["missing"]


# ---- 6. k4 cyclonic (Wave A #4 / backlog #4) ---------------------------------

def test_k4_industrial_not_forced_1_0():
    st = IL.resolve_k4_cyclonic({
        "jurisdiction": "india",
        "k4_class": "industrial",
        "force_k4_1_0": True,  # historical Ex11-style override — must refuse
    })
    assert st["found"] is True
    assert abs(st["k4"] - 1.15) < 1e-9
    assert st["forced_1_0_override_refused"] is True


def test_k4_post_cyclone_1_30():
    st = IL.resolve_k4_cyclonic({"k4_class": "post_cyclone"})
    assert st["found"] is True
    assert abs(st["k4"] - 1.30) < 1e-9


def test_k4_motel_all_other_1_00():
    st = IL.resolve_k4_cyclonic({"k4_class": "motel"})
    assert st["found"] is True
    assert abs(st["k4"] - 1.00) < 1e-9


def test_k4_found_false_without_class_or_rag():
    st = IL.resolve_k4_cyclonic({"jurisdiction": "india"})
    assert st["found"] is False
    assert st["k4"] is None


def test_k4_live_rag_fill_preferred():
    st = IL.resolve_k4_cyclonic({
        "k4_class": "motel",  # would be 1.0
        "k4_rag": {"found": True, "k4": 1.15, "cite": "LIVE RAG cl.6.3.4 industrial EXAMPLE",
                   "class": "industrial"},
    })
    assert st["found"] is True
    assert abs(st["k4"] - 1.15) < 1e-9
    assert st["source"] == "cfg.k4_rag"


def test_annex_a_vizag_50():
    st = IL.annex_a_basic_wind("Vizag")
    assert st["found"] is True
    assert abs(st["Vb_mps"] - 50.0) < 1e-9


def test_annex_a_noida_found_false_delhi_proxy():
    st = IL.annex_a_basic_wind("Noida")
    assert st["found"] is False
    assert st["proxy"]["Vb_mps"] == 47.0
    assert "do not invent" in (st["note"] or "").lower() or "NOT in" in (st["note"] or "")
