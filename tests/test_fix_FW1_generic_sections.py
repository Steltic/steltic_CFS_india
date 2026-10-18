"""2026-10 first wave, review item 1: computed thin lipped C / Z sections (cfs_generic_sections).

* labels make thickness and grade obvious (C200X65X20X1.6-G350, Z250X70X20X2.0-G350) and round-trip;
* the thin-wall routine reproduces textbook results exactly (plain channel shear centre and Cw, lipped channel m of
  IS 801 7.3, unlipped zed Cw) and the printed IS 811 rows within the 'conventional methods' tolerance;
* the grade is IS 277 grade 350 / Z275, Fy 350 MPa, inside the IS 801 Table 2 36 kgf/mm2 row (353 MPa);
* is811_sections.props / built_up and india_practical_sections resolve the generic labels; the IS 811 catalogue is
  unchanged."""
import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import cfs_generic_sections as G       # noqa: E402
import is811_sections as S             # noqa: E402
import india_practical_sections as P   # noqa: E402


def test_labels_round_trip_and_show_thickness_and_grade():
    assert G.make_label("C", 200, 65, 20, 1.6) == "C200X65X20X1.6-G350"
    assert G.make_label("Z", 250, 70, 20, 2.0) == "Z250X70X20X2.0-G350"
    assert G.make_label("C", 300, 80, 25, 3.15) == "C300X80X25X3.15-G350"
    assert G.parse_label("z250x70x20x2.0-g350") == ("Z", 250.0, 70.0, 20.0, 2.0, 350)
    assert G.looks_generic("C200X65X20X1.6-G350") and not G.looks_generic("CLR200X80X25X4")
    with pytest.raises(KeyError):
        G.props("C200X65X20X1.6-G550")                 # only the Table 2 36 kgf/mm2 row grade is carried


def test_family_grid():
    labs = G.family_labels("thin_C_G350")
    assert len(labs) == 5 * 6
    assert {G.parse_label(l)[1] for l in labs} == {100.0, 150.0, 200.0, 250.0, 300.0}
    assert {G.parse_label(l)[4] for l in labs} == {1.0, 1.2, 1.6, 2.0, 2.5, 3.15}
    cat = G.catalogue("thin_Z_G350")
    assert [r[1] for r in cat] == sorted(r[1] for r in cat)          # lightest first


def test_textbook_shear_centre_and_warping():
    b, h, t = 50.0, 100.0, 1.0
    q = G.thin_wall_props([(b, h), (0, h), (0, 0), (b, 0)], t)          # plain channel, sharp corners
    assert abs(q["xs"]) == pytest.approx(3 * b * b / (h + 6 * b), rel=1e-9)
    assert q["Cw"] == pytest.approx(b ** 3 * h ** 2 * t * (3 * b + 2 * h) / (12 * (6 * b + h)), rel=1e-9)
    c = 20.0
    q = G.thin_wall_props([(b, h - c), (b, h), (0, h), (0, 0), (b, 0), (b, c)], t)     # lipped channel, IS 801 7.3 m
    m = b * h * t / (4 * q["Ix"]) * (b * h + 2 * c * (h - 4 * c * c / (3 * h)))
    assert abs(q["xs"]) == pytest.approx(m, rel=1e-9)
    b, h = 40.0, 80.0
    q = G.thin_wall_props([(b, h), (0, h), (0, 0), (-b, 0)], t)         # unlipped zed
    assert q["Cw"] == pytest.approx(t * b ** 3 * h ** 2 * (b + 2 * h) / (12 * (2 * b + h)), rel=1e-9)
    assert q["xs"] == pytest.approx(q["xc"], abs=1e-9) and q["ys"] == pytest.approx(q["yc"], abs=1e-9)


@pytest.mark.parametrize("lab,kind", [("CLR250X80X25X4", "C"), ("CLR200X50X20X3.15", "C"), ("CLR100X50X15X2", "C"),
                                      ("LZ80X40X20X2", "Z"), ("LZ90X40X20X3.15", "Z")])
def test_reproduces_is811_rows(lab, kind):
    p = S.props(lab)
    q = G.thin_wall_props(G.centreline(kind, p["h"], p["b"], p["c"], p["t"]), p["t"])
    for k in ("A", "Ix", "Iy"):
        assert q[k] == pytest.approx(p[k], rel=0.035), (lab, k)
    if p.get("J"):
        assert q["J"] == pytest.approx(p["J"], rel=0.06)
    if p.get("Cw"):
        assert q["Cw"] == pytest.approx(p["Cw"], rel=0.10)
    if kind == "Z":
        assert abs(q["Ixy"]) == pytest.approx(p["Ixy"], rel=0.035)


def test_props_record_and_grade():
    c = S.props("C200X65X20X1.6-G350")                    # dispatched through the section DB
    assert c["generic"] and c["type"] == "CLR" and c["family"] == "thin_C_G350"
    assert c["Fy"] == 350.0 and 350.0 <= 36 * 9.80665 + 1e-9               # inside the 36 kgf/mm2 row (353.0 MPa)
    assert "IS 277 grade 350" in c["material"] and "Z275" in c["material"] and "IS 801 3.6" in c["material"]
    assert c["mass_kg_m"] == pytest.approx(c["A"] * 7850e-6, rel=1e-9)
    assert c["Zx"] == pytest.approx(c["Ix"] / 100.0, rel=1e-9)
    assert c["flats"]["web"] == pytest.approx(200.0 - 2 * (2.4 + 1.6))
    z = S.props("Z250X70X20X2.0-G350")
    assert z["type"] == "LZ" and z["Iu"] > z["Ix"] > z["Iy"] > z["Iv"] > 0 and 0 < z["tan_alpha"] < 1
    assert z["r_min"] == pytest.approx(z["rv"])
    pair = S.built_up("C200X65X20X1.6-G350", 2)
    assert pair["A"] == pytest.approx(2 * c["A"]) and pair["designator"] == "2xC200X65X20X1.6-G350"


def test_is801_geometry_limits_flag_slender_sections():
    thin = S.props("C300X80X25X1.0-G350")                  # h/t ~ 293 > 150 (IS 801 5.2.4)
    assert not thin["is801_geometry_ok"]
    assert any(r["check"].startswith("5.2.4") and not r["ok"] for r in thin["is801_geometry"])
    assert S.props("C200X65X20X1.6-G350")["is801_geometry_ok"]


def test_practical_resolver_and_catalogue_unchanged():
    r = P.resolve_is811_label("2xC200X65X20X1.6-G350")
    assert r["found"] and r["generic"] and not r["in_catalog"] and r["Fy"] == 350.0 and r["n_ply"] == 2
    assert P.resolve_is811_label("CLR250X80X25X4")["in_catalog"]
    assert S.props("CLR250X80X25X4")["A"] == 1700.0 and S.props("CLR250X80X25X4")["Fy"] is None
