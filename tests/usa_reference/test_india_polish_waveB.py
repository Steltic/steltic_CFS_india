"""CFS India polish Wave B: SBMF bolt, proprietary HD, Noida Annex E, mezzanine lateral."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "steel_engine"))
sys.path.insert(0, str(ROOT / "steltic"))

import india_sbmf_bolt as ISB
import india_proprietary_hd as IHD
import india_mezzanine_lateral as IML
import india_seismic as ISeis
import india_loads as IL
import report as R


# ---- 5. SBMF bolt slip/bearing ---------------------------------------------

def test_sbmf_bolt_found_false_default():
    st = ISB.sbmf_bolt_slip_bearing_status({
        "jurisdiction": "india",
        "system": "sbmf",
    })
    assert st["found"] is False
    assert st["sbmf_detected"] is True
    assert st["s400_E4_refused_as_india_law"] is True
    assert "E4" in (st["note"] or "") or "S400" in (st.get("s400_refuse_note") or "")


def test_sbmf_bolt_refuses_s400_e4_source():
    st = ISB.sbmf_bolt_slip_bearing_status({
        "jurisdiction": "india",
        "system": "sbmf",
        "sbmf_bolt": {
            "source": "s400_e4",
            "capacity": 12.0,
            "cite": "AISI S400 E4 EXAMPLE — must refuse",
        },
    })
    assert st["found"] is False
    assert st["s400_E4_refused_as_india_law"] is True


def test_sbmf_bolt_eor_with_cite_found_true():
    st = ISB.sbmf_bolt_slip_bearing_status({
        "jurisdiction": "india",
        "system": "sbmf",
        "sbmf_bolt": {
            "source": "eor_documented",
            "capacity_bearing": 15.0,
            "capacity_slip": 8.0,
            "limit_state": "bolt_bearing",
            "cite": "EXAMPLE EOR memo: manufacturer bolt bearing Rn=15 kip at design drift",
        },
    })
    assert st["found"] is True
    assert st["is801_recipe_found"] is False
    assert st["s400_E4_refused_as_india_law"] is True
    assert st["cited"]
    assert st["capacity_bearing"] == 15.0


def test_sbmf_bolt_capacity_without_cite_found_false():
    st = ISB.sbmf_bolt_slip_bearing_status({
        "jurisdiction": "india",
        "system": "sbmf",
        "sbmf_bolt": {"source": "manufacturer", "capacity": 10.0},
    })
    assert st["found"] is False


def test_refuse_s400_e4_gate():
    g = ISB.refuse_s400_e4_as_india_law({"system": "sbmf"})
    assert g["allowed_as_india_law"] is False
    assert g["s400_E4_refused_as_india_law"] is True


# ---- 8. Proprietary HD/anchor ----------------------------------------------

def test_hd_class_envelope_ok():
    st = IHD.proprietary_hd_anchor_status({
        "jurisdiction": "india",
        "device_class": "bolted",
    })
    assert st["found"] is True
    assert st["path"] == "class_envelope"
    assert st["invented_commercial_refused"] is False


def test_hd_deferred_submittal_ok():
    st = IHD.proprietary_hd_anchor_status({
        "jurisdiction": "india",
        "deferred_hd_submittal": True,
    })
    assert st["found"] is True
    assert st["path"] == "deferred_submittal"


def test_hd_refuses_invented_simpson_without_cite():
    st = IHD.proprietary_hd_anchor_status({
        "jurisdiction": "india",
        "hd_product": {
            "product": "Simpson HDU8",
            "source": "invented",
            "capacity": 8.0,
        },
    })
    assert st["found"] is False
    assert st["invented_commercial_refused"] is True


def test_hd_eor_product_with_cite_ok():
    st = IHD.proprietary_hd_anchor_status({
        "jurisdiction": "india",
        "hd_product": {
            "product": "Project-approved HD-A (manufacturer X)",
            "source": "eor_documented",
            "cite": "EXAMPLE EOR submittal memo 2026-09-19 — Tn=12 kip",
            "capacity": 12.0,
        },
    })
    assert st["found"] is True
    assert st["path"] == "eor_project_product"
    assert st["cited"]


def test_refuse_invented_commercial_gate():
    g = IHD.refuse_invented_commercial_product({
        "product": "Simpson Strong-Tie HDU5",
        "source": "catalogue",
    })
    # brand without cite → refused
    assert g["refused"] is True


# ---- 9. Noida Annex E / seismic town ---------------------------------------

def test_annex_e_noida_found_false_delhi_proxy():
    st = ISeis.annex_e_seismic_town("Noida")
    assert st["found"] is False
    assert st["proxy"]["zone"] == "IV"
    assert abs(st["proxy"]["Z"] - 0.24) < 1e-9
    assert "do not invent" in (st["note"] or "").lower() or "NOT" in (st["note"] or "")


def test_annex_e_delhi_zone_iv():
    st = ISeis.annex_e_seismic_town("Delhi")
    assert st["found"] is True
    assert st["zone"] == "IV"
    assert abs(st["Z"] - 0.24) < 1e-9


def test_noida_combined_wind_seismic_honesty():
    st = ISeis.noida_seismic_wind_honesty({"jurisdiction": "india"})
    assert st["found"] is False
    assert st["annex_a_wind"]["found"] is False
    assert st["annex_e_seismic"]["found"] is False
    assert st["delhi_proxy"]["Vb_mps"] == 47.0
    assert st["delhi_proxy"]["zone"] == "IV"


def test_annex_a_still_noida_proxy():
    # Wave A regression
    st = IL.annex_a_basic_wind("Noida")
    assert st["found"] is False
    assert st["proxy"]["Vb_mps"] == 47.0


# ---- 10. Mezzanine lateral model -------------------------------------------

def test_mezzanine_gravity_in_w_found_false():
    st = IML.mezzanine_lateral_model_status({
        "jurisdiction": "india",
        "system": "portal",
        "mezzanine": {
            "height_m": 3.5,
            "D_kN_m2": 1.5,
            "L_kN_m2": 3.0,
            "note": "Gravity in W; EXAMPLE path",
        },
    })
    assert st["mezzanine_detected"] is True
    assert st["found"] is False
    assert st["path"] == "gravity_in_W_only"
    assert st["lateral_modelled"] is False


def test_mezzanine_soft_claim_still_found_false():
    st = IML.mezzanine_lateral_model_status({
        "jurisdiction": "india",
        "mezzanine": {
            "note": "Mezzanine gravity from IS 875 P2; lateral share per diaphragm / frame model",
            "gravity_in_W": True,
        },
    })
    assert st["found"] is False
    assert st.get("soft_claim_without_model") is True


def test_mezzanine_separate_system_found_true():
    st = IML.mezzanine_lateral_model_status({
        "jurisdiction": "india",
        "mezzanine": {
            "separate_system": {
                "system": "strap_braced",
                "R": 2.5,
                "R_source": "eor_documented",
                "cite": "EXAMPLE: mezzanine own strap system separated from portals",
            },
        },
    })
    assert st["found"] is True
    assert st["path"] == "separate_system"
    assert st["lateral_modelled"] is True


def test_mezzanine_host_share_with_cite():
    st = IML.mezzanine_lateral_model_status({
        "jurisdiction": "india",
        "mezzanine": True,
        "mezzanine_host_frame_share": {
            "fraction": 0.35,
            "source": "eor_documented",
            "cite": "EXAMPLE EOR: 35% mezzanine V on end portals",
        },
    })
    assert st["found"] is True
    assert st["path"] == "host_frame_share"
    assert st["lateral_share"] == 0.35


def test_mezzanine_no_hint_na():
    st = IML.mezzanine_lateral_model_status({"jurisdiction": "india", "system": "portal"})
    assert st["path"] == "n/a"
    assert st["mezzanine_detected"] is False


# ---- Report AISI scrub (India Ch.9 / codes) --------------------------------

def test_india_ch9_mentions_sbmf_and_mezzanine():
    ch = R._chapters({"jurisdiction": "india"})
    blob = " ".join(ch[9][1]).lower()
    assert "s400 e4" in blob or "sbmf" in blob
    assert "mezzanine" in blob
    assert "commercial" in blob or "sku" in blob


def test_india_s400_chapter_refuses_e4():
    html = R._s400_capacity_chapter(
        {"jurisdiction": "india", "system": "sbmf",
         "seis": {"R": 2.5, "Cd": 1.0, "Om0": 1.0, "Ie": 1.0}},
        {},
    )
    low = html.lower()
    assert "not" in low and ("s400" in low or "india" in low)
    assert "sbmf" in low or "bolt" in low
    assert "invent" in low or "sku" in low or "proprietary" in low or "class envelope" in low


def test_usa_s400_chapter_keeps_e4():
    html = R._s400_capacity_chapter(
        {"jurisdiction": "usa", "force_usa_drift_ui": True, "system": "sbmf",
         "seis": {"R": 3.5, "Cd": 3.5, "Om0": 3.0, "Ie": 1.0, "SDS": 1.0, "SD1": 0.6}},
        {},
    )
    assert "S400 E4" in html or "bolt-bearing" in html.lower()


def test_india_design_basis_mentions_waveB():
    html = R._design_basis_codes(
        {"jurisdiction": "india"},
        {"R": 2.5, "SDS": 0.2, "SD1": 0.1, "Ie": 1.0},
    )
    assert "SBMF" in html or "mezzanine" in html or "Wave B" in html
