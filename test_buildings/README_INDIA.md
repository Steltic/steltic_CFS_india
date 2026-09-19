# Example briefs — steltic_CFS_india

USA AISI/ASCE CFS example briefs in this folder are **non-authoritative** templates for geometry /
OpenSees modelling patterns only. Prefer the India briefs:

- `IN_CFS_Ex1_ShearWall_4levels_Delhi.txt`
- `IN_CFS_Ex2_Portal_warehouse_Chennai_wind.txt`

Agents must still LIVE-retrieve IS 875 / IS 1893 into `cfg['load_plan']` every job, and ground
member checks in IS 801 / IS 811 (not AISI S100/S240/S400).

## COMPLETE-gate companions (EXAMPLE / not-for-construction)

- `IN_CFS_Ex1_EOR_inputs_EXAMPLE.json` — manufacturer `wall_vn_*` + `R`/`R_source=eor_documented`/`R_cite`
  so CI can exercise C7 COMPLETE without inventing IS 801 vn tables or IS 800 OMRF R.
  Labelled EXAMPLE / not-for-construction; real jobs still LIVE-retrieve load_plan and use
  project-specific cites. Proxy/`is800_omrf` R still refuses COMPLETE.
