"""Prefer stocked IS 811 channel / lipped-channel sizes for India portal / wall jobs.

When ``jurisdiction=india``, agents should pick from ``is811_shapes.csv`` (CLR/CLS/CWR/CWS/LZ…)
rather than arbitrary SFIA-only designators. This helper only resolves against the local
catalog — it does NOT invent properties or fabricate missing designations.

Missing / unmatched sizes → ``found:false`` (honest; RAG or EOR must supply an alternate).

Nx packs (``8xCLR…``, ``32xCLR…``) and built-ups (``2xCLR…``): parse ply count; stock
catalog covers single + conventional ``2x`` built-up. ``N>2`` → ``found:false`` with
nearest stocked / ``2x`` candidates as aid only (Ex5/Ex15) — do not invent Nx capacity.
"""
from __future__ import annotations

from typing import Any

# Framing Types typically stocked for studs / portal chords / rails (IS 811 Tables 3–6, 10).
PRACTICAL_TYPES: tuple[str, ...] = ("CLR", "CLS", "CWR", "CWS", "LZ")
# Portal column/rafter preference: lipped rectangular channels first.
PORTAL_TYPES: tuple[str, ...] = ("CLR", "CLS", "CWR", "CWS")
# Wall stud preference: lipped channels.
STUD_TYPES: tuple[str, ...] = ("CLR", "CLS", "CWS", "CWR")


def _india_jurisdiction(cfg_or_j: Any) -> bool:
    if isinstance(cfg_or_j, str):
        return cfg_or_j.lower() in ("india", "in", "is", "is_bis", "bis")
    cfg = cfg_or_j or {}
    j = str(cfg.get("jurisdiction") or "").lower()
    if j in ("india", "in", "is", "is_bis", "bis"):
        return True
    plan = cfg.get("load_plan")
    return isinstance(plan, dict) and str(plan.get("jurisdiction") or "").lower() in \
        ("india", "in", "is", "is_bis", "bis")


def _looks_sfia(name: str) -> bool:
    import re
    return bool(re.match(r"^(?:2[xX])?\d{3}[STUCZFH]\d{3}-\d{2,3}$", str(name or "").strip()))


def parse_nx_pack(name: str | None) -> dict[str, Any]:
    """Parse ``Nx<label>`` / ``2x<label>`` built-up / pack prefixes.

    Returns ``{n_ply, bare, prefix, is_nx_pack, is_built_up}``.
    ``n_ply=1`` when no leading integer× prefix. Does not invent properties.
    """
    import re
    raw = str(name or "").strip()
    lab = raw.upper().replace(" ", "")
    # Keep hyphens out of IS labels for catalog match; SFIA may use them
    lab_compact = lab.replace("-", "")
    m = re.match(r"^(\d+)X(.+)$", lab_compact)
    if m:
        n = int(m.group(1))
        bare = m.group(2)
        return dict(
            n_ply=n,
            bare=bare,
            prefix="%dx" % n,
            is_nx_pack=n > 2,
            is_built_up=n >= 2,
            requested=raw,
        )
    return dict(
        n_ply=1,
        bare=lab_compact or None,
        prefix=None,
        is_nx_pack=False,
        is_built_up=False,
        requested=raw,
    )


def resolve_is811_label(name: str) -> dict[str, Any]:
    """Look up an exact IS 811 label in the catalog.

    Returns ``found:true`` with props summary, or ``found:false`` without inventing.
    Supports ``2xCLR…`` built-up (catalog ply) and diagnoses ``Nx`` packs (N>2).
    """
    parsed = parse_nx_pack(name)
    bare = parsed.get("bare") or ""
    n_ply = int(parsed.get("n_ply") or 1)
    out: dict[str, Any] = {
        "requested": name,
        "label": bare or None,
        "found": False,
        "in_catalog": False,
        "built_up": bool(parsed.get("is_built_up")),
        "n_ply": n_ply,
        "is_nx_pack": bool(parsed.get("is_nx_pack")),
        "source": "is811_shapes.csv",
    }
    if not bare:
        out["note"] = "Empty section label (found:false)."
        return out
    try:
        import is811_sections as S
    except Exception as ex:
        out["note"] = "is811_sections unavailable: %s" % ex
        return out

    if not S.looks_is811(bare):
        out["note"] = (
            "Not an IS 811 designation (%r). For jurisdiction=india prefer CLR/CLS/CWR/CWS/LZ "
            "from is811_shapes.csv; SFIA twin remains non-authoritative (found:false for IS 811)."
            % (name,)
        )
        out["looks_sfia"] = _looks_sfia(name)
        return out
    try:
        props = S.props(bare, unit_system="N-mm")
    except KeyError as ex:
        out["note"] = str(ex)
        out["looks_is811"] = True
        return out

    # Bare label is in catalog
    base_note = (
        "IS 811 catalog hit (is811_shapes.csv). Verify OCR/QFM Ix when noisy "
        "(see india_is811_retrieval.ix_qfm_correction_status)."
    )
    out.update(
        label=props.get("label") or bare,
        type=props.get("Type"),
        table=props.get("Table"),
        designation_is=props.get("Designation_IS"),
        h_mm=props.get("h_mm"),
        b_mm=props.get("b_mm"),
        t_mm=props.get("t_mm"),
        A_mm2=props.get("A"),
        Ix_mm4=props.get("Ix"),
        Ix_si_cm4=props.get("Ix_si_cm4"),
        depth=props.get("depth", props.get("d")),
    )

    if n_ply == 1:
        out.update(found=True, in_catalog=True, note=base_note)
        return out

    if n_ply == 2:
        # Conventional back-to-back built-up — bare stocked; interconnection is agent/IS 801 item
        out.update(
            found=True,
            in_catalog=True,
            built_up_label="2x%s" % (props.get("label") or bare),
            note=base_note + (
                " Built-up 2x (back-to-back): stocked single ply resolved; "
                "interconnection / built-up rules are agent+IS 801 (not invented here)."
            ),
        )
        return out

    # N>2 pack: bare exists but Nx is NOT a stocked catalog designation
    out.update(
        found=False,
        in_catalog=False,  # the Nx pack itself is not a catalog row
        bare_in_catalog=True,
        bare_label=props.get("label") or bare,
        note=(
            "Nx pack %r (n_ply=%d) is NOT a stocked IS 811 designation (found:false). "
            "Bare ply %s is in is811_shapes.csv — listed as nearest-candidate aid only. "
            "Prefer single stocked CLR/CLS/… or conventional 2x built-up; engineered "
            "multi-ply packs need EOR/constructibility disclosure (do not invent Nx capacity)."
            % (name, n_ply, props.get("label") or bare)
        ),
    )
    return out


def prefer_practical_is811(
    requested: str | None = None,
    *,
    h_mm: float | None = None,
    b_mm: float | None = None,
    t_mm: float | None = None,
    type_pref: tuple[str, ...] | list[str] | None = None,
    role: str = "framing",
    jurisdiction: str | None = "india",
    max_candidates: int = 8,
) -> dict[str, Any]:
    """Prefer a stocked IS 811 size near the requested dims / label.

    - Exact catalog hit → ``found:true``, ``selection=exact``.
    - Dimensional nearest among ``type_pref`` → ``found:true``, ``selection=nearest_stocked``
      (candidate list only; agent/EOR still chooses).
    - Nothing usable → ``found:false`` (do not invent a label or SFIA substitute as IS law).
    """
    if jurisdiction is not None and not _india_jurisdiction(jurisdiction):
        return dict(
            found=False,
            jurisdiction=jurisdiction,
            note="prefer_practical_is811 is an India IS 811 helper; jurisdiction is not india.",
        )

    types = tuple(t.upper() for t in (type_pref or (
        PORTAL_TYPES if role in ("portal", "col", "raf", "rafter", "column") else
        STUD_TYPES if role in ("stud", "chord", "wall") else
        PRACTICAL_TYPES
    )))

    # Exact path first
    if requested:
        hit = resolve_is811_label(requested)
        if hit.get("found"):
            hit = dict(hit)
            hit["selection"] = "exact"
            hit["role"] = role
            hit["type_pref"] = list(types)
            return hit
        # If SFIA / unknown — continue to dimensional nearest when dims given
        sfia = hit.get("looks_sfia") or _looks_sfia(requested)
        if not any(v is not None for v in (h_mm, b_mm, t_mm)) and not sfia:
            return dict(
                found=False,
                requested=requested,
                selection=None,
                role=role,
                type_pref=list(types),
                note=hit.get("note") or ("IS 811 label %r not in catalog (found:false)." % requested),
                exact_status=hit,
            )

    try:
        import is811_sections as S
    except Exception as ex:
        return dict(found=False, note="is811_sections unavailable: %s" % ex)

    # Collect candidates by Type
    cands = []
    for typ in types:
        for lab in S.list_is811(typ):
            try:
                p = S.props(lab, unit_system="N-mm")
            except KeyError:
                continue
            cands.append(dict(
                label=p.get("label") or lab,
                type=p.get("Type"),
                h_mm=p.get("h_mm"),
                b_mm=p.get("b_mm"),
                t_mm=p.get("t_mm"),
                A_mm2=p.get("A"),
                Ix_si_cm4=p.get("Ix_si_cm4"),
                table=p.get("Table"),
            ))

    if not cands:
        return dict(
            found=False,
            requested=requested,
            role=role,
            type_pref=list(types),
            note="No IS 811 stocked rows for type_pref=%s (found:false)." % (list(types),),
        )

    # Score by available dims (mm). Missing target dims → list first stocked of preferred type only.
    if h_mm is None and b_mm is None and t_mm is None:
        # No dims: if requested was SFIA, refuse silent SFIA→IS invent; return found:false + sample.
        sample = cands[:max_candidates]
        return dict(
            found=False,
            requested=requested,
            selection=None,
            role=role,
            type_pref=list(types),
            looks_sfia=_looks_sfia(requested) if requested else False,
            candidates=sample,
            note=(
                "No exact IS 811 hit and no target h_mm/b_mm/t_mm supplied. "
                "Candidates listed for agent/EOR selection only — do not invent a designation. "
                "found:false until an IS 811 label is chosen from the catalog."
            ),
        )

    def _score(c: dict) -> float:
        s = 0.0
        if h_mm is not None and c.get("h_mm") is not None:
            s += abs(float(c["h_mm"]) - float(h_mm)) / max(float(h_mm), 1.0)
        if b_mm is not None and c.get("b_mm") is not None:
            s += abs(float(c["b_mm"]) - float(b_mm)) / max(float(b_mm), 1.0)
        if t_mm is not None and c.get("t_mm") is not None:
            s += abs(float(c["t_mm"]) - float(t_mm)) / max(float(t_mm), 0.1)
        # Prefer earlier type_pref
        try:
            s += 0.01 * types.index(str(c.get("type") or "").upper())
        except ValueError:
            s += 0.5
        return s

    ranked = sorted(cands, key=_score)
    best = ranked[0]
    return dict(
        found=True,
        requested=requested,
        selection="nearest_stocked",
        role=role,
        type_pref=list(types),
        label=best["label"],
        type=best.get("type"),
        h_mm=best.get("h_mm"),
        b_mm=best.get("b_mm"),
        t_mm=best.get("t_mm"),
        A_mm2=best.get("A_mm2"),
        Ix_si_cm4=best.get("Ix_si_cm4"),
        table=best.get("table"),
        candidates=ranked[:max_candidates],
        target_dims_mm=dict(h_mm=h_mm, b_mm=b_mm, t_mm=t_mm),
        note=(
            "Nearest stocked IS 811 size from is811_shapes.csv for role=%s. "
            "Agent/EOR must confirm constructibility / built-up detailing; "
            "this is not a capacity check."
            % role
        ),
        source="is811_shapes.csv",
    )


def prefer_portal_stock_or_built_up(
    requested: str | None = None,
    *,
    h_mm: float | None = None,
    b_mm: float | None = None,
    t_mm: float | None = None,
    jurisdiction: str | None = "india",
    max_candidates: int = 8,
) -> dict[str, Any]:
    """Portal / Nx pack path (Ex5/Ex15): prefer stocked IS 811 or 2x built-up.

    - Exact single / 2x catalog → found:true
    - Nx (N>2) even if bare stocked → found:false + nearest single/2x candidates
    - Missing → found:false with nearest-candidate aid only (no invented label)
    """
    if jurisdiction is not None and not _india_jurisdiction(jurisdiction):
        return dict(
            found=False,
            jurisdiction=jurisdiction,
            note="prefer_portal_stock_or_built_up is an India helper.",
        )

    parsed = parse_nx_pack(requested) if requested else dict(n_ply=1, bare=None, is_nx_pack=False)
    n_ply = int(parsed.get("n_ply") or 1)
    bare = parsed.get("bare")

    # Exact / 2x path via resolve
    if requested:
        hit = resolve_is811_label(requested)
        if hit.get("found"):
            hit = dict(hit)
            hit["selection"] = "exact" if n_ply == 1 else "built_up_2x"
            hit["role"] = "portal"
            return hit

        # Nx pack with bare in catalog → found:false but attach nearest aid
        if hit.get("is_nx_pack") and hit.get("bare_in_catalog"):
            dims = dict(
                h_mm=h_mm if h_mm is not None else hit.get("h_mm"),
                b_mm=b_mm if b_mm is not None else hit.get("b_mm"),
                t_mm=t_mm if t_mm is not None else hit.get("t_mm"),
            )
            nearest = prefer_practical_is811(
                hit.get("bare_label") or bare,
                h_mm=dims.get("h_mm"),
                b_mm=dims.get("b_mm"),
                t_mm=dims.get("t_mm"),
                role="portal",
                jurisdiction="india",
                max_candidates=max_candidates,
            )
            # Also propose conventional 2x of the bare label
            built = None
            if hit.get("bare_label") or bare:
                bl = hit.get("bare_label") or bare
                built = dict(
                    label="2x%s" % bl,
                    n_ply=2,
                    bare=bl,
                    note="Conventional 2x built-up of stocked ply (interconnection agent/IS 801).",
                )
            cands = list(nearest.get("candidates") or [])
            if built:
                cands = [built] + [c for c in cands if c.get("label") != bl]
            return dict(
                found=False,
                requested=requested,
                selection=None,
                role="portal",
                is_nx_pack=True,
                n_ply=n_ply,
                bare_label=hit.get("bare_label") or bare,
                bare_in_catalog=True,
                h_mm=hit.get("h_mm"),
                b_mm=hit.get("b_mm"),
                t_mm=hit.get("t_mm"),
                candidates=cands[:max_candidates],
                nearest_stocked=nearest if nearest.get("found") else None,
                built_up_candidate=built,
                note=hit.get("note"),
                source="is811_shapes.csv",
            )

    # Dimensional / unknown — fall through to practical nearest among portal types
    pref = prefer_practical_is811(
        requested if requested and n_ply == 1 else (bare or requested),
        h_mm=h_mm,
        b_mm=b_mm,
        t_mm=t_mm,
        role="portal",
        jurisdiction="india",
        max_candidates=max_candidates,
    )
    if pref.get("found") and pref.get("label"):
        # Offer 2x companion as optional built-up aid
        pref = dict(pref)
        pref["built_up_candidate"] = dict(
            label="2x%s" % pref["label"],
            n_ply=2,
            bare=pref["label"],
            note="Optional 2x built-up of nearest stocked ply.",
        )
    return pref


def section_selection_for_cfg(cfg: dict | None) -> dict[str, Any]:
    """Summarize practical section status for portal/wall cfg (col/raf/stud slots)."""
    cfg = cfg or {}
    if not _india_jurisdiction(cfg):
        return dict(found=False, note="Not India jurisdiction — practical IS 811 selection N/A.")

    slots = {}
    for key in ("col_section", "raf_section", "stud_section", "chord_section"):
        if key not in cfg:
            continue
        name = cfg[key]
        role = "portal" if key in ("col_section", "raf_section") else "stud"
        if role == "portal":
            dims = cfg.get("section_target_mm") or cfg.get("%s_target_mm" % key) or {}
            slots[key] = prefer_portal_stock_or_built_up(
                name,
                h_mm=dims.get("h_mm") if isinstance(dims, dict) else None,
                b_mm=dims.get("b_mm") if isinstance(dims, dict) else None,
                t_mm=dims.get("t_mm") if isinstance(dims, dict) else None,
                jurisdiction="india",
            )
            continue
        hit = resolve_is811_label(name)
        if hit.get("found"):
            slots[key] = dict(hit, selection="exact", role=role)
        else:
            dims = cfg.get("section_target_mm") or cfg.get("%s_target_mm" % key) or {}
            pref = prefer_practical_is811(
                name,
                h_mm=dims.get("h_mm") if isinstance(dims, dict) else None,
                b_mm=dims.get("b_mm") if isinstance(dims, dict) else None,
                t_mm=dims.get("t_mm") if isinstance(dims, dict) else None,
                role=role,
                jurisdiction="india",
            )
            slots[key] = pref

    any_found = any(s.get("found") for s in slots.values()) if slots else False
    missing = [k for k, s in slots.items() if not s.get("found")]
    return dict(
        found=any_found and not missing,
        jurisdiction="india",
        slots=slots,
        missing=missing,
        note=(
            "All India framing slots resolve to IS 811 catalog labels."
            if any_found and not missing else
            ("Practical IS 811 selection incomplete for %s — found:false on those slots; "
             "prefer stocked CLR/CLS/… or 2x built-up from is811_shapes.csv "
             "(Nx packs N>2 are not stock — candidates listed as aid only)."
             % (missing or "no section keys"))
        ),
    )
