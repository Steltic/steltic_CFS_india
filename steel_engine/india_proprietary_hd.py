"""Proprietary hold-down / anchor product stubs (Wave B backlog #8).

Honest policy:
- Class-envelope bands (strap / bolted / rod) are OK as design scaffolding —
  they are NOT a named commercial product.
- Refuse inventing Simpson / USP / MiTek / proprietary catalogue SKUs or
  capacities as India defaults.
- Improve disclosed EOR / project substitution paths: accept
  eor_documented / project_submittal product picks WITH cite, else found:false.
"""
from __future__ import annotations

from typing import Any

# Tokens that look like invented commercial product brands / SKU families.
# Matching these as a silent capacity source → refuse.
PROPRIETARY_BRAND_TOKENS = frozenset({
    "simpson", "strongtie", "strong-tie", "strong_tie", "hdu", "s/hdu",
    "usp", "mitek", "mi-tek", "holdown", "hold-down-product",
    "phanto", "phantom",  # placeholder brand names sometimes hallucinated
    "quicktie", "tie_down_engineering", "tiedown",
})

CLASS_OK = frozenset({"strap", "bolted", "rod", "continuous_rod", "class_envelope", "envelope"})

EOR_OK = frozenset({
    "eor_documented", "eor", "eor_explicit", "documented", "explicit",
    "project_eor", "project_submittal", "submittal", "manufacturer",
    "test", "tested", "catalogue", "catalog", "deferred_submittal",
})

REFUSED_SOURCES = frozenset({
    "aisi", "s400", "s240", "s100", "usa_default", "invented", "hallucinated",
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


def _looks_proprietary_brand(text: Any) -> bool:
    s = str(text or "").lower()
    if not s:
        return False
    for tok in PROPRIETARY_BRAND_TOKENS:
        if tok.replace("_", "") in s.replace("_", "").replace("-", "").replace(" ", ""):
            return True
        if tok in s:
            return True
    return False


def refuse_invented_commercial_product(blob: dict | None = None) -> dict[str, Any]:
    """Gate: never invent a commercial HD/anchor SKU as India capacity."""
    blob = blob or {}
    product = blob.get("product") or blob.get("sku") or blob.get("model") or blob.get("name")
    source = _norm(blob.get("source") or blob.get("capacity_source"))
    invented = bool(blob.get("invented")) or source in ("invented", "hallucinated")
    brandish = _looks_proprietary_brand(product) or _looks_proprietary_brand(source)
    # Brandish alone is OK IF eor_documented + cite — inventing without cite is the refuse.
    cite = (blob.get("cite") or blob.get("cited") or "").strip()
    refuse = invented or (brandish and not cite) or (brandish and source in REFUSED_SOURCES)
    return {
        "found": False,
        "allowed": not refuse,
        "refused": refuse,
        "product": product,
        "source": source or None,
        "cite": cite or None,
        "note": (
            "Refuse inventing commercial hold-down/anchor products as India defaults. "
            "Use class envelopes (strap/bolted/rod) OR an EOR/project_submittal product "
            "with cite (manufacturer ICC-ES / IS test / project memo). Do not mint "
            "Simpson/USP/MiTek SKUs."
            if refuse else
            "Product disclosure path open — requires eor_documented/project_submittal + cite."
        ),
    }


def proprietary_hd_anchor_status(cfg: dict | None = None) -> dict[str, Any]:
    """Status for India HD/anchor product substitution (Wave B #8).

    - Class-envelope device_class without a named SKU → found:true for class path
      (capacity still from envelope / agent; product deferred).
    - Named commercial product without EOR cite → found:false + refuse invent.
    - Named product with eor_documented/project_submittal + cite → found:true disclosure.
    """
    cfg = cfg or {}
    if not _india(cfg):
        return dict(
            found=False,
            jurisdiction=cfg.get("jurisdiction"),
            note="proprietary_hd_anchor_status is an India helper.",
        )

    out: dict[str, Any] = {
        "found": False,
        "jurisdiction": "india",
        "path": None,
        "device_class": None,
        "product": None,
        "source": None,
        "cited": None,
        "invented_commercial_refused": False,
        "cfg_hooks": {
            "hd_product": "dict product/sku/source/cite/capacity for EOR substitution",
            "holddown_eor": "same; or per-slot in holddowns[] / anchorage[]",
            "device_class": "strap|bolted|rod — class envelope (no SKU invent)",
            "deferred_hd_submittal": "bool — product deferred to shop drawings",
        },
        "note": None,
    }

    # Collect fills
    fills: list[dict] = []
    for key in ("hd_product", "holddown_eor", "anchor_product", "hd_anchor_eor",
                "proprietary_hd"):
        blob = cfg.get(key)
        if isinstance(blob, dict):
            fills.append(dict(blob))
        elif isinstance(blob, list):
            fills.extend(dict(x) for x in blob if isinstance(x, dict))

    # Also scan cfg holddowns / anchorage if present on a package-like cfg
    for key in ("holddowns", "anchorage"):
        rows = cfg.get(key) or []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and (
                    row.get("product") or row.get("sku") or row.get("hd_product")
                    or row.get("source") or row.get("device_class")
                ):
                    fills.append(dict(row))

    # Class-only path from cfg
    device_class = _norm(
        cfg.get("device_class")
        or cfg.get("hd_device_class")
        or (fills[0].get("device_class") if fills else None)
    )
    if device_class in CLASS_OK and not fills:
        out.update(
            found=True,
            path="class_envelope",
            device_class=device_class,
            note=(
                "Hold-down/anchor as class envelope (%s) — no proprietary SKU invented. "
                "EOR may substitute a specific product via deferred submittal + cite."
                % device_class
            ),
            deferred_submittal=bool(cfg.get("deferred_hd_submittal", True)),
        )
        return out

    if not fills and cfg.get("deferred_hd_submittal"):
        out.update(
            found=True,
            path="deferred_submittal",
            note=(
                "HD/anchor product deferred to shop drawings / EOR submittal "
                "(found:true disclosure). Class envelopes remain the analysis basis; "
                "do not invent commercial SKUs in the calc package."
            ),
            deferred_submittal=True,
        )
        return out

    if not fills:
        out.update(
            found=False,
            path="ungrounded",
            note=(
                "No HD/anchor product or class disclosure (found:false). "
                "Set device_class=strap|bolted|rod, deferred_hd_submittal=True, or "
                "hd_product={product,source=eor_documented|project_submittal,cite,...}. "
                "Refuse inventing Simpson/USP/etc. SKUs."
            ),
        )
        return out

    # Evaluate fills — any invented brand without cite fails the package status
    accepted = []
    refused = []
    for fill in fills:
        product = fill.get("product") or fill.get("sku") or fill.get("model") or fill.get("name")
        source = _norm(fill.get("source") or fill.get("capacity_source") or fill.get("R_source"))
        cite = (fill.get("cite") or fill.get("cited") or fill.get("R_cite") or "").strip()
        dclass = _norm(fill.get("device_class"))
        gate = refuse_invented_commercial_product(fill)

        # Pure class on a row
        if dclass in CLASS_OK and not product:
            accepted.append({
                "path": "class_envelope",
                "device_class": dclass,
                "found": True,
                "note": "Class envelope row — no SKU.",
            })
            continue

        if gate["refused"] or (product and _looks_proprietary_brand(product) and not cite):
            refused.append({
                "product": product,
                "source": source,
                "found": False,
                "note": gate["note"],
            })
            continue

        if source in REFUSED_SOURCES:
            refused.append({
                "product": product,
                "source": source,
                "found": False,
                "note": "Source %r refused for India HD/anchor (not eor/manufacturer)." % source,
            })
            continue

        if product and source in EOR_OK and cite:
            accepted.append({
                "path": "eor_project_product",
                "product": product,
                "source": source,
                "cited": cite,
                "capacity": fill.get("capacity") or fill.get("Tn") or fill.get("Rn"),
                "found": True,
                "note": (
                    "EOR/project HD/anchor product disclosed with cite — not an invented "
                    "default. Verify manufacturer data against demand."
                ),
            })
            continue

        if product and not cite:
            refused.append({
                "product": product,
                "source": source,
                "found": False,
                "note": (
                    "Named HD/anchor product without cite (found:false). "
                    "Provide eor_documented/project_submittal cite or drop to class envelope."
                ),
            })
            continue

        if dclass in CLASS_OK:
            accepted.append({
                "path": "class_envelope",
                "device_class": dclass,
                "found": True,
                "cited": cite or None,
                "note": "Class envelope with optional cite.",
            })
            continue

        refused.append({
            "product": product,
            "source": source,
            "found": False,
            "note": "HD/anchor fill incomplete (found:false).",
        })

    out["slots"] = accepted + refused
    out["invented_commercial_refused"] = bool(refused) and not accepted
    if accepted and not refused:
        primary = accepted[0]
        out.update(
            found=True,
            path=primary.get("path"),
            device_class=primary.get("device_class"),
            product=primary.get("product"),
            source=primary.get("source"),
            cited=primary.get("cited"),
            note=primary.get("note"),
        )
        return out
    if accepted and refused:
        out.update(
            found=False,
            path="mixed",
            note=(
                "Some HD/anchor slots accepted, but proprietary/invented rows refused "
                "(found:false overall until refused slots are fixed or dropped to class)."
            ),
            accepted=accepted,
            refused=refused,
        )
        return out

    out.update(
        found=False,
        path="refused",
        invented_commercial_refused=True,
        refused=refused,
        note=(
            refused[0]["note"] if refused else
            "Proprietary HD/anchor invent path refused (found:false)."
        ),
    )
    return out


def rag_query_plan_hd_anchor(cfg: dict | None = None) -> list[dict[str, Any]]:
    """Hooks — India codes do not catalogue proprietary HD SKUs."""
    return [
        {
            "stem": "IS_801_1975",
            "query": "anchorage hold down overturning uplift",
            "purpose": "is801_anchorage_general",
            "type": "fts",
            "found": None,
            "note": "General anchorage — not a product catalogue. Prefer class + EOR submittal.",
        },
        {
            "stem": "IS_456_2000",
            "query": "anchor bolt cast-in anchorage to concrete",
            "purpose": "concrete_anchorage_handoff",
            "type": "fts",
            "found": None,
            "note": "Concrete anchorage detailing is foundation-engineer scope.",
        },
    ]
