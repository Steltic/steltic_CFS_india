"""C01 (CFS-A-01 / A-11, E6 completion): IS 801 bending stress fb from N-mm demands.

1 N-mm = 0.1 N-cm, so kgf-cm = N-mm x N_TO_KGF / 10 (the old / 1e3 made fb 100 x too small in 6.7, 6.4.2 and the
fby term).  Hand values: CLR100X50X15X2 (IS 811: Ix 67.3 cm4, Zy 4.40 cm3, web flat 90 mm), M = 638 293 N-mm."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import is811_sections as S   # noqa: E402
import is801_members as M    # noqa: E402

MX = 638293.0


def test_unit_helper():
    assert M.nmm_to_kgfcm(98.0665) == pytest.approx(1.0)
    assert M.nmm_to_kgfcm(1.0e6) == pytest.approx(1.0e6 / 98.0665)


def test_fbx_hand_value_67():
    sec = S.props("CLR100X50X15X2")
    b = M.bending_allowable(sec, 240.0, 1000.0)
    assert b["Sx_eff_cm3"] == pytest.approx(13.46, rel=1e-3)
    r = M.combined_67(sec, 240.0, 5000.0, MX, 3000.0, 1000.0, 1000.0, wind_eq=True)
    assert r["fbx_MPa"] == pytest.approx(MX / 13460.0, rel=1e-3)          # 47.42 MPa (engine gave 0.474)
    assert r["fbx_MPa"] == pytest.approx(47.42, abs=0.01)
    assert r["dc"] == pytest.approx(0.332, abs=0.002)                       # was 0.088


def test_fbw_hand_value_642():
    sec = S.props("CLR100X50X15X2")
    w = M.web_bending_shear_643(sec, 240.0, MX, 2000.0)
    assert w["web_bending"]["value"] == pytest.approx(MX * 45.0 / 673000.0, rel=1e-6)   # M (h/2)/Ix = 42.68 MPa
    assert w["web_bending"]["value"] == pytest.approx(42.68, abs=0.01)
    assert w["web_bending"]["clause"] == "IS 801 6.4.2"


def test_fby_hand_value_my_path():
    sec = S.props("CLR100X50X15X2")
    My = 100000.0
    r0 = M.combined_67(sec, 240.0, 5000.0, 0.0, 3000.0, 1000.0, 1000.0)
    r1 = M.combined_67(sec, 240.0, 5000.0, 0.0, 3000.0, 1000.0, 1000.0, My_Nmm=My)
    assert r1["fby_MPa"] == pytest.approx(My / 4400.0, rel=1e-6)            # My / Zy = 22.73 MPa
    Fby = 0.6 * 240.0 * M.MPA_TO_KGF * M.KGF_CM2
    assert r1["dc"] - r0["dc"] == pytest.approx((My / 4400.0) / Fby, rel=1e-3)
