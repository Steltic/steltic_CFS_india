"""IS 1893 two-stage / podium / transfer stubs (Ex9 polish).

Honest policy:
- Prefer cfg hooks + status objects agents fill from LIVE RAG.
- Default: found:false for IS 1893 two-stage / podium / transfer-slab recipe.
- Refuse silent USA ASCE 7-22 §12.2.3.2 as India law (twin note only).
- Do NOT invent amplification factors, stiffness ratios, or period checks.
"""
from __future__ import annotations

from typing import Any

ASCE_REFUSE = (
    "Refuse silent USA ASCE 7-22 §12.2.3.2 two-stage ELF (podium ≥10× stiffness, "
    "T_combined ≤ 1.1 T_upper, reaction amplification (R_up/ρ_up)/(R_low/ρ_low)) as "
    "India law. Twin scaffolding may exist in cfs_engine.two_stage_* for USA paths only."
)

DEFAULT_TWO_STAGE = {
    "found": False,
    "stem": "IS_1893_Part_1_2016",
    "topic": "two_stage_analysis",
    "query": "two-stage analysis podium soft storey transfer upper portion",
    "note": (
        "IS 1893 two-stage / podium analysis recipe: found:false in shipped corpus. "
        "Do not invent ASCE 12.2.3.2 eligibility or reaction amplification. "
        "Agent: RAG-query LIVE, or design upper CFS with base at podium top and hand "
        "unamplified reactions to the podium/RC engineer with EOR disclosure."
    ),
    "asce_12_2_3_2_refused": True,
    "asce_refuse_note": ASCE_REFUSE,
}

DEFAULT_TRANSFER = {
    "found": False,
    "stem": "IS_1893_Part_1_2016",
    "topic": "transfer_podium",
    "query": "transfer girder floating column podium discontinuity vertical elements",
    "note": (
        "IS 1893 transfer / floating-column / in-plane discontinuity detailing for "
        "CFS-over-RC podium: found:false as an automated recipe. Flag Table 6 "
        "irregularities; podium engineer scope beyond CFS package."
    ),
    "asce_12_2_3_2_refused": True,
}


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


def _podium_hint(cfg: dict) -> bool:
    if cfg.get("podium") or cfg.get("two_stage") or cfg.get("podium_two_stage"):
        return True
    blob = " ".join(
        str(cfg.get(k) or "")
        for k in ("system", "arch", "feature", "notes", "structure_kind", "plan_desc")
    ).lower()
    return any(tok in blob for tok in (
        "podium", "two-stage", "two_stage", "5over2", "4over1", "transfer",
        "over concrete", "over rc",
    ))


def _merge_agent_fill(default: dict, filled: Any) -> dict[str, Any]:
    out = dict(default)
    if not isinstance(filled, dict):
        return out
    out.update(filled)
    # Never allow a fill that claims ASCE as India authority without explicit flag
    if out.get("found") and not (
        out.get("cite") or out.get("clause") or out.get("text") or out.get("rag_hit")
    ):
        out["found"] = False
        out["note"] = (
            (out.get("note") or "")
            + " Agent fill missing cite/clause/text — reverted to found:false."
        ).strip()
    out["asce_12_2_3_2_refused"] = True
    out.setdefault("asce_refuse_note", ASCE_REFUSE)
    return out


def two_stage_analysis_status(cfg: dict | None = None) -> dict[str, Any]:
    """Status for IS 1893 two-stage analysis (podium upper/lower)."""
    cfg = cfg or {}
    if not _india(cfg):
        return dict(
            found=False,
            jurisdiction=cfg.get("jurisdiction"),
            note="two_stage_analysis_status is an India helper.",
        )
    filled = (
        cfg.get("is1893_two_stage")
        or cfg.get("two_stage_clause")
        or cfg.get("podium_two_stage_clause")
    )
    out = _merge_agent_fill(DEFAULT_TWO_STAGE, filled)
    out["jurisdiction"] = "india"
    out["podium_detected"] = _podium_hint(cfg)
    out["cfg_hooks"] = {
        "is1893_two_stage": "dict with found/cite/text/eligibility from LIVE RAG",
        "podium": "bool — upper CFS base at podium top",
        "podium_reactions_unamplified": "bool — prefer True when clause found:false",
        "eor_podium_disclosure": "str — handoff note to RC/podium engineer",
    }
    if out.get("found"):
        out["note"] = out.get("note") or (
            "IS 1893 two-stage clause agent-filled from LIVE RAG — verify cite before use."
        )
        return out

    # Recommended practice when found:false
    out["recommended_practice"] = {
        "model_upper_cfs_base_at_podium_top": True,
        "amplify_reactions_per_asce_12_2_3_2": False,
        "report_unamplified_reactions_to_podium_engineer": True,
        "require_eor_disclosure": True,
        "note": (
            "With IS two-stage found:false: analyze upper CFS ELF/flexible diaphragm with "
            "base at podium top; do NOT invent ASCE amplification; disclose reactions + "
            "irregularity flags to podium EOR."
        ),
    }
    # Honor explicit cfg preference
    if cfg.get("podium_reactions_unamplified") is False and not out.get("found"):
        out["warn"] = (
            "cfg['podium_reactions_unamplified']=False but IS two-stage found:false — "
            "refusing silent ASCE amplification. Set eor_documented cite if project "
            "adopts a specific amplification basis."
        )
    return out


def transfer_podium_status(cfg: dict | None = None) -> dict[str, Any]:
    """Status for transfer / podium discontinuity (found:false stub)."""
    cfg = cfg or {}
    if not _india(cfg):
        return dict(found=False, note="India helper only.")
    filled = cfg.get("is1893_transfer") or cfg.get("transfer_clause")
    out = _merge_agent_fill(DEFAULT_TRANSFER, filled)
    out["jurisdiction"] = "india"
    out["podium_detected"] = _podium_hint(cfg)
    out["cfg_hooks"] = {
        "is1893_transfer": "dict found/cite/text from LIVE RAG",
        "transfer_level_storey": "int — storey index at podium top / transfer",
        "eor_transfer_disclosure": "str",
    }
    return out


def podium_package_status(cfg: dict | None = None) -> dict[str, Any]:
    """Combined Ex9 stub: two-stage + transfer + ASCE refuse."""
    cfg = cfg or {}
    ts = two_stage_analysis_status(cfg)
    tr = transfer_podium_status(cfg)
    detected = _podium_hint(cfg)
    any_found = bool(ts.get("found") or tr.get("found"))
    return {
        "found": any_found and bool(ts.get("found")),  # two-stage is the primary gate
        "podium_detected": detected,
        "jurisdiction": "india" if _india(cfg) else cfg.get("jurisdiction"),
        "two_stage": ts,
        "transfer": tr,
        "asce_12_2_3_2_refused": True,
        "asce_refuse_note": ASCE_REFUSE,
        "rag_query_plan": rag_query_plan_podium(cfg),
        "note": (
            "Podium/two-stage package: IS clauses found."
            if any_found else
            ("Podium/two-stage IS recipe found:false — use cfg hooks + EOR disclosure; "
             "refuse silent ASCE 12.2.3.2. " + ("" if detected else
             "(No podium hint in cfg — set podium=True when applicable.)"))
        ),
    }


def rag_query_plan_podium(cfg: dict | None = None) -> list[dict[str, Any]]:
    """LIVE RAG hooks for agents (Ex9)."""
    return [
        {
            "stem": "IS_1893_Part_1_2016",
            "query": "two-stage analysis buildings with abrupt change in lateral stiffness podium",
            "purpose": "two_stage_analysis",
            "type": "exact_clause",
            "found": None,
            "note": "Fill cfg['is1893_two_stage'] on hit; else leave found:false.",
        },
        {
            "stem": "IS_1893_Part_1_2016",
            "query": "Table 6 soft storey weak storey floating or stub columns transfer",
            "purpose": "vertical_irregularity_transfer",
            "type": "exact_table",
            "found": None,
        },
        {
            "stem": "IS_1893_Part_1_2016",
            "query": "in-plane discontinuity in vertical elements resisting lateral force",
            "purpose": "in_plane_discontinuity",
            "type": "keyword",
            "found": None,
        },
        {
            "stem": "IS_1893_Part_1_2016",
            "query": "dynamic analysis soft storey podium upper lower portion",
            "purpose": "dynamic_vs_two_stage",
            "type": "keyword",
            "found": None,
        },
    ]


def refuse_asce_two_stage_as_india_law(cfg: dict | None = None) -> dict[str, Any]:
    """Explicit gate: never treat cfs_engine.two_stage_* results as IS authority."""
    cfg = cfg or {}
    return {
        "found": False,
        "allowed_as_india_law": False,
        "asce_12_2_3_2_refused": True,
        "note": ASCE_REFUSE,
        "usa_engine_hooks_exist": True,
        "usa_hooks": ["cfs_engine.two_stage_check", "cfs_engine.two_stage_reactions"],
        "india_path": "india_podium_two_stage.podium_package_status",
        "podium_detected": _podium_hint(cfg),
    }
