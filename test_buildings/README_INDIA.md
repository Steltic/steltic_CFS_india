# Example briefs — steltic_CFS_india

USA AISI/ASCE CFS example briefs in this folder are **non-authoritative** templates for geometry /
OpenSees modelling patterns only. Prefer the India briefs:

- `IN_CFS_Ex1_ShearWall_4levels_Delhi.txt`
- `IN_CFS_Ex2_Portal_warehouse_Chennai_wind.txt`
- `IN_CFS_Ex3_SteelSheet_5levels_Mumbai.txt`
- `IN_CFS_Ex4_StrapBraced_6levels_Bengaluru.txt`
- `IN_CFS_Ex5_Portal_twospan_mezzanine_Hyderabad.txt`

Agents must still LIVE-retrieve IS 875 / IS 1893 into `cfg['load_plan']` every job, and ground
member checks in IS 801 / IS 811 (not AISI S100/S240/S400).

## COMPLETE-gate companions (EXAMPLE / not-for-construction)

Each India example has a matching `IN_CFS_ExN_EOR_inputs_EXAMPLE.json` fixture:

- Ex1 — manufacturer `wall_vn_*` + EOR-documented `R` (WSP shearwall)
- Ex2 — EOR-documented `R` only; wall vn N/A (portal)
- Ex3 — manufacturer `wall_vn_*` + EOR-documented `R` (steel-sheet shearwall)
- Ex4 — EOR-documented `R` + EXAMPLE strap Tn; wall vn N/A (strap-braced)
- Ex5 — EOR-documented `R` only; wall vn N/A (two-span portal + mezzanine)

Labelled EXAMPLE / not-for-construction; real jobs still LIVE-retrieve load_plan and use
project-specific cites. Proxy/`is800_omrf` R still refuses COMPLETE.

## Portal combo-path status

`steel_engine/cfs_frame.py` still contains the legacy portal solver and USA-shaped combo
labels for compatibility with portal demos. For `jurisdiction=india`, results carry an
explicit `india_combo_path: {"found": false}` status: native portal combinations must
come from LIVE IS 875 / IS 1893 RAG in `cfg['load_plan']`. No IS factors are inferred in
`cfs_frame`; practical section selection, IS 811 `Ix` OCR-to-QFM correction, and
connection/base D/Cs remain agent/EOR work.
