"""WP3.2 / WP3.3 -- IS 801 member checks (hand values from spec 3.2 / 4.2 and CFSREPO-01) and the IS 811 catalogue."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import is811_sections as S   # noqa: E402
import is801_members as M    # noqa: E402


# ---------------------------------------------------------------------------------------------------------------
# IS 811 catalogue (WP3.3)
# ---------------------------------------------------------------------------------------------------------------
def test_is811_finding_rows_are_corrected():
    p = S.props("CLR180X50X25X4")
    assert abs(p["Ix"] / 1e4 - 518.0) < 1.0                      # was 49 518 cm4 (CFSREPO-02)
    z = S.props("LZ230X75X20X2.55")
    assert abs(z["Ix"] / 1e4 - 793.0) < 1.0 and abs(z["Iy"] / 1e4 - 107.0) < 1.0 and abs(z["Iv"] / 1e4 - 46.7) < 0.2
    ea = S.props("EA20X20X1.25")
    assert abs(ea["Iy"] - ea["Ix"]) < 1e-9 and abs(ea["Iv"] / 1e4 - 0.067) < 0.001
    assert abs(ea["r_min"] - 3.8) < 0.05                          # rv = 0.38 cm (not 0.806 / 0.63)
    c = S.props("CLR100X50X15X2")
    assert abs(c["x0"] - 42.9) < 0.05 and abs(c["J"] / 1e4 - 0.056) < 0.001 and abs(c["Cw"] / 1e6 - 312.0) < 0.5
    assert c["Fy"] is None and c["_Fy_found"] is False
    assert c["flats"]["web"] == pytest.approx(90.0) and c["flats"]["flange"] == pytest.approx(40.0)
    assert "hat" in S.TYPE_TO_NAME["HRH"] and "hat" in S.TYPE_TO_NAME["HRB"]
    assert S.props("HRH50X40X20X3.15")["hat"] is True


def test_is811_validator_zero_failures_and_quarantine():
    sys.path.insert(0, os.path.join(ROOT, "steel_engine", "tools"))
    import validate_is811 as V
    assert V.main(os.path.join(ROOT, "steel_engine", "is811_shapes.csv")) == 0
    with pytest.raises(KeyError):
        S.props("LZ240X75X20X1.6")                                # quarantined found:false
    assert S.quarantined("LZ240X75X20X1.6")["found"] == "false"
    assert S.props("CLR200X80X25X4")["Cw"] is None                # corpus-flagged misprint blanked
    with pytest.raises(ValueError):
        S.parse_designator("8xCLR250X80X25X5")                    # packs > 2 refused (WP3.2)
    with pytest.raises(ValueError):
        S.built_up("CLR250X80X25X5", 16)


# ---------------------------------------------------------------------------------------------------------------
# IS 801 (WP3.2)
# ---------------------------------------------------------------------------------------------------------------
def test_stud_sheathing_braced_hand_value():
    """CLR100x50x15x2, Fy 250, KL = 3.0 m strong axis, sheathing-braced (8.1): Q 0.952, Fa1 103 MPa, Pa 44 kN."""
    sec = S.props("CLR100X50X15X2")
    r = M.compression_allowable(sec, 250.0, KLx_mm=3000.0, KLy_mm=300.0, braced_against_twist=True)
    assert r["Q"] == pytest.approx(0.952, abs=0.003)
    assert r["eff_widths_mm"]["web"] == pytest.approx(79.8, abs=0.3)
    assert r["Fa1_MPa"] == pytest.approx(103.0, abs=1.5)
    assert r["Pa_kN"] == pytest.approx(44.0, abs=0.6)
    assert r["capacity_basis"] == "IS801_allowable" and r["allowable_increase"] == 1.0


def test_stud_unbraced_torsional_flexural_hand_value():
    """Same section, KL = 3 m both axes, not braced against twist: Fa2 = 340 kgf/cm2, P = 14.2 kN (18.9 with +33 1/3 %)."""
    sec = S.props("CLR100X50X15X2")
    r = M.compression_allowable(sec, 250.0, 3000.0, 3000.0)
    assert r["KLr"] == pytest.approx(163.0, abs=0.5)
    assert r["sigma_TFO_kgf_cm2"] == pytest.approx(651.0, abs=3.0)
    assert r["Fa2_kgf_cm2"] == pytest.approx(340.0, abs=2.0)
    assert r["Pa_kN"] == pytest.approx(14.2, abs=0.15)
    rw = M.compression_allowable(sec, 250.0, 3000.0, 3000.0, wind_eq=True)
    assert rw["Pa_kN"] == pytest.approx(18.9, abs=0.2) and rw["allowable_increase"] == pytest.approx(4.0 / 3.0)


def test_fa1_and_fb_hand_values():
    assert M.is801_fa1(250.0, 1.0, 77.5) == pytest.approx(106.0, abs=1.0)
    sec = S.props("CLR250X80X25X5")
    b = M.bending_allowable(sec, 345.0, 6000.0, Cb=1.0)
    assert 40.0 <= b["Fb_MPa"] <= 46.0                            # spec: Fb ~ 41 MPa (6.3 elastic branch)
    assert "elastic" in b["ltb_clause"]
    # 0.6 Fy governs when the compression flange is restrained
    # restrained compression flange: 6.3 off; for this section at Fy 345 the 25 mm lip is below 5.2.2.1 dmin
    # (26.0 mm) so the flange is an unstiffened element and 6.2(b) governs below 0.6 Fy
    b2 = M.bending_allowable(sec, 345.0, 6000.0, compression_flange_restrained=True)
    assert b2["lip_5221"]["ok"] is False and b2["Fb_MPa"] < 0.6 * 345.0
    assert "6.3 not applicable" in b2["ltb_clause"]
    b3 = M.bending_allowable(S.props("CLR100X50X15X2"), 250.0, 1000.0, compression_flange_restrained=True)
    assert b3["Fb_MPa"] == pytest.approx(0.6 * 250.0, rel=0.01)


def test_lip_adequacy_and_unstiffened():
    sec = S.props("CLR100X50X15X2")
    lip = M.lip_adequacy_5221(sec["flats"]["flange"] / 10.0, 0.2, 250.0 * M.MPA_TO_KGF, 1.5)
    assert lip["dmin_mm"] == pytest.approx(14.4, abs=0.3) and lip["ok"]
    Fc, cl = M.Fc_unstiffened_62(5.0, 2549.0)
    assert Fc == pytest.approx(0.6 * 2549.0) and cl == "6.2(a)"


def test_combined_67_amplification_and_cm():
    sec = S.built_up("CLR250X80X25X5")
    c = M.combined_67(sec, 250.0, 60000.0, 12.0e6, 7000.0, 7000.0, 1500.0, cm_case="sway")
    assert c["Cm"] == 0.85 and c["amplification"] > 1.0
    assert c["clause"].startswith("IS 801 6.7.1") and c["dc"] is not None
    assert "interaction_stability" in c["checks"] and "interaction_strength" in c["checks"]


def test_wall_stud_81_and_connections():
    sec = S.props("CLR100X50X15X2")
    s = M.wall_stud_81(sec, 250.0, 3000.0, 300.0, 50.0, 20000.0)
    assert s["checks"]["(a) both faces"]["ok"] and s["Pmin_N"] > 0 and s["braced_against_twist"]
    assert "2 sqrt" in s["checks"]["(d) Pmin"]["cite"]
    w = M.weld_allowable_721(250.0)
    assert w["Fw_kgf_cm2"] == 1100.0                              # Fy 2549 kgf/cm2 in the 2500-3500 band
    assert M.weld_allowable_721(200.0)["Fw_kgf_cm2"] == 955.0
    b = M.bolted_connection_75(250.0, 2.0, 12.0, 3000.0, 2, 25.0, 50.0, T_member_N=6000.0)
    assert set(b["checks"]) >= {"7.5.1 edge / spacing", "7.5.3 bearing", "7.5.4 bolt shear", "7.5.2 net section"}
    assert M.interconnection_73(3000.0, 18.4, 60.0)["Smax_mm"] == pytest.approx(3000.0 * 18.4 / 120.0)
