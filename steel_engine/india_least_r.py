"""Dual / mixed SFRS least-R selection for India CFS (Ex10 polish).

Honest policy:
- When cfg declares dual/mixed SFRS or multiple R values, select the governing
  (least) R with a clear status object agents can fill from LIVE RAG.
- Do NOT invent an IS 1893 "dual-system least-R" clause text.
- If the IS 1893 dual least-R clause is not in the corpus / not agent-filled,
  emit found:false and require an eor_documented path for the governing R.
- ASCE 7 §12.2.3 / 12.2.3.1 analogues are twin notes only — never India law.
"""
from __future__ import annotations

from typing import Any

# Corpus default: no verified IS 1893 dual-system least-R clause in shipped RAG.
# Agents may flip this via cfg['least_R_clause'] = {found:true, cite, text, ...}
# after LIVE RAG — never invent clause numbers here.
DEFAULT_LEAST_R_CLAUSE = {
    "found": False,
    "stem": "IS_1893_Part_1_2016",
    "query": "dual system least R mixed SFRS response reduction",
    "asce_twin_note": (
        "ASCE 7-22 §12.2.3 / 12.2.3.1 least-R / dual-system rules are USA twin notes only; "
        "do NOT apply them as India law."
    ),
    "note": (
        "IS 1893 dual-system / least-R clause for mixed CFS SFRS: found:false in shipped "
        "corpus. Fill cfg['least_R_clause'] from LIVE RAG (found+cite+text) or document "
        "governing R via eor_documented (R_source/R_cite). Do not invent clause text."
    ),
}

EOR_OK = frozenset({
    "eor_documented", "eor", "eor_explicit", "documented", "explicit",
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
    # steltic_CFS_india defaults India when unset
    return not j or j in ("", "default")


def _collect_R_entries(cfg: dict) -> list[dict[str, Any]]:
    """Gather named R values from common dual/mixed cfg hooks."""
    entries: list[dict[str, Any]] = []
    seis = cfg.get("seis") if isinstance(cfg.get("seis"), dict) else {}

    def add(name: str, R: Any, *, source: Any = None, cite: Any = None, system: Any = None):
        if R is None or R == "":
            return
        try:
            Rf = float(R)
        except (TypeError, ValueError):
            return
        entries.append({
            "name": name,
            "R": Rf,
            "source": source,
            "cite": cite,
            "system": system,
        })

    # Explicit multi-R maps
    for key in ("R_by_system", "R_by_direction", "sfrs_R", "dual_R"):
        blob = cfg.get(key) or seis.get(key)
        if isinstance(blob, dict):
            for k, v in blob.items():
                if isinstance(v, dict):
                    add(str(k), v.get("R", v.get("value")),
                        source=v.get("source") or v.get("R_source"),
                        cite=v.get("cite") or v.get("R_cite"),
                        system=v.get("system") or k)
                else:
                    add(str(k), v, system=k)

    # Directional R
    for key, label in (("R_x", "X"), ("R_y", "Y"), ("Rx", "X"), ("Ry", "Y")):
        if key in cfg or key in seis:
            add(label, cfg.get(key, seis.get(key)),
                source=cfg.get("%s_source" % key) or seis.get("%s_source" % key),
                cite=cfg.get("%s_cite" % key) or seis.get("%s_cite" % key))

    # systems[] list of {name, R, ...}
    systems = cfg.get("systems") or cfg.get("sfrs") or cfg.get("dual_systems") or []
    if isinstance(systems, dict):
        systems = [{"name": k, **(v if isinstance(v, dict) else {"R": v})}
                   for k, v in systems.items()]
    if isinstance(systems, list):
        for i, s in enumerate(systems):
            if not isinstance(s, dict):
                continue
            add(str(s.get("name") or s.get("system") or "system_%d" % i),
                s.get("R"),
                source=s.get("R_source") or s.get("source"),
                cite=s.get("R_cite") or s.get("cite"),
                system=s.get("system") or s.get("name"))

    # Single declared R (still useful when dual flag is set)
    R0 = cfg.get("R")
    if R0 is None:
        R0 = seis.get("R")
    if R0 is not None and not entries:
        add("primary", R0,
            source=cfg.get("R_source") or seis.get("R_source"),
            cite=cfg.get("R_cite") or seis.get("R_cite"),
            system=cfg.get("system") or seis.get("system"))

    return entries


def _is_dual_cfg(cfg: dict, entries: list[dict]) -> bool:
    if cfg.get("dual_system") or cfg.get("mixed_sfrs") or cfg.get("dual_sfrs"):
        return True
    if cfg.get("R_by_system") or cfg.get("dual_R") or cfg.get("sfrs_R"):
        return True
    systems = cfg.get("systems") or cfg.get("sfrs") or cfg.get("dual_systems")
    if isinstance(systems, (list, dict)) and len(systems) >= 2:
        return True
    Rs = {round(e["R"], 6) for e in entries}
    if len(entries) >= 2 and (len(Rs) >= 2 or len(entries) >= 2):
        # two named systems even if same R (Ex10 SBMF + strap both R=2.5)
        names = {e["name"] for e in entries}
        if len(names) >= 2:
            return True
    # Explicit system string hints
    blob = " ".join(str(cfg.get(k) or "") for k in ("system", "arch", "notes", "feature")).lower()
    if any(tok in blob for tok in ("dual", "mixed sfrs", "mixed_sfrs", "sbmf+strap", "sbmf + strap")):
        return True
    return False


def least_R_clause_status(cfg: dict | None = None) -> dict[str, Any]:
    """Status of the IS 1893 dual least-R clause (never invent text)."""
    cfg = cfg or {}
    filled = cfg.get("least_R_clause") or cfg.get("is1893_least_R_clause")
    if isinstance(filled, dict) and filled.get("found") is True and (
        filled.get("cite") or filled.get("clause") or filled.get("text")
    ):
        out = dict(DEFAULT_LEAST_R_CLAUSE)
        out.update(filled)
        out["found"] = True
        out["source"] = "cfg_agent_rag"
        return out
    # Explicit found:false from agent RAG is fine
    if isinstance(filled, dict) and filled.get("found") is False:
        out = dict(DEFAULT_LEAST_R_CLAUSE)
        out.update(filled)
        out["found"] = False
        return out
    return dict(DEFAULT_LEAST_R_CLAUSE)


def dual_system_least_R(cfg: dict | None) -> dict[str, Any]:
    """Select least R for dual/mixed SFRS with honest found/eor status.

    Returns a status object:
      - dual: whether dual/mixed path applies
      - entries: collected R rows
      - least_R / governing_R when selectable
      - clause: least_R_clause_status
      - found: True only when selection is grounded (IS clause found OR
        eor_documented governing R with cite)
      - require_eor_documented: True when clause found:false
    """
    cfg = cfg or {}
    if not _india(cfg):
        return dict(
            found=False,
            dual=False,
            jurisdiction=cfg.get("jurisdiction"),
            note="dual_system_least_R is an India helper; jurisdiction is not india.",
        )

    entries = _collect_R_entries(cfg)
    dual = _is_dual_cfg(cfg, entries)
    clause = least_R_clause_status(cfg)

    out: dict[str, Any] = {
        "found": False,
        "dual": dual,
        "jurisdiction": "india",
        "entries": entries,
        "clause": clause,
        "require_eor_documented": not bool(clause.get("found")),
        "asce_12_2_3_refused": True,
        "note": None,
        "selection": None,
        "least_R": None,
        "governing_R": None,
        "governing_name": None,
    }

    if not dual:
        out["note"] = (
            "No dual/mixed SFRS or multi-R map detected — least-R dual clause N/A. "
            "Set cfg['dual_system']=True or cfg['R_by_system']/{systems:[{R..}]} when mixed."
        )
        # Single R still reported for convenience
        if len(entries) == 1:
            out["least_R"] = entries[0]["R"]
            out["governing_R"] = entries[0]["R"]
            out["governing_name"] = entries[0]["name"]
            out["selection"] = "single_system"
        return out

    if not entries:
        out["note"] = (
            "Dual/mixed SFRS declared but no R values collected (found:false). "
            "Provide R_by_system / systems[] / R_x+R_y, and ground governing R via "
            "eor_documented or LIVE IS 1893 least-R clause fill."
        )
        return out

    # Least R among declared values
    governing = min(entries, key=lambda e: e["R"])
    least = governing["R"]
    out["least_R"] = least
    out["governing_R"] = least
    out["governing_name"] = governing["name"]
    out["selection"] = "least_R_numeric"

    # Grounding: IS clause found → OK; else require eor_documented on governing / cfg R
    if clause.get("found"):
        out["found"] = True
        out["require_eor_documented"] = False
        out["note"] = (
            "Least R=%.4g selected from dual/mixed entries; IS 1893 least-R clause "
            "agent-filled from LIVE RAG (cite=%r)."
            % (least, clause.get("cite") or clause.get("clause"))
        )
        return out

    # eor path: cfg-level R_source or each entry source
    cfg_src = _norm(cfg.get("R_source") or (cfg.get("seis") or {}).get("R_source"))
    cfg_cite = (cfg.get("R_cite") or (cfg.get("seis") or {}).get("R_cite") or "").strip()
    entry_srcs = {_norm(e.get("source")) for e in entries if e.get("source")}
    eor_ok = cfg_src in EOR_OK or (entry_srcs and entry_srcs <= EOR_OK)
    if eor_ok and (cfg_cite or any((e.get("cite") or "").strip() for e in entries)):
        out["found"] = True
        out["selection"] = "least_R_eor_documented"
        out["require_eor_documented"] = True  # still the required path (clause absent)
        out["note"] = (
            "IS 1893 dual least-R clause found:false — governing least R=%.4g accepted "
            "via eor_documented path (cite present). NOT an IS 800 OMRF proxy; "
            "ASCE 7 §12.2.3 refused as India law."
            % least
        )
        return out

    out["found"] = False
    out["selection"] = "least_R_ungrounded"
    out["note"] = (
        "Dual/mixed SFRS: least R=%.4g computed from entries, but IS 1893 dual least-R "
        "clause found:false and R_source is not eor_documented with cite. "
        "Set R_source='eor_documented' + R_cite, or fill cfg['least_R_clause'] from LIVE RAG. "
        "Do not invent IS clause text; do not copy ASCE 7 §12.2.3 as India law."
        % least
    )
    return out


def rag_query_plan_least_R(cfg: dict | None = None) -> list[dict[str, Any]]:
    """Retrieval plan hooks agents can run against LIVE India RAG."""
    cfg = cfg or {}
    systems = cfg.get("systems") or cfg.get("sfrs") or []
    sys_hint = ""
    if isinstance(systems, list) and systems:
        names = [str(s.get("name") or s.get("system") or s) for s in systems if s]
        sys_hint = " ".join(names[:4])
    return [
        {
            "stem": "IS_1893_Part_1_2016",
            "query": "dual system different lateral force resisting systems same direction response reduction factor R",
            "purpose": "least_R_dual_system_clause",
            "type": "exact_clause",
            "found": None,
            "note": "Fill cfg['least_R_clause'] if hit; else leave found:false + eor_documented.",
        },
        {
            "stem": "IS_1893_Part_1_2016",
            "query": "Table 9 response reduction factor mixed system %s" % sys_hint,
            "purpose": "table9_per_system_R",
            "type": "exact_table",
            "found": None,
        },
        {
            "stem": "IS_1893_Part_1_2016",
            "query": "buildings with combination of different structural systems",
            "purpose": "combined_systems_clause",
            "type": "keyword",
            "found": None,
        },
    ]
