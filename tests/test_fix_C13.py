"""C13 (L-08): check_vendored.py resolves the HR root from STELTIC_HR_ROOT or a sibling checkout and SKIPs (exit 0)
when there is none; no /home/claude/rv paths in the IS 811 build tool."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "check_vendored.py")


def test_skip_without_hr_root(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "STELTIC_HR_ROOT"}
    # a copy of the script outside any repo layout: no sibling checkout -> SKIP, exit 0
    (tmp_path / "repo" / "scripts").mkdir(parents=True)
    (tmp_path / "repo" / "steel_engine" / "hr_vendor").mkdir(parents=True)
    dst = tmp_path / "repo" / "scripts" / "check_vendored.py"
    dst.write_text(open(SCRIPT).read())
    r = subprocess.run([sys.executable, str(dst)], capture_output=True, text=True, env=env)
    assert r.returncode == 0 and r.stdout.startswith("SKIP")


def test_sibling_checkout_is_found(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "STELTIC_HR_ROOT"}
    (tmp_path / "repo" / "scripts").mkdir(parents=True)
    (tmp_path / "repo" / "steel_engine" / "hr_vendor").mkdir(parents=True)
    (tmp_path / "repo" / "steel_engine" / "hr_vendor" / "a.py").write_text("x = 1\n")
    (tmp_path / "steltic_india-main" / "steel_engine").mkdir(parents=True)
    (tmp_path / "steltic_india-main" / "steel_engine" / "a.py").write_text("x = 1\n")
    dst = tmp_path / "repo" / "scripts" / "check_vendored.py"
    dst.write_text(open(SCRIPT).read())
    r = subprocess.run([sys.executable, str(dst)], capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "1 identical, 0 different" in r.stdout


def test_no_rv_paths_in_build_tool():
    src = open(os.path.join(ROOT, "steel_engine", "tools", "build_is811_shapes.py")).read()
    assert "/home/claude/rv" not in src
