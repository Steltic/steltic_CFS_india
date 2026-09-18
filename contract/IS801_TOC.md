# IS 801:1975 + IS 811:1987 — agent TOC pointer (India CFS)

Authoritative text lives in the **India RAG corpus**, not in this repo.

| Stem | Collection | Role |
|------|------------|------|
| `IS_801_1975` | `engineering_standards_IS801` | Code of practice — cold-formed light gauge steel members in general building construction (primary design provisions) |
| `IS_811_1987` | `engineering_standards_IS811` | Cold-formed light gauge structural steel sections — dimensions / properties |
| `IS_811_1987_Amd1_2011` | `engineering_standards_IS811_Amd1` | Amendment 1 — **may have 0 indexed sections**; `found:false` is honest |

Use `search_engineering_standards` with `doc=` / `collection=` and `clause` / FTS. Do not invent clause text.
Do **not** cite AISI S100/S240/S400 or AISC 360/341 for India CFS member design.

Loads (separate, **mandatory every job**): `IS_875_Part_*`, `IS_1893_Part_1_2016` → write into `cfg['load_plan']`.

The former `AISI_TOC.md` from USA `steltic_cfs` is **non-authoritative** on this branch (kept only as a USA twin reference).


## Section catalog (this repo)

- `steel_engine/is811_shapes.csv` + `is811_catalog.json` — Tables 1–10 properties (dual-path via `is811_sections` / `cfs_sections.gross_props`)
- Gaps / Amd1: `steel_engine/is811_GAPS.md` (`found:false` where OCR/Amd1 missing)
- Rebuild: `python3 steel_engine/tools/build_is811_shapes.py`
