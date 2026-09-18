# India CFS unit model (SI wave 1)

**Date:** 2026-09-18 Asia/Bangkok (UTC+7)

## Native system: **N-mm-sec**

Same as HR (`steltic_india`): force N, length mm, stress MPa, g=9810 mm/s², E=2e5 MPa.

## Boundaries

1. `india_units.apply_si_geometry(cfg)` for metric briefs (m → mm).
2. IS 811 props via `is811_sections.props` → mm (from `A_si_cm2` / `Ix_si_cm4` ×100 / ×10000).
3. SFIA designator geometry path remains inch/ksi (twin only — not IS 811 authority).
4. `load_plan` RAG gate unchanged (IS 875 / IS 1893).
5. Legacy: `units='kip-in'` / `force_kip_in=True`.

## Remaining kip islands

Report HTML kip/ksi labels; AISI S400 Ω0 scaffolding (`found:false`); SFIA tables; wall_line kip helpers.
