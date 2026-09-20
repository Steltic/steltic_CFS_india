#!/usr/bin/env python3
"""check_vendored.py -- the shared India engine in steel_engine/hr_vendor/ must be byte-identical to work/hr.

    python3 scripts/check_vendored.py            # sha256 compare every vendored file; exit 1 on any difference
    python3 scripts/check_vendored.py --sync     # print the cp commands that would re-sync (never copies itself)

The HR source root defaults to /home/claude/rv/work/hr (override with STELTIC_HR_ROOT). The commit the folder was
copied from is recorded in steel_engine/hr_vendor/VENDORED_FROM.md.
"""
from __future__ import annotations
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFS_ROOT = os.path.dirname(HERE)
VENDOR = os.path.join(CFS_ROOT, "steel_engine", "hr_vendor")
HR_ROOT = os.environ.get("STELTIC_HR_ROOT", "/home/claude/rv/work/hr")
HR_ENGINE = os.path.join(HR_ROOT, "steel_engine")
SKIP = {"VENDORED_FROM.md"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def vendored_files():
    out = []
    for root, dirs, files in os.walk(VENDOR):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in files:
            if fn in SKIP or fn.endswith((".pyc",)):
                continue
            p = os.path.join(root, fn)
            out.append(os.path.relpath(p, VENDOR))
    return sorted(out)


def compare():
    """Return (identical:list, different:list, missing_in_hr:list)."""
    same, diff, missing = [], [], []
    for rel in vendored_files():
        a = os.path.join(VENDOR, rel)
        b = os.path.join(HR_ENGINE, rel)
        if not os.path.exists(b):
            missing.append(rel)
        elif sha256(a) == sha256(b):
            same.append(rel)
        else:
            diff.append(rel)
    return same, diff, missing


def main(argv):
    same, diff, missing = compare()
    if "--sync" in argv:
        for rel in diff + missing:
            print("cp %s %s" % (os.path.join(HR_ENGINE, rel), os.path.join(VENDOR, rel)))
        return 0
    print("vendored: %d identical, %d different, %d missing in work/hr" % (len(same), len(diff), len(missing)))
    for rel in diff:
        print("  DIFFERENT %s" % rel)
    for rel in missing:
        print("  MISSING-IN-HR %s" % rel)
    return 1 if (diff or missing) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
