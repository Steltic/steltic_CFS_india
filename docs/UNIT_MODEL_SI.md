# India HR unit model (SI wave 2)

**Date:** 2026-09-18 Asia/Bangkok (UTC+7)

## Native system: **N-mm-sec**

| Quantity | Engine unit | Typical display |
|----------|-------------|-----------------|
| Force | N | kN |
| Length | mm | m (plan/story); mm (member) |
| Moment | N·mm | kN·m |
| Stress | MPa (= N/mm²) | MPa |
| Pressure (gravity) | kN/m² | kN/m² |
| Mass (OpenSees) | tonne (= N·s²/mm) | t |
| g | 9810 mm/s² | |
| E_steel | 200000 MPa | |
| G_steel | E/2.6 ≈ 76923 MPa | |

## Boundaries

1. **Brief → engine:** `india_units.apply_si_geometry(cfg)` (alias `apply_metric_geometry`) converts m → mm when `units` is metric/SI/m/mm. Sets `cfg['units']='N-mm'` and `engine3d.activate_si_units()`.
2. **load_plan RAG:** provenance strings stay in the units the standard cites (usually SI). Do not rewrite RAG text.
3. **Sections:** IS 808 / IS 1161 prefer `A_si_mm2`, `Izz_si_mm4`, `Iyy_si_mm4`; otherwise inch×25.4^n.
4. **Legacy kip-in:** `units='kip-in'` or `force_kip_in=True` → `apply_metric_geometry_legacy_kip_in`.
5. **Reports / CSV (wave 2):** HTML and `member_schedule.csv` use SI labels (kN, mm, kN·m, MPa) via `india_units.display_scale` / `demand_field_names`. Engine numbers stay N / N·mm; display divides by 1000 / 1e6.

## Remaining kip islands

See `india_units.KIP_ISLANDS`. USA archetype CFGs and AISC shape CSV fallbacks remain inch; India briefs do not use them.


## CFS package (WP3, 2026-09-20)

| Layer | Units | Note |
|---|---|---|
| cfg (brief-facing) | m, kN/m², m/s, mm for member dimensions | `cfg['units'] = 'm'`, `jurisdiction = 'india'`; no feet / psf / kip |
| IS 811 catalogue (`is811_sections`) | mm, mm², mm⁴, mm⁶, kg/m | SI-native from the corpus structured table; E 203 400 MPa, G 77 970 MPa (= IS 801 kgf/cm² values × 0.0980665) |
| IS 801 checks (`is801_members`) | internal kgf/cm², cm, kgf (the code's own constants: E 2 074 000, G 795 000 kgf/cm²) | every public function takes / returns SI (MPa, mm, N, N-mm) and records the kgf/cm² values used |
| Hot-rolled lateral frame (`hr_vendor`) | N-mm (vendored India HR engine) | forces to the CFS package in kN via `india_cfs_lateral` |
| All-CFS portal (`india_cfs_portal`) | N-mm | pressures kN/m² → N/mm² at the frame tributary; results reported kN / mm |
| Report (`report_cfs_india._set_report_units`) | kN, m, mm, MPa, kN/m (diaphragm) | no US units anywhere (consistency check greps) |
