"""2026-10 third wave (CFS): P3 repeatable frame models (sorted iteration in the lateral runner, the stated rule for a
column shared by X- and Y-braced bays, a fixed hash seed for the frame sub-run) and P9 cold-formed leftovers."""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.path.join(ROOT, "steel_engine")
RUNNER = os.path.join(ENG, "hr_vendor_runner.py")
sys.path.insert(0, ENG)


def _runner():
    """hr_vendor_runner loaded by path; the vendored folder it puts on sys.path is taken off again so the CFS modules
    of later tests are not shadowed."""
    saved = list(sys.path)
    try:
        sp = importlib.util.spec_from_file_location("hrv_runner_third_wave", RUNNER)
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
    finally:
        sys.path[:] = saved
    return m


# the Ex7 layout: a 2 x 2 bay plan braced on all four walls -> four corner columns in X- and Y-braced bays
SPEC = {"NX": 2, "NY": 2, "heights_m": [3.2, 3.2],
        "braced_bays": [["X", 0, 0], ["X", 1, 0], ["X", 0, 2], ["X", 1, 2],
                        ["Y", 0, 0], ["Y", 0, 1], ["Y", 2, 0], ["Y", 2, 1]],
        "moment_lines": [], "col": "C", "beam": "B", "default_strong": None}

_PROBE = r"""
import importlib.util, json, sys
sp = importlib.util.spec_from_file_location("r", %(runner)r)
m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
spec = json.loads(%(spec)r)
br, cs, bs, strong, rel = m._callables(spec)
out = {"braces": [list(b) for b in br(1, spec["NX"], spec["NY"])],
       "strong": [[i, j, strong(i, j, spec["NX"], spec["NY"])] for i in range(spec["NX"] + 1) for j in range(spec["NY"] + 1)],
       "orientation": m.column_orientation(spec, {"col_strong": strong})}
print(json.dumps(out, sort_keys=True))
"""


def _probe(spec, seed):
    code = _PROBE % {"runner": RUNNER, "spec": json.dumps(spec)}
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300,
                       env=dict(os.environ, PYTHONHASHSEED=str(seed), PYTHONDONTWRITEBYTECODE="1"))
    assert p.returncode == 0, p.stderr[-2000:]
    return p.stdout.strip().splitlines()[-1]


# ================================================================================================ P3
def test_P3_frame_callables_do_not_depend_on_the_hash_seed():
    outs = {_probe(SPEC, s) for s in (0, 1, 2, 3, 7, 11)}
    assert len(outs) == 1, "brace order / column axis changed with PYTHONHASHSEED"
    out = json.loads(outs.pop())
    assert out["braces"] == sorted(out["braces"])                     # element order: X before Y, then i, j


def test_P3_shared_corner_column_takes_the_bay_listed_first():
    r = _runner()
    _, _, _, strong, _ = r._callables(SPEC)
    assert strong(0, 0, 2, 2) == "X" and strong(2, 2, 2, 2) == "X"   # X bays listed first in the schedule
    assert strong(0, 1, 2, 2) == "Y" and strong(1, 0, 2, 2) == "X"   # mid-wall columns: their own wall
    rev = dict(SPEC, braced_bays=list(reversed(SPEC["braced_bays"])))
    _, _, _, strong2, _ = r._callables(rev)
    assert strong2(0, 0, 2, 2) == "Y"                                 # the rule follows the declared order
    co = r.column_orientation(SPEC, {"col_strong": strong})
    assert co["n_shared"] == 4 and [c["grid"] for c in co["shared_columns"]] == [[0, 0], [0, 2], [2, 0], [2, 2]]
    assert all(c["strong_axis"] == "X" for c in co["shared_columns"])
    assert "listed first" in co["rule"] and "both axes" in co["rule"]


def test_P3_moment_lines_both_directions_take_X_and_unclaimed_columns_the_default():
    r = _runner()
    spec = dict(SPEC, braced_bays=[], moment_lines=[["Y", 0], ["X", 0]])
    _, _, _, strong, _ = r._callables(spec)
    assert strong(0, 0, 2, 2) == "X"                                  # on an X line and a Y line -> X
    assert strong(0, 1, 2, 2) == "Y" and strong(1, 0, 2, 2) == "X"
    assert strong(1, 1, 2, 2) == "X"                                  # default X (was None when the key was null)
    assert r._callables(dict(spec, default_strong="Y"))[3](1, 1, 2, 2) == "Y"


def test_P3_builder_path_column_on_two_moment_lines_is_stable():
    r = _runner()
    calls = []

    def inner(i, j):
        calls.append((i, j))
        return "Y"
    cfg = {"_gold": {"col_strong": inner}}
    r._stable_gold_col_strong(cfg, {"gold": {"moment_lines": [["Y", 0], ["X", 0]]}})
    cs = cfg["_gold"]["col_strong"]
    assert cs(0, 0) == "X" and calls == []                            # X line + Y line: the rule, not the set order
    assert cs(0, 1) == "Y" and calls == [(0, 1)]                      # every other column: the builder's own rule
    cfg2 = {"_gold": {"col_strong": inner}}
    r._stable_gold_col_strong(cfg2, {"gold": {"moment_lines": [["Y", i] for i in range(4)]}})
    assert cfg2["_gold"]["col_strong"] is inner                       # one direction only: nothing to decide


def test_P3_frame_subrun_gets_a_fixed_hash_seed(monkeypatch, tmp_path):
    import india_cfs_lateral as L
    seen = {}

    class _P:
        stdout, stderr = "", ""

    def fake_run(cmd, **kw):
        seen["env"] = kw.get("env")
        raise RuntimeError("stop")
    monkeypatch.setattr(L.subprocess, "run", fake_run)
    monkeypatch.setattr(L, "build_hr_spec", lambda cfg, name: {"name": name})
    monkeypatch.setattr(L, "copy_rag_hits", lambda *a, **k: None)
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    with pytest.raises(RuntimeError):
        L.run_lateral({"name": "j"}, str(tmp_path / "lateral"))
    assert seen["env"]["PYTHONHASHSEED"] == "0"
    monkeypatch.setenv("PYTHONHASHSEED", "5")
    with pytest.raises(RuntimeError):
        L.run_lateral({"name": "j"}, str(tmp_path / "lateral"))
    assert seen["env"]["PYTHONHASHSEED"] == "5"


def test_P3_report_states_the_rule():
    import report_cfs_third_wave as R3
    import report_cfs_second_wave as RS
    r = _runner()
    _, _, _, strong, _ = r._callables(SPEC)
    html_ = R3.column_orientation_html({"column_orientation": r.column_orientation(SPEC, {"col_strong": strong})})
    assert "4 frame column(s) stand in frames of both directions" in html_ and "x-line 0, y-line 2" in html_
    assert "braced bay, x-lines 0-1 on y-line 0" in html_
    assert not RS.leaks(RS.tidy_html(html_))
    none = R3.column_orientation_html({"column_orientation": r.column_orientation(
        dict(SPEC, braced_bays=[["X", 0, 0]]), {"col_strong": strong})})
    assert "No frame column stands in frames of both directions" in none
    assert R3.column_orientation_html({}) == ""
