"""India CFS P1 C5 — richer IS 811 grounding via seeded retrieval-plan templates.

Problem (IN_CFS_Ex1): agents stopped at one vague FTS hit each to IS_811 and Amd1.
This helper expands a chosen CLR (or any IS 811 label / Type) into a multi-query plan
of exact_table / exact_section calls so agents do not stop at 1 query.

Amd1 (IS_811_1987_Amd1_2011): corpus has 0 indexed sections/tables — keep found:false
honest when empty (do not upgrade a page-scan FTS hit into a property-table claim).
"""
from __future__ import annotations

from typing import Any

# IS 811:1987 Tables 1–10 (member properties). Table 11 = 90° corners (not framing).
TYPE_TO_TABLE: dict[str, str] = {
    "EA": "1",
    "UA": "2",
    "CWS": "3",
    "CWR": "4",
    "CLS": "5",
    "CLR": "6",
    "HS": "7",
    "HRH": "8",
    "HRB": "9",
    "LZ": "10",
}

TYPE_TO_NAME: dict[str, str] = {
    "EA": "Equal angles",
    "UA": "unequal angles",
    "CWS": "channels without lips — square",
    "CWR": "channels without lips — rectangular",
    "CLS": "channels with lips — square",
    "CLR": "channels with lips — rectangular",
    "HS": "hat sections",
    "HRH": "hollow rectangular — hot rolled? / HRH",
    "HRB": "hollow rectangular bars / HRB",
    "LZ": "lipped zed sections",
}

# Related Types often co-considered when picking stud/chord (lips vs no lips, square vs rect).
RELATED_TYPES: dict[str, tuple[str, ...]] = {
    "CLR": ("CLS", "CWR", "CWS"),
    "CLS": ("CLR", "CWS", "CWR"),
    "CWR": ("CWS", "CLR", "CLS"),
    "CWS": ("CWR", "CLS", "CLR"),
    "EA": ("UA",),
    "UA": ("EA",),
    "HS": ("HRH", "HRB"),
    "HRH": ("HS", "HRB"),
    "HRB": ("HS", "HRH"),
    "LZ": ("CLR", "CLS"),
}

# Clause anchors under IS 811 cl.7 (dimensions & properties) — exact_section ids.
CLAUSE_ANCHORS: tuple[tuple[str, str, str], ...] = (
    ("7", "dimensions and properties (host)"),
    ("7.1.1", "internal radius generally 1.5 t"),
    ("7.2.2", "density 7.85 g/cm3 for mass"),
    ("7.2.3", "sectional properties Tables 1–11; Ri = 1.5 t assumption"),
)

STEM_IS811 = "IS_811_1987"
STEM_AMD1 = "IS_811_1987_Amd1_2011"
COLL_IS811 = "engineering_standards_IS811"
COLL_AMD1 = "engineering_standards_IS811_Amd1"

# Minimum richness: do not stop at a single vague FTS.
MIN_EXACT_LOOKUPS = 3  # ≥1 exact_table + ≥1 exact_section + designation/Amd1


def _norm_label(name: str) -> str:
    return str(name or "").upper().replace(" ", "").replace("-", "")


def parse_is811_label(name: str) -> dict[str, Any]:
    """Parse CLR100X50X15X2-style labels (or bare Type like 'CLR').

    Returns Type, table, designation fragments; looks up catalog when available.
    """
    lab = _norm_label(name)
    out: dict[str, Any] = {
        "label": lab or None,
        "type": None,
        "table": None,
        "table_name": None,
        "designation_is": None,
        "in_catalog": False,
    }
    if not lab:
        return out

    # Bare type
    if lab in TYPE_TO_TABLE:
        out["type"] = lab
        out["table"] = TYPE_TO_TABLE[lab]
        out["table_name"] = TYPE_TO_NAME.get(lab)
        return out

    # Prefixed label
    for pref in sorted(TYPE_TO_TABLE.keys(), key=len, reverse=True):
        if lab.startswith(pref) and (len(lab) == len(pref) or lab[len(pref)].isdigit()):
            out["type"] = pref
            out["table"] = TYPE_TO_TABLE[pref]
            out["table_name"] = TYPE_TO_NAME.get(pref)
            break

    # Catalog enrichment
    try:
        import is811_sections as S
        if lab and S.looks_is811(lab):
            try:
                props = S.props(lab, unit_system="N-mm")
                out["in_catalog"] = True
                out["type"] = out["type"] or props.get("Type")
                out["table"] = out["table"] or str(props.get("Table") or "") or None
                out["designation_is"] = props.get("Designation_IS")
                out["table_name"] = props.get("Table_name") or out["table_name"]
                if out["type"] and not out["table"]:
                    out["table"] = TYPE_TO_TABLE.get(str(out["type"]).upper())
            except KeyError:
                out["in_catalog"] = False
    except Exception:
        pass

    if out["type"] and not out["table"]:
        out["table"] = TYPE_TO_TABLE.get(str(out["type"]).upper())
    return out


def _q(
    *,
    collection: str,
    stem: str,
    qtype: str,
    query: str,
    purpose: str,
    required: bool = True,
    notes: str = "",
    clause: str = "",
) -> dict[str, Any]:
    d = {
        "collection": collection,
        "doc": stem,
        "stem": stem,
        "type": qtype,
        "query": query,
        "purpose": purpose,
        "required": bool(required),
        "notes": notes or "",
    }
    if clause:
        d["clause"] = clause
    return d


def seed_is811_retrieval_plan(
    section: str,
    *,
    include_amd1: bool = True,
    include_related: bool = True,
    include_designation_fts: bool = True,
) -> list[dict[str, Any]]:
    """Build a multi-query IS 811 plan for a chosen CLR (or any Type/label).

    Agents should execute EVERY required step (exact_table + exact_section anchors),
    then log Amd1 honestly as found:false when empty.
    """
    info = parse_is811_label(section)
    typ = (info.get("type") or "").upper() or None
    table = info.get("table")
    plan: list[dict[str, Any]] = []

    if table:
        plan.append(_q(
            collection=COLL_IS811, stem=STEM_IS811,
            qtype="exact_table", query=str(table),
            purpose="is811_section_properties_table",
            notes="IS 811 Table %s (%s) — primary property table for Type %s"
                  % (table, info.get("table_name") or typ or "?", typ or "?"),
        ))
    elif typ:
        plan.append(_q(
            collection=COLL_IS811, stem=STEM_IS811,
            qtype="fts", query="%s cold formed section properties" % typ,
            purpose="is811_type_navigate",
            required=True,
            notes="Type known but table unknown — navigate then follow up with exact_table",
        ))
    else:
        plan.append(_q(
            collection=COLL_IS811, stem=STEM_IS811,
            qtype="fts", query="cold formed light gauge steel sections tables",
            purpose="is811_navigate",
            notes="No Type/label — navigate to Tables 1–10 then re-seed with chosen CLR",
        ))

    for sid, why in CLAUSE_ANCHORS:
        plan.append(_q(
            collection=COLL_IS811, stem=STEM_IS811,
            qtype="exact_section", query=sid, clause=sid,
            purpose="is811_clause_%s" % sid.replace(".", "_"),
            notes=why,
        ))

    if info.get("label") and typ and info["label"] != typ:
        desig = info.get("designation_is") or info["label"]
        if include_designation_fts:
            plan.append(_q(
                collection=COLL_IS811, stem=STEM_IS811,
                qtype="fts",
                query=str(desig),
                purpose="is811_designation_row",
                required=False,
                notes="Pin the chosen designation row inside Table %s" % (table or "?"),
            ))

    if include_related and typ:
        for rel in RELATED_TYPES.get(typ, ()):
            rt = TYPE_TO_TABLE.get(rel)
            if not rt:
                continue
            plan.append(_q(
                collection=COLL_IS811, stem=STEM_IS811,
                qtype="exact_table", query=str(rt),
                purpose="is811_related_%s" % rel.lower(),
                required=False,
                notes="Related Type %s (Table %s) — optional alternate/chord comparison" % (rel, rt),
            ))

    if include_amd1:
        # Honest absence check — corpus has 0 indexed Amd1 tables/sections.
        plan.append(_q(
            collection=COLL_AMD1, stem=STEM_AMD1,
            qtype="exact_table", query=str(table or "6"),
            purpose="is811_amd1_property_delta",
            required=True,
            notes=(
                "Amd1 property-delta check. If empty / no indexed tables: log found:false "
                "(do NOT treat a cover-page FTS hit as a property amendment)."
            ),
        ))
        plan.append(_q(
            collection=COLL_AMD1, stem=STEM_AMD1,
            qtype="exact_section", query="1",
            purpose="is811_amd1_presence",
            required=False,
            notes="Optional Amd1 presence probe; empty → found:false is honest (is811_GAPS.md).",
        ))

    return plan


def expand_thin_plan(
    existing: list | None,
    section: str,
    *,
    include_amd1: bool = True,
) -> list[dict[str, Any]]:
    """Merge an existing thin plan with the seeded template (dedupe by stem+type+query)."""
    seeded = seed_is811_retrieval_plan(section, include_amd1=include_amd1)
    seen = set()
    out: list[dict[str, Any]] = []

    def _key(d: dict) -> tuple:
        return (
            str(d.get("stem") or d.get("doc") or d.get("collection") or "").upper(),
            str(d.get("type") or "").lower(),
            str(d.get("query") or d.get("clause") or "").strip().upper(),
        )

    for src in list(existing or []) + seeded:
        if not isinstance(src, dict):
            continue
        # Normalize bare legacy hits into plan rows when possible
        row = dict(src)
        if "stem" not in row and "doc" in row:
            row["stem"] = row["doc"]
        if "doc" not in row and "stem" in row:
            row["doc"] = row["stem"]
        k = _key(row)
        if k in seen:
            continue
        seen.add(k)
        out.append(row)
    return out


def plan_richness(plan: list | None) -> dict[str, Any]:
    """Score a plan / retrieval log for C5 richness."""
    plan = plan or []
    exact_table = 0
    exact_section = 0
    amd1 = 0
    is811 = 0
    for row in plan:
        if not isinstance(row, dict):
            continue
        stem = str(row.get("stem") or row.get("doc") or row.get("collection") or "").upper()
        qtype = str(row.get("type") or "").lower()
        if "811" in stem and "AMD" not in stem.replace("AMENDMENT", "AMD"):
            is811 += 1
            if "table" in qtype:
                exact_table += 1
            if "section" in qtype or qtype == "id":
                exact_section += 1
        if "AMD1" in stem or "AMD_1" in stem or "811_1987_AMD" in stem:
            amd1 += 1
        # collection form
        coll = str(row.get("collection") or "").upper()
        if "IS811_AMD" in coll or "IS_811_AMD" in coll:
            amd1 += 1
        elif "IS811" in coll or "IS_811" in coll:
            if "AMD" not in coll:
                is811 += 1
                if "table" in qtype:
                    exact_table += 1
                if "section" in qtype or qtype == "id":
                    exact_section += 1
    exact_lookups = exact_table + exact_section
    ok = exact_lookups >= MIN_EXACT_LOOKUPS and exact_table >= 1 and exact_section >= 1
    return {
        "ok": ok,
        "is811_queries": is811,
        "exact_table": exact_table,
        "exact_section": exact_section,
        "exact_lookups": exact_lookups,
        "amd1_queries": amd1,
        "min_exact_lookups": MIN_EXACT_LOOKUPS,
        "advice": (
            None if ok else
            "C5: expand IS 811 grounding — need ≥%d exact lookups including ≥1 exact_table "
            "and ≥1 exact_section for the chosen CLR/Type (use india_is811_retrieval."
            "seed_is811_retrieval_plan). Do not stop at 1 FTS query." % MIN_EXACT_LOOKUPS
        ),
    }


def plan_is_rich_enough(plan: list | None) -> tuple[bool, str]:
    r = plan_richness(plan)
    return bool(r["ok"]), (r["advice"] or "")


def amd1_honest_result(rag_out: dict | None, *, purpose: str = "") -> dict[str, Any]:
    """Normalize an Amd1 RAG response: empty / non-property hits → found:false.

    A cover-page or 'amendment' FTS hit must NOT be treated as a property-table amendment.
    """
    out = dict(rag_out or {})
    results = out.get("results") or out.get("hits") or []
    if not isinstance(results, list):
        results = []

    # Count hits that look like real property tables/sections
    propertyish = 0
    for h in results:
        if not isinstance(h, dict):
            continue
        if h.get("found") is False:
            continue
        tid = str(h.get("table_id") or "")
        sid = str(h.get("section_id") or "")
        kind = str(h.get("kind") or "").lower()
        title = str(h.get("title") or "").lower()
        # Indexed Amd1 tables/sections are currently 0 — any real table/section id counts.
        if kind == "table" or tid:
            propertyish += 1
        elif kind in ("section", "equation") and sid and not sid.startswith("spec-page:"):
            propertyish += 1
        elif "table" in title and any(c.isdigit() for c in title):
            propertyish += 1

    n = len([h for h in results if isinstance(h, dict) and h.get("found") is not False])
    if propertyish == 0:
        out["found"] = False
        out["amd1_property_delta_found"] = False
        note = (
            "IS_811_1987_Amd1_2011: no indexed property tables/sections for this query "
            "(found:false). Do not invent Amd1 property deltas; see is811_GAPS.md. "
            "A page-scan / cover FTS hit is not a Table 1–10 amendment."
        )
        prev = str(out.get("note") or "")
        out["note"] = (prev + " | " + note).strip(" |") if prev else note
        out["results"] = []
        out["hits"] = []
        out["purpose"] = purpose or out.get("purpose") or "is811_amd1_property_delta"
    else:
        out["found"] = True
        out["amd1_property_delta_found"] = True
        out.setdefault("purpose", purpose or "is811_amd1_property_delta")
    out["n_raw_hits"] = n
    out["n_propertyish"] = propertyish
    return out


def as_tool_calls(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project plan rows into search_engineering_standards argument dicts."""
    calls = []
    for row in plan or []:
        calls.append({
            "query": row.get("query") or row.get("clause") or "",
            "type": row.get("type") or "fts",
            "doc": row.get("doc") or row.get("stem") or STEM_IS811,
            "collection": row.get("collection") or COLL_IS811,
            "purpose": row.get("purpose") or "is811_grounding",
            "clause": row.get("clause") or "",
        })
    return calls


# ---------------------------------------------------------------------------
# IS 811 Ix OCR → QFM correction path (wave2 polish2)
# Catalog OCR sometimes concatenates Ix|Iy or drops digits. Agents must correct
# Ix from LIVE RAG / the IS corpus (QFM) — never invent numbers.
# ---------------------------------------------------------------------------

IX_QFM_PURPOSE = "is811_ix_qfm_correction"


def seed_ix_qfm_correction_plan(section: str) -> list[dict[str, Any]]:
    """Retrieval-plan hooks to re-read Ix from LIVE IS 811 RAG / QFM tables.

    Execute every required step against the IS corpus (RAG_API_URL); if OCR/catalog Ix
    is noisy, apply a cited QFM value via ``ix_qfm_correction_status`` /
    ``apply_ix_from_qfm`` — do not invent Ix.
    """
    info = parse_is811_label(section)
    typ = (info.get("type") or "").upper() or None
    table = info.get("table")
    desig = info.get("designation_is") or info.get("label") or section
    plan: list[dict[str, Any]] = []

    if table:
        plan.append(_q(
            collection=COLL_IS811, stem=STEM_IS811,
            qtype="exact_table", query=str(table),
            purpose=IX_QFM_PURPOSE,
            notes=(
                "Re-read Ix (cm4) for designation %s from IS 811 Table %s via QFM/LIVE RAG. "
                "Prefer table cell over OCR-concatenated catalog Ix when they disagree."
                % (desig, table)
            ),
        ))
    plan.append(_q(
        collection=COLL_IS811, stem=STEM_IS811,
        qtype="fts",
        query="%s Ix moment of inertia" % desig,
        purpose=IX_QFM_PURPOSE,
        required=bool(not table),
        notes="Pin the designation row and extract Ix (cm4) from the LIVE table extract.",
    ))
    if typ:
        plan.append(_q(
            collection=COLL_IS811, stem=STEM_IS811,
            qtype="fts",
            query="Table %s %s sectional properties" % (table or "?", typ),
            purpose="is811_ix_table_navigate",
            required=False,
            notes="Navigate property columns (A, Ix, Iy) for Type %s" % typ,
        ))
    # Always include the standard table/clause richness anchors for C5.
    plan = expand_thin_plan(plan, section, include_amd1=False)
    return plan


def catalog_ix_snapshot(section: str) -> dict[str, Any]:
    """Read catalog Ix (if present) without inventing. found:false when missing."""
    info = parse_is811_label(section)
    out: dict[str, Any] = {
        "section": section,
        "label": info.get("label"),
        "in_catalog": bool(info.get("in_catalog")),
        "found": False,
        "Ix_si_cm4": None,
        "source": "is811_shapes.csv",
    }
    if not info.get("in_catalog"):
        out["note"] = (
            "Section not in is811_shapes.csv (found:false). Retrieve Ix via "
            "seed_ix_qfm_correction_plan + LIVE RAG; do not invent."
        )
        return out
    try:
        import is811_sections as S
        props = S.props(info["label"] or section, unit_system="N-mm")
        ix = props.get("Ix_si_cm4")
        if ix is None and props.get("Ix") is not None:
            # Already converted path — report mm4 only
            out["Ix_mm4"] = props.get("Ix")
            out["found"] = True
            out["note"] = "Catalog has Ix (mm4); Ix_si_cm4 column absent — verify via QFM."
            return out
        if ix is None:
            out["note"] = "Catalog row present but Ix_si_cm4 missing (found:false) — use QFM."
            return out
        out["found"] = True
        out["Ix_si_cm4"] = float(ix)
        out["Ix_mm4"] = props.get("Ix")
        out["type"] = props.get("Type")
        out["table"] = props.get("Table")
        out["note"] = (
            "Catalog OCR Ix snapshot only. If LIVE QFM disagrees, prefer QFM with cite "
            "(apply_ix_from_qfm); do not average or invent."
        )
        return out
    except Exception as ex:
        out["note"] = "catalog Ix read failed: %s (found:false)" % ex
        return out


def ix_qfm_correction_status(
    section: str,
    *,
    qfm_ix_si_cm4: float | None = None,
    cite: str | None = None,
    rag_hit: dict | None = None,
) -> dict[str, Any]:
    """Status helper: compare catalog OCR Ix vs optional LIVE QFM value.

    Does **not** invent numbers. Without a cited QFM Ix, returns a correction
    plan + catalog snapshot and ``correction_applied=false``.
    """
    snap = catalog_ix_snapshot(section)
    plan = seed_ix_qfm_correction_plan(section)
    out: dict[str, Any] = {
        "purpose": IX_QFM_PURPOSE,
        "section": section,
        "catalog": snap,
        "retrieval_plan": plan,
        "retrieval_plan_tool_calls": as_tool_calls(plan),
        "correction_applied": False,
        "found": False,
    }
    # Optional rag_hit normalization (empty → found:false)
    if rag_hit is not None:
        hits = rag_hit.get("results") or rag_hit.get("hits") or []
        if not hits or rag_hit.get("found") is False:
            out["rag"] = dict(found=False, note="LIVE RAG/QFM returned no Ix row (found:false).")
        else:
            out["rag"] = dict(found=True, n_hits=len(hits), cite=rag_hit.get("cite") or cite)

    if qfm_ix_si_cm4 is None:
        out["note"] = (
            "No QFM Ix supplied yet. Run seed_ix_qfm_correction_plan against "
            "the IS corpus (RAG_API_URL); when a cited Ix (cm4) is retrieved, call "
            "apply_ix_from_qfm / ix_qfm_correction_status with qfm_ix_si_cm4 + cite. "
            "Do not invent Ix or patch OCR by guesswork."
        )
        return out

    if not cite:
        out["note"] = (
            "qfm_ix_si_cm4 provided without cite (found:false). Refuse silent correction; "
            "attach LIVE RAG/QFM clause or table cell cite."
        )
        out["qfm_ix_si_cm4"] = float(qfm_ix_si_cm4)
        return out

    cat_ix = snap.get("Ix_si_cm4")
    out.update(
        found=True,
        correction_applied=True,
        qfm_ix_si_cm4=float(qfm_ix_si_cm4),
        cite=cite,
        catalog_ix_si_cm4=cat_ix,
        delta_cm4=(None if cat_ix is None else float(qfm_ix_si_cm4) - float(cat_ix)),
        note=(
            "Ix corrected from LIVE RAG/QFM cite=%r. Prefer this over OCR catalog when "
            "they disagree. Provenance required for COMPLETE."
            % cite
        ),
    )
    return out


def apply_ix_from_qfm(
    section: str,
    ix_si_cm4: float,
    *,
    cite: str,
    source: str = "LIVE_RAG_QFM",
) -> dict[str, Any]:
    """Record a cited QFM Ix correction (does not mutate the CSV).

    Returns a props overlay agents can merge into cfg / package notes.
    Refuses without cite; never invents Ix.
    """
    if cite is None or str(cite).strip() == "":
        return dict(
            found=False,
            section=section,
            note="apply_ix_from_qfm refused: cite required (found:false). Do not invent Ix.",
        )
    try:
        ix = float(ix_si_cm4)
    except (TypeError, ValueError):
        return dict(
            found=False,
            section=section,
            note="apply_ix_from_qfm refused: ix_si_cm4 not numeric (found:false).",
        )
    if ix <= 0:
        return dict(
            found=False,
            section=section,
            note="apply_ix_from_qfm refused: Ix must be positive (found:false).",
        )
    status = ix_qfm_correction_status(section, qfm_ix_si_cm4=ix, cite=cite)
    mm4 = ix * 10000.0  # cm4 → mm4
    status["overlay"] = dict(
        label=str(section).upper().replace(" ", ""),
        Ix_si_cm4=ix,
        Ix=mm4,
        _Ix_source=source,
        _Ix_cite=cite,
        _Ix_ocr_corrected=True,
    )
    return status
