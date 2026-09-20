"""IS 801 perforated / Type II wall rules stub (Ex13 polish).

Honest policy:
- IS 801 does not ship a verified Type II / perforated-wall adjustment recipe in
  the India corpus → found:false by default (do not invent Ca or capacity).
- Allow practice / EOR / manufacturer disclosure of an adjustment factor without
  treating it as IS 801 tabulated law.
- AISI S400 E1 Type II twin is scaffolding only — never India authority.
"""
from __future__ import annotations

from typing import Any

S400_REFUSE = (
    "AISI S400-20 E1 Type II (perforated) adjustment factor is a USA twin note only. "
    "Do NOT cite S400 as India design authority for perforated walls."
)

DEFAULT_RULES = {
    "found": False,
    "stem": "IS_801_1975",
    "topic": "perforated_type_II_walls",
    "query": "perforated shear wall Type II openings adjustment factor full-height sheathing",
    "note": (
        "IS 801 perforated / Type II wall rules: found:false in shipped corpus "
        "(no verified Ca / adjustment-factor table for perforated CFS walls). "
        "Do not invent capacity. Disclose manufacturer/test Ca or EOR practice "
        "with wall_vn_source in {manufacturer,test,eor_documented} + cite; "
        "keep IS 801 perforated found:false in the status object."
    ),
    "s400_type_II_refused_as_india_law": True,
    "s400_refuse_note": S400_REFUSE,
}


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


def _perforated_hint(cfg: dict) -> bool:
    if cfg.get("type_II") or cfg.get("type_ii") or cfg.get("perforated") or cfg.get("perforated_walls"):
        return True
    blob = " ".join(
        str(cfg.get(k) or "")
        for k in ("system", "arch", "feature", "notes", "wall_type", "sheathing")
    ).lower()
    return any(tok in blob for tok in (
        "type ii", "type_ii", "typeii", "perforated", "perforation",
    ))


# Accepted practice disclosure sources (capacity still not IS 801 law)
PRACTICE_OK = frozenset({
    "manufacturer", "test", "tested", "lab", "eor_documented", "eor",
    "documented", "practice", "catalogue", "catalog",
})


def perforated_wall_rules_status(cfg: dict | None = None) -> dict[str, Any]:
    """IS 801 perforated/Type II rules stub + optional practice disclosure."""
    cfg = cfg or {}
    if not _india(cfg):
        return dict(
            found=False,
            jurisdiction=cfg.get("jurisdiction"),
            note="perforated_wall_rules_status is an India helper.",
        )

    filled = (
        cfg.get("is801_perforated_rules")
        or cfg.get("perforated_wall_rules")
        or cfg.get("type_II_rules")
    )
    out = dict(DEFAULT_RULES)
    out["jurisdiction"] = "india"
    out["perforated_detected"] = _perforated_hint(cfg)
    out["cfg_hooks"] = {
        "is801_perforated_rules": "dict found/cite/text from LIVE RAG (rare)",
        "perforated_Ca": "float — practice/EOR/manufacturer adjustment (not IS law)",
        "perforated_Ca_source": "manufacturer|test|eor_documented|practice",
        "perforated_Ca_cite": "str required when Ca disclosed",
        "type_II_ends_only_holddowns": "bool — ends HD + distributed track (practice)",
        "type_II_distributed_track": "bool",
    }
    out["s400_type_II_refused_as_india_law"] = True
    out["s400_refuse_note"] = S400_REFUSE

    if isinstance(filled, dict) and filled.get("found") is True and (
        filled.get("cite") or filled.get("clause") or filled.get("text")
    ):
        out.update(filled)
        out["found"] = True
        out["source"] = "cfg_agent_rag"
        out["note"] = out.get("note") or (
            "IS 801 perforated rules agent-filled from LIVE RAG — verify cite."
        )
    elif isinstance(filled, dict) and filled.get("found") is False:
        out.update({k: v for k, v in filled.items() if k != "found"})
        out["found"] = False

    # Practice / EOR disclosure of Ca (does NOT flip IS rules to found:true)
    nested = cfg.get("perforated") if isinstance(cfg.get("perforated"), dict) else {}
    Ca = cfg.get("perforated_Ca")
    if Ca is None:
        Ca = nested.get("Ca") or nested.get("adjustment_factor")
    Ca_src_raw = (
        cfg.get("perforated_Ca_source")
        or nested.get("source")
        or cfg.get("wall_vn_source")
    )
    Ca_src = _norm(Ca_src_raw)
    Ca_cite = str(
        cfg.get("perforated_Ca_cite")
        or nested.get("cite")
        or cfg.get("wall_vn_cite")
        or ""
    ).strip()

    practice: dict[str, Any] = {
        "Ca_disclosed": Ca is not None and Ca != "",
        "Ca": Ca,
        "source": Ca_src or None,
        "cite": Ca_cite or None,
        "accepted": False,
        "is_is801_law": False,
        "note": None,
    }
    if practice["Ca_disclosed"]:
        if Ca_src in PRACTICE_OK and Ca_cite:
            practice["accepted"] = True
            practice["note"] = (
                "Practice/EOR/manufacturer Ca disclosed with cite — usable for EXAMPLE/"
                "project envelopes. IS 801 perforated rules remain found:%s (not invented "
                "as IS tabulated law). S400 Type II refused as India authority."
                % ("true" if out.get("found") else "false")
            )
        else:
            practice["note"] = (
                "perforated_Ca present but source/cite incomplete. Use "
                "perforated_Ca_source in %s + perforated_Ca_cite. "
                "Do not invent IS 801 Ca."
                % sorted(PRACTICE_OK)
            )
    else:
        practice["note"] = (
            "No practice Ca disclosed. IS 801 perforated found:false — agent must "
            "obtain manufacturer/test/EOR Ca or leave wall capacity found:false."
        )

    out["practice_disclosure"] = practice
    out["detailing_practice_hooks"] = {
        "ends_only_holddowns": cfg.get("type_II_ends_only_holddowns"),
        "distributed_track": cfg.get("type_II_distributed_track"),
        "note": (
            "When perforated: prefer END hold-downs + distributed track anchorage "
            "(hold-downs at every pier silently reverts to segmented Type I behaviour). "
            "This is practice guidance, not an invented IS 801 clause."
        ),
    }
    return out


def rag_query_plan_perforated(cfg: dict | None = None) -> list[dict[str, Any]]:
    return [
        {
            "stem": "IS_801_1975",
            "query": "shear wall openings perforated sheathing diaphragm openings reduction",
            "purpose": "perforated_wall_rules",
            "type": "keyword",
            "found": None,
            "note": "Fill cfg['is801_perforated_rules'] on hit; else found:false + practice Ca.",
        },
        {
            "stem": "IS_801_1975",
            "query": "clause 9 light gauge steel diaphragms shear walls",
            "purpose": "diaphragm_shearwall_scope",
            "type": "exact_clause",
            "found": None,
        },
        {
            "stem": "IS_811_1987",
            "query": "wall stud perforated section properties",
            "purpose": "not_type_II_rules",
            "type": "keyword",
            "found": None,
            "note": "Section properties ≠ Type II shearwall Ca — do not conflate.",
        },
    ]
