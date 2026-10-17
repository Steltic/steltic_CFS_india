# steltic-cfs-india — 2026-10 first wave (review of the published CFS examples)

Branch `fix/2026-10-first-wave`. Scope: review D (cold-formed) items 1–9 of the first-wave brief, plus the lead's
item 5 request (collateral / PV as named non-permanent dead loads). `steel_engine/hr_vendor/` is **not** edited; the
root causes that live there are listed at the end for the HR repo.

## Results that change for existing jobs

- **No declared bracing = unbraced (review item 3).** A purlin / girt free flange is braced only by a declared
  `bracing` system (`{type: sag_rods | bridging | fly_braces | straps | blocking, lines, spacing_mm, ...}`) or the
  legacy PEB `sag_rods: <number of lines>`. An `L_unbraced_mm` without a bracing system is no longer used: the free
  flange is checked over the span, and the record says so. Joists are deck-restrained only when
  `compression_flange_restrained: true` is declared. The CFS golds and the Ex3 test fixture now declare their
  bracing explicitly; the PEB secondary jobs (`sag_rods: n`) are unchanged.
- **CFS status inherits the frame report (review item 4).** The numerical self-consistency list of the linked hot-rolled
  frame report ("N item(s) to reconcile") and any frame connection without an evaluated capacity are now open items of
  the CFS design status. With the current vendored HR engine every CFS gold therefore reads PARTIAL until the HR root
  cause below is fixed and re-vendored.
- **Member D/C** excludes detailing rows (IS 801 5.2.3 / 5.2.4 geometry, 8.2.1 spacing) and brace elements (sag rods,
  straps). Those rows still block the status when they fail.
- **Combination citations (review item 8).** Each cold-formed combination row carries `row_cite`. The 0.9 DL ± WL / EL
  rows are cited as additional uplift / overturning combinations, not as IS 875 (Part 5) 8.1 rows.

## New capabilities

- **Computed thin sections (`cfs_generic_sections.py`, review item 1).** Lipped channels `C<h>X<b>X<c>X<t>-G350` and
  lipped zeds `Z<h>X<b>X<c>X<t>-G350`. Depths 100 / 150 / 200 / 250 / 300 mm (flange × lip 50×15, 60×20, 65×20, 70×20,
  80×25), base-metal t 1.0 / 1.2 / 1.6 / 2.0 / 2.5 / 3.15 mm, Ri = 1.5 t.
  - Properties are computed with a thin-wall centreline model: A, I, Ixy, principal axes, J, shear centre, Cw.
  - The routine reproduces the textbook channel / zed shear centre and Cw exactly, and the printed IS 811 rows within
    3.5 % (A, Ix, Iy, Ixy) and 10 % (J, Cw).
  - Material: IS 277 grade 350 coil, Z275 coating, Fy 350 MPa. That is inside the IS 801 Table 2 row 36 kgf/mm² =
    353.0 MPa (corpus transcription, IS_801_1975.md p.11). IS 801 2.2 requires the coil to meet IS 1079 (mill
    certificate, VERIFY).
  - `is811_sections.props` / `built_up` and `india_practical_sections` resolve the labels. Every record states the
    5.2.3 / 5.2.4 limits. IS 811 sections remain available unchanged.
- **Auto-selection (review item 2).** `auto_select: {family, depth / thickness limits, n_ply_options,
  reference_section}` picks the lightest section of the family that passes every IS 801 check of the group (studs: all
  storeys). The report states the family, the number of candidates, the lighter sections rejected (with the failing
  check) and the reference section. Families: `thin_C_G350`, `thin_Z_G350`, `IS811_CLR`, `IS811_LZ`.
- **Restraint basis and IS 801 8.2 (review item 3).** Every purlin / girt / joist / stud row returned by
  `design_purlins`, `design_joists` and `design_studs` carries `restraint`, and the record carries `restraint_basis`.
  The HR PEB secondary jobs can print it.
  - 8.2.1: spacing a ≤ L/4. It is shown for reference when one flange is sheeted (8.2 (a) and its footnote) and blocks
    when neither flange is connected.
  - 8.2.2: P1 = 1.5 K′ w a, plus the concentrated-load terms. K′ = m/d (m by IS 801 7.3) for channels and Ixy/Ix for
    zeds.
  - Sag rods are sized M10–M24 (minimum M12), with the force accumulated over the members per line. Capacity to
    IS 800:2007 11.2.1 / 6.3.1 working stress, on the gross area and on the thread root.
  - Flat-strap bridging is checked to IS 801 6.1. Other brace types need a declared capacity.
- **Non-permanent dead loads (lead item 5).** `design_purlins(..., collateral_kNm2=, pv_kNm2=)` and
  `design_joists(..., collateral_kNm2=, pv_kNm2=)`, also read from the group spec or `cfg['loads']` (default 0). They
  are included where dead load adds to the effect and excluded from uplift / suction rows. Each component is a separate
  row of the record's `load_table`. The API stays backward compatible.
- **Girts:** checks read "suction, inner flange in compression" / "pressure, outer flange in compression".
- **All-CFS portal (review item 5).** The basis statement has no hot-rolled boilerplate (`india_cfs_basis.basis_statement`).
  The frame wind-pattern table and the wind / earthquake base shears are printed. Bolt groups show the IS 801 7.5
  per-bolt capacity (bearing 2.1 Fy d t, edge force 0.6 Fy t e, bolt shear) against the most loaded bolt. The 7.5.1
  1.5 d edge distance (the old "D/C 0.800") is a detailing row. The base plate is a declared input; the engine does
  not size it.
- **Report (review items 6–8).**
  - Titles by building type: all-CFS portal / CFS purlins and girts on a hot-rolled portal / hot-rolled braced or
    moment frame with LGSF infill and cold-formed floors (`report_title` overrides).
  - No raw dicts, no float noise and no "None" lengths. Moments are in kN·m and forces in kN, with a unit column.
  - Internal labels (rulings, D-numbers, engine hashes, fallbacks) are removed and "EOR" is spelt out.
  - The importance factor is stated on its occupancy basis.
  - Grade and coating are given per member and in chapter 1. IS 801:1975 (Reaffirmed 2021) / IS 811:1987
    (Reaffirmed 2024).
  - A "Durability, fire and acoustics" chapter covers: a coastal coating note (city list or `site.coastal_exposure`);
    the NBC fire statement; acoustics for dwellings, hostels and clinics; and a cold-service toughness note
    (`service_temperature_C`, IS 2062:2025 quality C at −20 °C, 12.5 / 12.1.1).
- **Lateral sub-run (review item 4, CFS-side root causes).**
  - `hr_vendor_runner` writes the sub-job's `cfg.py` (rebuilt from the spec, no re-analysis). This clears "cfg.py not
    found".
  - `india_cfs_lateral.ponding_input` passes an IS 875-4 4.4 ponding-screen input for roofs with beams of 12 m or
    more: the roof beam taken simply supported under max(snow, Lr), which is conservative. This clears "NO ponding
    evaluation".
  - The cold-formed members are added to the frame run's `delegated_design` register. This clears "delegated-design
    components referenced … but no register".
  - The frame report's consistency list and the connection check names travel back in `lateral_result.json`.
- **Environment fix:** the HR lateral subprocess keeps the vendored modules first even when the repo is reached through
  a symlink (`work/steltic_CFS_india`). Before this fix, the CFS `preflight` shadowed the HR one and every lateral
  run was blocked.

## Tests

- New: `tests/test_fix_FW1_generic_sections.py` (11), `tests/test_fix_FW3_status_report.py` (9).
- New: `tests/test_fix_FW2_restraint_autoselect.py` now has 11 tests (strap bridging, brace rows outside the member
  D/C, ply options).
- `python3 -m pytest tests -q -p no:cacheprovider`: 353 collected, 352 passed and 1 failed. The failure is
  `test_vendored_engine_is_byte_identical`. It compares `hr_vendor/` with the live `/home/claude/steltic_india` working
  tree, which the HR first-wave branch is editing now. `hr_vendor/` is unchanged and equals steltic_india `main`,
  checked file by file.

## Gold re-run (15 CFS golds, working copies in /home/claude/gold/jobs_cfs)

- Every gold `cfg.py` has a "2026-10 first wave (CFS)" block. Its groups are auto-selected from the thin G350 family,
  the IS 811 section is kept as the reference, the bracing is declared, and Ex2 has `service_temperature_C`.
- Results: CFS kg/m² down 30–60 %. The worst CFS D/C is 0.79–0.98. The hot-rolled frames are unchanged.
- Status: Ex3 COMPLETE. The other 14 are PARTIAL, solely from the inherited frame-report items of HR root cause 1
  below.
- The before / after table is in the lead's brief folder (`CFS_RESULT.md`).

## Root causes in the vendored HR engine (for steltic_india; not edited here)

1. `consistency._named_not_computed_issues` flags the `delegated_criteria` text that `india_is800_s12` (base rows,
   `detail.concrete_breakout.delegated_criteria`) copies from `cfg['delegated_design']` into every base row of
   `capacity_design`, as "symbolic REQUIREMENT, not a COMPUTED check". This accounts for 10–79 items per CFS gold. A
   delegated item is by definition not a computed check. Fix: skip `delegated_criteria` / `delegated_design` in
   `_gather_uncomputed_text`, or reference the register by id instead of copying the text.
2. `india_seismic.importance_factor` prints "owner ruling D8 (area proxy …)" as the Table 8 row (`D8_AREA_ROW`, clinic
   row). The CFS report now states the occupancy basis itself, but the HR frame report still prints the ruling label.
3. The HR frame report lists "IS 875 (Part 4):1987 / Part 5:1987" in its codes table while the snow is to
   IS 875 (Part 4):2021 (review finding 10, Ex2).
4. `consistency._consultancy_issues` (B8) fires on engine-written floor-system text ("joists"). The CFS side now
   declares a register entry, but the rule should ignore engine boilerplate.
