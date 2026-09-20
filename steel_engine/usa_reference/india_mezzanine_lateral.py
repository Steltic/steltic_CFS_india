"""Explicit mezzanine lateral model hook (Ex5 polish Wave B).

Honest policy:
- Gravity-in-W alone is NOT a lateral model. Packages that only fold mezzanine
  dead/live into seismic W must disclose lateral share as found:false unless
  an explicit frame / diaphragm / separate-system model is declared.
- Do not invent mezzanine lateral force share percentages or dual-system R.
- Accept EOR/project model disclosures with cite, or clear
  gravity_only_disclosed / separate_system / host_frame_share stubs.
"""
from __future__ import annotations

from typing import Any

EOR_OK = frozenset({
    "eor_documented", "eor", "eor_explicit", "documented", "explicit",
    "project_eor", "analysis", "modelled", "modeled",
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


def _mezz_hint(cfg: dict) -> bool:
    if cfg.get("mezzanine") or cfg.get("has_mezzanine") or cfg.get("mezz"):
        return True
    blob = " ".join(
        str(cfg.get(k) or "")
        for k in ("system", "arch", "feature", "notes", "plan_desc", "title", "building")
    ).lower()
    return "mezzanine" in blob or "mezz" in blob.split()


def _mezz_block(cfg: dict) -> dict:
    m = cfg.get("mezzanine")
    if isinstance(m, dict):
        return dict(m)
    if cfg.get("mezzanine") is True or cfg.get("has_mezzanine"):
        return {"present": True}
    plan = cfg.get("load_plan") if isinstance(cfg.get("load_plan"), dict) else {}
    ms = plan.get("mezzanine_summary") or plan.get("mezzanine") or cfg.get("mezzanine_summary")
    if isinstance(ms, dict):
        return dict(ms)
    return {}


def mezzanine_lateral_model_status(cfg: dict | None = None) -> dict[str, Any]:
    """Status for Ex5-style mezzanine lateral share / frame model.

    found:true only when an explicit lateral model path is disclosed:
      - separate_system (own wall/frame cfg + R)
      - host_frame_share (mezzanine mass + stated lateral share on host portals)
      - diaphragm_model / analysis with cite
      - eor_documented model note with cite
    Gravity-in-W only → found:false with clear disclosure.
    """
    cfg = cfg or {}
    if not _india(cfg):
        return dict(
            found=False,
            jurisdiction=cfg.get("jurisdiction"),
            note="mezzanine_lateral_model_status is an India helper.",
        )

    detected = _mezz_hint(cfg)
    mezz = _mezz_block(cfg)
    plan = cfg.get("load_plan") if isinstance(cfg.get("load_plan"), dict) else {}

    out: dict[str, Any] = {
        "found": False,
        "jurisdiction": "india",
        "mezzanine_detected": detected or bool(mezz),
        "path": None,
        "gravity_in_W": None,
        "lateral_modelled": False,
        "cited": None,
        "source": None,
        "cfg_hooks": {
            "mezzanine": (
                "dict with lateral_model|lateral_share|separate_system|"
                "host_frame_share|gravity_only + cite"
            ),
            "mezzanine_lateral_model": "str/dict explicit model declaration",
            "load_plan.mezzanine_summary": "may carry gravity; lateral still needs model hook",
        },
        "note": None,
    }

    if not out["mezzanine_detected"]:
        out["note"] = (
            "No mezzanine hint in cfg — lateral model N/A. "
            "Set mezzanine={...} when a mezzanine is present."
        )
        out["path"] = "n/a"
        return out

    # Explicit lateral model fields
    lat = (
        cfg.get("mezzanine_lateral_model")
        or mezz.get("lateral_model")
        or mezz.get("lateral")
        or mezz.get("model")
    )
    share = mezz.get("lateral_share") or mezz.get("V_share") or cfg.get("mezzanine_lateral_share")
    separate = (
        mezz.get("separate_system")
        or cfg.get("mezzanine_separate_system")
        or mezz.get("own_system")
    )
    host_share = mezz.get("host_frame_share") or cfg.get("mezzanine_host_frame_share")
    gravity_only = (
        mezz.get("gravity_only")
        or mezz.get("gravity_in_W_only")
        or _norm(mezz.get("note") or "").startswith("gravity")
    )
    # Detect gravity-in-W phrasing
    note_l = str(mezz.get("note") or "").lower()
    gravity_in_w = (
        "gravity in w" in note_l
        or "gravity_in_w" in note_l
        or "gravity-only" in note_l
        or mezz.get("gravity_in_W") is True
        or plan.get("mezzanine_in_W") is True
    )
    out["gravity_in_W"] = bool(gravity_in_w or gravity_only)

    cite = (
        mezz.get("cite") or mezz.get("cited") or mezz.get("lateral_cite")
        or cfg.get("mezzanine_lateral_cite") or ""
    )
    cite = str(cite).strip()
    source = _norm(
        mezz.get("source") or mezz.get("lateral_source") or cfg.get("mezzanine_lateral_source")
    )

    # --- Accepted modelled paths ------------------------------------------------
    if separate:
        # separate_system may be bool or dict {system, R, ...}
        sep = separate if isinstance(separate, dict) else {"declared": True}
        out.update(
            found=True,
            path="separate_system",
            lateral_modelled=True,
            separate_system=sep,
            cited=cite or sep.get("cite") or sep.get("R_cite"),
            source=source or _norm(sep.get("source") or sep.get("R_source")) or "eor_documented",
            note=(
                "Mezzanine declared as its OWN lateral system (separate from host "
                "portals/walls). Host frames must not silently carry mezzanine lateral "
                "mass unless a separation joint is stated. Gravity may still enter W "
                "of the mezzanine system only."
            ),
        )
        return out

    if host_share is not None or (isinstance(share, (int, float)) and not gravity_only):
        # Numeric share or explicit host_frame_share dict
        share_val = host_share if host_share is not None else share
        if isinstance(share_val, dict):
            cite = cite or str(share_val.get("cite") or share_val.get("cited") or "").strip()
            source = source or _norm(share_val.get("source"))
            share_num = share_val.get("fraction") or share_val.get("share") or share_val.get("V_share")
        else:
            share_num = share_val
        if source in EOR_OK and cite:
            out.update(
                found=True,
                path="host_frame_share",
                lateral_modelled=True,
                lateral_share=share_num,
                cited=cite,
                source=source,
                note=(
                    "Mezzanine lateral share on host frame disclosed via eor_documented "
                    "path (share=%r, cite=%s). Not gravity-in-W alone."
                    % (share_num, cite)
                ),
            )
            return out
        if share_num is not None and cite:
            out.update(
                found=True,
                path="host_frame_share",
                lateral_modelled=True,
                lateral_share=share_num,
                cited=cite,
                source=source or "eor_documented",
                note=(
                    "Mezzanine lateral share=%r on host frame with cite — verify analysis "
                    "matches. Gravity-in-W alone is insufficient."
                    % share_num
                ),
            )
            return out
        # Share claimed without cite → not grounded
        out.update(
            found=False,
            path="host_frame_share_ungrounded",
            lateral_share=share_num,
            note=(
                "Mezzanine host_frame_share/lateral_share declared but missing "
                "eor_documented cite (found:false). Do not invent share fractions."
            ),
        )
        return out

    if isinstance(lat, dict) and (
        lat.get("found") is True or lat.get("type") or lat.get("model")
    ):
        cite = cite or str(lat.get("cite") or lat.get("cited") or "").strip()
        source = source or _norm(lat.get("source"))
        if cite or source in EOR_OK:
            out.update(
                found=True,
                path=str(lat.get("type") or lat.get("model") or "explicit_model"),
                lateral_modelled=True,
                cited=cite or None,
                source=source or "eor_documented",
                model=lat,
                note=lat.get("note") or (
                    "Explicit mezzanine lateral model disclosed (cite=%s)."
                    % (cite or "cfg")
                ),
            )
            return out

    if isinstance(lat, str) and lat.strip():
        lat_n = _norm(lat)
        if lat_n in (
            "separate_system", "own_system", "host_frame_share",
            "diaphragm_model", "frame_model", "modelled", "modeled", "analysis",
        ):
            if cite or source in EOR_OK:
                out.update(
                    found=True,
                    path=lat_n,
                    lateral_modelled=True,
                    cited=cite or None,
                    source=source or "eor_documented",
                    note="Mezzanine lateral_model=%r disclosed with grounding." % lat,
                )
                return out
            out.update(
                found=False,
                path=lat_n + "_ungrounded",
                note=(
                    "mezzanine lateral_model=%r declared without cite/eor source "
                    "(found:false)."
                    % lat
                ),
            )
            return out

    # Gravity-in-W only — honest found:false
    if out["gravity_in_W"] or gravity_only or note_l:
        # Even if note says "lateral share per diaphragm / frame model" without hooks
        soft_claim = any(
            tok in note_l for tok in ("lateral share", "frame model", "diaphragm")
        )
        out.update(
            found=False,
            path="gravity_in_W_only",
            lateral_modelled=False,
            soft_claim_without_model=soft_claim,
            note=(
                "Mezzanine present but lateral model found:false — gravity-in-W "
                "(or gravity-only note) is NOT an explicit lateral share / frame model. "
                "Set mezzanine.lateral_model / separate_system / host_frame_share with "
                "cite, or disclose gravity_only=True intentionally for EXAMPLE with "
                "this found:false status attached. Do not invent V_share."
                + (" Soft claim in note without model hooks." if soft_claim else "")
            ),
        )
        return out

    out.update(
        found=False,
        path="unspecified",
        note=(
            "Mezzanine detected but no lateral model hooks (found:false). "
            "Provide separate_system, host_frame_share+cite, or lateral_model dict."
        ),
    )
    return out


def rag_query_plan_mezzanine_lateral(cfg: dict | None = None) -> list[dict[str, Any]]:
    return [
        {
            "stem": "IS_1893_Part_1_2016",
            "query": "mezzanine floor lateral force storey mass irregularity",
            "purpose": "mezzanine_mass_lateral",
            "type": "fts",
            "found": None,
            "note": "Do not invent share; fill mezzanine.lateral_model on hit or leave found:false.",
        },
        {
            "stem": "IS_875_Part_2_1987",
            "query": "imposed load mezzanine floor",
            "purpose": "mezzanine_gravity_live",
            "type": "fts",
            "found": None,
            "note": "Gravity only — still need lateral model hook separately.",
        },
    ]
