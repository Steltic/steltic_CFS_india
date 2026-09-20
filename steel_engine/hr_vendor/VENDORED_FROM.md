# hr_vendor — the shared India engine, vendored byte-identically from work/hr

Source: `/home/claude/rv/work/hr` (steltic_india, hot-rolled IS 800 engine)
Commit: **92799238961d237c19f90350d999e23c24519f9f** (`9279923`, "WP2.7/WP1.11/WP2.3: IS 875-4:2021 5.2.4 multilevel-roof
drift snow + 4.4 ponding screen …"), copied 2026-09-20 with `git show HEAD:steel_engine/<file>` (every file of
`steel_engine/` at that commit except `tools/`).

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
