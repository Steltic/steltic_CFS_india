# hr_vendor — the shared India engine, vendored byte-identically from work/hr

Source: steltic_india (hot-rolled IS 800 engine), branch steltic_india main (PEB variations merged)
Commit: **c7c9cc9e65b0efdbb8502ede3f8fb6022c5e92c6** [steltic_india main, PEB variations merged] (copied with `git show c7c9cc9:steel_engine/<path>` by scripts/revendor_hr.py, 2026-10-23)

**2026-10 re-sync:** the vendored files were rewritten together with `steltic_india` branch `fix/2026-10-peb-briefs` (the 2026-10 renumbering of the example briefs: brief ids in comments, docstrings and one message string; no logic change). Merged steltic_india commit: **083a500845e04566a3b3dfc5be79e494498c3ef1**.

**2026-10 PEB re-sync:** rewritten together with `steltic_india` branch `fix/2026-10-peb-tapered` (the PEB release: welded and web-tapered portal frames). Ten files changed (design_pipeline, engine3d, india_combos, india_connections, india_is800, india_is800_s12, report_india, roof_geometry, sections, static_model) and four are new (peb_build, peb_checks, peb_outputs, peb_report). The CFS gold runs are unchanged (gold pack REGRESSION_2026-10.md). Merged steltic_india commit: **083a500845e04566a3b3dfc5be79e494498c3ef1**.

**2026-10 first-wave re-sync:** rewritten from steltic_india commit 54e7463 (branch `fix/2026-10-first-wave`): HR-1 (`consistency._gather_uncomputed_text` skips `delegated_criteria` / `delegated_item`), HR-2 (the IS 1893 Table 8 floor-area row text), HR-3 (codes table IS 875 (Part 4):2021), collateral / PV non-permanent dead loads, crane bracket, STAAD load export and report clean-up. 14 files changed and 3 are new (`crane_bracket.py`, `report_first_wave.py`, `staad_loads.py`); 52 files in all. Earlier pin: 69701f6070706e5d2adc6fefaea16b42c9f4e221. `scripts/check_vendored.py` now compares against the pinned commit (`git show <commit>:steel_engine/<path>`), not the live HR working tree.

**2026-10 first-wave re-sync 2:** from 9f3cd6f -- `consistency._DELEGATED_KEYS` also skips `delegated_design` (the register copied into capacity_design); only consistency.py changed (52 files).

**2026-10-23 re-sync (scripts/revendor_hr.py):** from dd1d8c1 (fix/2026-10-second-wave) -- rewritten (2): `consistency.py`, `report_india.py`; new (1): `report_second_wave.py`; every other file byte-identical.

**2026-10-23 re-sync (scripts/revendor_hr.py):** from c7c9cc9 (steltic_india main (PEB variations merged)) -- rewritten (7): `design_pipeline.py`, `engine3d.py`, `india_is800.py`, `india_is800_s12.py`, `peb_checks.py`, `pipeline.py`, `report_second_wave.py`; new (2): `peb_autosize.py`, `peb_levers.py`; every other file byte-identical.

Rules (IMPL_BRIEF conventions, spec WP1.14):
- Every file in this folder is byte-identical to `work/hr/steel_engine/<same path>` at the commit above.
  `python3 scripts/check_vendored.py` compares sha256 per file and fails on any difference.
- **No CFS-specific edit is ever written here.** CFS behaviour lives in the cfs-only modules of
  `steel_engine/` (`india_cfs_*.py`, `is801_members.py`, `is811_sections.py`, `report_cfs_india.py`, …).
- The lead re-syncs this folder from work/hr at integration time (`scripts/check_vendored.py --sync` prints the
  copy commands; it never copies on its own).

How the CFS repo uses it:
- **In process** (`import india_cfs_env` appends this folder to `sys.path` *after* `steel_engine/`): the shared
  load / seismic / wind / combination / unit core (`india_loads`, `india_seismic`, `india_units`,
  `india_wind_tables`, `india_combos`, `india_seismic_gates`, `india_is800`, `sections` = IS 808 / IS 1161 DB …)
  is imported from here — there is no second copy of any shared module in the CFS repo.
- **In a subprocess** (`india_cfs_lateral.run_lateral`): the hot-rolled IS 800 §12 lateral frame of a CFS job is
  analysed and checked by the complete HR India pipeline (`pipeline.design_and_report` → `design_pipeline.design_india`
  → `report_india`, `india_seismic_gates.design_status`) with this folder as `sys.path[0]`, so the HR modules named
  `preflight`, `consistency`, `report`, `pipeline` never collide with the CFS modules of the same name.
