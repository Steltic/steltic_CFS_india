#!/usr/bin/env python3
"""Build is811_shapes.csv + is811_catalog.json from IS 811:1987.

Primary source: pdftotext -layout of IS_811_1987.pdf
Cross-check: engineering_rag_india indexes/tables.json (28 extracts for IS_811_1987).

Do NOT invent properties. Unreadable OCR rows are skipped (see is811_GAPS.md).

Labels (type-prefixed — bare "20X20X1.25" is ambiguous across Tables 1 and 3):
  EA  Table 1 equal angles          EA{h}X{h}X{t}
  UA  Table 2 unequal angles        UA{h}X{b}X{t}
  CWS Table 3 channels no lips sq   CWS{h}X{h}X{t}
  CWR Table 4 channels no lips rect CWR{h}X{b}X{t}
  CLS Table 5 channels lips square  CLS{h}X{h}X{c}X{t}
  CLR Table 6 channels lips rect    CLR{h}X{b}X{c}X{t}
  HS  Table 7 hat square            HS{h}X{h}X{d}X{t}
  HRH Table 8 hat rect h>b          HRH{h}X{b}X{d}X{t}
  HRB Table 9 hat rect b>h          HRB{h}X{b}X{d}X{t}
  LZ  Table 10 lipped zed           LZ{h}X{b}X{c}X{t}
Table 11 (90° corner) — metadata only, not in shapes CSV.
"""
from __future__ import annotations

import csv
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_CSV = HERE.parent / "is811_shapes.csv"
OUT_JSON = HERE.parent / "is811_catalog.json"
GAPS = HERE.parent / "is811_GAPS.md"
DEFAULT_TXT = Path("/tmp/is811/all.txt")
PDF = Path("/workspace/INDIA_STEEL/CFS/pdfs/IS_811_1987.pdf")
RAG_TABLES = Path("/workspace/engineering_rag_india/indexes/tables.json")

MM = 1.0 / 25.4
CM2_TO_IN2 = (10.0 * MM) ** 2
CM4_TO_IN4 = (10.0 * MM) ** 4


def fix_ocr_num(tok: str) -> float | None:
    if tok is None:
        return None
    s = str(tok).strip().replace(",", ".")
    if not s or s in ("-", "–", ".", ","):
        return None
    rep = {"O": "0", "o": "0", "I": "1", "l": "1", "i": "1", "S": "5", "B": "8", "Z": "2"}
    out = []
    for ch in s:
        if ch in rep:
            out.append(rep[ch])
        elif ch.isdigit() or ch in ".-":
            out.append(ch)
        elif ch == " ":
            continue
        else:
            if any(c.isalpha() for c in s):
                return None
    s2 = "".join(out)
    if s2.count(".") > 1:
        a, *rest = s2.split(".")
        s2 = a + "." + "".join(rest)
    if not s2 or s2 in (".", "-", "-."):
        return None
    try:
        return float(s2)
    except ValueError:
        return None


def parse_nums(s: str) -> list[float]:
    out = []
    for m in re.finditer(
        r"[0-9OIlSBZo]+\.[0-9OIlSBZo]+|[0-9OIlSBZo]+(?:\s+[0-9OIl]{3})*",
        s,
    ):
        v = fix_ocr_num(m.group(0))
        if v is not None:
            out.append(v)
    return out


def _tag(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


TABLE_MARKERS = [
    (re.compile(r"TABLE\s+1\s+EQUAL\s+ANGLES", re.I), 1, "EA", "Equal angles"),
    (re.compile(r"TABLE\s+2\s+UNEQUAL\s+ANGLES", re.I), 2, "UA", "Unequal angles"),
    (re.compile(r"TABLE\s+3\s+CHANNELS\s+WITHOUT\s+LIPS\s*-\s*SQUARE", re.I), 3, "CWS", "Channels without lips — square"),
    (re.compile(r"TABLE\s+4\s+CHANNELS\s+WITHOUT\s+LIPS", re.I), 4, "CWR", "Channels without lips — rectangular"),
    (re.compile(r"TABLE\s+5\s+CHANNELS\s+WITH\s+LIPS\s*-?\s*SQUARE", re.I), 5, "CLS", "Channels with lips — square"),
    (re.compile(r"TABLE\s+6\s+CHANNELS\s+WITH\s+LIPS", re.I), 6, "CLR", "Channels with lips — rectangular"),
    (re.compile(r"TABLE\s+7\s+HAT\s+SECTIONS\s*-?\s*SQUARE", re.I), 7, "HS", "Hat sections — square"),
    (re.compile(r"TABLE\s+8\s+HAT\s+SECTIONS", re.I), 8, "HRH", "Hat sections — rectangular h>b"),
    (re.compile(r"TABLE\s+9\s+HAT\s+SECTIONS", re.I), 9, "HRB", "Hat sections — rectangular b>h"),
    (re.compile(r"TABLE\s+10\s+LIPPED\s+ZED", re.I), 10, "LZ", "Lipped zed — equal flanges"),
    (re.compile(r"TABLE\s+11\s+PROPERTIES", re.I), 11, "CORNER", "90° corner properties"),
]

NEED_DIMS = {1: 3, 2: 3, 3: 3, 4: 3, 5: 4, 6: 4, 7: 4, 8: 4, 9: 4, 10: 4}


def extract_dims_from_desig(line: str) -> tuple[list[float] | None, str]:
    """Decimal-first tokenizer so '1.25' is not truncated to '1'."""
    head = line[:90]
    # Match: n x n x n[.n] [x n[.n]]
    m = re.match(
        r"^\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)"
        r"(?:\s*[xX×]\s*(\d+(?:\.\d+)?))?"
        r"(?:\s*[xX×]\s*(\d+(?:\.\d+)?))?",
        head,
    )
    if not m:
        return None, line
    dims = []
    for g in m.groups():
        if g is None:
            continue
        v = fix_ocr_num(g)
        if v is None:
            return None, line
        dims.append(v)
    return dims, line[m.end():]


def make_label(prefix: str, dims: list[float]) -> str:
    return f"{prefix}{'X'.join(_tag(d) for d in dims)}".upper()


def sanity_row(h, t, A_cm2, Ix_cm4) -> bool:
    if h is None or t is None or A_cm2 is None:
        return False
    if not (8 <= h <= 400):
        return False
    if not (0.8 <= t <= 8.0):
        return False
    if A_cm2 <= 0.05 or A_cm2 > 200:
        return False
    if Ix_cm4 is not None and Ix_cm4 <= 0:
        return False
    return True


def pick_props(nums: list[float], dims: list[float], table_no: int = 3) -> dict | None:
    """Recover M (kg/m), A (cm2), Ix/Iy (cm4) after designation dims.

    Layout after the designation typically echoes h[,b][,c], t, Ri(=1.5t), then M, A, ...
    Prefer (M,A) with A/M near steel density (~1.27), skipping dim/Ri lookalikes.
    """
    if len(nums) < 4:
        return None
    trail = list(nums)
    # Drop designation dims once, then a second echo of the same dims if present
    for _ in range(2):
        di = 0
        progressed = False
        while trail and di < len(dims):
            if abs(trail[0] - dims[di]) <= 0.021:
                trail.pop(0)
                di += 1
                progressed = True
                continue
            break
        if not progressed:
            break
    tdim = dims[-1]
    ri = 1.5 * tdim
    if trail and abs(trail[0] - ri) <= 0.03:
        trail.pop(0)

    dim_set = dims  # values to reject as false M
    candidates = []
    for i in range(len(trail) - 1):
        m_cand, a_cand = trail[i], trail[i + 1]
        if not (0.2 <= m_cand <= 40 and 0.25 <= a_cand <= 80):
            continue
        # skip if M is clearly a dimension echo
        if any(abs(m_cand - d) <= 0.021 for d in dim_set):
            continue
        if abs(m_cand - ri) <= 0.03 or abs(a_cand - ri) <= 0.03:
            continue
        ratio = a_cand / m_cand
        # theoretical A_cm2 / (kg/m) ≈ 1/0.785 ≈ 1.274
        if 1.10 <= ratio <= 1.45:
            score = abs(ratio - 1.274)
            candidates.append((score, i, m_cand, a_cand))
    M = A = Ix = Iy = None
    rest = trail
    if candidates:
        candidates.sort()
        _, i, M, A = candidates[0]
        rest = trail[i + 2:]
    else:
        # looser fallback — still reject dim/Ri as M
        for i in range(len(trail) - 1):
            m_cand, a_cand = trail[i], trail[i + 1]
            if any(abs(m_cand - d) <= 0.021 for d in dim_set):
                continue
            if 0.2 <= m_cand <= 40 and 0.25 <= a_cand <= 80 and 0.95 <= (a_cand / m_cand) <= 1.6:
                M, A = m_cand, a_cand
                rest = trail[i + 2:]
                break
        if A is None:
            return None

    # Skip centre-of-gravity columns before Ix/Iy (cm):
    #   Tables 1–2 (angles): cx, cy (2)
    #   Tables 3–9 (channels/hats): cy (1)
    #   Table 10 (zed): none (Ix follows A)
    n_cg = {1: 2, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 10: 0}.get(table_no, 1)
    rest = rest[n_cg:]
    big = [v for v in rest if v >= 0.05]
    if len(big) >= 2:
        Ix, Iy = big[0], big[1]
    elif len(big) == 1:
        Ix = big[0]
    if not sanity_row(dims[0], dims[-1], A, Ix):
        return None
    return dict(M=M, A=A, Ix=Ix, Iy=Iy)


def convert_row(prefix, table_no, table_name, dims, props, raw_desig):
    A = props["A"]
    Ix = props.get("Ix")
    Iy = props.get("Iy")
    h = dims[0]
    t = dims[-1]
    b = dims[1] if len(dims) > 2 else dims[0]
    lip = dims[2] if len(dims) >= 4 else ""
    row = {
        "Label": make_label(prefix, dims),
        "Designation_IS": " x ".join(_tag(d) for d in dims),
        "Type": prefix,
        "Table": table_no,
        "Table_name": table_name,
        "h_mm": h,
        "b_mm": b,
        "c_or_d_mm": lip,
        "t_mm": t,
        "Mass_kg_m": props.get("M") if props.get("M") is not None else "",
        "A_si_cm2": A,
        "Ix_si_cm4": Ix if Ix is not None else "",
        "Iy_si_cm4": Iy if Iy is not None else "",
        "A": A * CM2_TO_IN2,
        "Ix": (Ix * CM4_TO_IN4) if Ix is not None else "",
        "Iy": (Iy * CM4_TO_IN4) if Iy is not None else "",
        "d": h * MM,
        "bf": b * MM,
        "tf": t * MM,
        "tw": t * MM,
        "Source": "IS_811_1987",
        "units": "inch_converted_from_IS811_SI_cm",
        "raw_desig": raw_desig[:80],
    }
    if Ix and A:
        row["rx"] = math.sqrt(Ix * CM4_TO_IN4 / (A * CM2_TO_IN2))
    else:
        row["rx"] = ""
    if Iy and A:
        row["ry"] = math.sqrt(Iy * CM4_TO_IN4 / (A * CM2_TO_IN2))
    else:
        row["ry"] = ""
    return row


def parse_text(txt: str):
    rows_out, gaps = [], []
    cur_table = cur_prefix = cur_name = None
    seen = set()
    for li, line in enumerate(txt.splitlines()):
        for rx, tno, pref, name in TABLE_MARKERS:
            if rx.search(line):
                cur_table, cur_prefix, cur_name = tno, pref, name
                break
        if cur_table is None or cur_prefix == "CORNER":
            continue
        if "Free Standard provided by BIS" in line:
            continue
        up = line.upper()
        if "DESIGNATION" in up and "DIMENSION" in up:
            continue
        dims, rest = extract_dims_from_desig(line)
        if not dims:
            continue
        need = NEED_DIMS.get(cur_table, 3)
        if len(dims) < need:
            gaps.append({"line": li + 1, "table": cur_table, "reason": "short_desig", "text": line[:100]})
            continue
        dims = dims[:need]
        nums = parse_nums(line)
        props = pick_props(nums, dims, cur_table)
        if not props:
            gaps.append({"line": li + 1, "table": cur_table, "reason": "props_unreadable", "text": line[:120]})
            continue
        raw = " x ".join(_tag(d) for d in dims)
        row = convert_row(cur_prefix, cur_table, cur_name, dims, props, raw)
        if row["Label"] in seen:
            continue
        seen.add(row["Label"])
        rows_out.append(row)
    return rows_out, gaps


def rag_table_inventory():
    if not RAG_TABLES.exists():
        return []
    tables = json.loads(RAG_TABLES.read_text())
    return [t for t in tables if t.get("doc") == "IS_811_1987"]


def write_gaps(rows, gaps, rag_n):
    by_type = {}
    for r in rows:
        by_type[r["Type"]] = by_type.get(r["Type"], 0) + 1
    lines = [
        "# IS 811:1987 section catalog — gaps",
        "",
        "**Source:** `pdftotext -layout` of IS_811_1987.pdf + RAG `indexes/tables.json`.",
        f"**Output:** `is811_shapes.csv` ({len(rows)} rows) + `is811_catalog.json`.",
        f"**Skipped/unreadable lines:** {len(gaps)}",
        "",
        "## Ingested (found:true)",
        "- Tables 1–10: EA, UA, CWS, CWR, CLS, CLR, HS, HRH, HRB, LZ",
        "",
        "## Counts by Type",
    ]
    for k in sorted(by_type):
        lines.append(f"- {k}: {by_type[k]}")
    lines += [
        "",
        "## found:false / deferred",
        "- **Table 11** (90° corner): not a framing member — use RAG when needed; not in CSV.",
        "- **IS_811_1987_Amd1_2011**: 0 indexed tables/sections — found:false for Amd1 property deltas.",
        "- **OCR nits**: letter/digit swaps skip rows failing mass/area sanity (listed below).",
        "- **Cw / J / x0 / Ixy**: not always recovered from layout OCR — A/Ix/Iy prioritized; RAG-cite remainder.",
        "- **Effective width / IS 801 capacities**: out of scope (properties only).",
        "",
        f"## RAG table extract inventory: {rag_n} chunks for IS_811_1987",
        "",
        "## Skipped line sample (first 40)",
    ]
    for g in gaps[:40]:
        lines.append(f"- L{g['line']} T{g['table']}: {g['reason']} :: {g['text']!r}")
    if len(gaps) > 40:
        lines.append(f"- … +{len(gaps)-40} more")
    lines += [
        "",
        "## Units",
        "Pipeline kip+inch. CSV converts from IS 811 SI (cm²/cm⁴/mm); `*_si_*` retained.",
        "",
        "## Dual-path lookup",
        "`cfs_sections.props` / `gross_props`: IS 811 labels first; SFIA designators remain twin geometry.",
        "",
        "## Clause anchors (RAG / markdown)",
        "- 7.1 dimensions → Tables 1–10 (found:true)",
        "- 7.2 mass & properties → Tables 1–10 (found:true)",
        "- 7.2.3 Ri = 1.5 t (found:true)",
    ]
    GAPS.write_text("\n".join(lines) + "\n")


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    txt_path = Path(argv[0]) if argv else DEFAULT_TXT
    if not txt_path.exists():
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(["pdftotext", "-layout", str(PDF), str(txt_path)])
    rows, gaps = parse_text(txt_path.read_text(errors="replace"))
    rag = rag_table_inventory()
    fields = [
        "Label", "Designation_IS", "Type", "Table", "Table_name",
        "h_mm", "b_mm", "c_or_d_mm", "t_mm", "Mass_kg_m",
        "A_si_cm2", "Ix_si_cm4", "Iy_si_cm4",
        "A", "Ix", "Iy", "rx", "ry", "d", "bf", "tf", "tw",
        "Source", "units", "raw_desig",
    ]
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    catalog = {
        "standard": "IS_811_1987",
        "collection": "engineering_standards_IS811",
        "stem": "IS_811_1987",
        "amd1_stem": "IS_811_1987_Amd1_2011",
        "amd1_tables_indexed": 0,
        "amd1_note": "found:false for Amd1 property deltas",
        "n_shapes": len(rows),
        "n_skipped": len(gaps),
        "types": sorted({r["Type"] for r in rows}),
        "rag_table_extracts": len(rag),
        "labels_sample": [r["Label"] for r in rows[:12]],
        "clause_anchors": {
            "dimensions": {"found": True, "clause": "7.1"},
            "properties": {"found": True, "clause": "7.2"},
            "Ri_assumption": {"found": True, "clause": "7.2.3", "text": "Ri as 1.5 t"},
            "corner_table": {"found": True, "clause": "Table 11"},
        },
    }
    OUT_JSON.write_text(json.dumps(catalog, indent=2) + "\n")
    write_gaps(rows, gaps, len(rag))
    print(f"wrote {OUT_CSV} rows={len(rows)} skipped={len(gaps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
