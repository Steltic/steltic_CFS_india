# hr_vendor — the shared India engine, vendored byte-identically from work/hr

Source: steltic_india (hot-rolled IS 800 engine), branch fix/2026-09-review
Commit: **1a8f988aae125649ad2f6a3f4262b37072ab1fab** (steltic_india fix/2026-09-review, 2026-09-26, after the 2026-09 review fixes), copied with every file of `steel_engine/` except `tools/` and `__pycache__/`. After the steltic_india PR merges, re-run `scripts/check_vendored.py` against the merged checkout and record the merged commit here.

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
