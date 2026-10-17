"""2026-10 first wave, review items 2 / 3 and lead item 5 (india_cfs_members):

* restraint basis: every purlin / girt / joist / stud row carries 'restraint'; with no declared bracing the free flange
  is checked unbraced over the span (an L_unbraced_mm alone is not used); the legacy PEB 'sag_rods' = n stays valid;
* IS 801 8.2: 8.2.1 spacing (reference when one flange is sheeted, blocking when neither is), 8.2.2 brace force,
  sag rods sized to IS 800 11.2.1;
* girts report 'suction' / 'pressure', never 'uplift';
* collateral_kNm2 / pv_kNm2: included in gravity rows, excluded from uplift rows, separate load-table rows;
* auto-select: the lightest passing section of the declared family, with the selection record."""
import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_members as CM   # noqa: E402
import is811_sections as S       # noqa: E402


def _cfg():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex3")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    cfg = copy.deepcopy(Bx.build_cfg())
    cfg["load_plan"]["story_forces"] = {}
    return cfg


def _bend(rec, word):
    return [c for c in rec["checks"] if "bending" in c["check"] and word in c["check"]]


def test_no_declared_bracing_means_unbraced():
    cfg = _cfg()
    braced = CM.design_purlins(cfg, "purlin")
    pu = cfg["cfs_members"]["purlins"]
    pu.pop("bracing")                                               # L_unbraced_mm 3000 stays, but no bracing system
    free = CM.design_purlins(cfg, "purlin")
    up_b, up_f = _bend(braced, "uplift"), _bend(free, "uplift")
    assert up_b and up_f
    assert all(c["L_unbraced_mm"] == pytest.approx(3000.0) for c in up_b)
    assert all(c["L_unbraced_mm"] == pytest.approx(5000.0) for c in up_f)   # the span
    assert max(c["dc"] for c in up_f) > max(c["dc"] for c in up_b)
    assert "UNBRACED" in up_f[0]["restraint"] and "not used" in free["restraint_basis"]["free_text"]
    assert "braced at a = 3000 mm by 1 sag-rod line(s)" in up_b[0]["restraint"]
    assert all(c.get("restraint") for c in braced["checks"])        # every row prints the restraint basis


def test_legacy_sag_rods_integer_is_read():
    cfg = _cfg()
    pu = cfg["cfs_members"]["purlins"]
    pu.pop("bracing"); pu.pop("L_unbraced_mm"); pu["sag_rods"] = 2
    rec = CM.design_purlins(cfg, "purlin")
    br = rec["restraint_basis"]["bracing"]
    assert br["declared"] and br["type"] == "sag_rods" and br["lines"] == 2
    assert br["spacing_mm"] == pytest.approx(5000.0 / 3.0)


def test_is801_8_2_rows_and_sag_rod_sizing():
    rec = CM.design_purlins(_cfg(), "purlin")
    rows = {c["check"].split(" (")[0]: c for c in rec["checks"] if c["combo"].startswith("bracing")}
    s821 = rows["8.2.1 brace spacing a <= L/4"]
    assert s821["informational"] and s821["dc"] is None and s821["a_over_L4"] == pytest.approx(3000.0 / 1250.0)
    p1 = [c for c in rec["checks"] if c["check"].startswith("8.2.2 brace force")][0]
    sec = S.props(rec["section"])
    kp, _ = CM.k_prime_82(sec)
    # K' = m/d with m from IS 801 7.3 -- close to the IS 811 printed shear-centre offset (x0 - Cy + t/2)
    assert kp * sec["h"] == pytest.approx(sec["x0"] - sec["Cy"] + sec["t"] / 2.0, rel=0.06)
    rod = [c for c in rec["checks"] if c["check"].startswith("sag rod")][0]
    assert rod["ok"] and rod["dc"] <= 1.0 and rod["value"] > p1["value"] and rod["rod"]["d_mm"] >= 12.0
    rc = CM.rod_capacity(12.0)
    assert rc["T_allow_N"] == pytest.approx(min(0.6 * 250 * rc["Ag_mm2"], 0.69 * 0.9 * rc["A_root_mm2"] * 410 / 1.25))


def test_neither_flange_sheeted_makes_8_2_1_blocking():
    cfg = _cfg()
    jt = cfg["cfs_members"]["joists"]
    jt["compression_flange_restrained"] = False
    jt["bracing"] = {"type": "bridging", "lines": 1, "capacity_N": 5000.0, "capacity_source": "test value -- VERIFY"}
    rec = CM.design_joists(cfg)
    s821 = [c for c in rec["checks"] if c["check"].startswith("8.2.1")][0]
    assert not s821.get("informational") and s821["ok"] is False and s821["detailing"]    # 1500 > 3000/4
    assert rec["ok"] is False


def test_joist_restraint_must_be_declared():
    cfg = _cfg()
    cfg["cfs_members"]["joists"].pop("compression_flange_restrained")
    rec = CM.design_joists(cfg)
    b = [c for c in rec["checks"] if "bending" in c["check"]][0]
    assert b["L_unbraced_mm"] == pytest.approx(3000.0) and "not declared" in b["restraint"]
    assert any(c["check"].startswith("8.2.1") and c["ok"] is False for c in rec["checks"])


def test_girts_see_suction_not_uplift():
    rec = CM.design_purlins(_cfg(), "girt")
    names = " ".join(c["check"] for c in rec["checks"])
    assert "uplift" not in names and "suction, inner flange" in names and "pressure, outer flange" in names
    assert rec["restraint_basis"]["free_flange"] == "inner"
    assert [r["component"] for r in rec["load_table"]][0].startswith("wind suction")


def test_collateral_and_pv_only_where_dead_load_adds():
    cfg = _cfg()
    base = CM.design_purlins(cfg, "purlin")
    rec = CM.design_purlins(cfg, "purlin", collateral_kNm2=0.25, pv_kNm2=0.15)
    def m(r, combo):
        return [c for c in r["checks"] if c["combo"] == combo and "bending" in c["check"]][0]
    g0, g1 = m(base, "DL+IL"), m(rec, "DL+IL")
    assert g1["nonpermanent_dead_included"] and g1["M_Nmm"] > g0["M_Nmm"]
    up = [c for c in rec["checks"] if c["combo"].startswith("0.9DL+") and "uplift" in c["check"]][0]
    up0 = [c for c in base["checks"] if c["combo"] == up["combo"] and "uplift" in c["check"]][0]
    assert not up["nonpermanent_dead_included"] and up["M_Nmm"] == pytest.approx(up0["M_Nmm"])
    lt = {r["component"].split(" (")[0]: r for r in rec["load_table"]}
    assert lt["collateral"]["kNm2"] == 0.25 and lt["rooftop PV"]["kNm2"] == 0.15
    # spec / cfg['loads'] keys work the same way (the PEB secondary jobs pass cfg dicts)
    cfg2 = _cfg(); cfg2["loads"]["collateral_kNm2"] = 0.25; cfg2["cfs_members"]["purlins"]["pv_kNm2"] = 0.15
    assert m(CM.design_purlins(cfg2, "purlin"), "DL+IL")["M_Nmm"] == pytest.approx(g1["M_Nmm"])
    j0, j1 = CM.design_joists(_cfg()), CM.design_joists(_cfg(), collateral_kNm2=0.3)
    assert m(j1, "DL+IL")["M_Nmm"] > m(j0, "DL+IL")["M_Nmm"]


def test_auto_select_lightest_passing_thin_section():
    cfg = _cfg()
    pu = cfg["cfs_members"]["purlins"]
    pu["auto_select"] = {"family": "thin_C_G350"}
    pu["section"] = "auto"
    recs = CM.design_all(dict(cfg, cfs_members={"Fy_MPa": 294.0, "purlins": pu}))
    rec = recs[0]
    a = rec["auto_selected"]
    assert rec["ok"] is True and a["family"] == "thin_C_G350" and rec["section"].endswith("-G350")
    assert rec["Fy_MPa"] == 350.0 and "IS 277 grade 350" in rec["material"]
    lighter = [c for c in CM.family_candidates("thin_C_G350") if c[1] < rec["mass_kg_m"] - 1e-9]
    assert len(a["lighter_rejected"]) == min(6, len(lighter)) and a["n_tried"] == len(lighter) + 1
    for lab, *_ in lighter:                                        # none of the lighter candidates passes
        r = CM.design_purlins(cfg, "purlin", spec=dict(pu, section=lab))
        assert r["ok"] is not True
    # reference IS 811 section of the same group is recorded for the before / after comparison
    pu2 = dict(pu, section="CLR180X80X20X3.15")
    r2 = CM.design_all(dict(cfg, cfs_members={"Fy_MPa": 294.0, "purlins": pu2}))[0]
    assert r2["auto_selected"]["reference_section"] == "CLR180X80X20X3.15"
    assert r2["mass_kg_m"] < r2["auto_selected"]["reference_mass_kg_m"]


def test_auto_select_studs_over_all_storeys_and_is811_family():
    cands = CM.family_candidates("IS811_CLR", {"auto_select": {"depth_min_mm": 200, "depth_max_mm": 200}})
    assert cands and all(S.props(c[0])["h"] == 200.0 for c in cands)
    with pytest.raises(ValueError):
        CM.family_candidates("thin_X_G999")
