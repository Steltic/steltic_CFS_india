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


def test_C1_vendor_pinned_to_hr_second_wave():
    pin = open(os.path.join(ROOT, "steel_engine", "hr_vendor", "VENDORED_FROM.md")).read()
    assert "Commit: **dd1d8c1f86de79489ea1432c0b1ff748326f23af**" in pin
    assert os.path.exists(os.path.join(ROOT, "steel_engine", "hr_vendor", "report_second_wave.py"))
    import india_cfs_env
    assert india_cfs_env.vendored_commit().startswith("dd1d8c1")
