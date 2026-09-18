"""IS 811:1987 cold-formed section catalog lookup (India CFS).

Dual-path with cfs_sections:
  1. IS 811 labels (EA/UA/CWS/CWR/CLS/CLR/HS/HRH/HRB/LZ…) from is811_shapes.csv
  2. SFIA / geometry designators via cfs_sections (non-authoritative twin for India jobs)

Missing labels → KeyError with found:false guidance (do not invent properties).
Amd1 (IS_811_1987_Amd1_2011): 0 indexed tables — see is811_GAPS.md.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CSV_DEFAULT = _HERE / "is811_shapes.csv"
_DB = None
_DB_PATH = None

_PREFIXES = ("EA", "UA", "CWS", "CWR", "CLS", "CLR", "HS", "HRH", "HRB", "LZ")


def _csv_path() -> Path | None:
    env = os.environ.get("IS811_CSV")
    if env and Path(env).exists():
        return Path(env)
    return _CSV_DEFAULT if _CSV_DEFAULT.exists() else None


def looks_is811(name: str) -> bool:
    u = str(name).upper().replace(" ", "")
    return any(u.startswith(p) for p in _PREFIXES)


def _load():
    global _DB, _DB_PATH
    path = _csv_path()
    if _DB is not None and _DB_PATH == str(path):
        return _DB
    db = {}
    if not path:
        _DB, _DB_PATH = db, None
        return db
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            lab = (row.get("Label") or "").strip().upper().replace(" ", "")
            if not lab:
                continue

            def g(*keys):
                for k in keys:
                    v = row.get(k)
                    if v not in (None, "", "-"):
                        try:
                            return float(v)
                        except ValueError:
                            pass
                return None

            entry = dict(
                A=g("A"), Ix=g("Ix"), Iy=g("Iy"), rx=g("rx"), ry=g("ry"),
                d=g("d"), bf=g("bf"), tf=g("tf"), tw=g("tw"),
                h_mm=g("h_mm"), b_mm=g("b_mm"), t_mm=g("t_mm"),
                Mass_kg_m=g("Mass_kg_m"),
                A_si_cm2=g("A_si_cm2"), Ix_si_cm4=g("Ix_si_cm4"), Iy_si_cm4=g("Iy_si_cm4"),
                Type=row.get("Type"), Table=row.get("Table"),
                Designation_IS=row.get("Designation_IS"),
                Source=row.get("Source") or "IS_811_1987",
                label=lab,
            )
            db[lab] = entry
            des = (row.get("Designation_IS") or "").strip().upper().replace(" ", "")
            # Secondary index: type+compact desig without prefix collision handling via Type
            if des:
                alt = f"{row.get('Type', '')}{des}".upper().replace(" ", "")
                db.setdefault(alt, entry)
    _DB, _DB_PATH = db, str(path)
    return db


def props(name: str, unit_system: str | None = None) -> dict:
    """Return property dict for an IS 811 label (N-mm default; kip-in on request)."""
    lab = str(name).upper().replace(" ", "")
    db = _load()
    if lab not in db:
        if looks_is811(lab):
            raise KeyError(
                f"IS 811 section {name!r} not found in is811_shapes.csv "
                f"(found:false for this designation — see is811_GAPS.md / RAG IS_811_1987). "
                f"Do not invent properties or substitute an SFIA stud."
            )
        raise KeyError(f"not an IS 811 label: {name!r}")
    raw = dict(db[lab])
    try:
        from india_units import active_unit_system
        us = unit_system or active_unit_system()
    except Exception:
        us = unit_system or "N-mm"
    if us != "N-mm":
        raw["_units"] = "in"
        return raw
    mm = 25.4
    out = dict(raw)
    if raw.get("A_si_cm2") is not None:
        out["A"] = raw["A_si_cm2"] * 100.0  # cm² → mm²
    elif raw.get("A") is not None:
        out["A"] = raw["A"] * mm**2
    if raw.get("Ix_si_cm4") is not None:
        out["Ix"] = raw["Ix_si_cm4"] * 10000.0  # cm⁴ → mm⁴
    elif raw.get("Ix") is not None:
        out["Ix"] = raw["Ix"] * mm**4
    if raw.get("Iy_si_cm4") is not None:
        out["Iy"] = raw["Iy_si_cm4"] * 10000.0
    elif raw.get("Iy") is not None:
        out["Iy"] = raw["Iy"] * mm**4
    for key, power in (("rx", 1), ("ry", 1), ("d", 1), ("bf", 1), ("tf", 1), ("tw", 1)):
        if raw.get(key) is not None:
            out[key] = raw[key] * (mm ** power)
    # prefer native mm dims when present
    if raw.get("h_mm") is not None:
        out["d"] = raw["h_mm"]
    if raw.get("b_mm") is not None:
        out["bf"] = raw["b_mm"]
    if raw.get("t_mm") is not None:
        out["tf"] = raw["t_mm"]
        out["tw"] = raw["t_mm"]
    out["_units"] = "mm"
    return out


def list_is811(prefix: str | None = None) -> list[str]:
    db = _load()
    labs = sorted({v["label"] for v in db.values() if v.get("label")})
    if prefix:
        p = prefix.upper()
        labs = [x for x in labs if x.startswith(p)]
    return labs


def catalog_meta() -> dict:
    import json
    p = _HERE / "is811_catalog.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"found": False, "note": "is811_catalog.json missing — run tools/build_is811_shapes.py"}
