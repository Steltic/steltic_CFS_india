"""WP3 -- end-to-end: IN_CFS_Ex1 (Delhi, hot-rolled SCBF + IS 801 studs / joists) and IN_CFS_Ex5 (Hyderabad, all-CFS
elastic portal) through india_cfs_pipeline.design_and_report.  The fixtures are the CFS_REFERENCE worked buildings;
the numbers asserted here are the contract's worked-method reference (contract/CFS_REFERENCE.md)."""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "tests", "_jobs")
os.environ["STEEL_BUILDER_JOBS"] = JOBS
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
import india_cfs_env  # noqa: E402,F401

US = re.compile(r"\b(AISI|S100|S240|S400|ASCE|AISC|LRFD|SDPWS|SFIA|ksi|kip|plf|psf|SDS|SD1)\b")


def _run(ex):
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_" + ex)
    sys.path.insert(0, fix)
    for m in ("build_and_run",):
        sys.modules.pop(m, None)
    import build_and_run as Bx
    cfg = Bx.build_cfg()
    root = os.path.join(JOBS, Bx.NAME)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root, exist_ok=True)
    shutil.copytree(os.path.join(fix, "rag"), os.path.join(root, "rag"))
    import india_cfs_pipeline as CP
    out = CP.design_and_report(Bx.NAME, cfg, outdir=root)
    pkg = json.load(open(os.path.join(root, "design", "calc_package_cfs.json")))
    sys.path.remove(fix)
    return out, pkg, root


@pytest.fixture(scope="module")
def ex1():
    return _run("Ex1")


@pytest.fixture(scope="module")
def ex5():
    return _run("Ex5")


def test_vendored_engine_is_byte_identical():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_vendored.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_ex1_lateral_frame_numbers(ex1):
    out, pkg, root = ex1
    lat = pkg["lateral_frame"]
    ss = lat["seismic_summary"]
    assert lat["system"] == "SCBF" and lat["R"] == 4.5 and ss["zone"] == "IV" and ss["Z"] == 0.24 and ss["I"] == 1.0
    assert ss["Ah"] == pytest.approx((0.24 / 2) * (1.0 / 4.5) * 2.5, rel=1e-3)          # 0.0667
    assert ss["VB_kN"] == pytest.approx(ss["Ah"] * ss["W_kN"], rel=1e-3)
    assert 1100 < ss["W_kN"] < 1400                                                     # 4 x 96 m2 light CFS floors + frame
    assert lat["seismic_analysis"]["rsa_used_in_demands"] is True                       # 7.7.1 (Zone IV)
    assert lat["drift_max"] < 0.004
    dcs = {m["role"]: m["DC"] for m in lat["members"]}
    assert all(v <= 1.0 for v in dcs.values()) and {"brace", "lateral_col", "gravity_col", "floor", "roof"} <= set(dcs)
    assert all(c["DC"] <= 1.0 for c in lat["connections"])
    import india_cfs_env
    assert lat["vendored_commit"] == india_cfs_env.vendored_commit() and len(lat["vendored_commit"]) >= 7


def test_ex1_cfs_members_and_basis(ex1):
    out, pkg, root = ex1
    assert pkg["design_basis"] == "IS801_WSM" and pkg["lateral_frame_basis"] == "IS800_LSD"
    ids = {m["role"]: m for m in pkg["cfs_members"]}
    stud, joist = ids["stud"], ids["joist"]
    assert stud["section"] == "CLR100X50X15X2" and stud["braced_against_twist"] is True
    assert stud["DC"] <= 1.0 and joist["DC"] <= 1.0 and joist["ok"] is True and stud["ok"] is True
    incs = {round(c["allowable_increase"], 4) for c in stud["checks"]
            if c["combo"].startswith(("DL+1.0W", "DL+IL+1.0W", "0.9DL")) and not c.get("informational")}
    assert incs == {round(4.0 / 3.0, 4)}
    assert all(c["allowable_increase"] == 1.0 for c in joist["checks"] if c["combo"] in ("DL", "DL+IL"))
    assert all(c["capacity_basis"] in ("IS801_allowable", "test", "EOR_input", "IS800_Table6") for c in stud["checks"])
    assert pkg["diaphragm"] and all(r["ok"] is True for r in pkg["diaphragm"])
    assert not pkg["consistency"]


def test_ex1_status_complete_after_tension_share_fix(ex1):
    """WP6-fix 922d24a in steltic_india: 12.8.2.4 tension share on the lateral load only -> Ex1 is COMPLETE."""
    out, pkg, root = ex1
    st = pkg["design_status"]
    assert st["status"] == "complete", st["reasons"]
    assert not st["reasons"]


def test_ex1_report_is_india_only(ex1):
    out, pkg, root = ex1
    html = open(os.path.join(root, "report.html"), encoding="utf-8").read()
    text = re.sub(r"<[^>]+>", " ", html)
    hits = [m.group(0) for m in US.finditer(text)]
    assert not hits, hits
    assert "MISSING" not in text
    for s in ("IS 801:1975", "IS 811:1987", "IS 875 (Part 3):2015", "IS 1893 (Part 1):2016", "IS 800:2007", "IS 18168:2023", "Ah ="):
        assert s in text
    assert os.path.exists(os.path.join(root, "viewer_3d.html")) and os.path.exists(os.path.join(root, "STATUS.md"))
    assert os.path.exists(os.path.join(root, "EOR_inputs.json"))


def test_ex5_all_cfs_portal(ex5):
    out, pkg, root = ex5
    lat = pkg["lateral_frame"]
    assert lat["seismic_basis"] == "elastic_R1" and lat["R"] == 1.0
    assert "R = 1.0" in lat["statement"] and "Section 12 is not applicable" in lat["statement"]
    ss = lat["seismic_summary"]
    assert ss["Ah"] == pytest.approx(0.125)                                              # (0.10/2)(1/1)(2.5)
    assert lat["wind_vs_eq"]["governing"] == "wind"
    d = {x["load"]: x for x in lat["drift_table"]}
    assert d["DL+1.0EL"]["ok"] and d["DL+1.0EL"]["limit"] == 0.004
    assert any(x["limit"] == pytest.approx(1 / 150) and x["ok"] for x in lat["drift_table"])   # IS 800 Table 6 h/150 at 1.0 W
    roles = {m["role"]: m for m in pkg["cfs_members"]}
    assert {"column", "rafter", "knee brace", "purlin", "girt", "joist", "mezzanine post"} <= set(roles)
    assert all(m["DC"] <= 1.0 and m["ok"] for m in roles.values())
    assert roles["column"]["n_ply"] == 2 and "Annex D" in roles["column"]["K_cite"]
    assert all(c["ok"] for c in pkg["cfs_connections"]) and all(c["dc"] <= 1.0 for c in pkg["cfs_connections"])
    assert pkg["design_status"]["status"] == "complete", pkg["design_status"]["reasons"]
    text = re.sub(r"<[^>]+>", " ", open(os.path.join(root, "report.html"), encoding="utf-8").read())
    assert not [m.group(0) for m in US.finditer(text)]
    assert "SEISMIC BASIS" in text


def test_ex5_fails_closed_without_pressures_or_combinations(ex5):
    import copy
    import india_cfs_portal as PO
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex5")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    cfg = Bx.build_cfg()
    c1 = copy.deepcopy(cfg); c1["site"].pop("k2_table")
    with pytest.raises(PO.PortalError):
        PO.run(c1, JOBS)
    c2 = copy.deepcopy(cfg); c2["load_plan"]["cfs_combinations"] = None
    with pytest.raises(PO.PortalError):
        PO.run(c2, JOBS)


def test_ex5_portal_rerun_in_place_regenerates_its_viewer(ex5):
    """WP6-fix: a second design_and_report into the same outdir (the gold-standard packages are re-run in place) must not
    trip over the existing viewer_3d.html -- the portal path has no HR lateral root, so its SVG viewer is rebuilt."""
    import copy
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex5")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    out, pkg, root = ex5
    cwd = os.getcwd()
    os.chdir(root)                                     # the failing case: cwd == outdir and viewer_3d.html already there
    try:
        import india_cfs_pipeline as CP
        out2 = CP.design_and_report(Bx.NAME, copy.deepcopy(Bx.build_cfg()), outdir=root)
    finally:
        os.chdir(cwd)
    assert out2["status"] == out["status"]
    assert os.path.getsize(os.path.join(root, "viewer_3d.html")) > 1000
