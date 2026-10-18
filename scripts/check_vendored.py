#!/usr/bin/env python3
"""check_vendored.py -- the shared India engine in steel_engine/hr_vendor/ must be byte-identical to work/hr.

    python3 scripts/check_vendored.py            # sha256 compare every vendored file; exit 1 on any difference
    python3 scripts/check_vendored.py --sync     # print the commands that would re-sync (never copies itself)
    python3 scripts/check_vendored.py --worktree # compare with the live HR working tree instead of the pinned commit

2026-10 first wave: by default the comparison is against the PINNED commit recorded in VENDORED_FROM.md ("Commit:
**<sha>**"), read from the HR git repository with `git show <sha>:steel_engine/<path>` -- a branch being edited in the
HR checkout no longer breaks the check. Every file of the HR steel_engine/ at that commit (tools/ excepted) must be
vendored, and no vendored file may be missing from it.

The HR source root is $STELTIC_HR_ROOT, else a sibling checkout ../steltic_india or ../steltic_india-main next to this
repo; when none exists the script prints SKIP and exits 0 (nothing to compare against).  The commit the folder was
copied from is recorded in steel_engine/hr_vendor/VENDORED_FROM.md.
"""
from __future__ import annotations
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFS_ROOT = os.path.dirname(HERE)
VENDOR = os.path.join(CFS_ROOT, "steel_engine", "hr_vendor")


def resolve_hr_root():
    """C13 / L-08: $STELTIC_HR_ROOT, else the sibling ../steltic_india or ../steltic_india-main checkout, else None."""
    env = os.environ.get("STELTIC_HR_ROOT")
    if env:
        return env
    for name in ("steltic_india", "steltic_india-main"):
        cand = os.path.join(os.path.dirname(CFS_ROOT), name)
        if os.path.isdir(os.path.join(cand, "steel_engine")):
            return cand
    return None


HR_ROOT = resolve_hr_root()
HR_ENGINE = os.path.join(HR_ROOT, "steel_engine") if HR_ROOT else None
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


def pinned_commit():
    """The commit recorded in VENDORED_FROM.md (first 'Commit: **<sha>**' line), or None."""
    try:
        for line in open(os.path.join(VENDOR, "VENDORED_FROM.md"), encoding="utf-8"):
            if line.startswith("Commit:") and "**" in line:
                return line.split("**")[1].strip()
    except OSError:
        return None
    return None


def _git(*args):
    import subprocess
    return subprocess.run(["git", "-C", HR_ROOT] + list(args), capture_output=True)


def commit_files(commit):
    """{rel path: bytes} of steel_engine/ at the commit (tools/ excluded), or None when git cannot read it."""
    r = _git("ls-tree", "-r", "--name-only", commit, "steel_engine")
    if r.returncode != 0:
        return None
    out = {}
    for path in r.stdout.decode().splitlines():
        rel = path[len("steel_engine/"):]
        if rel.startswith("tools/") or "__pycache__" in rel:
            continue
        b = _git("show", "%s:%s" % (commit, path))
        if b.returncode != 0:
            return None
        out[rel] = b.stdout
    return out


def compare(commit=None):
    """Return (identical:list, different:list, missing_in_hr:list, not_vendored:list)."""
    same, diff, missing = [], [], []
    ref = commit_files(commit) if commit else None
    if commit and ref is None:                      # no git history (e.g. an exported tree): fall back to the files
        print("NOTE: commit %s not readable from %s (git); comparing with the working tree" % (commit, HR_ROOT))
    for rel in vendored_files():
        a = os.path.join(VENDOR, rel)
        if ref is not None:
            if rel not in ref:
                missing.append(rel)
            elif hashlib.sha256(ref[rel]).hexdigest() == sha256(a):
                same.append(rel)
            else:
                diff.append(rel)
            continue
        b = os.path.join(HR_ENGINE, rel)
        if not os.path.exists(b):
            missing.append(rel)
        elif sha256(a) == sha256(b):
            same.append(rel)
        else:
            diff.append(rel)
    have = set(vendored_files())
    not_vendored = sorted(r for r in (ref or {}) if r not in have)
    return same, diff, missing, not_vendored


def main(argv):
    if not HR_ROOT:
        print("SKIP: no HR checkout to compare against (set STELTIC_HR_ROOT, or place steltic_india next to this repo)")
        return 0
    commit = None if "--worktree" in argv else pinned_commit()
    same, diff, missing, not_vendored = compare(commit)
    if "--sync" in argv:
        for rel in diff + not_vendored:
            if commit:
                print("git -C %s show %s:steel_engine/%s > %s" % (HR_ROOT, commit, rel, os.path.join(VENDOR, rel)))
            else:
                print("cp %s %s" % (os.path.join(HR_ENGINE, rel), os.path.join(VENDOR, rel)))
        return 0
    print("vendored: %d identical, %d different, %d missing in %s, %d not vendored (against %s)"
          % (len(same), len(diff), len(missing), HR_ROOT, len(not_vendored), commit or "the working tree"))
    for rel in diff:
        print("  DIFFERENT %s" % rel)
    for rel in missing:
        print("  MISSING-IN-HR %s" % rel)
    for rel in not_vendored:
        print("  NOT-VENDORED %s" % rel)
    return 1 if (diff or missing or not_vendored) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
