"""
india_loads.py — India (IS/BIS) load path for steltic_CFS_india: LIVE RAG retrieval,
not hardcoded formulas.

CRITICAL (same rule as steltic_india HR):
  USA steltic_cfs embeds ASCE 7-22 wind/seismic/LRFD combo math in the engine
  (cfs_engine.elf, cfs_pipeline.wind_story_forces / enumerate_combos, design_pipeline.combos).
  India MUST NOT replace that with a permanent Python port of IS 875 / IS 1893.
  Every job the agent RAG-queries IS 875 Parts 1–5 and IS 1893 Part 1:2016, then writes
  the retrieved combination factors and story forces into cfg['load_plan']. This module
  only VALIDATES that plan and turns it into the (label, fD, fL, fLr, lateral, col_only)
  tuples the demand envelope already understands.

Design authority for CFS members/profiles: IS 801:1975 + IS 811:1987 (+ Amd1 when relevant).
Loads remain IS 875 / IS 1893 via this load_plan path — never re-hardcoded here.

Schema (cfg['load_plan']): see steltic_india india_loads.py — identical contract.
"""
from __future__ import annotations

# Canonical India load / seismic stems the agent must hit via RAG every job.
LOAD_STEMS = (
    "IS_875_Part_1_2026",   # dead loads
    "IS_875_Part_2_1987",   # imposed / live
    "IS_875_Part_3_2015",   # wind
    "IS_875_Part_4_1987",   # snow
    "IS_875_Part_5_1987",   # special loads / combinations notes
    "IS_1893_Part_1_2016",  # seismic
)

# CFS design stems (not loads — listed for contract / retrieval plans).
DESIGN_STEMS = (
    "IS_801_1975",
    "IS_811_1987",
    "IS_811_1987_Amd1_2011",  # may have 0 sections — found:false is honest
)

# Agent-facing RAG collection names → preferred document stem.
COLLECTION_TO_STEM = {
    "engineering_standards_IS801": "IS_801_1975",
    "engineering_standards_IS811": "IS_811_1987",
    "engineering_standards_IS811_Amd1": "IS_811_1987_Amd1_2011",
    "engineering_standards_IS875_P1": "IS_875_Part_1_2026",
    "engineering_standards_IS875_P2": "IS_875_Part_2_1987",
    "engineering_standards_IS875_P3": "IS_875_Part_3_2015",
    "engineering_standards_IS875_P4": "IS_875_Part_4_1987",
    "engineering_standards_IS875_P5": "IS_875_Part_5_1987",
    "engineering_standards_IS1893": "IS_1893_Part_1_2016",
    # short aliases
    "IS801": "IS_801_1975",
    "IS811": "IS_811_1987",
    "IS875_P3": "IS_875_Part_3_2015",
    "IS1893": "IS_1893_Part_1_2016",
}

STEM_TO_COLLECTION = {v: k for k, v in COLLECTION_TO_STEM.items()
                      if k.startswith("engineering_standards_")}


class LoadPlanError(ValueError):
    """cfg['load_plan'] missing, incomplete, or not RAG-backed."""


def _as_lateral(raw):
    """Normalize lateral story map to {int: (fx, fy, mz)}."""
    if not raw:
        return {}
    out = {}
    for k, v in dict(raw).items():
        ki = int(k)
        if isinstance(v, dict):
            out[ki] = (float(v.get("fx", 0)), float(v.get("fy", 0)), float(v.get("mz", 0)))
        else:
            seq = list(v)
            fx = float(seq[0]) if len(seq) > 0 else 0.0
            fy = float(seq[1]) if len(seq) > 1 else 0.0
            mz = float(seq[2]) if len(seq) > 2 else 0.0
            out[ki] = (fx, fy, mz)
    return out


def validate_load_plan(cfg) -> list:
    """Return a list of (level, message) findings. level in ERROR/WARN/INFO.

    ERRORs mean the demand envelope must not invent loads — agent must RAG-fill load_plan.
    """
    out = []
    plan = cfg.get("load_plan") if isinstance(cfg, dict) else None
    if not plan or not isinstance(plan, dict):
        out.append(("ERROR",
                    "cfg['load_plan'] missing. India CFS jobs MUST RAG-query IS 875 Parts 1–5 and "
                    "IS 1893 Part 1:2016 LIVE this job, then write retrieved combination factors "
                    "and story forces into cfg['load_plan'] (see india_loads.py). The engine will "
                    "NOT compute ASCE 7 or hardcode IS load formulas."))
        return out

    if str(plan.get("jurisdiction", "")).lower() not in ("india", "is", "is_bis", "bis"):
        out.append(("WARN",
                    "cfg['load_plan'].jurisdiction should be 'india' (got %r)" % plan.get("jurisdiction")))

    retrieval = plan.get("retrieval") or []
    if not isinstance(retrieval, list) or len(retrieval) < 2:
        out.append(("ERROR",
                    "cfg['load_plan'].retrieval must list ≥2 LIVE RAG hits this job "
                    "(IS 875 family + IS 1893 as applicable). Do not invent citations; "
                    "found:false is honest."))
    else:
        stems_hit = set()
        found_any = False
        for i, hit in enumerate(retrieval):
            if not isinstance(hit, dict):
                out.append(("ERROR", "load_plan.retrieval[%d] must be an object" % i))
                continue
            stem = str(hit.get("stem") or hit.get("doc") or "")
            if stem:
                stems_hit.add(stem)
            if hit.get("found") is True:
                found_any = True
            if hit.get("found") is False:
                out.append(("WARN",
                            "load_plan.retrieval[%d] found:false for %s — do not invent; "
                            "retry FTS/exact or note gap" % (i, stem or "?")))
            if not (hit.get("query") or hit.get("cite")):
                out.append(("WARN", "load_plan.retrieval[%d] missing query/cite" % i))
        if not any(s.startswith("IS_875") for s in stems_hit):
            out.append(("ERROR",
                        "load_plan.retrieval has no IS_875_* stem — query dead/imposed/wind/snow "
                        "from IS 875 Parts 1–5 before running the pipeline."))
        seis = cfg.get("seis") or {}
        if seis and not any("1893" in s for s in stems_hit):
            out.append(("ERROR",
                        "cfg has seismic inputs but load_plan.retrieval has no IS_1893_* hit — "
                        "RAG-query IS 1893 Part 1:2016 for zone factor / design spectrum / base shear."))
        if not found_any:
            out.append(("ERROR",
                        "load_plan.retrieval has no found:true hits — refuse to invent load factors."))

    combos = plan.get("combinations") or []
    if not isinstance(combos, list) or len(combos) < 1:
        out.append(("ERROR",
                    "cfg['load_plan'].combinations empty — after RAG, write partial-factor "
                    "combinations with fD/fL/fLr and any lateral story forces (cite IS 875/1893 "
                    "and IS 801 serviceability / design combo notes as retrieved)."))
    else:
        for i, c in enumerate(combos):
            if not isinstance(c, dict):
                out.append(("ERROR", "combinations[%d] must be an object" % i))
                continue
            if not c.get("label"):
                out.append(("ERROR", "combinations[%d] missing label" % i))
            for key in ("fD", "fL", "fLr"):
                if key not in c:
                    out.append(("ERROR", "combinations[%d] missing %s" % (i, key)))
            if not c.get("cite"):
                out.append(("WARN", "combinations[%d] (%s) has no cite — attach the retrieved clause"
                            % (i, c.get("label", "?"))))

    if cfg.get("use_asce7_engine_loads"):
        out.append(("ERROR",
                    "use_asce7_engine_loads is set — forbidden on steltic_CFS_india. "
                    "Remove it and supply cfg['load_plan'] from IS RAG."))

    return out


def cases_from_load_plan(cfg) -> list:
    """Build design_pipeline combo tuples from cfg['load_plan']. Raises LoadPlanError on ERRORs."""
    findings = validate_load_plan(cfg)
    errors = [m for lvl, m in findings if lvl == "ERROR"]
    if errors:
        raise LoadPlanError("India load_plan invalid:\n- " + "\n- ".join(errors))

    plan = cfg["load_plan"]
    cases = []
    for c in plan["combinations"]:
        label = str(c["label"])
        fD = float(c["fD"])
        fL = float(c.get("fL", 0.0))
        fLr = float(c.get("fLr", 0.0))
        lateral = _as_lateral(c.get("lateral") or {})
        ref = c.get("lateral_ref")
        if ref and not lateral:
            forces = (plan.get("story_forces") or {}).get(ref)
            if forces is None:
                raise LoadPlanError("combinations entry %r lateral_ref=%r not in load_plan.story_forces"
                                    % (label, ref))
            lateral = _as_lateral(forces)
        col_only = bool(c.get("col_only", False))
        cases.append((label, fD, fL, fLr, lateral, col_only))
    return cases


def combo_dicts_from_load_plan(cfg) -> list:
    """Wall-path package combos: list of dicts with label + factors (no invented ASCE labels)."""
    findings = validate_load_plan(cfg)
    errors = [m for lvl, m in findings if lvl == "ERROR"]
    if errors:
        raise LoadPlanError("India load_plan invalid:\n- " + "\n- ".join(errors))
    out = []
    for c in cfg["load_plan"]["combinations"]:
        d = dict(label=str(c["label"]), D=float(c["fD"]),
                 L=float(c.get("fL", 0.0)), Lr=float(c.get("fLr", 0.0)),
                 cite=c.get("cite"), role=c.get("role"))
        if c.get("lateral") or c.get("lateral_ref"):
            d["has_lateral"] = True
        if c.get("W") is not None:
            d["W"] = float(c["W"])
        if c.get("E") is not None:
            d["E"] = float(c["E"])
        if c.get("dir"):
            d["dir"] = c["dir"]
        if c.get("sign"):
            d["sign"] = c["sign"]
        out.append(d)
    return out


def render_findings(findings) -> str:
    if not findings:
        return "[india_loads] load_plan OK"
    lines = ["[india_loads] load_plan check:"]
    for lvl, msg in findings:
        lines.append("  [%s] %s" % (lvl, msg))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# IS 875 Part 3 §6.3.4 k4 (cyclonic importance) + Annex A town honesty
# Corpus QFM 2026-09-19: exact_section 6.3.4 / fts k4 now HIT (was OCR-broken).
# Prefer LIVE RAG fill; fall back to recovered corpus table by structure class.
# Never invent; never silently force k4=1.0 when class is industrial/post-cyclone.
# ---------------------------------------------------------------------------

# Recovered from IS_875_Part_3_2015.pdf cl.6.3.4 (QFM polish handoff).
K4_CORPUS_BY_CLASS = {
    "post_cyclone": 1.30,
    "post-cyclone": 1.30,
    "postcyclone": 1.30,
    "emergency": 1.30,
    "cyclone_shelter": 1.30,
    "hospital": 1.30,
    "school": 1.30,
    "communication_tower": 1.30,
    "industrial": 1.15,
    "industry": 1.15,
    "all_other": 1.00,
    "other": 1.00,
    "all-other": 1.00,
    "residential": 1.00,
    "motel": 1.00,
    "hotel": 1.00,
    "office": 1.00,
}

K4_CLAUSE = {
    "stem": "IS_875_Part_3_2015",
    "clause": "6.3.4",
    "cite": "IS 875 Part 3:2015 cl.6.3.4 Importance Factor for Cyclonic Region (k4)",
    "coastal_belt_note": (
        "Applies in ~60 km coastal belt on east coast and Gujarat coast. "
        "§6.6: offshore to ~200 km may use 1.15× nearest coast in addition to k4 "
        "(IS 15498 referenced in clause)."
    ),
    "qfm_handoff": "/workspace/handoff/qfm/IS875_P3_k4_AnnexA_polish_2026-09-19.md",
}

# Annex A basic wind speed honesty (town → Vb m/s). Not a full table — known fixes only.
ANNEX_A_KNOWN = {
    "vizag": {"Vb_mps": 50.0, "annex_name": "Vishakapatnam / Visakhapatnam", "found": True},
    "visakhapatnam": {"Vb_mps": 50.0, "annex_name": "Visakhapatnam", "found": True},
    "vishakapatnam": {"Vb_mps": 50.0, "annex_name": "Vishakapatnam", "found": True},
    "vishakhapatnam": {"Vb_mps": 50.0, "annex_name": "Vishakhapatnam", "found": True},
    "delhi": {"Vb_mps": 47.0, "annex_name": "Delhi", "found": True},
    "noida": {
        "Vb_mps": None,
        "annex_name": None,
        "found": False,
        "proxy": {"town": "Delhi", "Vb_mps": 47.0},
        "note": (
            "Noida is NOT in IS 875 Part 3 Annex A (found:false — do not invent a Noida row). "
            "Nearest listed NCR town: Delhi Vb=47 m/s as proxy, or use Fig.1 zone map."
        ),
    },
}


def _norm_class(s) -> str:
    return str(s or "").strip().lower().replace(" ", "_").replace("-", "_")


def normalize_k4_class(raw) -> str | None:
    """Map free-text structure class to canonical key: post_cyclone|industrial|all_other."""
    if raw is None or raw == "":
        return None
    s = _norm_class(raw)
    post = {
        "post_cyclone", "postcyclone", "emergency", "cyclone_shelter",
        "hospital", "school", "communication_tower",
    }
    industrial = {"industrial", "industry"}
    other = {"all_other", "other", "residential", "motel", "hotel", "office"}
    if s in post:
        return "post_cyclone"
    if s in industrial:
        return "industrial"
    if s in other:
        return "all_other"
    if "post" in s and "cyclone" in s:
        return "post_cyclone"
    if "industrial" in s or s == "industry":
        return "industrial"
    if any(tok in s for tok in ("shelter", "hospital", "emergency", "school", "communication")):
        return "post_cyclone"
    if any(tok in s for tok in ("motel", "hotel", "residential", "office", "all_other", "other")):
        return "all_other"
    return None


def resolve_k4_cyclonic(cfg=None, *, wind_summary=None) -> dict:
    """Resolve IS 875 P3 §6.3.4 k4 for cyclonic coastal sites.

    Preference order:
      1. LIVE RAG fill on load_plan.wind / wind_summary / cfg['k4_rag'] with found+value+cite
      2. Structure class → recovered corpus table (cl.6.3.4 QFM HIT) with cite
      3. found:false — never invent; never silently force 1.0 for industrial/post-cyclone

    Drops the historical Ex11 agent override that forced k4=1.0 (all-other) whenever
    OCR table was found:false — class industrial→1.15 / post-cyclone→1.30 now apply.
    """
    cfg = cfg or {}
    plan = cfg.get("load_plan") if isinstance(cfg.get("load_plan"), dict) else {}
    wind = wind_summary if isinstance(wind_summary, dict) else None
    if wind is None:
        wind = plan.get("wind") if isinstance(plan.get("wind"), dict) else {}
    if not wind:
        wind = plan.get("wind_summary") if isinstance(plan.get("wind_summary"), dict) else {}
    rag = cfg.get("k4_rag") if isinstance(cfg.get("k4_rag"), dict) else {}

    out = {
        "found": False,
        "k4": None,
        "class": None,
        "class_key": None,
        "cite": None,
        "stem": K4_CLAUSE["stem"],
        "clause": K4_CLAUSE["clause"],
        "source": None,
        "coastal_belt_note": K4_CLAUSE["coastal_belt_note"],
        "forced_1_0_override_refused": False,
        "note": None,
    }

    # Class from cfg / wind
    class_raw = (
        cfg.get("k4_class")
        or cfg.get("structure_class_k4")
        or cfg.get("cyclonic_structure_class")
        or wind.get("k4_class")
        or wind.get("structure_class")
        or rag.get("class")
    )
    class_key = normalize_k4_class(class_raw)
    out["class"] = class_raw
    out["class_key"] = class_key

    # Detect forbidden silent force-1.0 override
    force_1 = cfg.get("force_k4_1_0") or wind.get("force_k4_1_0") or rag.get("force_k4_1_0")
    if force_1 and class_key in ("industrial", "post_cyclone"):
        out["forced_1_0_override_refused"] = True
        out["note"] = (
            "Refuse force_k4_1_0 override: structure class=%r maps to k4=%s per "
            "IS 875 P3 cl.6.3.4 corpus (QFM HIT). Drop the all-other=1.0 agent override."
            % (class_raw, K4_CORPUS_BY_CLASS.get(class_key))
        )

    # 1) Explicit LIVE RAG / agent fill with found:true
    for blob, src in (
        (rag, "cfg.k4_rag"),
        (wind, "load_plan.wind"),
        (plan.get("k4") if isinstance(plan.get("k4"), dict) else {}, "load_plan.k4"),
    ):
        if not blob:
            continue
        if blob.get("found") is True and blob.get("k4") is not None:
            try:
                k4v = float(blob["k4"])
            except (TypeError, ValueError):
                continue
            cite = blob.get("cite") or blob.get("clause") or K4_CLAUSE["cite"]
            out.update(
                found=True, k4=k4v, cite=cite, source=src,
                note=blob.get("note") or "k4 from LIVE RAG / load_plan fill.",
            )
            if class_key and abs(k4v - K4_CORPUS_BY_CLASS.get(class_key, k4v)) > 0.011:
                out["warn"] = (
                    "RAG k4=%.3f differs from corpus class %s→%.2f — confirm cite."
                    % (k4v, class_key, K4_CORPUS_BY_CLASS[class_key])
                )
            return out
        if blob.get("found") is False and blob.get("k4") is None and not class_key:
            out["note"] = (
                blob.get("note")
                or "k4 retrieval found:false and no structure class — do not invent k4."
            )
            out["source"] = src
            # continue — class path may still resolve

    # Bare numeric on wind without found flag: only accept with cite
    if wind.get("k4") is not None and (wind.get("cite") or wind.get("k4_cite") or rag.get("cite")):
        try:
            k4v = float(wind["k4"])
            out.update(
                found=True, k4=k4v,
                cite=wind.get("cite") or wind.get("k4_cite") or rag.get("cite"),
                source="load_plan.wind.k4+cite",
                note="k4 accepted with cite (LIVE RAG / agent).",
            )
            return out
        except (TypeError, ValueError):
            pass

    # 2) Corpus table by structure class (QFM-recovered HIT)
    if class_key and class_key in K4_CORPUS_BY_CLASS:
        # If agent explicitly marked retrieval found:false AND force stayed on all-other path
        # but class is industrial/post-cyclone — still apply corpus (drop override).
        k4v = float(K4_CORPUS_BY_CLASS[class_key])
        out.update(
            found=True,
            k4=k4v,
            cite=K4_CLAUSE["cite"],
            source="corpus_IS875_P3_6.3.4_qfm",
            note=(
                "k4=%.2f from IS 875 Part 3:2015 cl.6.3.4 recovered corpus table "
                "(QFM 2026-09-19 HIT) for structure class=%r. "
                "Prefer LIVE RAG confirmation when available; do not invent other values."
                % (k4v, class_raw)
            ),
        )
        if out["forced_1_0_override_refused"]:
            out["note"] += " Silent force_k4_1_0 override refused for this class."
        return out

    # 3) Explicit found:false from RAG with no usable class
    if (rag.get("found") is False) or (wind.get("k4_found") is False):
        out["found"] = False
        out["note"] = (
            "k4 found:false (retrieval failed / OCR gap) and no resolvable structure class. "
            "Set k4_class to post_cyclone|industrial|all_other or fill k4_rag from LIVE "
            "exact_section 6.3.4 — do not invent."
        )
        return out

    out["note"] = (
        "k4 unresolved (found:false): provide LIVE RAG fill (exact_section 6.3.4 / fts k4) "
        "or cfg['k4_class'] in {post_cyclone, industrial, all_other}. "
        "Do not invent; do not force 1.0 when class is industrial/post-cyclone."
    )
    return out


def annex_a_basic_wind(town: str | None, *, cfg=None) -> dict:
    """Honest Annex A Vb lookup for known towns (Vizag/Delhi/Noida proxy).

    Noida → found:false with Delhi 47 proxy note — never invent a Noida row.
    Unknown towns → found:false (agent must RAG Annex A / Fig.1).
    """
    cfg = cfg or {}
    key = _norm_class(town or cfg.get("city") or cfg.get("town") or cfg.get("site_town"))
    out = {
        "found": False,
        "town": town or cfg.get("city") or cfg.get("town"),
        "town_key": key or None,
        "Vb_mps": None,
        "annex_name": None,
        "proxy": None,
        "stem": "IS_875_Part_3_2015",
        "cite": "IS 875 Part 3:2015 Annex A",
        "note": None,
    }
    if not key:
        out["note"] = "No town supplied — RAG Annex A / Fig.1 (found:false)."
        return out
    hit = ANNEX_A_KNOWN.get(key)
    if not hit:
        out["note"] = (
            "Town %r not in the small known Annex A honesty map — LIVE RAG Annex A / "
            "Fig.1 required (found:false; do not invent Vb)."
            % (town or key,)
        )
        return out
    out.update(
        found=bool(hit.get("found")),
        Vb_mps=hit.get("Vb_mps"),
        annex_name=hit.get("annex_name"),
        proxy=hit.get("proxy"),
        note=hit.get("note"),
    )
    if out["found"]:
        out["note"] = out["note"] or (
            "Annex A %s Vb=%.0f m/s (corpus / QFM)."
            % (out["annex_name"], float(out["Vb_mps"]))
        )
    elif out.get("proxy"):
        # Noida path — expose proxy clearly without claiming Annex A row
        out["Vb_mps_proxy"] = out["proxy"].get("Vb_mps")
        out["proxy_town"] = out["proxy"].get("town")
    return out


def rag_query_plan_k4_annex(cfg=None) -> list:
    """Retrieval plan hooks for k4 + Annex A (Ex11 / Ex9)."""
    cfg = cfg or {}
    town = cfg.get("city") or cfg.get("town") or ""
    return [
        {
            "stem": "IS_875_Part_3_2015",
            "query": "6.3.4",
            "purpose": "k4_cyclonic_importance",
            "type": "exact_section",
            "found": None,
            "note": "Expect 1.30 / 1.15 / 1.00 table (QFM HIT).",
        },
        {
            "stem": "IS_875_Part_3_2015",
            "query": "k4",
            "purpose": "k4_fts",
            "type": "fts",
            "found": None,
        },
        {
            "stem": "IS_875_Part_3_2015",
            "query": "importance factor for the cyclonic region",
            "purpose": "k4_phrase",
            "type": "fts",
            "found": None,
        },
        {
            "stem": "IS_875_Part_3_2015",
            "query": str(town or "Annex A basic wind speed"),
            "purpose": "annex_a_town_Vb",
            "type": "fts",
            "found": None,
            "note": "Noida → found:false + Delhi 47 proxy; Vizag → 50.",
        },
    ]
