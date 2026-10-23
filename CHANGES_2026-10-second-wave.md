# steltic-CFS-india — 2026-10 second wave (report-only, HR engine re-vendor)

Branch `fix/2026-10-second-wave`, from origin/main 1e7220e (the first wave merged). Scope: the CFS items of the second
wave (C1–C4 of the brief). No design changes: every cold-formed section, ratio and status and every hot-rolled frame
result is unchanged (checked on all 15 golds against a snapshot taken before any change; table below). The fixed bases
and the 500 × 600 × 40 plate of CFS Ex3 are kept (owner decision). New report text lives in
`steel_engine/report_cfs_second_wave.py`; `report_cfs_india.py` only hooks it in.

## C1 — HR engine re-vendored, scripted

- **`scripts/revendor_hr.py` (new).** `python3 scripts/revendor_hr.py --commit <sha|ref> --label "<branch>"
  [--dry-run]` re-vendors `steel_engine/hr_vendor/` from one commit of steltic_india:
  - it reads the committed `steel_engine/` files with `git show` (`tools/` and `__pycache__/` excluded, the same set
    `check_vendored.py` compares), so a branch being edited in the HR checkout cannot leak in;
  - it writes the changed and new files, deletes vendored files the commit no longer has, moves the pin in
    `VENDORED_FROM.md` and appends a dated re-sync note;
  - it ends with `check_vendored.py` against the new pin (exit 0 = byte-identical). A second run writes nothing.
- **Re-vendored from steltic_india `fix/2026-10-second-wave` dd1d8c1** (the HR second wave): `consistency.py` and
  `report_india.py` rewritten, `report_second_wave.py` new; 53 files byte-identical. The frame reports of the CFS
  jobs now carry the HR second-wave text (strength headline, soil statement, citations).
- When the PEB variations branch is merged into steltic_india main, the lead re-vendors with the same command and the
  merge commit, then runs the tests and the CFS golds.

## C2 — CFS Ex3: the base plate as a design result (no frame change)

- `india_cfs_portal.plate_design` (record `plate_design` on the `column-base` connection):
  - the adopted plate with its governing check, value / limit, ratio, combination and base;
  - each plate of `cfs_connections_spec.base.compare_plates`, checked against the **same** reactions over every
    combination and base (anchors kept at the declared edge distance, lever arm f = L/2 − edge unless declared);
  - the fixity basis: the IS 800:2007 Annex D sway K of the exterior column for fixed and for pinned bases, and the
    in-plane KL/r of the columns for both against the IS 801 6.6.3 limit of 200.
- Chapter 7 prints "Column base plate: design result": the adopted plate, the compared plate that fails with its
  governing check and ratio, and "Why fixed bases" (K, KL/r, owner decision). Chapter 1 and the connection table name
  the plate's governing check.
- Gold Ex3 `cfg.py`: a "2026-10 second wave (CFS)" block declares `compare_plates` = 400 × 500 × 32 (the plate the
  review expected) and `portal.base_reason`. Report-only inputs.

## C3 — report-only fixes

- **Headline = worst cold-formed STRENGTH ratio; slenderness beside it (as in HR).**
  - `report_cfs_second_wave.headline(pkg)` → `pkg["headline"]` and `design/headline.json`: `strength` (the
    headline: IS 801 6.1–6.7 bending, shear, web crippling, axial and combined ratios), `slenderness` (largest KL/r of
    a cold-formed compression member against the IS 801 6.6.3 limit of 200, from the corpus transcription of
    IS 801:1975), `serviceability` (declared IS 800 Table 6 deflection criteria), `bracing_81` (stud sheathing
    bracing), `detailing` (5.2.3 / 5.2.4 / 7.3 / 7.5.1), `brace_element` (sag rods, straps), `connections`,
    `member_dc_max` (the old single figure, the larger of strength and deflection) and `frame` (the hot-rolled frame's
    own headline from its report).
  - The status block prints the headline line and a "Governing ratios" table; each cold-formed member header reads
    "strength ratio x (check, combination); deflection y; KL/r z / 200 (ratio)" instead of one mixed D/C.
  - KL/r is kept on the compression rows (`KL_r` on stud and eave-strut interaction rows, portal columns, rafters,
    knee braces, mezzanine posts). Report-only: the values were already computed by `compression_allowable`.
  - Chapter 4 member table: strength ratio with its combination and KL/r / limit (ratio) in separate columns, for the
    hot-rolled frame (from the frame run: `hr_vendor_runner` adds `headline`, `strength_dc`, `KL_r` to
    `lateral_result.json`) and for the all-CFS portal. The frame's own headline line is printed above the table.
- **Soil type and basis (as in HR).** Chapter 2 prints the declared type and its basis (`site.soil_note` or the HR
  wording: "medium soil assumed, not from a site investigation; confirm by site investigation") and, from the vendored
  `report_second_wave.base_shear_notes`, what the next softer type would do to V_B at the design Ta. All 15 jobs: Ta is
  on both plateaus, V_B would not change. The declared types are kept (Ex10 and Ex15 Type III).
- **Moment-frame Ta note.** Where a moment-frame direction (the all-CFS portal plane; `lateral_frame.moment_lines`)
  takes Ta by IS 1893 7.6.2(c), a note gives the bare-frame 7.6.2(a) Ta and its V_B ratio (Ex1 X, Ex3 X: V_B
  unchanged, both on the plateau).
- **One citation style.** `report_cfs_second_wave.tidy_html` normalises the printed text: IS 801:1975, IS 811:1987,
  IS 875 (Part 1):2026, (Part 2):1987, (Part 3):2015, (Part 4):2021, (Part 5):1987, IS 1893 (Part 1):2016 with
  Amendments 1 and 2, IS 2062 (Part 1):2025, "IS 875 (Part N)" for the old "IS 875-N". Chapter 9 adds a "Standards
  cited (editions)" table listing only the standards the report cites (IS 277 for the coil, the reaffirmation years
  of IS 801 and IS 811 as a status).
- **Other review leftovers (D_CFS):**
  - Scope line in chapter 1: fire resistance, acoustic performance, corrosion beyond the stated coating, undeclared
    connections, declared diaphragm capacities, foundations and (hybrid jobs) load-bearing LGSF walls as the lateral
    system are outside the design. The coastal coating note (first wave) is unchanged.
  - Diaphragm table: a "source status" column (assumed allowable / the design engineer's calculation / cited); a note
    flags any ratio of 0.90 or more against a capacity that is not yet sourced (Ex13 storey 6 Y, 7.93 / 8.0 kN/m).
  - Map readings in words: Vb and seismic zone read from Fig. 1 where the city is not in the annex (Ex14 Noida).
  - All-CFS portal: W is stated as one transverse frame's seismic weight, with the whole building's W and V_B for
    the longitudinal bracing; "governing combination" (not "pattern") for the frame wind base shear.
  - Gold Ex2 `cfg.py`: the purlin deflection criterion stays span/180; its label now reads the brittle-cladding row of
    IS 800 Table 6 (the old label called span/180 the elastic-cladding row). Text only.
  - "an EOR assumption" now reads "a design engineer's assumption".
- `contract/AGENT_START.md` names the report-only keys (`soil_basis`, `site.zone_source` / `Vb_source`,
  `base.compare_plates`, `portal.base_reason`).

## Tests

- `tests/test_second_wave_2026_10.py` (new, 17 tests): the re-vendor script on a throw-away HR repository (dry run,
  write, delete, pin, repeat), the pin, the Ex3 plate record and text, the frame unchanged, row classes, the strength
  headline against deflection, slenderness from compression rows only, headline.json and the report in the Ex7
  fixture, member headers, soil and Type III notes (V_B × 1.10 hand check at Ta 0.6 s), the Ta notes (0.085 h^0.75 hand
  check), map readings, diaphragm sources, scope, portal W, citations and the rendered reports.
- Whole suite: see the gold section below for the counts.

## Gold re-run (15 CFS golds, /home/claude/gold/jobs_cfs)

GOLD_TABLE_PLACEHOLDER
