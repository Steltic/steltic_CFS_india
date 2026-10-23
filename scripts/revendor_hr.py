#!/usr/bin/env python3
"""revendor_hr.py -- re-vendor steel_engine/hr_vendor/ from one commit of the HR repo (steltic_india), repeatably.

    python3 scripts/revendor_hr.py --commit <sha|ref> [--label "<branch / why>"] [--dry-run]

What it does (2026-10 second wave, item C1; the same steps the first-wave re-syncs made by hand):
  1. reads every file of steel_engine/ at the commit with `git show <sha>:steel_engine/<path>` (tools/ and
     __pycache__/ excluded, exactly the set scripts/check_vendored.py compares);
  2. writes the files that differ or are new into steel_engine/hr_vendor/ (byte-identical copies) and deletes the
     vendored files the commit no longer has (VENDORED_FROM.md and __pycache__ are never touched);
  3. moves the pin in hr_vendor/VENDORED_FROM.md: the "Commit: **<sha>**" line becomes the new full sha and a dated
     re-sync note (files changed / added / removed, the label) is appended after the existing re-sync notes;
  4. runs scripts/check_vendored.py against the new pin and exits with its code (0 = byte-identical).

--dry-run lists what would change and touches nothing.  The HR checkout is $STELTIC_HR_ROOT, else the sibling
../steltic_india (the same resolution as check_vendored.py).  Nothing is copied from a working tree: only committed
files at the named commit, so a branch being edited in the HR checkout cannot leak into the vendor folder.
After a re-vendor: run the test suite and the CFS golds (each under /home/claude/bin/heavy), then commit hr_vendor/
together with VENDORED_FROM.md.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFS_ROOT = os.path.dirname(HERE)
VENDOR = os.path.join(CFS_ROOT, "steel_engine", "hr_vendor")
PIN_FILE = os.path.join(VENDOR, "VENDORED_FROM.md")
sys.path.insert(0, HERE)
import check_vendored as CV  # noqa: E402


def _git(hr_root, *args):
    return subprocess.run(["git", "-C", hr_root] + list(args), capture_output=True)


def resolve_commit(hr_root, ref):
    r = _git(hr_root, "rev-parse", "--verify", "%s^{commit}" % ref)
    if r.returncode != 0:
        raise SystemExit("revendor_hr: %r is not a commit of %s (%s)" % (ref, hr_root, r.stderr.decode().strip()))
    return r.stdout.decode().strip()


def plan(hr_root, sha):
    """(writes {rel: bytes}, added [rel], removed [rel], unchanged n) for re-vendoring at sha."""
    CV.HR_ROOT = hr_root
    ref = CV.commit_files(sha)
    if ref is None:
        raise SystemExit("revendor_hr: cannot read steel_engine/ at %s from %s" % (sha, hr_root))
    have = set(CV.vendored_files())
    writes, added, same = {}, [], 0
    for rel, data in sorted(ref.items()):
        p = os.path.join(VENDOR, rel)
        if rel in have and os.path.isfile(p) and hashlib.sha256(data).hexdigest() == CV.sha256(p):
            same += 1
            continue
        writes[rel] = data
        if rel not in have:
            added.append(rel)
    removed = sorted(r for r in have if r not in ref)
    return writes, added, removed, same


def update_pin(sha, short, label, changed, added, removed, today=None):
    """Move the Commit: **<sha>** line and append a dated re-sync note (returns the new text)."""
    txt = open(PIN_FILE, encoding="utf-8").read()
    today = today or datetime.date.today().isoformat()
    lab = (" [steltic_india %s]" % label) if label else ""
    new_line = "Commit: **%s**%s (copied with `git show %s:steel_engine/<path>` by scripts/revendor_hr.py, %s)" % (
        sha, lab, short, today)
    if re.search(r"^Commit:.*$", txt, flags=re.M):
        txt = re.sub(r"^Commit:.*$", lambda _m: new_line, txt, count=1, flags=re.M)
    else:
        txt = new_line + "\n\n" + txt
    if label:
        txt = re.sub(r"^(Source: .*?), branch \S+.*$", lambda m_: "%s, branch %s" % (m_.group(1), label), txt, count=1,
                     flags=re.M)
    rewritten = [c for c in changed if c not in added]
    parts = []
    if rewritten:
        parts.append("rewritten (%d): %s" % (len(rewritten), ", ".join("`%s`" % c for c in rewritten)
                                             if len(rewritten) <= 15 else "see git diff"))
    if added:
        parts.append("new (%d): %s" % (len(added), ", ".join("`%s`" % c for c in added)))
    if removed:
        parts.append("removed (%d): %s" % (len(removed), ", ".join("`%s`" % c for c in removed)))
    note = ("**%s re-sync (scripts/revendor_hr.py):** from %s%s -- %s; every other file byte-identical.\n"
            % (today, short, (" (" + label + ")") if label else "", "; ".join(parts) or "no file changed"))
    m = re.search(r"\nRules \(", txt)
    if m:                                               # notes sit above the "Rules (...)" block
        txt = txt[:m.start()] + "\n" + note + txt[m.start():]
    else:
        txt = txt.rstrip("\n") + "\n\n" + note
    return txt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--commit", required=True, help="HR commit (sha or ref) to vendor")
    ap.add_argument("--label", default="", help="branch / reason recorded with the pin")
    ap.add_argument("--hr-root", default=None, help="HR checkout (default: $STELTIC_HR_ROOT or ../steltic_india)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    hr_root = a.hr_root or CV.resolve_hr_root()
    if not hr_root:
        raise SystemExit("revendor_hr: no HR checkout (set STELTIC_HR_ROOT or pass --hr-root)")
    sha = resolve_commit(hr_root, a.commit)
    short = sha[:7]
    writes, added, removed, same = plan(hr_root, sha)
    print("revendor_hr: %s @ %s -- %d to write (%d new), %d to remove, %d unchanged"
          % (hr_root, short, len(writes), len(added), len(removed), same))
    for rel in sorted(writes):
        print("  %s %s" % ("ADD  " if rel in added else "WRITE", rel))
    for rel in removed:
        print("  DEL   %s" % rel)
    if a.dry_run:
        return 0
    for rel, data in writes.items():
        p = os.path.join(VENDOR, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
    for rel in removed:
        os.remove(os.path.join(VENDOR, rel))
    new_txt = update_pin(sha, short, a.label, sorted(writes), added, removed)
    with open(PIN_FILE, "w", encoding="utf-8") as f:
        f.write(new_txt)
    CV.HR_ROOT = hr_root
    CV.HR_ENGINE = os.path.join(hr_root, "steel_engine")
    return CV.main([])


if __name__ == "__main__":
    sys.exit(main())
