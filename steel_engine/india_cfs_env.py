"""india_cfs_env.py -- import-path setup for the India CFS engine.

The shared India core (india_loads, india_seismic, india_units, india_wind_tables, india_combos, india_seismic_gates,
india_is800, sections = IS 808 / IS 1161 DB, engine3d, ...) lives ONLY in steel_engine/hr_vendor/ (byte-identical
copy of work/hr, see hr_vendor/VENDORED_FROM.md).  `import india_cfs_env` puts steel_engine/ first and hr_vendor/
after it on sys.path, so a flat `import india_seismic` resolves to the vendored module while the CFS modules of the
same name as HR ones (preflight, consistency, report, pipeline) stay the CFS versions in process.
The HR lateral-frame pipeline itself is run in a subprocess with hr_vendor/ as sys.path[0] (india_cfs_lateral).
"""
from __future__ import annotations
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "hr_vendor")
REPO = os.path.dirname(HERE)


def activate():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if VENDOR not in sys.path:
        # after steel_engine/ (CFS modules win on name collisions in process), before everything else
        sys.path.insert(sys.path.index(HERE) + 1, VENDOR)
    return VENDOR


def vendored_commit() -> str | None:
    try:
        for line in open(os.path.join(VENDOR, "VENDORED_FROM.md")):
            if line.startswith("Commit:"):
                return line.split("**")[1]
    except Exception:
        return None
    return None


activate()
