"""consistency.py (CFS India) -- package-level FAIL rules for an India CFS job (spec WP0.3 / WP3.1 / WP3.6).

check(name, root=None, pkg=None, verbose=True) -> list of issue strings (empty = consistent).
Rules:
  * every capacity slot carries capacity_basis + allowable_increase; working-stress demands never meet an LSD
    capacity (and vice versa); 1.333 only on IS 801 allowables (india_cfs_basis.basis_issues);
  * D/C recomputed as demand / capacity everywhere it can be (4 % tolerance on the stored dc);
  * no waived entries (WP0.2), no literal D/C constants 0.80 / 0.90 / 1.000 without value + limit, no capacity
    derived from demand (grep patterns), no `*.bak` / pipeline_error files in the package;
  * report text has 0 US-residue hits (india_cfs_gates.US_RE), grounding table has no MISSING row;
  * lateral_frame system / R agree between the CFS package and the HR calc package;
  * retrieval entries marked found:true name a stored hit (rag/ file or cite text).
"""
from __future__ import annotations
import glob
import json
import os
import re

import india_cfs_env  # noqa: F401
import india_cfs_basis as B
import india_cfs_gates as G

TOL = 0.04


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _dc_issues(pkg):
    issues = []

    def walk(obj, path):
        if isinstance(obj, dict):
            if obj.get("waived"):
                issues.append("%s: waived:true (nothing is waived, WP0.2)" % path)
            v, c = obj.get("value"), obj.get("limit")
            dc = obj.get("dc", obj.get("DC"))
            if _num(v) and _num(c) and c > 0 and _num(dc):
                r = abs(v) / c
                if abs(r - dc) > TOL * max(dc, 1e-9) + 1e-6:
                    issues.append("%s: stored dc %.4f != value/limit %.4f" % (path, dc, r))
            if _num(dc) and (v is None or c is None) and "checks" not in obj and dc in (0.8, 0.9, 1.0):
                issues.append("%s: literal D/C %.2f without value / limit" % (path, dc))
            for k, val in obj.items():
                walk(val, path + "." + str(k))
        elif isinstance(obj, list):
            for i, val in enumerate(obj):
                walk(val, "%s[%d]" % (path, i))
        elif isinstance(obj, str) and G.DEMAND_CAP_RE.search(obj):
            issues.append("%s: capacity-from-demand pattern %r" % (path, obj[:60]))
    walk(pkg, "pkg")
    return issues


def _system_issues(pkg, root):
    out = []
    lat = pkg.get("lateral_frame") or {}
    cp = os.path.join(root or "", "lateral", str(lat.get("name") or ""), "design", "calc_package.json") if root else None
    if cp and os.path.exists(cp):
        hr = json.load(open(cp))
        sc, cd = hr.get("seismic_calc") or {}, hr.get("capacity_design") or {}
        for key, a, b in (("system", lat.get("system"), sc.get("system")), ("R", lat.get("R"), sc.get("R")),
                          ("system", lat.get("system"), cd.get("system")), ("R", lat.get("R"), cd.get("R"))):
            if a is not None and b is not None and str(a).upper() != str(b).upper():
                out.append("lateral_frame.%s %s != HR package %s" % (key, a, b))
    return out


def _file_issues(root):
    out = []
    if not root:
        return out
    for pat in ("design/*.bak", "design/*.bak*", "pipeline_error.txt", "**/*.bak"):
        for f in glob.glob(os.path.join(root, pat), recursive=True):
            out.append("stale file in the package: %s" % os.path.relpath(f, root))
    return out


def _report_issues(root, pkg):
    out = []
    if not root:
        return out
    rp = os.path.join(root, "report.html")
    if os.path.exists(rp):
        html = open(rp, encoding="utf-8", errors="replace").read()
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"(?i)(no |never |not )(US|AISI|ASCE|LRFD)[^.]*\.", " ", text)     # the basis statement itself
        hits = sorted({m.group(0) for m in G.US_RE.finditer(text)})
        hits = [h for h in hits if h.lower() not in ("cd",)]
        if hits:
            out.append("report US residue: %s" % ", ".join(hits[:12]))
        if "MISSING" in text and "grounding" in text.lower():
            out.append("report grounding table has a MISSING row")
    return out


def _retrieval_issues(root, cfg):
    out = []
    plan = (cfg or {}).get("load_plan") or {}
    for i, h in enumerate(plan.get("retrieval") or []):
        if isinstance(h, dict) and h.get("found") is True and not (h.get("cite") or h.get("file")):
            out.append("retrieval[%d] found:true without a stored cite / rag file" % i)
        if isinstance(h, dict) and h.get("file") and root and not os.path.exists(os.path.join(root, h["file"])):
            out.append("retrieval[%d] names %s but the file is not in the package" % (i, h["file"]))
    return out


def check(name, root=None, pkg=None, verbose=True):
    if pkg is None and root:
        p = os.path.join(root, "design", "calc_package_cfs.json")
        pkg = json.load(open(p)) if os.path.exists(p) else {}
    pkg = pkg or {}
    cfg = pkg.get("cfg_snapshot") or {}
    if root and os.path.exists(os.path.join(root, "cfg_snapshot.json")):
        cfg = json.load(open(os.path.join(root, "cfg_snapshot.json")))
    issues = []
    issues += ["basis: " + x for x in B.basis_issues(pkg)]
    issues += _dc_issues(pkg)
    issues += _system_issues(pkg, root)
    issues += _file_issues(root)
    issues += _report_issues(root, pkg)
    issues += _retrieval_issues(root, cfg)
    if verbose:
        print("[consistency] %s: %d issue(s)" % (name, len(issues)))
        for x in issues:
            print("  -", x)
    return issues
