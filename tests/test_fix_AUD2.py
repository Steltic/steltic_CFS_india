"""AUD-2 (gold audit H2 / M1): the all-CFS portal base plate takes the IS 2062:2025 Table 3 fy for its thickness
(india_connections.plate_fy_is2062 of the vendored HR engine); a declared fy above the band is reduced and recorded."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "steel_engine"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import india_cfs_env  # noqa: E402,F401
import india_cfs_portal as PO  # noqa: E402
from test_fix_C07 import JOBS, _cfg  # noqa: E402


def test_portal_base_plate_fy_by_thickness():
    os.makedirs(JOBS, exist_ok=True)
    """AUD-2: portal base plate fy from IS 2062 Table 3 for its thickness (declared 250 on a 40 mm E250 plate -> 240)."""
    cfg = _cfg(); cfg["cfs_connections_spec"]["base"]["fy_plate_MPa"] = 250.0
    base = [c for c in PO.run(cfg, JOBS)["connections"] if c["id"] == "column-base"][0]
    assert base["plate_fy"]["fy_used_MPa"] == 240.0 and base["plate_fy"]["reduced"] is True
    row = [r for r in base["checks"] if r["check"] == "plate bending 11.4.1(c)"][0]
    assert row["limit"] == pytest.approx(0.75 * 240.0 * row.get("allowable_increase", 1.0), rel=1e-6)
