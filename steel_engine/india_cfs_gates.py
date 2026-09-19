"""India CFS P0/P1 gates: wall vn + R provenance + complete-label + IS 800 ban.

C1 — No silent provisional 700 plf ASD wall shear default.
     Require cfg['wall_vn_plf_asd'] (or nested wall_vn) with a non-provisional
     manufacturer/test/IS-table source, OR hard-fail with found:false
     (IS 801 cl.9 / cl.9.1.4 messaging).

C2 — No silent IS 800 OMRF R=3.0 proxy when CFS is missing from IS 1893 Table 9.
     Require explicit cfg['R'] (or seis['R']) + R_source + R_cite. Allowlisted
     sources include eor_documented / explicit / is1893_table9 (NOT proxy/
     is800_omrf). Never auto-fill R from IS 800. Preflight ERROR if the
     silent-proxy path would have been used.

C6 — Hard-ban IS_800_2007 on CFS India jobs except allowlisted purposes
     (sfrs_gap_found_false / document_absence / found_false_log / …).
     Default refuse silent HR R proxy path (reinforces C2).

C7 — Refuse labeling COMPLETE when vn source is provisional OR R source is proxy.
     PARTIAL is the correct admin label until both sources are authoritative.

C5 (helper): india_is811_retrieval.seed_is811_retrieval_plan — richer IS 811
     exact_table/exact_section plans; Amd1 found:false when empty.

load_plan RAG gate (india_loads) remains mandatory and is not replaced here.
"""
from __future__ import annotations

# --- wall unit shear (vn) -------------------------------------------------
# Acceptable provenance for ASD allowable unit shear (plf).
WALL_VN_OK_SOURCES = frozenset({
    "manufacturer", "test", "tested", "lab", "is801_table", "is801",
    "documented", "eor_documented", "catalogue", "catalog",
})
# Explicitly refused (C1 hard-fail). Includes the Ex1 "provisional 700" pattern.
WALL_VN_PROVISIONAL = frozenset({
    "provisional", "assumed", "assumption", "default", "silent", "silent_default",
    "industry_guess", "placeholder", "todo", "tbd",
})

# --- response reduction R -------------------------------------------------
R_PROXY_SOURCES = frozenset({
    "proxy", "omrf_proxy", "is800_omrf", "steel_omrf", "omrf", "silent_proxy",
    "is_800_omrf", "table9_steel_omrf", "cfs_systems_twin",
})
R_OK_SOURCES = frozenset({
    "is1893_table9", "is_1893_table9", "table9", "is1893", "rag",
    "explicit", "eor_explicit", "documented", "eor_documented", "eor",
    "manufacturer_sfrs",
})

IS801_VN_MSG = (
    "IS 801:1975 cl.9 / cl.9.1.4 — light-gauge diaphragms/shear walls are outside "
    "IS 801 tabulated scope (found:false for WSP/steel-sheet vn tables in IS 801/811). "
    "Set cfg['wall_vn_plf_asd'] from manufacturer/test data with cfg['wall_vn_source'] "
    "in {manufacturer,test,is801_table,documented} and cfg['wall_vn_cite']. "
    "Do NOT invent a silent provisional 700 plf ASD default."
)


def _norm(s) -> str:
    return str(s or "").strip().lower().replace(" ", "_").replace("-", "_")


def _wall_systems(cfg) -> bool:
    sysname = _norm(cfg.get("system") if isinstance(cfg, dict) else "")
    return any(k in sysname for k in (
        "wsp_shearwall", "steelsheet", "gypsum_wall", "strap_braced", "shearwall", "shear_wall",
    )) or bool((cfg or {}).get("lines_x") or (cfg or {}).get("lines_y"))


def resolve_wall_vn(cfg) -> dict:
    """Normalize wall vn from flat or nested cfg keys. Does not invent values."""
    cfg = cfg or {}
    nested = cfg.get("wall_vn") if isinstance(cfg.get("wall_vn"), dict) else {}
    plf = cfg.get("wall_vn_plf_asd")
    if plf is None:
        plf = nested.get("plf_asd", nested.get("vn_plf_asd", nested.get("capacity")))
    source = cfg.get("wall_vn_source") or nested.get("source") or nested.get("vn_source")
    cite = cfg.get("wall_vn_cite") or nested.get("cite") or nested.get("citation")
    found = cfg.get("wall_vn_found")
    if found is None:
        found = nested.get("found")
    return {
        "plf_asd": plf,
        "source": source,
        "cite": cite,
        "found": found,
        "raw_source": _norm(source),
    }


def resolve_R(cfg) -> dict:
    """Normalize R + provenance from cfg / seis / load_plan.seismic_summary."""
    cfg = cfg or {}
    seis = cfg.get("seis") if isinstance(cfg.get("seis"), dict) else {}
    plan = cfg.get("load_plan") if isinstance(cfg.get("load_plan"), dict) else {}
    summ = plan.get("seismic_summary") if isinstance(plan.get("seismic_summary"), dict) else {}

    R = cfg.get("R")
    if R is None:
        R = seis.get("R")
    if R is None:
        R = summ.get("R")

    source = (cfg.get("R_source") or seis.get("R_source") or summ.get("R_source")
              or cfg.get("r_source") or summ.get("response_reduction_source"))
    cite = cfg.get("R_cite") or seis.get("R_cite") or summ.get("R_cite") or summ.get("cite")
    # Table 9 CFS-row found flag (False = missing CFS system in Table 9)
    cfs_row = cfg.get("R_cfs_table9_found")
    if cfs_row is None:
        cfs_row = seis.get("R_cfs_table9_found")
    if cfs_row is None:
        cfs_row = summ.get("R_cfs_table9_found")
    if cfs_row is None:
        cfs_row = summ.get("cfs_table9_found")

    return {
        "R": R,
        "source": source,
        "cite": cite,
        "cfs_table9_found": cfs_row,
        "raw_source": _norm(source),
    }


def validate_wall_vn(cfg) -> list:
    """Return (severity, message) findings for C1. ERROR = hard-fail."""
    out = []
    if not isinstance(cfg, dict):
        return [("ERROR", "cfg is not a dict")]
    if not _wall_systems(cfg):
        return out  # portals / non-wall: wall vn N/A

    vn = resolve_wall_vn(cfg)
    plf, src = vn["plf_asd"], vn["raw_source"]

    if plf is None or plf == "":
        out.append(("ERROR",
                    "cfg['wall_vn_plf_asd'] missing (found:false). " + IS801_VN_MSG))
        return out

    try:
        plf_f = float(plf)
    except (TypeError, ValueError):
        out.append(("ERROR",
                    "cfg['wall_vn_plf_asd']=%r is not numeric — " % (plf,) + IS801_VN_MSG))
        return out

    if plf_f <= 0:
        out.append(("ERROR",
                    "cfg['wall_vn_plf_asd']=%.4g must be > 0 — " % plf_f + IS801_VN_MSG))

    if not src:
        out.append(("ERROR",
                    "cfg['wall_vn_source'] missing. Refuse silent provisional defaults. "
                    + IS801_VN_MSG))
        return out

    if src in WALL_VN_PROVISIONAL or "provisional" in src:
        out.append(("ERROR",
                    "wall_vn_source=%r is provisional — hard-fail (C1). "
                    "Do not use a silent/provisional 700 plf ASD default. "
                    "Substitute manufacturer/test vn or leave wall shear found:false. "
                    % (vn["source"],) + IS801_VN_MSG))
        return out

    if src not in WALL_VN_OK_SOURCES:
        out.append(("ERROR",
                    "wall_vn_source=%r not accepted. Use one of %s with wall_vn_cite. "
                    % (vn["source"], sorted(WALL_VN_OK_SOURCES)) + IS801_VN_MSG))
        return out

    if not (vn["cite"] or "").strip():
        out.append(("ERROR",
                    "cfg['wall_vn_cite'] required when wall_vn_source=%r "
                    "(document manufacturer/test/table). " % (vn["source"],) + IS801_VN_MSG))

    if vn["found"] is False and src in WALL_VN_OK_SOURCES:
        out.append(("WARN",
                    "wall_vn_found=false with source=%s — confirm cite still grounds capacity"
                    % vn["source"]))

    return out


def validate_R(cfg) -> list:
    """Return (severity, message) findings for C2. ERROR if silent OMRF proxy would apply."""
    out = []
    if not isinstance(cfg, dict):
        return [("ERROR", "cfg is not a dict")]

    # Always require explicit R on India CFS (seismic block is mandatory in preflight).
    info = resolve_R(cfg)
    R, src = info["R"], info["raw_source"]

    if R is None or R == "":
        out.append(("ERROR",
                    "cfg['R'] / cfg['seis']['R'] missing. India CFS must set R explicitly "
                    "from IS 1893 Part 1 Table 9 RAG (or EOR-documented value). "
                    "Silent IS 800 OMRF R=3.0 proxy is forbidden (C2)."))
        return out

    try:
        float(R)
    except (TypeError, ValueError):
        out.append(("ERROR", "R=%r is not numeric" % (R,)))
        return out

    if not src:
        # The silent-proxy failure mode from IN_CFS_Ex1: seis.R=3.0 with no provenance.
        out.append(("ERROR",
                    "cfg['R_source'] (or seis/load_plan.seismic_summary R_source) missing — "
                    "silent IS 800 / Table 9 steel OMRF R=3.0 proxy would have been used (C2). "
                    "RAG-query IS 1893 Table 9 for the CFS SFRS row; if CFS is absent set "
                    "R_cfs_table9_found=false and an EXPLICIT EOR R with R_source="
                    "'eor_documented'|'explicit'|'documented' (not 'proxy'/'is800_omrf'). "
                    "Never auto-fill R from IS 800. Do not invent OMRF R=3 silently."))
        return out

    if src in R_PROXY_SOURCES or "proxy" in src or "omrf" in src:
        # Disclosed proxy: preflight WARN (not the silent failure mode). C7 still refuses COMPLETE.
        # Preferred: R_source='eor_documented'|'explicit' + R_cfs_table9_found=false + R_cite
        # (no "proxy"/"is800_omrf"; never auto-fill from IS 800).
        out.append(("WARN",
                    "R_source=%r is an OMRF/proxy path (C2/C7). Job MUST stay PARTIAL — "
                    "complete_allowed=false. Prefer R_source='eor_documented'|'explicit'|'documented' "
                    "with R_cfs_table9_found=false when Table 9 has no CFS row; never auto-fill "
                    "from IS 800; do not silently default to IS 800 OMRF R=3.0." % (info["source"],)))

    if src not in R_OK_SOURCES and src not in ("eor", "user", "brief"):
        out.append(("WARN",
                    "R_source=%r unusual — prefer is1893_table9 / eor_documented / explicit / documented"
                    % (info["source"],)))

    # When CFS Table 9 row is known-missing, require found:false disclosure + cite.
    if info["cfs_table9_found"] is False:
        if not (info["cite"] or "").strip():
            out.append(("ERROR",
                        "R_cfs_table9_found=false but R_cite missing — disclose the EOR basis "
                        "for cfg R (found:false for CFS row in IS 1893 Table 9)."))
        out.append(("WARN",
                    "CFS SFRS row missing from IS 1893 Table 9 (found:false). "
                    "R_source must stay non-proxy (eor_documented/explicit/documented). C7 still refuses "
                    "COMPLETE if R_source is proxy OR wall vn is provisional. Amd1 found:false alone "
                    "does not block COMPLETE."))

    return out


def vn_is_provisional(cfg, pkg=None) -> bool:
    """True if cfg or package marks wall vn as provisional."""
    vn = resolve_wall_vn(cfg or {})
    if vn["raw_source"] in WALL_VN_PROVISIONAL or "provisional" in vn["raw_source"]:
        return True
    if not isinstance(pkg, dict):
        return False
    notes = pkg.get("design_basis_notes") or {}
    if "provisional" in _norm(notes.get("wall_shear") or notes.get("wall_vn") or ""):
        return True
    if "provisional" in _norm(pkg.get("status_agent") or ""):
        # only if wall-related
        sa = _norm(pkg.get("status_agent") or "")
        if "wall" in sa or "vn" in sa or "shear" in sa:
            return True
    for w in pkg.get("wall_lines") or []:
        if not isinstance(w, dict):
            continue
        blob = " ".join(str(w.get(k) or "") for k in
                        ("limit_state", "capacity_unit", "cited", "vn_source", "source"))
        if "provisional" in _norm(blob):
            return True
        if w.get("found_is801_table") is False and not (cfg or {}).get("wall_vn_plf_asd"):
            return True
    return False


def R_is_proxy(cfg, pkg=None) -> bool:
    """True if R provenance is an OMRF/proxy path."""
    info = resolve_R(cfg or {})
    src = info["raw_source"]
    if src in R_PROXY_SOURCES or "proxy" in src or "omrf" in src:
        return True
    if not src and info["R"] is not None:
        # missing source with a numeric R = silent-proxy class
        return True
    if not isinstance(pkg, dict):
        return False
    notes = pkg.get("design_basis_notes") or {}
    blob = _norm(notes.get("R_basis") or notes.get("R_source") or "")
    if "proxy" in blob or "omrf" in blob:
        return True
    summ = ((pkg.get("load_plan") or {}).get("seismic_summary")
            if isinstance(pkg.get("load_plan"), dict) else None) or {}
    if "proxy" in _norm(summ.get("R_source") or summ.get("note") or ""):
        return True
    return False


def complete_allowed(cfg, pkg=None) -> tuple:
    """C7: (ok, reasons). Refuse COMPLETE if vn provisional OR R proxy.

    Amd1 empty (IS_811_1987_Amd1_2011 found:false) and S400 Ω0 N/A (found:false)
    must NOT alone block COMPLETE — those are honest gaps, not C7 refusals.
    """
    reasons = []
    if vn_is_provisional(cfg, pkg):
        reasons.append("wall vn source is provisional (C7) — manufacturer/test vn required for COMPLETE")
    if R_is_proxy(cfg, pkg):
        reasons.append("R source is proxy / silent OMRF (C7) — IS 1893 Table 9 CFS R or R_source='eor_documented' (non-proxy) required for COMPLETE")
    # Also refuse if wall vn / R gates still ERROR
    for sev, msg in validate_wall_vn(cfg or {}) + validate_R(cfg or {}):
        if sev == "ERROR":
            reasons.append(msg)
    # de-dupe while preserving order
    seen = set()
    uniq = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return (len(uniq) == 0, uniq)


def amd1_gap_blocks_complete(cfg=None, pkg=None) -> bool:
    """Amd1 empty / found:false must never alone refuse COMPLETE (C5 honesty)."""
    return False


def s400_omega0_blocks_complete(cfg=None, pkg=None) -> bool:
    """S400 Ω0 capacity-design is N/A under IS 801 — found:false does not block COMPLETE."""
    return False

def design_status(cfg, pkg=None) -> dict:
    """Admin-facing label helper: complete | partial | blocked."""
    ok, reasons = complete_allowed(cfg, pkg)
    if ok:
        return {"status": "complete", "reasons": [], "admin_notify": "complete"}
    # If hard preflight ERRORs on vn/R → blocked; else partial
    hard = [m for s, m in (validate_wall_vn(cfg or {}) + validate_R(cfg or {})) if s == "ERROR"]
    if hard and not (pkg and (pkg.get("wall_lines") or pkg.get("members"))):
        return {"status": "blocked", "reasons": reasons or hard, "admin_notify": "partial"}
    return {"status": "partial", "reasons": reasons, "admin_notify": "partial"}


def validate_india_cfs_p0(cfg) -> list:
    """Combined C1+C2 findings for preflight."""
    return list(validate_wall_vn(cfg)) + list(validate_R(cfg))


# =============================================================================
# C6 — IS_800_2007 hard-ban / allowlist on CFS India jobs
# =============================================================================
# Hot-rolled IS 800 must not be the silent path for CFS R, load combos, or
# member checks. Allowed only for documented SFRS-gap / absence logging with
# found:false — never as a silent OMRF R=3 proxy (reinforce C2).

IS800_STEMS = frozenset({
    "IS_800_2007", "IS_800", "IS800", "IS800_2007", "IS-800", "IS-800-2007",
})
IS800_COLLECTION_MARKERS = (
    "is800", "is_800", "engineering_standards_is800", "engineering_standard_is800",
)

# purpose= values that MAY touch IS 800 (still must log found:false when used for gap).
IS800_ALLOWLIST_PURPOSES = frozenset({
    "sfrs_gap_found_false",
    "sfrs_gap",
    "document_absence",
    "document_absence_check",
    "found_false_log",
    "cfs_row_absent_log",
    "eor_documented_exception",
})

IS800_BAN_MSG = (
    "C6: IS_800_2007 is hard-banned on CFS India jobs except allowlisted purposes "
    "(sfrs_gap_found_false / document_absence / found_false_log / eor_documented_exception). "
    "Use IS 801 + IS 811 for CFS design and IS 875/1893 for loads. "
    "Silent HR OMRF R=3 proxy via IS 800 is forbidden (C2/C6) — set explicit R + R_source."
)


def _norm_purpose(p) -> str:
    return str(p or "").strip().lower().replace(" ", "_").replace("-", "_")


def is_is800_target(collection: str = "", doc: str = "", stem: str = "") -> bool:
    """True if the RAG target is hot-rolled IS 800."""
    blob = " ".join(str(x or "") for x in (collection, doc, stem)).strip().lower()
    if not blob:
        return False
    compact = blob.replace("-", "_").replace(" ", "")
    if any(m in compact for m in ("is_800", "is800")):
        # Avoid false positive on IS_801 / IS_808 / IS_811
        if "is_801" in compact or "is801" in compact:
            return False
        if "is_808" in compact or "is808" in compact:
            return False
        if "is_811" in compact or "is811" in compact:
            return False
        return True
    for s in IS800_STEMS:
        if s.lower().replace("-", "_") in compact:
            return True
    return False


def is800_purpose_allowed(purpose: str = "") -> bool:
    p = _norm_purpose(purpose)
    if not p:
        return False
    if p in IS800_ALLOWLIST_PURPOSES:
        return True
    # substring allow for longer agent prose purposes
    return any(a in p for a in IS800_ALLOWLIST_PURPOSES)


def gate_is800_query(collection: str = "", doc: str = "", stem: str = "",
                     purpose: str = "") -> tuple:
    """Return (allowed: bool, message: str). Refused queries must not hit the RAG."""
    if not is_is800_target(collection=collection, doc=doc, stem=stem):
        return True, ""
    if is800_purpose_allowed(purpose):
        return True, (
            "C6 allowlisted IS 800 purpose=%r — log found:false when documenting a gap; "
            "do NOT adopt IS 800 OMRF R as a silent CFS proxy." % (purpose,)
        )
    return False, IS800_BAN_MSG


def is800_refusal_payload(collection: str = "", purpose: str = "", query: str = "") -> dict:
    """Standard refused-search payload (found:false, no hits)."""
    return {
        "results": [],
        "hits": [],
        "found": False,
        "refused": True,
        "collection": collection or "engineering_standards_IS800",
        "query": query or "",
        "purpose": purpose or "",
        "note": IS800_BAN_MSG,
        "c6": True,
    }


def validate_is800_retrieval(cfg_or_plan) -> list:
    """Scan cfg['load_plan'].retrieval (and optional design_retrieval) for banned IS 800 hits.

    ERROR if an IS 800 stem appears without an allowlisted purpose.
    """
    out = []
    if isinstance(cfg_or_plan, dict) and "retrieval" not in cfg_or_plan \
            and "load_plan" in (cfg_or_plan or {}):
        plan = cfg_or_plan.get("load_plan") or {}
        rows = list(plan.get("retrieval") or [])
        rows += list((cfg_or_plan.get("design_retrieval") or
                      cfg_or_plan.get("is811_retrieval") or []))
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
        coll = hit.get("collection") or ""
        purpose = hit.get("purpose") or hit.get("why") or ""
        ok, msg = gate_is800_query(collection=coll, doc=stem, stem=stem, purpose=purpose)
        if not ok:
            out.append(("ERROR",
                        "load_plan/design retrieval[%d] targets IS 800 without allowlisted "
                        "purpose (got purpose=%r). %s" % (i, purpose, msg)))
        elif is_is800_target(collection=coll, doc=stem, stem=stem):
            # Allowlisted: still require found:false disclosure for gap logging
            if hit.get("found") is True and "gap" in _norm_purpose(purpose):
                out.append(("WARN",
                            "retrieval[%d] IS 800 allowlisted purpose=%r but found=true — "
                            "gap logs should usually be found:false" % (i, purpose)))
            out.append(("WARN",
                        "retrieval[%d] touches IS 800 under allowlisted purpose=%r (C6) — "
                        "confirm this is gap documentation, not an HR R proxy"
                        % (i, purpose)))
    return out


def validate_india_cfs_p1(cfg) -> list:
    """C6 (+ optional C5 richness WARN when is811_retrieval is present and thin)."""
    out = list(validate_is800_retrieval(cfg))
    # Optional C5: if agent attached an is811_retrieval / design_retrieval plan, score it
    plan = None
    if isinstance(cfg, dict):
        plan = cfg.get("is811_retrieval") or cfg.get("design_retrieval")
    if plan:
        try:
            import india_is811_retrieval as R811
            ok, advice = R811.plan_is_rich_enough(plan)
            if not ok:
                out.append(("WARN", advice))
        except Exception:
            pass
    return out
