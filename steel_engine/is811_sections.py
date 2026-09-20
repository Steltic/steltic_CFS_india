"""is811_sections.py -- IS 811:1987 cold-formed section catalogue (India CFS), SI-native (WP3.3).

Data: steel_engine/is811_shapes.csv, rebuilt column-aware from the corpus structured table
(tools/build_is811_shapes.py; validator tools/validate_is811.py: A, M = 0.785 A, thin-wall Ix, Iu + Iv = Ix + Iy).
Rows that fail the validator or carry a corpus-flagged misprint are in is811_quarantine.csv:
`found:false` rows raise KeyError here; `partial` rows load with the misprinted property set to None.

Units: every property is returned in N-mm (mm, mm2, mm4, mm3, mm6, kg/m).  No inch path exists on the
India branch (WP3.4: "N-mm throughout with explicit units").

Labels are repo labels (prefix + h X b [X c] X t):
    EA / UA  Table 1 / 2 angles         CWS / CWR  Table 3 / 4 channels without lips
    CLS / CLR Table 5 / 6 channels with lips (studs, joists, purlins, portal members)
    HS / HRH / HRB Table 7 / 8 / 9 HAT sections (IS 811 Tables 7-9: "HAT SECTIONS"; not hollow)
    LZ Table 10 lipped zeds.  IS 811 Table 11 is not in the corpus (found:false).
IS 811 3.1 designates sections by depth x width x thickness; the prefixes are repo conventions.

Material: IS 811 5.1 -> IS 1079 steel (not lower than St 34); IS 801 Table 2 grades (yield 21/24/30/36 kgf/mm2).
`props()['Fy'] is None` -- the design grade must be declared explicitly by the job (no silent 250 MPa).
IS 811 Amd 1 (Nov 2011) is editorial only (IS 852-1985 -> IS 1852:1985 in cl. 8.5); it changes no property.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CSV_DEFAULT = _HERE / "is811_shapes.csv"
_QUAR_DEFAULT = _HERE / "is811_quarantine.csv"
_DB = None
_QUAR = None

_PREFIXES = ("EA", "UA", "CWS", "CWR", "CLS", "CLR", "HS", "HRH", "HRB", "LZ")
TYPE_TO_NAME = {
    "EA": "equal angle (IS 811 Table 1)", "UA": "unequal angle (Table 2)",
    "CWS": "channel without lips, square (Table 3)", "CWR": "channel without lips, rectangular (Table 4)",
    "CLS": "channel with lips, square (Table 5)", "CLR": "channel with lips, rectangular (Table 6)",
    "HS": "hat section, square (Table 7)", "HRH": "hat section, rectangular h > b (Table 8)",
    "HRB": "hat section, rectangular b > h (Table 9)", "LZ": "lipped zed, equal flanges (Table 10)",
}
SINGLY_SYMMETRIC = ("CWS", "CWR", "CLS", "CLR", "HS", "HRH", "HRB")     # one axis of symmetry (x-x): 6.6.1.2 applies
POINT_SYMMETRIC = ("LZ",)
NONSYMMETRIC = ("EA", "UA")
UNITS = "N-mm (mm, mm2, mm4, mm3, mm6, kg/m)"
E_MPA = 203400.0        # IS 801 6.3 / 6.6.1.1: E = 2 074 000 kgf/cm2 (verified on the PDF, p.15 / p.18)
G_MPA = 77970.0         # IS 801 6.6.1.2: G = 795 000 kgf/cm2 (PDF p.20)
KGF_CM2_TO_MPA = 0.0980665


def looks_is811(name) -> bool:
    u = str(name).upper().replace(" ", "")
    return any(u.startswith(p) for p in _PREFIXES)


def _f(v):
    if v in (None, "", "-"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _load():
    global _DB, _QUAR
    if _DB is not None:
        return _DB
    db = {}
    path = Path(os.environ.get("IS811_CSV") or _CSV_DEFAULT)
    if path.exists():
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                lab = (row.get("Label") or "").strip().upper().replace(" ", "")
                if lab:
                    db[lab] = row
    quar = {}
    qp = Path(os.environ.get("IS811_QUARANTINE_CSV") or _QUAR_DEFAULT)
    if qp.exists():
        with qp.open(newline="") as f:
            for row in csv.DictReader(f):
                quar[(row.get("Label") or "").strip().upper()] = row
    _DB, _QUAR = db, quar
    return db


def quarantined(name) -> dict | None:
    """Quarantine record {found, reason} for a label, or None."""
    _load()
    return _QUAR.get(str(name).upper().replace(" ", ""))


def list_labels(prefix: str | None = None) -> list:
    db = _load()
    return sorted(k for k in db if (prefix is None or k.startswith(prefix.upper())))


def _flats(p, ri, t):
    """Flat widths (IS 801 3 'flat-width ratio'): overall dimension minus the bends, IS 811 7.1.1 Ri = 1.5 t."""
    k = ri + t
    typ = p["type"]
    h, b, c = p["h"], p["b"], p.get("c")
    if typ in ("EA", "UA"):
        return {"leg_h": max(h - k, 0.0), "leg_b": max(b - k, 0.0)}
    if typ in ("CWS", "CWR"):
        return {"web": max(h - 2 * k, 0.0), "flange": max(b - k, 0.0)}
    if typ in ("CLS", "CLR"):
        return {"web": max(h - 2 * k, 0.0), "flange": max(b - 2 * k, 0.0), "lip": max((c or 0.0) - k, 0.0)}
    if typ in ("HS", "HRH", "HRB"):
        return {"web": max(h - 2 * k, 0.0), "flange": max(b - 2 * k, 0.0), "lip": max((c or 0.0) - k, 0.0)}
    if typ == "LZ":
        return {"web": max(h - 2 * k, 0.0), "flange": max(b - 2 * k, 0.0), "lip": max((c or 0.0) - k, 0.0)}
    return {}


def props(name: str, unit_system: str | None = None) -> dict:
    """Section properties of an IS 811 label in N-mm.  KeyError (found:false) for unknown / quarantined labels."""
    if unit_system not in (None, "N-mm", "SI", "mm"):
        raise ValueError("is811_sections.props: only N-mm properties exist on the India branch (asked %r)" % unit_system)
    lab = str(name).upper().replace(" ", "")
    db = _load()
    q = _QUAR.get(lab)
    if lab not in db:
        if q is not None:
            raise KeyError("IS 811 section %r is quarantined (found:false): %s" % (name, q.get("reason")))
        if looks_is811(lab):
            raise KeyError("IS 811 section %r not found in is811_shapes.csv (found:false -- IS 811 Tables 1-10 only; "
                           "Table 11 is not in the corpus). Do not invent properties." % (name,))
        raise KeyError("not an IS 811 label: %r" % (name,))
    r = db[lab]
    typ = r["Type"]
    p = {
        "label": lab, "designation": r.get("Designation_IS"), "type": typ, "type_name": TYPE_TO_NAME.get(typ),
        "table": r.get("Table"), "table_name": r.get("Table_name"), "pdf_page": r.get("pdf_page"),
        "h": _f(r["h_mm"]), "b": _f(r["b_mm"]), "c": _f(r["c_mm"]), "t": _f(r["t_mm"]), "Ri": _f(r["Ri_mm"]),
        "A": _f(r["A_mm2"]), "mass_kg_m": _f(r["Mass_kg_m"]),
        "Ix": _f(r["Ix_mm4"]), "Iy": _f(r["Iy_mm4"]), "Iu": _f(r["Iu_mm4"]), "Iv": _f(r["Iv_mm4"]), "Ixy": _f(r["Ixy_mm4"]),
        "rx": _f(r["rx_mm"]), "ry": _f(r["ry_mm"]), "ru": _f(r["ru_mm"]), "rv": _f(r["rv_mm"]), "r_min": _f(r["r_min_mm"]),
        "tan_alpha": _f(r["tan_alpha"]),
        "Zx": _f(r["Zx_mm3"]), "Zy": _f(r["Zy_mm3"]), "Zu": _f(r["Zu_mm3"]), "Zv": _f(r["Zv_mm3"]),
        "Cx": _f(r["Cx_mm"]), "Cy": _f(r["Cy_mm"]), "x0": _f(r["x0_mm"]), "J": _f(r["J_mm4"]), "Cw": _f(r["Cw_mm6"]),
        "Fy": None, "_Fy_found": False,
        "units": UNITS, "source": r.get("Source"), "validator": r.get("validator"), "corpus_check": r.get("corpus_check"),
        "hat": typ in ("HS", "HRH", "HRB"), "singly_symmetric": typ in SINGLY_SYMMETRIC,
        "point_symmetric": typ in POINT_SYMMETRIC, "nonsymmetric": typ in NONSYMMETRIC,
        "lipped": typ in ("CLS", "CLR", "HS", "HRH", "HRB", "LZ"),
    }
    if p["Ri"] is None and p["t"]:
        p["Ri"] = 1.5 * p["t"]                     # IS 811 7.1.1
    p["flats"] = _flats(p, p["Ri"], p["t"]) if p["t"] else {}
    p["flats_basis"] = "IS 811 7.1.1 Ri = 1.5 t (printed Ri column); flat = overall - bends"
    p["_x0_found"] = p["x0"] is not None
    p["_J_found"] = p["J"] is not None
    p["_Cw_found"] = p["Cw"] is not None
    if q is not None:
        p["quarantine_note"] = q.get("reason")
    # derived radii when the table prints none (Table 10 prints only rv)
    if p["A"]:
        for I_, k in (("Ix", "rx"), ("Iy", "ry"), ("Iu", "ru"), ("Iv", "rv")):
            if p[k] is None and p[I_] is not None:
                p[k] = (p[I_] / p["A"]) ** 0.5
        rs = [p[k] for k in ("rx", "ry", "ru", "rv") if p[k] is not None]
        p["r_min"] = min(rs) if rs else None
    return p


def next_size(name: str, direction: int = +1) -> str | None:
    """Resize hint: the next label of the same family (same type, sorted by Ix then A)."""
    lab = str(name).upper().replace(" ", "")
    db = _load()
    if lab not in db:
        return None
    typ = db[lab]["Type"]
    fam = sorted((k for k, r in db.items() if r["Type"] == typ),
                 key=lambda k: (_f(db[k]["Ix_mm4"]) or 0.0, _f(db[k]["A_mm2"]) or 0.0))
    i = fam.index(lab) + direction
    return fam[i] if 0 <= i < len(fam) else None


def built_up(name: str, n_ply: int = 2) -> dict:
    """Back-to-back pair (I-section from two channels, IS 801 7.3) or a single: n_ply in {1, 2} only.
    Doubly-symmetric when n_ply = 2 (x0 = 0); A, Ix, Iy, J, Cw scaled by n (Iy about the common web plane is the
    parallel-axis sum: 2 (Iy1 + A1 Cy^2) for channels)."""
    n = int(n_ply)
    if n not in (1, 2):
        raise ValueError("n_ply must be 1 or 2 (IS 801 7.3 two channels back to back); packs of %d plies are not "
                         "constructible (spec WP3.2)" % n)
    p = props(name)
    if n == 1:
        return dict(p, n_ply=1, designator=p["label"])
    A1, Cy = p["A"], p.get("Cy") or 0.0
    out = dict(p)
    out.update(n_ply=2, designator="2x" + p["label"], A=2 * A1, Ix=2 * p["Ix"],
               Iy=2 * (p["Iy"] + A1 * Cy ** 2) if p["Iy"] is not None else None,
               Zx=2 * p["Zx"] if p["Zx"] is not None else None,
               J=2 * p["J"] if p["J"] is not None else None, Cw=None, _Cw_found=False,
               x0=0.0, _x0_found=True, singly_symmetric=False, doubly_symmetric=True,
               mass_kg_m=2 * p["mass_kg_m"] if p["mass_kg_m"] is not None else None,
               built_up_note="two channels back to back (IS 801 7.3 connector spacing governs); Cw of the built-up "
                             "I not tabulated (found:false) -- torsional-flexural buckling not evaluated for the pair; "
                             "6.7.1 doubly-symmetric interaction applies")
    out["rx"] = (out["Ix"] / out["A"]) ** 0.5
    out["ry"] = (out["Iy"] / out["A"]) ** 0.5 if out["Iy"] else None
    out["r_min"] = min(x for x in (out["rx"], out["ry"]) if x)
    return out


def parse_designator(name: str):
    """'2xCLR100X50X15X2' -> (2, 'CLR100X50X15X2'); 'CLR100X50X15X2' -> (1, ...).  n > 2 raises (WP3.2)."""
    s = str(name).strip().upper().replace(" ", "")
    n = 1
    if "X" in s and s.split("X", 1)[0].isdigit() and not looks_is811(s):
        n, s = int(s.split("X", 1)[0]), s.split("X", 1)[1]
    if n not in (1, 2):
        raise ValueError("%r: n_ply = %d is not constructible; IS 801 7.3 covers two channels back to back (max 2)"
                         % (name, n))
    return n, s
