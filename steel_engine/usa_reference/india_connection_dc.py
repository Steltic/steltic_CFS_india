"""India connection / base-anchor D/C reporting (wave2 polish2).

Portal knee/apex connections and base anchors must cite IS 801 (cl.7 connections)
and/or manufacturer EOR capacities. Silent USA AISI S100/S240 defaults are refused
for jurisdiction=india — use found:false + eor_documented paths instead of inventing.
"""
from __future__ import annotations

from typing import Any

AISI_REFUSE_NOTE = (
    "India jurisdiction: refuse silent USA AISI S100/S240/S400 connection defaults. "
    "Cite IS 801:1975 cl.7 (connections) / cl.8 (bracing) or manufacturer EOR capacity; "
    "found:false until a project cite is supplied."
)


def _india_jurisdiction(cfg: dict | None) -> bool:
    cfg = cfg or {}
    j = str(cfg.get("jurisdiction") or "").lower()
    if j in ("india", "in", "is", "is_bis", "bis"):
        return True
    plan = cfg.get("load_plan")
    return isinstance(plan, dict) and str(plan.get("jurisdiction") or "").lower() in \
        ("india", "in", "is", "is_bis", "bis")


def _slot_from_cfg(cfg: dict | None, slot_id: str) -> dict | None:
    """Pull optional agent/EOR capacity for a connection/anchor slot from cfg."""
    cfg = cfg or {}
    for key in ("connection_capacities", "eor_connections", "india_connections"):
        block = cfg.get(key)
        if isinstance(block, dict) and slot_id in block and isinstance(block[slot_id], dict):
            return dict(block[slot_id])
        if isinstance(block, list):
            for row in block:
                if isinstance(row, dict) and str(row.get("id") or row.get("slot")) == slot_id:
                    return dict(row)
    # Flat keys: cfg['conn-knee'] etc.
    if slot_id in cfg and isinstance(cfg[slot_id], dict):
        return dict(cfg[slot_id])
    return None


def connection_dc_status(
    slot_id: str,
    cfg: dict | None = None,
    *,
    kind: str = "connection",
    demand: dict | None = None,
) -> dict[str, Any]:
    """Build an honest D/C stub for a portal/wall connection or base-anchor slot.

    - If cfg supplies manufacturer/EOR capacity + cite → found:true with DC when both
      demand and capacity are numeric.
    - Otherwise found:false; DC=None; cited points at IS 801 RAG obligation.
    - Never fills AISI S100 J as a silent default under India jurisdiction.
    """
    cfg = cfg or {}
    india = _india_jurisdiction(cfg)
    demand = demand or {}

    base = dict(
        id=slot_id,
        kind=kind,
        jurisdiction="india" if india else (cfg.get("jurisdiction") or "unspecified"),
        found=False,
        DC=None,
        capacity=None,
        cited=None,
        limit_state=None,
        source=None,
    )

    if not india:
        base["note"] = "Non-India jurisdiction — AISI connection path is out of scope here."
        return base

    eor = _slot_from_cfg(cfg, slot_id)
    # Also accept kind-level defaults: cfg['base_anchor_eor'], cfg['knee_eor'], ...
    if eor is None:
        aliases = {
            "base-anchor": ["base_anchor_eor", "anchor_eor", "base_anchor"],
            "conn-knee": ["knee_eor", "knee_connection"],
            "conn-apex": ["apex_eor", "apex_connection"],
        }
        for alt in aliases.get(slot_id, []):
            if isinstance(cfg.get(alt), dict):
                eor = dict(cfg[alt])
                break

    if eor:
        cite = eor.get("cited") or eor.get("cite") or eor.get("R_cite")
        source = str(eor.get("source") or eor.get("capacity_source") or "").lower()
        cap = eor.get("capacity")
        # Refuse AISI-labelled sources even if present
        if source in ("aisi", "aisi_s100", "s100", "s240", "s400", "usa_default"):
            base.update(
                found=False,
                note=AISI_REFUSE_NOTE + " (cfg source=%r refused)." % source,
                source=source,
                cited=cite,
            )
            return base
        ok_sources = (
            "is801", "is_801", "manufacturer", "eor", "eor_documented", "test",
            "is801_rag", "project_eor",
        )
        if source and source not in ok_sources and "is 801" not in source and "is801" not in source:
            # Unknown source with cite still OK if explicitly eor-ish keys present
            if not cite:
                base.update(
                    found=False,
                    note=("Connection capacity source=%r not allowlisted for India and no cite "
                          "(found:false). Use source=is801|manufacturer|eor_documented + cite."
                          % source),
                    source=source,
                )
                return base

        if not cite:
            base.update(
                found=False,
                capacity=cap,
                source=source or None,
                note=("Capacity present without cite (found:false). Attach IS 801 cl.7 / "
                      "manufacturer EOR cite before COMPLETE."),
            )
            return base

        dc = eor.get("DC")
        if dc is None and cap is not None:
            # Try demand keys commonly seeded on portal packages
            for dk in ("M_transfer_kipin", "V_base_kip", "T_net_uplift_kip", "M_base_kipin",
                       "demand", "Mu", "Vu", "Tu"):
                if dk in demand and demand[dk] is not None:
                    try:
                        dem = abs(float(demand[dk]))
                        cval = abs(float(cap))
                        if cval > 0:
                            dc = round(dem / cval, 3)
                            break
                    except (TypeError, ValueError):
                        pass
                if dk in eor and eor[dk] is not None and cap is not None:
                    try:
                        dem = abs(float(eor[dk]))
                        cval = abs(float(cap))
                        if cval > 0:
                            dc = round(dem / cval, 3)
                            break
                    except (TypeError, ValueError):
                        pass

        base.update(
            found=True,
            DC=dc if dc is not None else eor.get("DC"),
            capacity=cap,
            cited=cite,
            limit_state=eor.get("limit_state") or eor.get("limit"),
            source=source or "eor_documented",
            note=eor.get("note") or (
                "India connection D/C from %s (cite=%s). Not an AISI default."
                % (source or "eor_documented", cite)
            ),
        )
        return base

    # No EOR capacity — honest stub
    cite_hint = (
        "IS 801:1975 cl.7 connections / base anchorage — LIVE RAG required; "
        "or manufacturer EOR capacity with cite"
    )
    base.update(
        found=False,
        cited=None,
        limit_state=None,
        capacity=None,
        DC=None,
        note=AISI_REFUSE_NOTE + " Suggested cite path: " + cite_hint + ".",
        demand_seed=demand or None,
    )
    return base


def apply_india_connection_stubs(pkg: dict, cfg: dict | None) -> dict:
    """Annotate portal/wall package connection + anchorage slots for India jurisdiction.

    Mutates and returns pkg. Adds ``india_connection_path`` summary.
    """
    cfg = cfg or {}
    if not _india_jurisdiction(cfg):
        return pkg

    statuses = []
    for c in pkg.get("connections") or []:
        if not isinstance(c, dict):
            continue
        sid = str(c.get("id") or c.get("joint") or "connection")
        demand = {k: c.get(k) for k in
                  ("M_transfer_kipin", "V_kip", "P_kip", "demand") if k in c}
        st = connection_dc_status(sid, cfg, kind="connection", demand=demand)
        statuses.append(st)
        # Wire fields without inventing AISI defaults
        c["india_dc"] = st
        if st.get("found"):
            if st.get("DC") is not None:
                c["DC"] = st["DC"]
            if st.get("capacity") is not None:
                c["capacity"] = st["capacity"]
            if st.get("cited"):
                c["cited"] = st["cited"]
            if st.get("limit_state"):
                c["limit_state"] = st["limit_state"]
        else:
            # Ensure we do not leave a silent USA cite
            if not c.get("cited"):
                c["cited"] = None
            if c.get("DC") is None:
                c["DC"] = None
            c.setdefault(
                "note",
                (c.get("note") or "") + (" | " if c.get("note") else "") + st.get("note", ""),
            )
            # Refuse if someone pre-seeded AISI
            cited_l = str(c.get("cited") or "").lower()
            if any(x in cited_l for x in ("s100", "s240", "s400", "aisi")):
                c["cited"] = None
                c["DC"] = None
                c["capacity"] = None
                c["india_dc"] = dict(st, note=st["note"] + " Cleared AISI pre-seed.")

    for a in pkg.get("anchorage") or []:
        if not isinstance(a, dict):
            continue
        sid = str(a.get("id") or "base-anchor")
        demand = {k: a.get(k) for k in
                  ("V_base_kip", "T_net_uplift_kip", "M_base_kipin") if k in a}
        st = connection_dc_status(sid, cfg, kind="anchorage", demand=demand)
        statuses.append(st)
        a["india_dc"] = st
        if st.get("found"):
            if st.get("DC") is not None:
                a["DC"] = st["DC"]
            if st.get("capacity") is not None:
                a["capacity"] = st["capacity"]
            if st.get("cited"):
                a["cited"] = st["cited"]
            if st.get("limit_state"):
                a["limit_state"] = st["limit_state"]
        else:
            if not a.get("cited"):
                a["cited"] = None
            note = a.get("note") or ""
            # Rewrite USA-flavoured uplift combo hint when India
            if "0.9D+1.0W" in note and "IS" not in note:
                note = note.replace(
                    "0.9D+1.0W",
                    "net-uplift case from cfg['load_plan'] (IS 875 RAG; not ASCE 0.9D+1.0W default)",
                )
            a["note"] = (note + (" | " if note else "") + st.get("note", "")).strip(" |")

    any_found = any(s.get("found") for s in statuses)
    pkg["india_connection_path"] = dict(
        found=any_found,
        jurisdiction="india",
        n_slots=len(statuses),
        n_found=sum(1 for s in statuses if s.get("found")),
        slots=statuses,
        note=(
            "India connection/anchor D/Cs supplied from IS 801 / manufacturer EOR cites."
            if any_found else
            "India connection/anchor D/Cs pending (found:false). "
            + AISI_REFUSE_NOTE
        ),
    )
    return pkg
