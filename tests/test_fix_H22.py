"""H22 CFS side (ruling R1, IS 1893 7.3.6): partitions in W default to max(0.5, partition design allowance) in the
lateral builder and the HR runner; preflight WARNs when a declared partition_seismic_kNm2 is below the allowance."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))

import india_cfs_lateral as L   # noqa: E402
import preflight as PF          # noqa: E402


def test_default_partition_seismic():
    assert L.partition_seismic_default({"partition_design_kNm2": 1.0}) == 1.0
    assert L.partition_seismic_default({"partition_design_kNm2": 0.3}) == 0.5
    assert L.partition_seismic_default({}) == 0.5
    assert L.partition_seismic_default({"partition_design_kNm2": 1.0, "partition_seismic_kNm2": 0.75}) == 0.75


def test_runner_default():
    import importlib.util
    sp = importlib.util.spec_from_file_location("hr_vendor_runner_t", os.path.join(ROOT, "steel_engine", "hr_vendor_runner.py"))
    src = open(sp.origin).read()
    assert 'max(0.5, float(spec.get("partition_design_kNm2") or 0.0))' in src


def _cfg():
    fix = os.path.join(ROOT, "tests", "fixtures", "IN_CFS_Ex1")
    sys.path.insert(0, fix); sys.modules.pop("build_and_run", None)
    import build_and_run as Bx
    sys.path.remove(fix)
    return Bx.build_cfg()


def test_preflight_warns_below_allowance():
    cfg = _cfg()
    cfg["loads"].update(partition_design_kNm2=1.0, partition_seismic_kNm2=0.5)
    w = [m for s, m in PF.check(cfg) if s == "WARN" and "7.3.6" in m]
    assert w and "higher values shall be used" in w[0]
    cfg["loads"]["partition_seismic_kNm2"] = 1.0
    assert not [m for s, m in PF.check(cfg) if "7.3.6" in m]
    cfg["loads"]["partition_seismic_kNm2"] = 0.4
    assert [m for s, m in PF.check(cfg) if s == "ERROR" and "7.3.6" in m]
    spec = L.build_hr_spec(dict(cfg, loads=dict(cfg["loads"], partition_seismic_kNm2=None)), "t")
    assert spec["partition_seismic_kNm2"] == 1.0
