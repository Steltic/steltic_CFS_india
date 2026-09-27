#!/usr/bin/env python3
"""build_is811_shapes.py -- rebuild steel_engine/is811_shapes.csv from the corpus structured table (WP3.3).

Source (column-aware, per IS 811 Table 1-10, already consistency-checked by the corpus build):
    <INDIA_CORPUS_ROOT>/documents/standards/IS_811_1987/structured/sections.csv
(INDIA_CORPUS_ROOT: your IS corpus, built in the Steltic hub from your licensed BIS PDFs; unset, a sibling corpus folder
 is tried; override the file with IS811_CORPUS_CSV).  IS 811 Table 11 is not in the corpus and is not built.

Output columns are SI (mm, mm2, mm4, mm3, mm6, kg/m).  Every row is validated here a second time
(steel_engine/tools/validate_is811.py rules: A vs thin-wall geometry, M = 0.785 A, thin-wall Ix, Iu + Iv = Ix + Iy);
rows failing any rule, and rows the corpus flags as misprints, are written to is811_quarantine.csv with `found:false`
and are NOT loaded by is811_sections.props() (KeyError).

Label convention (repo labels, not IS 811 designations -- IS 811 3.1 designates by depth x width x thickness):
    Table 1 EA, 2 UA, 3 CWS, 4 CWR, 5 CLS, 6 CLR, 7 HS, 8 HRH (hat, h > b), 9 HRB (hat, b > h), 10 LZ
    e.g. CLR100X50X15X2  = IS 811 Table 6 channel with lips 100 x 50 x 15 x 2.00

Usage:  python3 steel_engine/tools/build_is811_shapes.py [--check-only]
"""
from __future__ import annotations
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from validate_is811 import validate_row  # noqa: E402

_REPO = os.path.dirname(ENGINE)
_CORPUS_ROOT = os.environ.get("INDIA_CORPUS_ROOT") or os.path.join(os.path.dirname(_REPO), "engineering_rag_india")
CORPUS_CSV = os.environ.get("IS811_CORPUS_CSV",
                            os.path.join(_CORPUS_ROOT, "documents", "standards", "IS_811_1987", "structured", "sections.csv"))
OUT = os.path.join(ENGINE, "is811_shapes.csv")
QUAR = os.path.join(ENGINE, "is811_quarantine.csv")

PREFIX = {"1": "EA", "2": "UA", "3": "CWS", "4": "CWR", "5": "CLS", "6": "CLR", "7": "HS", "8": "HRH", "9": "HRB", "10": "LZ"}
TABLE_NAME = {"1": "Equal angles", "2": "Unequal angles", "3": "Channels without lips (square)",
              "4": "Channels without lips (rectangular)", "5": "Channels with lips (square)",
              "6": "Channels with lips (rectangular)", "7": "Hat sections - square",
              "8": "Hat sections - rectangular h > b", "9": "Hat sections - rectangular b > h",
              "10": "Lipped zed sections (equal flanges)"}
TYPE_NAME = {"EA": "equal angle", "UA": "unequal angle", "CWS": "channel without lips", "CWR": "channel without lips",
             "CLS": "channel with lips", "CLR": "channel with lips", "HS": "hat section", "HRH": "hat section",
             "HRB": "hat section", "LZ": "lipped zed"}

COLS = ["Label", "Designation_IS", "Type", "Table", "Table_name", "pdf_page", "h_mm", "b_mm", "c_mm", "t_mm", "Ri_mm",
        "Mass_kg_m", "A_mm2", "Cx_mm", "Cy_mm", "Ix_mm4", "Iy_mm4", "Iu_mm4", "Iv_mm4", "Ixy_mm4", "rx_mm", "ry_mm",
        "ru_mm", "rv_mm", "r_min_mm", "tan_alpha", "Zx_mm3", "Zy_mm3", "Zu_mm3", "Zv_mm3", "x0_mm", "J_mm4", "Cw_mm6",
        "Source", "corpus_check", "validator"]


def _num(v):
    if v in (None, "", "-"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _fmt_t(t):
    s = ("%.2f" % t).rstrip("0").rstrip(".")
    return s


def label_for(row):
    p = PREFIX[row["table"]]
    h, b, t = _num(row["h"]), _num(row["b"]), _num(row["t"])
    c = _num(row["c"])
    parts = [str(int(round(h))), str(int(round(b)))]
    if c is not None and p not in ("EA", "UA", "CWS", "CWR"):
        parts.append(str(int(round(c))))
    parts.append(_fmt_t(t))
    return p + "X".join(parts)


def build(check_only=False):
    rows = list(csv.DictReader(open(CORPUS_CSV, newline="")))
    out, quar = [], []
    seen = set()
    for r in rows:
        if r["table"] not in PREFIX:
            continue
        lab = label_for(r)
        if lab in seen:
            quar.append((lab, r["designation"], r["table"], "false", "duplicate label"))
            continue
        seen.add(lab)
        p = PREFIX[r["table"]]
        rec = {
            "Label": lab, "Designation_IS": r["designation"], "Type": p, "Table": r["table"],
            "Table_name": TABLE_NAME[r["table"]], "pdf_page": r.get("pdf_page"),
            "h_mm": _num(r["h"]), "b_mm": _num(r["b"]), "c_mm": _num(r["c"]), "t_mm": _num(r["t"]), "Ri_mm": _num(r["Ri"]),
            "Mass_kg_m": _num(r["mass_kg_m"]), "A_mm2": _num(r["A_mm2"]), "Cx_mm": _num(r["Cx"]), "Cy_mm": _num(r["Cy"]),
            "Ix_mm4": _num(r["Ixx_mm4"]), "Iy_mm4": _num(r["Iyy_mm4"]), "Iu_mm4": _num(r["Iuu_mm4"]), "Iv_mm4": _num(r["Ivv_mm4"]),
            "Ixy_mm4": _num(r["Ixy_mm4"]), "rx_mm": _num(r["rxx"]), "ry_mm": _num(r["ryy"]), "ru_mm": _num(r["ruu"]),
            "rv_mm": _num(r["rvv"]), "tan_alpha": _num(r["tan_alpha"]), "Zx_mm3": _num(r["Zx"]), "Zy_mm3": _num(r["Zy"]),
            "Zu_mm3": _num(r["Zu"]), "Zv_mm3": _num(r["Zv"]), "x0_mm": _num(r["x0"]), "J_mm4": _num(r["J_mm4"]),
            "Cw_mm6": _num(r["Cw_mm6"]), "Source": "IS_811_1987 (corpus structured/sections.csv, p.%s)" % r.get("pdf_page"),
            "corpus_check": r.get("check") or "",
        }
        # derived: rx/ry from I/A when the table does not print them (Table 10 prints only rv); r_min
        A = rec["A_mm2"]
        if A:
            for I_, k in (("Ix_mm4", "rx_mm"), ("Iy_mm4", "ry_mm"), ("Iu_mm4", "ru_mm"), ("Iv_mm4", "rv_mm")):
                if rec[k] is None and rec[I_] is not None:
                    rec[k] = round((rec[I_] / A) ** 0.5, 3)
        rs = [rec[k] for k in ("rx_mm", "ry_mm", "ru_mm", "rv_mm") if rec[k] is not None]
        rec["r_min_mm"] = min(rs) if rs else None
        v = validate_row(rec)
        rec["validator"] = v["status"]
        flagged = str(rec["corpus_check"]).upper().startswith("FLAG")
        fl = rec["corpus_check"].lower()
        only_mass = v["status"] != "PASS" and all(f.startswith("M ") for f in v["failures"]) and "mass" in fl
        if v["status"] != "PASS" and not only_mass:
            quar.append((lab, r["designation"], r["table"], "false",
                         ("corpus: " + rec["corpus_check"] + "; " if flagged else "") + "; ".join(v["failures"])))
            continue
        if flagged:
            # corpus-flagged misprint in ONE printed property: keep the row, blank that property (found:false for it)
            blanked = []
            for key, col in (("cw", "Cw_mm6"), (" j ", "J_mm4"), ("ryy", "ry_mm"), ("mass", "Mass_kg_m"), ("iuu", "Iu_mm4"),
                             ("tan(theta)", "tan_alpha")):
                if key in fl:
                    rec[col] = None
                    blanked.append(col)
            rec["validator"] = "PASS (corpus-flagged misprint blanked: %s)" % ",".join(blanked)
            quar.append((lab, r["designation"], r["table"], "partial (row kept, %s = None)" % ",".join(blanked),
                         "corpus: " + rec["corpus_check"]))
        out.append(rec)
    if check_only:
        print("rows %d, kept %d, quarantined %d" % (len(rows), len(out), len(quar)))
        for q in quar:
            print("  QUARANTINE", q)
        return out, quar
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for rec in out:
            w.writerow({k: ("" if rec.get(k) is None else rec.get(k)) for k in COLS})
    with open(QUAR, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Label", "Designation_IS", "Table", "found", "reason"])
        for lab, des, tab, found, why in quar:
            w.writerow([lab, des, tab, found, why])
    print("wrote %s (%d rows) and %s (%d rows)" % (OUT, len(out), QUAR, len(quar)))
    return out, quar


if __name__ == "__main__":
    build(check_only="--check-only" in sys.argv)
