"""2026-10 second wave (CFS): C1 scripted re-vendor, C2 Ex3 base plate as a design result, C3 report-only fixes
(headline strength ratio with slenderness beside it, soil basis, one citation style, scope / diaphragm / Ta notes)."""
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))


# ================================================================================================ C1 re-vendor
def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd)] + list(args), check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                            GIT_COMMITTER_EMAIL="t@t"))


def _fake_layout(tmp_path):
    """A CFS repo copy (scripts + hr_vendor with a pin) and an HR git repo with two commits."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for fn in ("check_vendored.py", "revendor_hr.py"):
        (repo / "scripts" / fn).write_text(open(os.path.join(SCRIPTS, fn)).read())
    hv = repo / "steel_engine" / "hr_vendor"
    hv.mkdir(parents=True)
    hr = tmp_path / "steltic_india"
    (hr / "steel_engine" / "tools").mkdir(parents=True)
    _git(tmp_path, "init", "-q", str(hr))
    (hr / "steel_engine" / "a.py").write_text("a = 1\n")
    (hr / "steel_engine" / "gone.py").write_text("g = 1\n")
    (hr / "steel_engine" / "tools" / "t.py").write_text("tool = 1\n")
    _git(hr, "add", "-A")
    _git(hr, "commit", "-q", "-m", "c1")
    c1 = subprocess.run(["git", "-C", str(hr), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (hr / "steel_engine" / "a.py").write_text("a = 2\n")
    (hr / "steel_engine" / "new.py").write_text("n = 1\n")
    (hr / "steel_engine" / "gone.py").unlink()
    _git(hr, "add", "-A")
    _git(hr, "commit", "-q", "-m", "c2")
    c2 = subprocess.run(["git", "-C", str(hr), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (hv / "a.py").write_text("a = 1\n")
    (hv / "gone.py").write_text("g = 1\n")
    (hv / "VENDORED_FROM.md").write_text("# hr_vendor\n\nSource: steltic_india (hot-rolled IS 800 engine), branch old\n"
                                         "Commit: **%s** [old]\n\nRules (x):\n- byte-identical\n" % c1)
    return repo, hr, c1, c2


def test_C1_revendor_is_scripted_and_repeatable(tmp_path):
    repo, hr, c1, c2 = _fake_layout(tmp_path)
    env = dict(os.environ, STELTIC_HR_ROOT=str(hr))
    chk = [sys.executable, str(repo / "scripts" / "check_vendored.py")]
    assert subprocess.run(chk, capture_output=True, text=True, env=env).returncode == 0      # pinned at c1: identical
    rv = [sys.executable, str(repo / "scripts" / "revendor_hr.py"), "--commit", c2[:7], "--label", "fix/x"]
    dry = subprocess.run(rv + ["--dry-run"], capture_output=True, text=True, env=env)
    assert dry.returncode == 0 and "WRITE a.py" in dry.stdout and "ADD   new.py" in dry.stdout and "DEL   gone.py" in dry.stdout
    assert (repo / "steel_engine" / "hr_vendor" / "a.py").read_text() == "a = 1\n"            # dry run touches nothing
    r = subprocess.run(rv, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    hv = repo / "steel_engine" / "hr_vendor"
    assert (hv / "a.py").read_text() == "a = 2\n" and (hv / "new.py").read_text() == "n = 1\n"
    assert not (hv / "gone.py").exists() and not (hv / "tools").exists()
    pin = (hv / "VENDORED_FROM.md").read_text()
    assert "Commit: **%s**" % c2 in pin and "branch fix/x" in pin and "re-sync (scripts/revendor_hr.py)" in pin
    assert pin.index("re-sync (scripts/revendor_hr.py)") < pin.index("Rules (")
    assert "3 identical, 0 different" in r.stdout or "2 identical, 0 different" in r.stdout
    # repeatable: a second run against the same commit writes nothing and the check still passes
    again = subprocess.run(rv + ["--dry-run"], capture_output=True, text=True, env=env)
    assert "0 to write (0 new), 0 to remove" in again.stdout
    assert subprocess.run(chk, capture_output=True, text=True, env=env).returncode == 0


def test_C1_vendor_pinned_to_hr_main():
    """hr_vendor follows steltic_india main after the second wave and the PEB variations merge (c7c9cc9); the
    PEB-LEVERS hooks it brings do nothing without cfg['peb_rules'], so the CFS results are unchanged."""
    pin = open(os.path.join(ROOT, "steel_engine", "hr_vendor", "VENDORED_FROM.md")).read()
    assert "Commit: **c7c9cc9e65b0efdbb8502ede3f8fb6022c5e92c6**" in pin
    for f in ("report_second_wave.py", "peb_levers.py", "peb_autosize.py"):
        assert os.path.exists(os.path.join(ROOT, "steel_engine", "hr_vendor", f))
    import india_cfs_env
    assert india_cfs_env.vendored_commit().startswith("c7c9cc9")


# ================================================================================================ fixtures
JOBS = os.path.join(ROOT, "tests", "_jobs")


def _run(ex, tweak=None):
    import shutil
    os.environ["STEEL_BUILDER_JOBS"] = JOBS
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_" + ex)
    sys.path.insert(0, fix)
    sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    cfg = Bx.build_cfg()
    if tweak:
        tweak(cfg)
    root = os.path.join(JOBS, Bx.NAME + "_sw2")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root, exist_ok=True)
    shutil.copytree(os.path.join(fix, "rag"), os.path.join(root, "rag"))
    import india_cfs_pipeline as CP
    out = CP.design_and_report(Bx.NAME, cfg, outdir=root)
    pkg = json.load(open(os.path.join(root, "design", "calc_package_cfs.json")))
    sys.path.remove(fix)
    return out, pkg, root, open(os.path.join(root, "report.html"), encoding="utf-8").read()


def _text(html_):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_)).replace("&amp;", "&")


@pytest.fixture(scope="module")
def ex3():
    def tw(cfg):
        cfg["cfs_connections_spec"]["base"]["compare_plates"] = [{"B_mm": 400.0, "L_mm": 500.0, "t_plate_mm": 32.0}]
        cfg["portal"]["base_reason"] = "fixed bases kept by owner decision"
    return _run("Ex3", tw)


@pytest.fixture(scope="module")
def ex7():
    return _run("Ex7")


# ================================================================================================ C2 base plate
def test_C2_plate_is_a_design_result(ex3):
    out, pkg, root, html_ = ex3
    assert out["status"] == "complete"
    base = [c for c in pkg["cfs_connections"] if c["id"] == "column-base"][0]
    pdz = base["plate_design"]
    a = pdz["adopted"]
    assert (a["B_mm"], a["L_mm"], a["t_mm"]) == (500.0, 600.0, 40.0)
    assert a["dc"] == pytest.approx(base["dc"], rel=1e-9) and a["ok"] is True       # the governing check of the design run
    assert a["dc"] == pytest.approx(a["value"] / a["limit"], rel=1e-6)
    assert a["governing_check"] == max(a["checks_dc"], key=a["checks_dc"].get)
    sm = pdz["compared"][0]
    assert (sm["B_mm"], sm["L_mm"], sm["t_mm"]) == (400.0, 500.0, 32.0)
    assert sm["ok"] is False and sm["dc"] > 1.0 and sm["governing_check"] == "plate bending (uplift side)"
    assert "lever arm f = 200 mm" in sm["anchors"]                       # anchors kept 50 mm from the smaller plate's edge
    fx = pdz["fixity"]
    assert fx["base"] == "fixed" and fx["K_pinned"] > 2.0 * fx["K_fixed"] > 2.0
    assert fx["KLr_pinned"] == pytest.approx(fx["KLr_fixed"] * fx["K_pinned"] / fx["K_fixed"], rel=1e-9)
    t = _text(html_)
    assert "Column base plate: design result" in t and "Adopted plate 500 x 600 x 40 mm" in t
    assert re.search(r"smaller 400 x 500 x 32 mm plate fails on plate bending \(uplift side\) at a ratio of 1\.\d{3}", t)
    assert "Why fixed bases" in t and "IS 801 6.6.3 limit of 200" in t and "owner decision" in t


def test_C2_frame_unchanged_by_the_comparison(ex3):
    """The compared plate never feeds back: the members, the reactions and the adopted base D/C are the design run's."""
    out, pkg, root, _ = ex3
    base = [c for c in pkg["cfs_connections"] if c["id"] == "column-base"][0]
    assert base["type"].startswith("base plate 500.0x600.0x40.0")
    col = [m for m in pkg["cfs_members"] if m["role"] == "column"][0]
    assert col["DC"] == pytest.approx(0.853, abs=0.0015)                # COLUMN_67_DC of the WP3 reference test


# ================================================================================================ C3 headline
def _m(mid, rows):
    return {"id": mid, "designator": mid.split("-", 1)[-1], "checks": rows,
            "DC": max(r["dc"] for r in rows if r.get("dc") is not None and not r.get("detailing") and not r.get("informational"))}


def test_C3_row_classes():
    import report_cfs_second_wave as RS
    assert RS.row_class({"check": "6.5 web crippling (end reaction)", "clause": "IS 801 6.5(b)(1)"}) == "strength"
    assert RS.row_class({"check": "deflection under imposed load", "capacity_basis": "IS800_Table6"}) == "serviceability"
    assert RS.row_class({"check": "(b) a <= amax", "clause": "IS 801 8.1 (b)", "combo": "8.1 bracing"}) == "bracing_81"
    assert RS.row_class({"check": "5.2.4(a) web h/t", "detailing": True}) == "detailing"
    assert RS.row_class({"check": "7.3 (a) interconnection spacing"}) == "detailing"
    assert RS.row_class({"check": "sag rod M16 tension (sized)", "detailing": True, "brace_element": True}) == "brace_element"
    assert RS.row_class({"check": "8.2.2 brace force", "informational": True}) == "information"


def test_C3_headline_is_strength_not_deflection():
    import report_cfs_second_wave as RS
    pkg = {"cfs_members": [
        _m("purlin-C200X65X20X1.6-G350", [
            {"combo": "service", "check": "deflection", "value": 29.0, "limit": 30.0, "dc": 0.968, "capacity_basis": "IS800_Table6", "units": "mm"},
            {"combo": "DL+IL", "check": "6.1/6.2/6.3 bending", "value": 5.0e6, "limit": 7.0e6, "dc": 0.714, "units": "N-mm"}]),
        _m("joist-C200X65X20X2.5-G350", [
            {"combo": "DL+IL", "check": "6.5 web crippling (end reaction)", "value": 7760.0, "limit": 10000.0, "dc": 0.776, "units": "N"},
            {"combo": "geometry", "check": "5.2.4(a) web h/t", "value": 80.0, "limit": 100.0, "dc": 0.8, "detailing": True}])]}
    h = RS.headline(pkg)
    assert h["strength"]["dc"] == 0.776 and h["strength"]["member"].startswith("joist")
    assert h["serviceability"]["dc"] == 0.968 and h["member_dc_max"]["dc"] == 0.968
    assert h["detailing"]["dc"] == 0.8 and h["slenderness"] is None and "does not apply" in h["slenderness_note"]
    s = RS.headline_sentence(h)
    assert s.startswith("worst cold-formed member strength ratio 0.776 (joist-C200X65X20X2.5-G350, 6.5 web crippling")
    # every ratio names its source, so the package consistency check never reads a bare 0.80 as a literal constant
    import consistency as CC
    assert not [x for x in CC._dc_issues({"headline": h}) if "literal" in x or "stored dc" in x]


def test_C3_slenderness_from_compression_rows():
    import report_cfs_second_wave as RS
    stud = _m("stud-S1-C100X50X15X1.0-G350", [
        {"combo": "DL+1.0W_X", "check": "interaction", "value": 0.5, "limit": 1.0, "dc": 0.5, "P_N": 650.0, "KL_r": 75.4},
        {"combo": "DL", "check": "interaction", "value": 0.1, "limit": 1.0, "dc": 0.1, "P_N": 0.0, "KL_r": 250.0}])
    r = RS.member_ratios(stud)
    assert r["slenderness"] == {"KL_r": 75.4, "limit": 200.0, "ratio": round(75.4 / 200.0, 6), "clause": "IS 801 6.6.3",
                                "basis": RS.SLENDER_TEXT}                 # a row without axial compression is not counted
    assert "KL/r 75.4 / 200 (0.377)" in RS.member_ratio_text(stud)


def test_C3_headline_in_fixture_report_and_json(ex7):
    out, pkg, root, html_ = ex7
    assert out["status"] == "complete"
    h = json.load(open(os.path.join(root, "design", "headline.json")))
    assert h == pkg["headline"]
    assert h["strength"]["dc"] <= 1.0 and h["slenderness"]["limit"] == 200.0
    studs = [m for m in pkg["cfs_members"] if m["role"] == "stud"]
    klr = max(c["KL_r"] for m in studs for c in m["checks"] if c.get("KL_r") is not None)
    assert h["slenderness"]["KL_r"] == pytest.approx(klr)
    import is811_sections as S
    sec = S.props(studs[0]["section"])
    assert klr == pytest.approx(max(m["height_mm"] for m in studs) / sec["rx"], abs=0.2)    # KL = L about x (in plane)
    t = _text(html_)
    assert "Headline: worst cold-formed member strength ratio %.3f" % h["strength"]["dc"] in t
    assert "Governing ratios" in t and "IS 801 6.6.3" in t
    # the frame's own headline travels from its report (strength first, KL/r against IS 800 Table 3 beside it)
    fh = pkg["lateral_frame"]["headline"]
    assert fh["strength"]["dc"] <= 1.0 and fh["slenderness"]["limit"] in (180, 180.0)
    assert "Frame headline (its own report): worst member strength ratio" in t
    assert all("strength_dc" in m for m in pkg["lateral_frame"]["members"])
    assert "strength ratio" in t and "KL/r / limit (ratio)" in t


def test_C3_member_header_prints_strength_first(ex7):
    _, pkg, _, html_ = ex7
    t = _text(html_)
    j = [m for m in pkg["cfs_members"] if m["role"] == "joist"][0]
    assert re.search(re.escape(j["id"]) + r" -- .*? strength ratio \d\.\d{3} \(", t)


# ================================================================================================ C3 soil / Ta
def _pkg_ss(**ss):
    base = {"zone": "III", "soil": "II", "Z": 0.16, "I": 1.0, "R": 4.5, "Ta_x_s": 0.3, "Ta_y_s": 0.3, "rho_min": 0.011}
    base.update(ss)
    return {"lateral_frame": {"seismic_summary": base}}


def test_C3_soil_basis_and_type_III_note():
    import report_cfs_second_wave as RS
    cfg = {"site": {"soil": "II"}}
    h = RS.soil_html(cfg, _pkg_ss())
    assert "Type II, medium stiff soil" in h and "confirm by site investigation" in h and "would not change" in h
    # past the Type II corner (0.55 s): Type III keeps 2.5 to 0.67 s -> V_B x 2.5 / (1.36 / 0.6) = 1.10
    h2 = RS.soil_html(cfg, _pkg_ss(Ta_x_s=0.6, Ta_y_s=0.3))
    assert "V_B ratio" in h2 and "1.10" in h2
    h3 = RS.soil_html({"site": {"soil": "III", "soil_note": "reclaimed coastal site"}}, _pkg_ss(soil="III"))
    assert "Type III" in h3 and "reclaimed coastal site" in h3 and "softest soil type" in h3


def test_C3_ta_note_for_moment_frame_directions():
    import report_cfs_second_wave as RS
    cfg = {"all_cfs_portal": True, "portal": {"apex_m": 8.4, "spans_m": [12.0, 12.0]}}
    ta = 0.09 * 8.4 / 24.0 ** 0.5
    pkg = _pkg_ss(zone="II", Z=0.1, R=1.0, Ta_x_s=ta, Ta_y_s=ta, Ta_formula="0.09 h/sqrt(d) (7.6.2(c)), h = apex, d = frame width")
    n = RS.ta_notes(cfg, pkg)
    assert [r["dir"] for r in n] == ["X"]
    assert n[0]["Ta_a_s"] == pytest.approx(0.085 * 8.4 ** 0.75, rel=1e-3) and n[0]["VB_ratio"] == 1.0
    assert "would not change" in RS.ta_html(cfg, pkg)
    hr = {"lateral_frame": {"system": "SCBF", "moment_lines": [["X", 0], ["X", 1]], "hr_cfg_extra": {"system": "SMF+SCBF"}}}
    pk = _pkg_ss(Ta_x_s=0.1273, Ta_y_s=0.0779, d_x_m=18.0, d_y_m=48.0,
                 Ta_formula="0.09 h/sqrt(d) (IS 1893 7.6.2(c) all other buildings; braced / CFS-clad frame is not a bare MRF)")
    n2 = RS.ta_notes(hr, pk)
    assert [r["dir"] for r in n2] == ["X"] and n2[0]["h_m"] == pytest.approx(6.0, abs=0.01)
    # a direction already on the bare-frame formula gets no note
    pk3 = _pkg_ss(Ta_formula="IS 1893 7.6.2: Y (transverse SMRF, bare steel MRF) 0.085 h^0.75; X (EBF) 0.09 h/sqrt(d)",
                  d_x_m=76.0, d_y_m=21.0)
    assert RS.ta_notes({"lateral_frame": {"moment_lines": [["Y", 0]]}}, pk3) == []


def test_C3_map_reading_sources():
    import report_cfs_second_wave as RS
    assert "Fig. 1 basic wind speed map" in RS.vb_source_text({"Vb_source": "derived_from_map"}, {})
    assert RS.vb_source_text({}, {}) == "IS 875 (Part 3):2015 Annex A"
    assert "seismic zone map" in RS.zone_text({"zone": "IV", "Z": 0.24, "zone_source": "derived_from_map"})


def test_C3_diaphragm_sources_flagged():
    import report_cfs_second_wave as RS
    unsourced = ("EOR input: 18 mm cement-bonded board on CFS joists at 400, screws 100 mm edge / 300 mm field, blocked; "
                 "allowable diaphragm shear 8.0 kN/m from the manufacturer's tested diaphragm table (report to be filed) -- VERIFY")
    assert RS.diaphragm_source(unsourced)[0] == "unsourced"
    assert RS.diaphragm_source("EOR roof-bracing calc: 3 braced roof bays per side ...")[0] == "calculated"
    rows = [{"storey": 6, "dir": "Y", "governing_line_m": 22.667, "v_unit_kN_per_m": 7.9295, "capacity": 8.0,
             "capacity_source": unsourced},
            {"storey": 5, "dir": "Y", "governing_line_m": 0.0, "v_unit_kN_per_m": 6.73, "capacity": 8.0, "capacity_source": unsourced}]
    h = RS.diaphragm_notes_html(rows)
    assert "storey 6, Y direction, line at 22.67 m: 7.93 / 8.00 kN/m (ratio 0.99)" in h and "storey 5" not in h


def test_C3_scope_and_portal_weight():
    import report_cfs_second_wave as RS
    s = RS.scope_html({}, {"cfs_connections": []}, "hybrid")
    assert "fire resistance" in s and "acoustic performance" in s and "Outside this design" in s
    w = RS.portal_weight_text({"W_kN": 63.7, "W_portal_total_kN": 445.8, "VB_portal_total_kN": 55.72,
                               "mezzanine_lateral": "own bracing (not on the portal)"})
    assert w.startswith("W = 63.7 kN is the seismic weight of one transverse frame") and "W = 445.8 kN" in w


# ================================================================================================ C3 citations
def test_C3_one_citation_style():
    import report_cfs_second_wave as RS
    n = RS.normalise_citations
    assert n("IS 875-3 Annex A (Chennai 50 m/s)") == "IS 875 (Part 3) Annex A (Chennai 50 m/s)"
    assert n("IS 1893 (Part 1):2016 + Amd 1, 2") == "IS 1893 (Part 1):2016 with Amendments 1 and 2"
    assert n("IS 2062:2025 quality C") == "IS 2062 (Part 1):2025 quality C"
    assert n("IS 801:1975 (Reaffirmed 2021) working stress") == "IS 801:1975 working stress"
    assert n("IS 811:1987 (Reaffirmed 2024)") == "IS 811:1987"
    assert n("IS 875 (Part 4):1987 / IS 875 (Part 1):1987") == "IS 875 (Part 4):2021 / IS 875 (Part 1):2026"
    assert n("IS 875 Parts 1-5") == "IS 875 (Parts 1 to 5)"
    assert RS.tidy_html("<a href='IS 875-3'>IS 875-3</a>") == "<a href='IS 875-3'>IS 875 (Part 3)</a>"


def test_C3_reports_use_one_style(ex3, ex7):
    for _, pkg, _, html_ in (ex3, ex7):
        t = _text(html_)
        assert not re.search(r"IS 875-\d|Amd 1, 2|IS 2062:\d|Reaffirmed 20\d\d\)|IS 875 \(Part [14]\):1987", t)
        assert "Standards cited (editions)" in t and "IS 1893 (Part 1):2016 with Amendments 1 and 2" in t
        assert "IS 801:1975" in t and "IS 811:1987" in t
        if "G350" in t:                                                   # computed thin sections: the IS 277 coil
            assert "IS 277" in t
        assert "Soil: Type II" in t and "confirm by site investigation" in t and "Scope:" in t


def test_C3_report_us_residue_free(ex3, ex7):
    import india_cfs_gates as G
    for _, pkg, _, html_ in (ex3, ex7):
        hits = [h for h in {m.group(0) for m in G.US_RE.finditer(_text(html_))} if h.lower() != "cd"]
        assert not hits, hits
