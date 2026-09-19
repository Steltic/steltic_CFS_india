# Example briefs — steltic_CFS_india

USA AISI/ASCE CFS example briefs in this folder are **non-authoritative** templates for geometry /
OpenSees modelling patterns only. Prefer the India briefs:

- `IN_CFS_Ex1_ShearWall_4levels_Delhi.txt`
- `IN_CFS_Ex2_Portal_warehouse_Chennai_wind.txt`
- `IN_CFS_Ex3_SteelSheet_5levels_Mumbai.txt`
- `IN_CFS_Ex4_StrapBraced_6levels_Bengaluru.txt`
- `IN_CFS_Ex5_Portal_twospan_mezzanine_Hyderabad.txt`
- `IN_CFS_Ex6_WSP_5levels_Lplan_Pune.txt`
- `IN_CFS_Ex7_SteelSheet_6levels_Zplan_Surat.txt`
- `IN_CFS_Ex8_StrapBraced_4levels_Tplan_Ahmedabad.txt`
- `IN_CFS_Ex9_Podium_5over2_Uplan_Noida.txt`
- `IN_CFS_Ex10_SBMF_2levels_highbay_Nagpur.txt`
- `IN_CFS_Ex11_Gypsum_3levels_coastal_Vizag.txt`
- `IN_CFS_Ex12_SteelSheet_8levels_crossplan_Kolkata.txt`
- `IN_CFS_Ex13_TypeII_perforated_4levels_Lucknow.txt`
- `IN_CFS_Ex14_Mixed_3levels_splitlevel_Coimbatore.txt`
- `IN_CFS_Ex15_ColdStorage_portal_Srinagar.txt`

Agents must still LIVE-retrieve IS 875 / IS 1893 into `cfg['load_plan']` every job, and ground
member checks in IS 801 / IS 811 (not AISI S100/S240/S400).

## COMPLETE-gate companions (EXAMPLE / not-for-construction)

Each India example has a matching `IN_CFS_ExN_EOR_inputs_EXAMPLE.json` fixture:

- Ex1 — manufacturer `wall_vn_*` + EOR-documented `R` (WSP shearwall)
- Ex2 — EOR-documented `R` only; wall vn N/A (portal)
- Ex3 — manufacturer `wall_vn_*` + EOR-documented `R` (steel-sheet shearwall)
- Ex4 — EOR-documented `R` + EXAMPLE strap Tn; wall vn N/A (strap-braced)
- Ex5 — EOR-documented `R` only; wall vn N/A (two-span portal + mezzanine)
- Ex6 — manufacturer `wall_vn_*` + EOR-documented `R` (WSP L-plan, Pune)
- Ex7 — manufacturer `wall_vn_*` + EOR-documented `R` (steel-sheet Z-plan, Surat)
- Ex8 — EOR-documented `R` + EXAMPLE strap Tn; wall vn N/A (strap T-plan, Ahmedabad)
- Ex9 — manufacturer `wall_vn_*` + EOR-documented `R` (WSP podium 5-over-2 U-plan, Noida)
- Ex10 — EOR-documented `R` + EXAMPLE strap Tn for strap lines; wall vn N/A (SBMF highbay, Nagpur)
- Ex11 — manufacturer gypsum `wall_vn_*` (+ WSP upgrade note) + EOR-documented `R` (coastal Vizag)
- Ex12 — manufacturer `wall_vn_*` + EOR-documented `R` (steel-sheet cruciform, Kolkata)
- Ex13 — manufacturer perforated WSP `wall_vn_*` + EOR-documented `R` (Type II, Lucknow)
- Ex14 — WSP `wall_vn_*` + strap Tn + EOR-documented `R` (mixed split-level, Coimbatore)
- Ex15 — EOR-documented `R` only; wall vn N/A (cold-storage portal + snow, Srinagar)

Labelled EXAMPLE / not-for-construction; real jobs still LIVE-retrieve load_plan and use
project-specific cites. Proxy/`is800_omrf` R still refuses COMPLETE.

## Portal combo-path status (wave2 polish2)

`steel_engine/cfs_frame.py` retains the legacy portal solver for compatibility. For
`jurisdiction=india`:

- When `cfg['load_plan'].combinations` already carries LIVE IS 875 / IS 1893 RAG factors,
  `run()` consumes those rows (`india_combo_path.found=true`). No IS factors are invented
  inside `cfs_frame`.
- When load_plan lacks combinations, `india_combo_path` stays `found:false` and legacy
  ASCE-shaped labels remain scaffolding only.

## Practical IS 811 sections

`steel_engine/india_practical_sections.py` prefers stocked CLR/CLS/CWR/CWS/LZ sizes from
`is811_shapes.csv`. Missing designations → `found:false` (do not invent or silently
substitute SFIA as IS law).

## IS 811 Ix OCR → QFM

`steel_engine/india_is811_retrieval.py` exposes `seed_ix_qfm_correction_plan`,
`ix_qfm_correction_status`, and `apply_ix_from_qfm` so agents can correct noisy OCR Ix
from LIVE RAG/QFM with a cite. No invented numbers.

## Connection / anchor D/Cs

`steel_engine/india_connection_dc.py` stubs portal knee/apex and base-anchor D/C reporting.
Silent USA AISI S100/S240 defaults are refused for India; supply IS 801 / manufacturer
EOR capacity + cite (or leave `found:false`).
