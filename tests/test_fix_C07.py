"""C07 (CFS-A-12): all-CFS portal -- gable Cpe from IS 875-3 Table 5 of the building (was a fixed 0.7 + 0.5), bracing
overturning axial in the mezzanine posts under EL, a mezzanine beam role (IS 801 6.1 - 6.5), an anchorage embedment
EOR input slot on the column base."""
import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "tests", "_jobs")
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_portal as PO   # noqa: E402


def _cfg():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex5")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    return Bx.build_cfg()


@pytest.fixture(scope="module")
def run5():
    os.makedirs(JOBS, exist_ok=True)
    return PO.run(_cfg(), JOBS)


def test_gable_cpe_table5(run5):
    g = PO.gable_cpe(_cfg())
    assert g["theta_deg"] == 90.0 and g["windward"] == pytest.approx(0.7) and g["leeward"] == pytest.approx(-0.2)
    assert g["net"] == pytest.approx(0.9)                                # h/w 0.29, l/w 1.25 (was 1.2)
    lb = [c for c in run5["connections"] if c["id"].startswith("longitudinal-bracing")][0]
    gw = lb["gable_wind"]
    assert gw["F_N"] == pytest.approx(0.9 * run5["wind_summary"]["pd_kNm2"] * 24.0 * (7.0 + 8.4) / 2.0 * 1e3)


def test_mezzanine_posts_carry_bracing_overturning(run5):
    post = [m for m in run5["members"] if m["role"] == "mezzanine post"][0]
    el = [r for r in post["checks"] if "EL(mezzanine X)" in r["combo"]]
    assert {r["combo"] for r in el} == {"DL+1.0EL(mezzanine X)", "DL+IL+1.0EL(mezzanine X)"}
    Fe = run5["seismic_summary"]["VB_mezzanine_kN"] * 1e3
    assert el[0]["P_overturning_N"] == pytest.approx(Fe / 2 * 3500.0 / 3000.0, rel=1e-3)
    assert all(r["allowable_increase"] == pytest.approx(4 / 3) for r in el)


def test_mezzanine_beam_role(run5):
    bm = [m for m in run5["members"] if m["role"] == "mezzanine beam"][0]
    assert bm["id"] == "mezzanine-beam-2xCLR250X80X25X4" and bm["ok"] is True
    b = [r for r in bm["checks"] if r["check"] == "6.1/6.2/6.3 bending" and r["combo"] == "DL+IL"][0]
    assert b["M_Nmm"] == pytest.approx((1.5 + 7.5) * 3.0 * 3000.0 ** 2 / 8.0)
    cfg = _cfg(); cfg["mezzanine"].pop("beams")
    rec = PO.mezzanine_beam(cfg, 294.0)
    assert rec["ok"] is None and "not declared" in rec["checks"][0]["note"]


def test_anchorage_embedment_slot(run5):
    base = [c for c in run5["connections"] if c["id"] == "column-base"][0]
    emb = [r for r in base["checks"] if r["check"] == "anchorage embedment (EOR)"]
    assert emb and emb[0]["capacity_basis"] == "EOR_input" and emb[0]["limit"] == 45200.0 and emb[0]["ok"] is True
    cfg = _cfg(); cfg["cfs_connections_spec"]["base"]["anchors"].pop("embedment_capacity_N")
    out = PO.run(cfg, JOBS)
    base = [c for c in out["connections"] if c["id"] == "column-base"][0]
    assert base["ok"] is None and any(r["check"] == "anchorage embedment (EOR)" and r["ok"] is None for r in base["checks"])
