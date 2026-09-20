"""SBMF bolt slip / bearing capacity path (Ex10 polish Wave B).

Honest policy:
- IS 801 does not ship a verified SBMF (special bolted moment frame) bolt
  slip / bearing energy-dissipation recipe in the India corpus → found:false
  by default. Do not invent slip/bearing capacities or drift fuse rules.
- AISI S400-20 E4 (SBMF bolt-bearing energy dissipation) is a USA twin note
  only — never silent India law.
- Capacity path: manufacturer / test / eor_documented with cite, OR leave
  found:false with clear disclosure for EXAMPLE packages.
"""
from __future__ import annotations

from typing import Any

S400_E4_REFUSE = (
    "AISI S400-20 E4 (CFS special bolted moment frame — bolt-bearing energy "
    "dissipation at design drift, capacity-protected columns/connections) is a "
    "USA twin note only. Do NOT apply S400 E4 as India design authority under "
    "IS 801. Prefer IS 801 cl.7 connections RAG + manufacturer/EOR bolt "
    "slip/bearing capacities with cite, or leave found:false."
)

DEFAULT_BOLT_RULES = {
    "found": False,
    "stem": "IS_801_1975",
    "topic": "sbmf_bolt_slip_bearing",
    "query": (
        "bolted moment frame beam-column connection bolt slip bearing "
        "energy dissipation CFS cold formed"
    ),
    "note": (
        "IS 801 SBMF bolt slip/bearing recipe: found:false in shipped corpus. "
        "Do not invent slip loads, bearing capacities, or S400 E4 fuse rules as "
        "India law. Supply manufacturer/test/eor_documented capacity + cite via "
        "cfg['sbmf_bolt'] / connection_capacities, or keep EXAMPLE disclosure."
    ),
    "s400_E4_refused_as_india_law": True,
    "s400_refuse_note": S400_E4_REFUSE,
}

EOR_OK = frozenset({
    "manufacturer", "test", "tested", "lab", "eor_documented", "eor",
    "eor_explicit", "documented", "explicit", "project_eor", "catalogue",
    "catalog", "is801", "is_801", "is801_rag",
})

REFUSED_SOURCES = frozenset({
    "aisi", "aisi_s400", "s400", "s400_e4", "e4", "usa_default", "s100", "s240",
})


def _norm(s: Any) -> str:
    return str(s or "").strip().lower().replace(" ", "_").replace("-", "_")


def _india(cfg: dict | None) -> bool:
    cfg = cfg or {}
    j = str(cfg.get("jurisdiction") or "").lower()
    if j in ("india", "in", "is", "is_bis", "bis"):
        return True
    plan = cfg.get("load_plan")
    if isinstance(plan, dict) and str(plan.get("jurisdiction") or "").lower() in (
        "india", "in", "is", "is_bis", "bis",
    ):
        return True
    return not j or j in ("", "default")


def _sbmf_hint(cfg: dict) -> bool:
    if cfg.get("sbmf") or cfg.get("special_bolted_moment_frame"):
        return True
    sys = _norm(cfg.get("system") or cfg.get("structure_kind") or "")
    if sys in ("sbmf", "special_bolted_moment_frame", "bolted_moment_frame"):
        return True
    blob = " ".join(
        str(cfg.get(k) or "")
        for k in ("system", "arch", "feature", "notes", "structure_kind")
    ).lower()
    return any(tok in blob for tok in (
        "sbmf", "bolted moment", "special bolted", "bolt slip", "bolt bearing",
    ))


def _collect_bolt_fill(cfg: dict) -> dict | None:
    """Pull agent/EOR bolt slip/bearing fill from common cfg hooks."""
    for key in (
        "sbmf_bolt", "sbmf_bolt_slip", "sbmf_bolt_bearing",
        "bolt_slip_bearing", "is801_sbmf_bolt",
    ):
        blob = cfg.get(key)
        if isinstance(blob, dict):
            return dict(blob)
    # connection_capacities / eor_connections keyed slots
    for block_key in ("connection_capacities", "eor_connections", "india_connections"):
        block = cfg.get(block_key)
        if not isinstance(block, dict):
            continue
        for slot in ("sbmf-bolt", "sbmf_bolt", "bolt-slip", "bolt-bearing",
                     "conn-sbmf", "beam-column-bolt"):
            if slot in block and isinstance(block[slot], dict):
                return dict(block[slot])
    return None


def refuse_s400_e4_as_india_law(cfg: dict | None = None) -> dict[str, Any]:
    """Explicit gate: never treat S400 E4 as IS 801 authority."""
    cfg = cfg or {}
    return {
        "found": False,
        "allowed_as_india_law": False,
        "s400_E4_refused_as_india_law": True,
        "note": S400_E4_REFUSE,
        "sbmf_detected": _sbmf_hint(cfg),
        "india_path": "india_sbmf_bolt.sbmf_bolt_slip_bearing_status",
    }


def sbmf_bolt_slip_bearing_status(cfg: dict | None = None) -> dict[str, Any]:
    """Status for SBMF bolt slip/bearing capacity under India jurisdiction.

    Returns found:true only when manufacturer/test/eor_documented capacity is
    supplied with a cite — never by silently copying S400 E4.
    """
    cfg = cfg or {}
    if not _india(cfg):
        return dict(
            found=False,
            jurisdiction=cfg.get("jurisdiction"),
            note="sbmf_bolt_slip_bearing_status is an India helper.",
        )

    out: dict[str, Any] = dict(DEFAULT_BOLT_RULES)
    out["jurisdiction"] = "india"
    out["sbmf_detected"] = _sbmf_hint(cfg)
    out["cfg_hooks"] = {
        "sbmf_bolt": (
            "dict: found/cite/source/capacity_slip|capacity_bearing|"
            "Vn_slip|Vn_bearing/limit_state from manufacturer or EOR"
        ),
        "connection_capacities['sbmf-bolt']": "same shape as sbmf_bolt",
        "is801_sbmf_bolt": "LIVE RAG fill of IS 801 bolt clause (found/cite/text)",
    }
    out["rag_query_plan"] = rag_query_plan_sbmf_bolt(cfg)

    # Agent RAG fill of an IS 801 clause (rare — prefer honesty)
    clause = cfg.get("is801_sbmf_bolt") or cfg.get("sbmf_bolt_clause")
    if isinstance(clause, dict) and clause.get("found") is True and (
        clause.get("cite") or clause.get("clause") or clause.get("text")
    ):
        out.update(clause)
        out["found"] = True
        out["source"] = clause.get("source") or "cfg_agent_rag"
        out["s400_E4_refused_as_india_law"] = True
        out["note"] = (
            clause.get("note")
            or "IS 801 SBMF bolt clause agent-filled from LIVE RAG — verify cite before use."
        )
        return out

    fill = _collect_bolt_fill(cfg)
    if fill:
        source = _norm(fill.get("source") or fill.get("capacity_source"))
        cite = (fill.get("cite") or fill.get("cited") or fill.get("R_cite") or "").strip()
        # Refuse AISI / S400 E4 labelled sources even if present
        if source in REFUSED_SOURCES or any(
            tok in source for tok in ("s400", "aisi", "e4")
        ):
            out.update(
                found=False,
                source=source,
                cited=cite or None,
                note=S400_E4_REFUSE + " (cfg source=%r refused)." % source,
                capacity=fill.get("capacity") or fill.get("capacity_bearing")
                or fill.get("capacity_slip"),
            )
            return out

        cap = (
            fill.get("capacity")
            or fill.get("capacity_bearing")
            or fill.get("capacity_slip")
            or fill.get("Vn_bearing")
            or fill.get("Vn_slip")
            or fill.get("Rn")
        )
        limit = fill.get("limit_state") or fill.get("limit") or fill.get("governing")

        if source in EOR_OK or (cite and not source):
            if not cite:
                out.update(
                    found=False,
                    source=source or None,
                    capacity=cap,
                    note=(
                        "SBMF bolt capacity present without cite (found:false). "
                        "Attach manufacturer/EOR/IS 801 cl.7 cite before COMPLETE."
                    ),
                )
                return out
            out.update(
                found=True,
                source=source or "eor_documented",
                cited=cite,
                capacity=cap,
                capacity_slip=fill.get("capacity_slip") or fill.get("Vn_slip"),
                capacity_bearing=fill.get("capacity_bearing") or fill.get("Vn_bearing"),
                limit_state=limit,
                DC=fill.get("DC"),
                note=fill.get("note") or (
                    "SBMF bolt slip/bearing from %s (cite=%s). "
                    "IS 801 SBMF recipe remains found:false as automated law; "
                    "S400 E4 refused as India authority."
                    % (source or "eor_documented", cite)
                ),
                is801_recipe_found=False,
                s400_E4_refused_as_india_law=True,
            )
            return out

        out.update(
            found=False,
            source=source or None,
            cited=cite or None,
            capacity=cap,
            note=(
                "SBMF bolt fill source=%r not allowlisted and/or missing cite "
                "(found:false). Use source=manufacturer|test|eor_documented + cite; "
                "never silent S400 E4."
                % (source or "",)
            ),
        )
        return out

    # No fill — honest stub
    if out["sbmf_detected"]:
        out["note"] = (
            "SBMF detected; IS 801 bolt slip/bearing recipe found:false. "
            "Set cfg['sbmf_bolt'] with manufacturer/EOR capacity + cite, or leave "
            "EXAMPLE disclosure. " + S400_E4_REFUSE
        )
    else:
        out["note"] = (
            DEFAULT_BOLT_RULES["note"]
            + " (No SBMF hint in cfg — set system='sbmf' when applicable.)"
        )
    out["recommended_practice"] = {
        "use_s400_e4_as_india_law": False,
        "require_manufacturer_or_eor_cite": True,
        "limit_states": ["bolt_slip", "bolt_bearing", "member_at_connection"],
        "note": (
            "Disclose bolt slip vs bearing governing limit state from manufacturer "
            "data or IS 801 cl.7 RAG; keep S400 E4 as twin scaffolding only."
        ),
    }
    return out


def rag_query_plan_sbmf_bolt(cfg: dict | None = None) -> list[dict[str, Any]]:
    """LIVE RAG hooks for agents (Ex10)."""
    return [
        {
            "stem": "IS_801_1975",
            "query": "7",
            "purpose": "is801_cl7_connections",
            "type": "exact_section",
            "found": None,
            "note": "Bolt/connection clauses — fill sbmf_bolt on hit; else found:false.",
        },
        {
            "stem": "IS_801_1975",
            "query": "bolted connections bearing slip moment frame",
            "purpose": "bolt_slip_bearing",
            "type": "fts",
            "found": None,
        },
        {
            "stem": "IS_801_1975",
            "query": "beam column connection cold formed bolted",
            "purpose": "beam_column_bolted",
            "type": "fts",
            "found": None,
        },
        {
            "stem": "IS_4000_1992",
            "query": "high strength bolt slip resistant bearing",
            "purpose": "hsfg_twin_note",
            "type": "fts",
            "found": None,
            "note": (
                "IS 4000 may inform hot-rolled HSFG practice — do not silently "
                "rebrand as CFS SBMF S400 E4; disclose scope."
            ),
        },
    ]
