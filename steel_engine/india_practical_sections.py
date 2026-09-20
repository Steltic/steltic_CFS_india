"""india_practical_sections.py -- resolve a requested cold-formed section against the IS 811:1987 catalogue (WP3.3).

India programme (D3): every cold-formed member is an IS 811 section from steel_engine/is811_shapes.csv (SI, rebuilt from the
corpus structured table and thin-wall validated; quarantined rows are found:false).  An SFIA / AISI-style designator
(600S162-54, 2x362T125-33 ...) is NOT a substitute and is an ERROR here (SFIAError) -- the preflight refuses the cfg too.

    resolve_is811_label("2xCLR250X80X25X5")  -> {found, label, n_ply, built_up, h, b, c, t, A, Ix, Iy, r_min, table, ...}
    prefer_practical_is811(role="stud", h_mm=100, t_mm=2)  -> exact hit or the nearest stocked candidates (found:true,
                                                              selection="nearest_stocked"; the agent / EOR still chooses)

Nothing here invents a property: a label not in the catalogue is found:false; n_ply > 2 is found:false (IS 801 7.3 covers
two channels back to back only, is811_sections.built_up).
"""
from __future__ import annotations

import re
from typing import Any

# Framing types typically stocked for studs / portal chords / rails (IS 811 Tables 3-6, 10).
PRACTICAL_TYPES: tuple[str, ...] = ("CLR", "CLS", "CWR", "CWS", "LZ")
PORTAL_TYPES: tuple[str, ...] = ("CLR", "CLS", "CWR", "CWS")
STUD_TYPES: tuple[str, ...] = ("CLR", "CLS", "CWS", "CWR")

SFIA_RE = re.compile(r"^(?:\d+[xX])?\d{3,4}[STUCZFH]\d{3}-\d{2,3}$")


class SFIAError(ValueError):
    """An AISI / SFIA designator was offered where an IS 811 label is required (D3)."""


def _india_jurisdiction(cfg_or_j: Any) -> bool:
    if isinstance(cfg_or_j, str):
        return cfg_or_j.lower() in ("india", "in", "is", "is_bis", "bis")
    cfg = cfg_or_j or {}
    j = str(cfg.get("jurisdiction") or "").lower()
    if j in ("india", "in", "is", "is_bis", "bis"):
        return True
    plan = cfg.get("load_plan")
    return isinstance(plan, dict) and str(plan.get("jurisdiction") or "").lower() in ("india", "in", "is", "is_bis", "bis")


def looks_sfia(name: str) -> bool:
    return bool(SFIA_RE.match(str(name or "").strip()))


def parse_nx_pack(name: str | None) -> dict[str, Any]:
    """Parse ``Nx<label>`` / ``2x<label>`` built-up prefixes: {n_ply, bare, prefix, is_nx_pack, is_built_up, requested}."""
    raw = str(name or "").strip()
    lab = raw.upper().replace(" ", "")
    m = re.match(r"^(\d+)X(.+)$", lab)
    if m and not looks_sfia(raw):
        n = int(m.group(1))
        return dict(n_ply=n, bare=m.group(2), prefix="%dx" % n, is_nx_pack=n > 2, is_built_up=n >= 2, requested=raw)
    return dict(n_ply=1, bare=lab or None, prefix=None, is_nx_pack=False, is_built_up=False, requested=raw)


def resolve_is811_label(name: str) -> dict[str, Any]:
    """Exact IS 811 catalogue lookup (found:true with the SI properties) or found:false; SFIA -> SFIAError."""
    if looks_sfia(name):
        raise SFIAError("%r is an AISI / SFIA designator: not an IS 811 label and not a design basis on the India programme "
                        "(D3). Use an IS 811 label (CLR100X50X15X2, 2xCLR250X80X25X5 ...) from is811_shapes.csv." % (name,))
    parsed = parse_nx_pack(name)
    bare = parsed.get("bare") or ""
    n_ply = int(parsed.get("n_ply") or 1)
    out: dict[str, Any] = {"requested": name, "label": bare or None, "found": False, "in_catalog": False,
                           "built_up": bool(parsed.get("is_built_up")), "n_ply": n_ply,
                           "is_nx_pack": bool(parsed.get("is_nx_pack")), "source": "is811_shapes.csv (IS 811:1987, corpus structured table)"}
    if not bare:
        out["note"] = "Empty section label (found:false)."
        return out
    import is811_sections as S
    if not S.looks_is811(bare):
        out["note"] = "Not an IS 811 designation (%r): use CLR / CLS / CWR / CWS / EA / UA / HS / HRH / HRB / LZ labels." % (name,)
        return out
    if n_ply > 2:
        out["note"] = ("%d plies requested: IS 801 7.3 covers two channels back to back only (is811_sections.built_up n_ply <= 2); "
                       "found:false -- a %d-channel pack has no IS capacity route." % (n_ply, n_ply))
        return out
    try:
        p = S.props(bare)
    except KeyError as ex:
        out["note"] = str(ex)
        q = S.quarantined(bare)
        if q:
            out["quarantined"] = q
        return out
    if n_ply == 2:
        p = S.built_up(bare, 2)
    out.update(found=True, in_catalog=True, label=p.get("label") or bare, type=p.get("type"), table=p.get("table"),
               designation=p.get("designation"), h=p.get("h"), b=p.get("b"), c=p.get("c"), t=p.get("t"), Ri=p.get("Ri"),
               A=p.get("A"), mass_kg_m=p.get("mass_kg_m"), Ix=p.get("Ix"), Iy=p.get("Iy"), rx=p.get("rx"), ry=p.get("ry"),
               r_min=p.get("r_min"), Fy=None, units="mm, mm2, mm4, kg/m (SI; Fy is never in IS 811)",
               note="IS 811 catalogue hit; Fy from cfg['cfs_members']['Fy_MPa'] with its IS 1079 / IS 801 Table 2 cite.")
    return out


def prefer_practical_is811(requested: str | None = None, *, role: str = "", h_mm: float | None = None,
                           b_mm: float | None = None, t_mm: float | None = None, type_pref=None,
                           jurisdiction: Any = None, max_candidates: int = 8) -> dict[str, Any]:
    """Exact hit -> selection 'exact'; else the nearest stocked sections of the preferred types by (h, b, t) distance ->
    selection 'nearest_stocked' (candidate list; the agent / EOR chooses); nothing usable -> found:false."""
    if jurisdiction is not None and not _india_jurisdiction(jurisdiction):
        return dict(found=False, jurisdiction=jurisdiction, note="prefer_practical_is811 is an India IS 811 helper; jurisdiction is not india.")
    types = tuple(t.upper() for t in (type_pref or (
        PORTAL_TYPES if role in ("portal", "col", "raf", "rafter", "column") else
        STUD_TYPES if role in ("stud", "chord", "wall") else PRACTICAL_TYPES)))
    if requested:
        hit = resolve_is811_label(requested)          # SFIAError propagates (D3)
        if hit.get("found"):
            return dict(hit, selection="exact", role=role, type_pref=list(types))
        if not any(v is not None for v in (h_mm, b_mm, t_mm)):
            return dict(found=False, requested=requested, selection=None, role=role, type_pref=list(types),
                        note=hit.get("note") or ("IS 811 label %r not in catalogue (found:false)." % requested), exact_status=hit)
    import is811_sections as S
    cands = []
    for typ in types:
        for lab in S.list_labels(typ):
            try:
                p = S.props(lab)
            except KeyError:
                continue
            cands.append(dict(label=lab, type=p.get("type"), h=p.get("h"), b=p.get("b"), t=p.get("t"), A=p.get("A"), Ix=p.get("Ix"), table=p.get("table")))
    if not cands:
        return dict(found=False, requested=requested, role=role, type_pref=list(types), note="No IS 811 rows for type_pref=%s (found:false)." % (list(types),))
    if h_mm is None and b_mm is None and t_mm is None:
        return dict(found=False, requested=requested, selection=None, role=role, type_pref=list(types), candidates=cands[:max_candidates],
                    note="No exact IS 811 hit and no target h_mm / b_mm / t_mm supplied (found:false); sample of stocked rows attached.")

    def dist(c):
        d = 0.0
        for v, k, w in ((h_mm, "h", 1.0), (b_mm, "b", 1.0), (t_mm, "t", 25.0)):
            if v is not None and c.get(k) is not None:
                d += w * ((float(c[k]) - float(v)) / max(1.0, float(v))) ** 2
        return d
    cands.sort(key=dist)
    return dict(found=True, requested=requested, selection="nearest_stocked", role=role, type_pref=list(types),
                candidates=cands[:max_candidates], nearest=cands[0]["label"],
                note="nearest stocked IS 811 rows by (h, b, t); the agent / EOR chooses and re-runs the IS 801 checks.")
