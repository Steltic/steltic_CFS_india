"""india_cfs_gates.py -- the ONE COMPLETE authority of an India CFS job (spec WP0.2, WP3.5 as re-ruled by D3).

design_status(cfg, pkg) -> {status: complete | partial | example_only, reasons[], authority}
complete_allowed(cfg, pkg) -> (bool, reasons)   (kept for steltic/agent.py)

A package is `complete` only when ALL of the following hold:
  * the hot-rolled lateral frame (vendored HR India pipeline) reached `complete` in its own authority
    (india_seismic_gates.design_status: IS 1893 7.7.1 method, W = engine mass, Table 9 / IS 18168 system gate,
    IS 800 member checks D/C <= 1, Section 12 / IS 18168 chain, connections and bases with numeric capacities,
    drift <= 0.004 h, irregularity screens, IS grounding, no US residue);
  * every CFS member (studs, joists, purlins, girts, all-CFS portal members) has an IS 801 record with numeric demand
    and capacity, DC recomputed here as demand / capacity, DC <= 1.0, no `ok is None` outside informational rows;
  * design_basis is IS801_WSM with the two labelled combination families (india_cfs_basis.validate_load_plan) and
    no mixed capacity bases (india_cfs_basis.basis_issues);
  * the diaphragm / collector path is evaluated (a cited product / test capacity for the deck / sheathing) -- or the
    package is honest about it (found:false blocks COMPLETE);
  * every anchor / connection of the CFS members has a capacity from geometry + clause or a cited product value;
  * no cite / label / source matches /example|acme|not.for.construction|placeholder|synthetic/i -> `example_only`;
  * no capacity is a function of its own demand (consistency grep rules);
  * no SFIA / AISC designator and no US clause string in the package.
Nothing is waived: `waived: true` is an ERROR.

C6 (IS 800 retrieval) is re-ruled by D3: the lateral frame IS an IS 800 Section 12 frame, so IS 800 / IS 18168
queries are allowed for the purposes `lateral_frame_is800`, `serviceability_limits_table6` (deflection limits, WP3.6),
`sfrs_gap_found_false`, `document_absence`, `found_false_log`.  IS 800 must still never be used as a capacity source
for a cold-formed member (IS 801 governs those) and never as an R proxy for a CFS system (there is none, D3).
"""
from __future__ import annotations
import re

EXAMPLE_RE = re.compile(r"example|acme|not.for.construction|placeholder|synthetic", re.I)
US_RE = re.compile(r"\b(AISI|S100|S240|S400|ASCE\s*7|ASCE7|AISC\s*3[456][018]|SDPWS|SFIA|FEMA\s*P-?695|LRFD|SDS|SD1|Cd\b|"
                   r"Omega_?0|\bpsf\b|\bplf\b|\bkip\b|\bksi\b|Risk Category|Table 12\.\d)", re.I)
SFIA_RE = re.compile(r"^\d{3,4}[SsTtUuFfLl]\d{2,3}-\d{2,3}$")
DEMAND_CAP_RE = re.compile(r"cap\s*=\s*max\(.*\*\s*1\.(15|25)|DC\"?\s*[:=]\s*0\.8\b|seeded D/C", re.I)
AUTHORITY = "india_cfs_gates.design_status (CFS) over india_seismic_gates.design_status (vendored HR, lateral frame)"

IS800_STEMS = ("IS_800_2007", "IS800", "IS_800", "engineering_standards_IS800", "IS_18168_2023", "IS18168")
IS800_ALLOWLIST_PURPOSES = frozenset({
    "lateral_frame_is800", "lateral_frame", "section_12", "is800_table4", "serviceability_limits_table6",
    "sfrs_gap_found_false", "document_absence", "found_false_log", "eor_documented_exception",
})
IS800_BAN_MSG = ("IS 800 / IS 18168 retrieval on a CFS job is limited to the hot-rolled lateral frame (purpose "
                 "'lateral_frame_is800'), the IS 800 Table 6 deflection limits ('serviceability_limits_table6') and gap "
                 "logging. Cold-formed members are designed to IS 801:1975 / IS 811:1987 -- IS 800 is never their "
                 "capacity source and never an R proxy for a CFS system (decision D3).")


def _norm_purpose(p) -> str:
    return str(p or "").strip().lower().replace(" ", "_").replace("-", "_")


def is_is800_target(collection: str = "", doc: str = "", stem: str = "") -> bool:
    blob = " ".join(str(x or "") for x in (collection, doc, stem)).strip().lower()
    if not blob:
        return False
    compact = blob.replace("-", "_").replace(" ", "")
    if any(m in compact for m in ("is_800", "is800", "is_18168", "is18168")):
        if any(x in compact for x in ("is_801", "is801", "is_808", "is808", "is_811", "is811")):
            return False
        return True
    return False


def is800_purpose_allowed(purpose: str = "") -> bool:
    p = _norm_purpose(purpose)
    return bool(p) and (p in IS800_ALLOWLIST_PURPOSES or any(a in p for a in IS800_ALLOWLIST_PURPOSES))


def gate_is800_query(collection: str = "", doc: str = "", stem: str = "", purpose: str = "") -> tuple:
    if not is_is800_target(collection=collection, doc=doc, stem=stem):
        return True, ""
    if is800_purpose_allowed(purpose):
        return True, "IS 800 / IS 18168 query allowed for purpose=%r (hot-rolled lateral frame / Table 6 / gap log)" % (purpose,)
    return False, IS800_BAN_MSG


def is800_refusal_payload(collection: str = "", purpose: str = "", query: str = "") -> dict:
    return {"results": [], "hits": [], "found": False, "refused": True,
            "collection": collection or "engineering_standards_IS800", "query": query or "", "purpose": purpose or "",
            "note": IS800_BAN_MSG, "c6": True}


def validate_is800_retrieval(cfg_or_plan) -> list:
    out = []
    if isinstance(cfg_or_plan, dict) and "retrieval" not in cfg_or_plan and "load_plan" in cfg_or_plan:
        rows = list((cfg_or_plan.get("load_plan") or {}).get("retrieval") or []) + list(cfg_or_plan.get("is811_retrieval") or [])
    elif isinstance(cfg_or_plan, dict):
        rows = list(cfg_or_plan.get("retrieval") or [])
    elif isinstance(cfg_or_plan, list):
        rows = cfg_or_plan
    else:
        return out
    for i, hit in enumerate(rows):
        if not isinstance(hit, dict):
            continue
        stem = hit.get("stem") or hit.get("doc") or ""
        ok, msg = gate_is800_query(collection=hit.get("collection") or "", doc=stem, stem=stem, purpose=hit.get("purpose") or "")
        if not ok:
            out.append(("ERROR", "retrieval[%d] targets IS 800 without an allowed purpose (got %r). %s"
                        % (i, hit.get("purpose"), msg)))
    return out


# ---------------------------------------------------------------------------------------------------------------
def _walk_strings(obj, path="pkg"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, path + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, "%s[%d]" % (path, i))
    elif isinstance(obj, str):
        yield path, obj


def example_hits(obj) -> list:
    return [(p, s) for p, s in _walk_strings(obj) if EXAMPLE_RE.search(s) and not p.endswith((".note", ".reason", ".authority"))
            and "example_only" not in s.lower() and "no us" not in s.lower()]


def us_residue_hits(obj) -> list:
    out = []
    for p, s in _walk_strings(obj):
        if p.endswith((".note", ".reason", ".cite", ".authority", ".basis_statement")) and ("no " in s.lower() or "never" in s.lower()):
            continue
        m = US_RE.search(s)
        if m:
            out.append((p, m.group(0)))
    return out


def _dc(entry):
    v = entry.get("value") if entry.get("value") is not None else entry.get("demand")
    c = entry.get("limit") if entry.get("limit") is not None else entry.get("capacity")
    if isinstance(v, (int, float)) and isinstance(c, (int, float)) and c > 0:
        return abs(v) / c
    return None


def cfs_member_issues(pkg) -> list:
    """Every CFS member: numeric demand / capacity per check, DC recomputed here, DC <= 1, nothing unevaluated."""
    reasons = []
    for m in pkg.get("cfs_members") or []:
        mid = m.get("id")
        if m.get("waived"):
            reasons.append("cfs member %s: waived:true is not permitted (WP0.2)" % mid)
        checks = m.get("checks") or []
        if not checks:
            reasons.append("cfs member %s has no IS 801 checks" % mid)
        for c in checks:
            if c.get("informational"):
                continue
            if c.get("ok") is None:
                reasons.append("cfs member %s / %s / %s: not evaluated (found:false / ok None)%s"
                               % (mid, c.get("combo"), c.get("check"), (": " + c["note"]) if c.get("note") else ""))
                continue
            if c.get("capacity_basis") is None:
                reasons.append("cfs member %s / %s: capacity_basis missing" % (mid, c.get("check")))
            dc = _dc(c)
            if dc is None and c.get("dc") is None and c.get("limit") is not None:
                reasons.append("cfs member %s / %s / %s: no numeric demand / capacity" % (mid, c.get("combo"), c.get("check")))
            elif dc is not None and dc > 1.0 + 1e-9:
                reasons.append("cfs member %s / %s / %s: D/C = %.3f > 1.0 (recomputed %s / %s)"
                               % (mid, c.get("combo"), c.get("check"), dc, c.get("value"), c.get("limit")))
            elif c.get("ok") is False:
                reasons.append("cfs member %s / %s / %s: ok:false" % (mid, c.get("combo"), c.get("check")))
    return reasons


def lateral_issues(pkg) -> list:
    lat = pkg.get("lateral_frame") or {}
    st = (lat.get("status") or {})
    if not lat:
        return ["hot-rolled lateral frame not analysed (lateral_frame missing) -- D3: every CFS building has an IS 800 Section 12 frame"]
    if lat.get("error"):
        return ["lateral frame run error: %s" % lat["error"]]
    if str(st.get("status")).lower() != "complete":
        return ["lateral frame (HR authority) status %s: %s" % (st.get("status"), r) for r in (st.get("reasons") or [])[:60]] or \
               ["lateral frame (HR authority) status %s" % st.get("status")]
    return []


def diaphragm_issues(pkg) -> list:
    out = []
    for r in pkg.get("diaphragm") or []:
        if r.get("ok") is None or r.get("found") is False:
            out.append("%s storey %s %s: capacity not evaluated (%s)" % ("collector" if r.get("kind") == "collector" else "diaphragm",
                                                                         r.get("storey"), r.get("dir"), r.get("note") or "found:false"))
        elif _dc(r) is not None and _dc(r) > 1.0:
            out.append("diaphragm storey %s %s: D/C %.2f > 1" % (r.get("storey"), r.get("dir"), _dc(r)))
    return out


def anchorage_issues(pkg) -> list:
    out = []
    for a in pkg.get("cfs_connections") or []:
        if a.get("waived"):
            out.append("connection %s: waived:true is not permitted" % a.get("id")); continue
        if a.get("ok") is None:
            out.append("connection %s: not evaluated (%s)" % (a.get("id"), a.get("note") or "found:false")); continue
        dc = _dc(a) if a.get("dc") is None else a.get("dc")
        if dc is None:
            out.append("connection %s: no numeric demand / capacity" % a.get("id"))
        elif dc > 1.0 + 1e-9:
            out.append("connection %s: D/C %.3f > 1" % (a.get("id"), dc))
    return out


def design_status(cfg, pkg=None) -> dict:
    import india_cfs_basis as B
    pkg = pkg or {}
    reasons = []
    ex = example_hits({"cfg": {k: v for k, v in (cfg or {}).items() if k != "load_plan"}, "pkg": pkg,
                       "retrieval": ((cfg or {}).get("load_plan") or {}).get("retrieval")})
    status = "partial"
    if ex:
        reasons += ["EXAMPLE provenance: %s = %r" % (p, s[:80]) for p, s in ex[:10]]
        status = "example_only"
    for sev, msg in B.validate_load_plan(cfg or {}):
        if sev == "ERROR":
            reasons.append("load plan: " + msg)
    reasons += ["basis: " + x for x in B.basis_issues(pkg)]
    reasons += lateral_issues(pkg)
    reasons += cfs_member_issues(pkg)
    reasons += diaphragm_issues(pkg)
    reasons += anchorage_issues(pkg)
    for p, s in _walk_strings({"cfg": cfg or {}}):
        if SFIA_RE.match(s.strip()):
            reasons.append("SFIA designator %r at %s is not permitted on an India job (use IS 811 labels)" % (s, p))
    us = us_residue_hits(pkg)
    if us:
        reasons += ["US residue in the package: %s (%s)" % (p, m) for p, m in us[:10]]
    for p, s in _walk_strings(pkg):
        if DEMAND_CAP_RE.search(s):
            reasons.append("capacity derived from demand pattern at %s" % p)
    if pkg.get("report_us_residue"):
        reasons += ["US residue in the report: %s" % x for x in pkg["report_us_residue"][:10]]
    if pkg.get("grounding_missing"):
        reasons += ["report grounding row MISSING: %s" % x for x in pkg["grounding_missing"]]
    if not reasons:
        status = "complete"
    return {"status": status, "reasons": reasons, "n_reasons": len(reasons), "authority": AUTHORITY}


def complete_allowed(cfg, pkg=None) -> tuple:
    st = design_status(cfg, pkg)
    return st["status"] == "complete", st["reasons"]


def validate_india_cfs_p0(cfg) -> list:
    """Preflight-level CFS gates: basis, SFIA designators, IS 800 purposes, drift limit."""
    import india_cfs_basis as B
    out = [("ERROR", m) if s == "ERROR" else (s, m) for s, m in B.validate_load_plan(cfg or {})]
    out += validate_is800_retrieval(cfg or {})
    for p, s in _walk_strings({"cfg": {k: v for k, v in (cfg or {}).items() if k != "load_plan"}}):
        if SFIA_RE.match(s.strip()):
            out.append(("ERROR", "SFIA designator %r at %s -- India jobs use IS 811 labels (cfg['allow_sfia_twin'] is not honoured)" % (s, p)))
    dl = (cfg or {}).get("drift_limit")
    if dl not in (None, "") and float(dl) > 0.004 + 1e-12:
        out.append(("ERROR", "drift_limit %.4f > 0.004 h (IS 1893 7.11.1.1)" % float(dl)))
    return out


validate_india_cfs_p1 = validate_is800_retrieval
