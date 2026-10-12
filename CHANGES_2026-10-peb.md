# steltic-CFS-india — 2026-10: PEB release (lapped zed purlins and girts; HR engine re-sync)

Branch `fix/2026-10-peb-tapered`, one PR with the 2026-10 renumbering commit before it (`CHANGES_2026-10-peb-briefs.md`,
prepared as `fix/2026-10-peb-briefs`, never pushed on its own). It goes with the steltic_india PEB release.
Owner decision D-T5: the purlins and girts of the PEB golds are designed by this engine (IS 801) and imported into
the HR package.

## Engine
- **`is801_members.py`**
  - A lipped zed (LZ) in compression buckles about its minor principal axis: KL / r_min.
  - `bending_allowable(..., zed_basis=)` designs an LZ about its geometric x-x axis **only** with a declared
    restraint basis (sheeting through-fastened to one flange; the free flange held by sag rods and fly braces).
    Without it the C15 refusal is unchanged.
  - `combined_67` passes the basis through.
- **`india_cfs_members.py`**
  - `continuous_unit_effects(n_spans, L, lap)`: a continuous beam on equal spans with the laps at 2 EI. It returns
    the span, support and lap-end moments, the shears, the reactions and the deflection for w = 1 N/mm.
  - `design_purlins` with `continuity: 'lapped'` (`n_spans`, `lap_mm`, `zed_basis`, optional `L_unbraced_hog_mm`)
    checks, per working-stress combination:
    - bending in the span, at the lap end and at the interior support (two nested sections);
    - 6.4.1 web shear;
    - 6.4.3 web bending with shear at the lap end;
    - 6.5 web crippling at the interior and end supports;
    - the deflection of the lapped beam.
  - The eave strut passes its restraint flags.
- **`steel_engine/hr_vendor/`:** re-synced byte-identically with steltic_india `fix/2026-10-peb-tapered`. Ten files
  changed (including `india_connections`: the end-plate prying and web-tension fixes) and four are new (`peb_build`,
  `peb_checks`, `peb_outputs`, `peb_report`). `check_vendored.py`: 49
  identical. Recorded in `VENDORED_FROM.md`.

## Regression
The 15 CFS golds of the 2026-09-27 pack were re-run with the re-synced vendor folder. All reproduce:
- design_status and the lateral status;
- the governing CFS member;
- the lateral member and connection D/C.

The only differences are of the order of 1e-4 on non-governing lateral connections, and a second run of the same
engine shows the same differences (tie-break order). The evidence is in the gold pack, `REGRESSION_2026-10.md`.

## Tests
`tests/test_peb_lapped_zed.py` (6 tests):
- 2- and 3-span textbook coefficients;
- the laps drawing moment to the supports;
- the LZ zed basis and r_min;
- a lapped purlin record on the IN_CFS_Ex3 fixture.
