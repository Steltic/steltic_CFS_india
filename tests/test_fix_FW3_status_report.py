"""2026-10 first wave, review items 4-8 (status honesty, all-CFS portal, titles, report cleanup, citations) and the
lateral-run environment fix:

* the CFS design status inherits the frame report's open items ('N item(s) to reconcile', connections not evaluated);
* the lateral sub-job gets a cfg.py, a ponding-screen input for long roof beams, and the CFS register entry;
* the vendored HR modules win in the lateral subprocess even when the repo is reached through a symlink;
* the all-CFS portal never carries the hot-rolled lateral-frame sentence; bolt groups show IS 801 7.5 capacities;
* titles by building type; no internal labels; I stated on its occupancy basis; durability / cold-service notes;
* 0.9 DL rows are cited as additional uplift rows, not IS 875-5 8.1 rows."""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.path.join(ROOT, "steel_engine")
sys.path.insert(0, ENG)

import india_cfs_env  # noqa: E402,F401
import india_cfs_basis as B        # noqa: E402
import india_cfs_gates as G        # noqa: E402
import india_cfs_lateral as L      # noqa: E402
import is801_members as M          # noqa: E402
import report_cfs_india as R       # noqa: E402


def test_status_inherits_frame_report_items():
    pkg = {"lateral_frame": {"status": {"status": "complete", "reasons": []},
                             "consistency": ["cfg.py not found", "[capacity_design] 'x >= 6 d' is symbolic (1)",
                                             "[capacity_design] 'x >= 6 d' is symbolic (2)"],
                             "connections": [{"id": "conn-a", "type": "column splice / base", "DC": None, "not_evaluated": ["splice"]},
                                             {"id": "conn-b", "type": "column splice / base", "DC": None, "not_evaluated": [],
                                              "all_checks_ok": True, "check_names": ["column splice: no_splice"]},
                                             {"id": "conn-c", "type": "brace", "DC": None}]}}
    items = G.lateral_report_items(pkg)
    assert items[0].startswith("lateral frame report: 3 item(s) to reconcile")
    assert any("(x2)" in x for x in items)                         # grouped duplicates
    assert any("conn-a" in x and "not evaluated" in x for x in items)
    assert not any("conn-b" in x for x in items)                   # declared single-length column: checked, no ratio
    assert any("conn-c" in x for x in items)
    assert G.lateral_report_items({"lateral_frame": pkg["lateral_frame"], "portal": {"x": 1}}) == []


def test_ponding_input_and_register():
    cfg = {"lateral_frame": {"bay_x_m": 18.0, "bay_y_m": 6.0, "beam": "WPB340X300X134.16",
                             "beam_sec": {"roof_X": "WPB340X300X134.16"}},
           "portal": {"eave_m": 6.0, "apex_m": 7.59, "spans_m": [18.0]}, "loads": {"Lr": 0.75, "snow": 0.0},
           "cfs_members": {"purlins": {"section": "C200X65X20X1.6-G350"}}}
    p = L.ponding_input(cfg)
    import sections as HS
    Ix = HS.props("WPB340X300X134.16")["Ix"]
    assert p["delta_mm"] == pytest.approx(5 * 0.75e-3 * 6000 * 18000 ** 4 / (384 * 2e5 * Ix), rel=1e-3)
    assert p["roof_slope"] == pytest.approx(1.59 / 9.0, rel=1e-3) and p["span_mm"] == 18000.0
    assert L.ponding_input(dict(cfg, lateral_frame=dict(cfg["lateral_frame"], bay_x_m=9.0))) is None    # < 12 m
    assert L.ponding_input({k: v for k, v in cfg.items() if k != "portal"}) is None                      # no slope
    reg = L.delegated_register(dict(cfg, delegated_design=[{"item": "anchor breakout", "criteria": "c", "interface_forces": "f"}]))
    assert len(reg) == 2 and "IS 801" in reg[1]["item"] and not any(w in json.dumps(reg[1]).lower()
                                                                     for w in ("anchor", "pedestal", "breakout", ">=", "<="))


def test_runner_writes_job_cfg_py(tmp_path):
    import importlib.util
    sp = importlib.util.spec_from_file_location("hrv_runner_t", os.path.join(ENG, "hr_vendor_runner.py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    root = tmp_path / "job_lateral"; root.mkdir()
    (tmp_path / "lateral_frame_spec.json").write_text("{}")
    m._write_job_cfg_py(str(root), str(tmp_path / "lateral_frame_spec.json"))
    src = (root / "cfg.py").read_text()
    assert "build_cfg(_spec, esm=False, saved_plan=_plan)" in src and "../lateral_frame_spec.json" in src
    compile(src, "cfg.py", "exec")


def test_vendored_modules_win_through_a_symlinked_repo(tmp_path):
    link = tmp_path / "eng_link"
    os.symlink(ENG, link)
    code = ("import sys; sys.path.insert(0, %r); "
            "src = open(%r).read().split('def _callables')[0]; "
            "exec(compile(src, %r, 'exec'), {'__file__': %r, '__name__': 'x'}); "
            "import pipeline, preflight; print(pipeline.__file__); print(preflight.__file__)"
            % (os.path.realpath(ENG), str(link / "hr_vendor_runner.py"), str(link / "hr_vendor_runner.py"),
               str(link / "hr_vendor_runner.py")))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(tmp_path), timeout=300)
    files = out.stdout.strip().splitlines()
    assert files and all(os.sep + "hr_vendor" + os.sep in f for f in files[-2:]), out.stdout + out.stderr


def test_bolt_capacity_per_bolt():
    r = M.bolted_connection_75(294.0, 5.0, 16.0, 10000.0, 12, 30.0, 60.0, bolt_class="4.6", wind_eq=True)
    Fy = 294.0 / 0.0980665
    caps = r["capacity_components_N"]
    assert caps["7.5.3 bearing (2.1 Fy d t)"] == pytest.approx(2.1 * Fy * 1.6 * 0.5 * (4 / 3) * 9.80665, rel=1e-9)
    assert r["capacity_per_bolt_N"] == min(caps.values()) and r["dc_force"] == pytest.approx(10000.0 / r["capacity_per_bolt_N"])


def test_portal_basis_and_titles():
    assert "hot-rolled IS 800:2007 frame" not in B.basis_statement({"all_cfs_portal": True})
    assert "Section 12 does not apply" in B.basis_statement({"all_cfs_portal": True})
    assert "hot-rolled IS 800:2007 frame" in B.basis_statement({})
    assert "Reaffirmed 2021" in B.basis_statement({})
    assert R.report_title({"all_cfs_portal": True}).startswith("All-cold-formed portal")
    hr_portal = {"portal": {"spans_m": [18]}, "cfs_members": {"purlins": {}, "girts": {}},
                 "lateral_frame": {"system": "SCBF", "hr_cfg_extra": {"system": "SMF+SCBF"}}}
    assert R.report_title(hr_portal).startswith("Cold-formed purlins and girts on a hot-rolled")
    hyb = {"cfs_members": {"studs": {}, "joists": {}}, "lateral_frame": {"system": "SCBF"}}
    assert R.report_title(hyb) == "Hot-rolled braced frame with LGSF infill walls and cold-formed floor joists (IS 800 / IS 801)"
    assert R.report_title(dict(hyb, report_title="X")) == "X"


def test_report_cleanup_helpers():
    t = R.clean("brief text; D3: hot-rolled SCBF (D3 / D5 / L7); F = 1800 (owner ruling R12: Fy 294); "
                "Table 5 (in-repo fallback; prefer corpus exact_table 5); EOR input")
    for bad in ("D3", "ruling", "fallback", "EOR"):
        assert bad not in t, (bad, t)
    assert "design engineer input" in t
    assert R._num(13.799999999999999) == "13.8" and R._num(0.7999999999999999) == "0.8"
    assert R._val_units(18724500.0, "N-mm") == ("18.72", "kN-m") and R._val_units(1460.0, "N") == ("1.46", "kN")
    ss = {"I": 1.2, "I_row": "owner ruling D8 (area proxy for Table 8 (ii))"}
    txt = R.importance_text(ss, {"use": "dormitory", "area_m2": 10656})
    assert "Table 8 (ii)" in txt and "occupant count" in txt and "proxy" not in txt and "ruling" not in txt
    assert "Table 8 (i)" in R.importance_text({"I": 1.2, "I_row": "owner ruling D8 (clinic; not a Table 8 row)"}, {"use": "clinic"})


def test_durability_paragraph():
    pkg = {"cfs_members": [{"material": "IS 277 grade 350 ..., Z275 zinc coating"}]}
    coast = R.durability_text({"site": {"city": "Chennai"}, "occupancy": {"use": "warehouse"}}, pkg)
    assert "coastal" in coast and "heavier coating class" in coast and "Fire" in coast
    inland = R.durability_text({"site": {"city": "Nagpur"}, "occupancy": {"use": "student hostel"}}, pkg)
    assert "inland" in inland and "sound-insulation" in inland
    cold = R.durability_text({"site": {"city": "Srinagar"}, "service_temperature_C": -23, "occupancy": {"use": "cold store"}}, pkg)
    assert "-23 deg C" in cold and "-20 deg C" in cold and "IS 2062" in cold


def test_uplift_rows_are_not_cited_as_8_1_rows():
    rows = B.cfs_combinations({"story_forces": {"W_X": 1, "EQ_X": 1}})
    for r in rows:
        if r["label"].startswith("0.9DL"):
            assert not r["is875_8_1_row"] and "not an IS 875 (Part 5) 8.1 row" in r["row_cite"]
            assert "Notes 4/5" not in r["cite"]
        else:
            assert r["is875_8_1_row"] and r["row_cite"].startswith("IS 875 (Part 5):1987 8.1 (")
