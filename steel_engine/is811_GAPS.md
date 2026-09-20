# IS 811:1987 section catalogue — provenance and gaps (WP3.3)

**Source:** the India corpus structured table `documents/standards/IS_811_1987/structured/sections.csv` (SI, column-aware,
with the corpus's own `FLAG:` annotations), NOT layout OCR of the PDF. Rebuild: `python3 steel_engine/tools/build_is811_shapes.py`;
validate: `python3 steel_engine/tools/validate_is811.py steel_engine/is811_shapes.csv`.
**Output:** `is811_shapes.csv` (463 rows; columns h/b/c/t/Ri, mass, A, Cx/Cy, Ix/Iy/Iu/Iv/Ixy, rx/ry/ru/rv/r_min, tan α,
Zx/Zy/Zu/Zv, x0, J, Cw, Source, corpus_check, validator) and `is811_quarantine.csv` (11 rows). `is811_catalog.json` and
`patch_is811_ocr` are gone (US-era OCR artefacts; the old JSON is under `usa_reference/`).

## Ingested (found:true)
Tables 1–10: EA 28, UA 31, CWS 28, CWR 90, CLS 20, CLR 81, HS 24, HRH 20, HRB 6 (HRH / HRB = hat sections, Table 8 / 9), LZ 135.
Every row passed the thin-wall validator: A within 4 %, mass = 0.785 A within 2 %, Ix within 8 % of the rounded-corner
midline model (r = Ri + t/2, Ri = 1.5 t per IS 811 7.2.3), Iu + Iv = Ix + Iy within 2 % (where printed).

## Quarantine (`is811_quarantine.csv`)
* **found:false (row absent, `props()` raises KeyError with the reason):** LZ120X45X20X2 (Iuu printed 144 cm⁴ inconsistent,
  Iu+Iv ≠ Ix+Iy), LZ240X75X20X1.6 (Ix −11 % vs thin-wall, Iu+Iv ≠ Ix+Iy).
* **partial (row kept, the flagged property blanked to None):** CWR100X50X5 (Cw), CLR70X25X10X1.6 (ry), CLR70X25X15X2 (ry),
  CLR180X50X20X3.15 (J), CLR200X80X25X4 (Cw), CLR200X80X25X5 (Cw), HS30X30X10X1.6 (mass), LZ250X75X20X2.3 (tan α),
  LZ260X75X20X1.6 (mass). A check that needs the blanked property (e.g. 6.6.1.2 torsional-flexural with Cw / J) reports
  found:false for that row instead of computing with the misprint; brace the member against twist or pick the neighbour size.

## found:false / not in the catalogue
* **Table 11** (90° corner / special profiles): not a framing member — not in the CSV; RAG when needed.
* **IS_811_1987_Amd1_2011:** editorial amendment; 0 indexed tables / sections in the corpus — found:false for any Amd 1
  property delta (`india_is811_retrieval.amd1_honest_result`).
* **Yield strength:** not in IS 811 — `Fy = None` on every row; Fy comes from `cfg['cfs_members']['Fy_MPa']` with its IS 1079 /
  IS 801 Table 2 cite.
* **Effective widths / capacities:** out of scope of the catalogue (IS 801 checks in `is801_members`).
* **SFIA / AISI designators (600S162-54):** not IS 811 labels — `india_practical_sections.SFIAError`, preflight ERROR (D3).
