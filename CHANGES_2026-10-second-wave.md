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
  governing check and ratio, and "Why fixed bases" (K, KL/r, owner decision). The connection table names
  the plate's governing check.
- Gold Ex3 `cfg.py`: a "2026-10 second wave (CFS)" block declares `compare_plates` = 400 × 500 × 32 (the plate the
  review expected) and `portal.base_reason`. Report-only inputs.
- Result (Ex3 gold): adopted 500 × 600 × 40 with 6 M24: plate bending on the uplift side, 121.5 / 180.0 MPa, ratio
  0.675 (DL+1.0WM0+R). 400 × 500 × 32 with the same anchors 50 mm from its edge (lever arm 200 mm): plate bending on
  the uplift side, ratio 1.163, FAIL (the first-wave note quoted 1.10; the anchor layout behind that figure is not recorded). Fixed bases: K = 1.20,
  in-plane KL/r 90; pinned: K = 2.47, KL/r 184 against the IS 801 6.6.3 limit of 200.

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
  `report_second_wave.base_shear_notes`, what the next softer type would do to V_B at the design Ta. The 13 Type II
  jobs: Ta is on both plateaus, V_B would not change. Ex10 and Ex15 are declared Type III, the softest type (stated).
  The declared types are kept.
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
- Whole suite: 370 passed (origin/main: 353).

## Gold re-run (15 CFS golds, /home/claude/gold/jobs_cfs)

Snapshot first: before any change the outputs of the 15 CFS golds (run_summary.json, design/, report.html, STATUS.md,
viewer, the lateral sub-run's design/, lateral_result.json and report.html) and the md5 of every `cfg.py` were copied to
`/home/claude/gold/baseline_2026-10-23_cfs/` (produced by 81e8bbe, the tree of origin/main). All 15 were then re-run in
place with the gold harness, each under `/home/claude/bin/heavy`, at 2bbbace and again at the final engine commit 86f23d6
(every run rc 0). The comparison script compares at six decimals: every cold-formed member (section, plies, every check
row's value / limit / ratio / result, member D/C), the cold-formed connections, the diaphragm rows, the hot-rolled frame
summary (system, R, seismic summary, members, connections, drift, Section 12 counts, status), the frame's own calc
package (member checks, connections, drift, Section 12 checks) and kg/m². Report-only keys added by this wave (`KL_r`,
`headline`, `plate_design`, the frame headline) are listed, not compared.

| Job | Status before → after | Worst CFS member D/C (mixed) before → after | Headline: worst CFS strength ratio (member, check) | Slenderness KL/r / 200 (ratio, member) | Frame headline: strength / KL/r (limit) | kg/m² before → after | Design vs snapshot |
|---|---|---|---|---|---|---|---|
| Ex1 | COMPLETE → COMPLETE | 0.976 → 0.976 | 0.976 (girt-Z200X65X20X2.0-G350, 6.1/6.2/6.3 bending, span (single, suction)) | — (no compression members) | 0.687 / 152.1 (180) | girt 4.4; purlin 5.4 (unchanged) | identical |
| Ex2 | COMPLETE → COMPLETE | 0.796 → 0.796 | 0.796 (purlin-C300X80X25X3.15-G350, 6.1/6.2/6.3 bending (gravity, top flange in compression)) | — (no compression members) | 0.928 / 133.4 (180) | girt 3.0; purlin 10.0 (unchanged) | identical |
| Ex3 | COMPLETE → COMPLETE | 0.910 → 0.910 | 0.910 (purlin-Z150X60X20X2.0-G350, 6.1/6.2/6.3 bending, span (single, uplift)) | 143.0 (0.715, mezzanine-post-2xCLR150X50X25X4) | — (all-CFS portal) | girt 2.8; joist 11.4; purlin 3.5 (unchanged) | identical |
| Ex4 | COMPLETE → COMPLETE | 0.826 → 0.826 | 0.826 (joist-C200X65X20X2.5-G350, 6.1/6.2/6.3 bending) | 67.2 (0.336, stud-S1-C150X60X20X1.2-G350) | 0.760 / 158.7 (180) | girt 4.3; joist 17.2; purlin 5.4; stud 7.1 (unchanged) | identical |
| Ex5 | COMPLETE → COMPLETE | 0.968 → 0.968 | 0.776 (joist-C200X65X20X2.5-G350, 6.5 web crippling (end reaction)) | 74.8 (0.374, stud-S1-C100X50X15X1.6-G350) | 0.666 / 213.4 (250) | joist 17.2; purlin 11.2; stud 6.8 (unchanged) | identical |
| Ex6 | COMPLETE → COMPLETE | 0.857 → 0.857 | 0.822 (joist-C200X65X20X2.5-G350, 6.1/6.2/6.3 bending) | 89.8 (0.449, stud-S1-C100X50X15X1.6-G350) | 0.840 / 168.9 (180) | joist 17.2; stud 6.8 (unchanged) | identical |
| Ex7 | COMPLETE → COMPLETE | 0.789 → 0.789 | 0.789 (stud-S4-C100X50X15X1.0-G350, 6.5 web crippling at track (end reaction)) | 74.1 (0.370, stud-S1-C100X50X15X1.0-G350) | 0.739 / 133.1 (180) | joist 11.6; stud 4.4 (unchanged) | CFS identical; frame numbers vary run to run (note 3) |
| Ex8 | COMPLETE → COMPLETE | 0.974 → 0.974 | 0.974 (joist-C250X70X20X2.5-G350, 6.5 web crippling (end reaction)) | 74.1 (0.370, stud-S1-C100X50X15X1.0-G350) | 0.888 / 155.7 (180) | joist 20.2; stud 4.4 (unchanged) | identical |
| Ex9 | COMPLETE → COMPLETE | 0.972 → 0.972 | 0.972 (joist-C200X65X20X2.0-G350, 6.5 web crippling (end reaction)) | 79.8 (0.399, stud-S1-C100X50X15X1.6-G350) | 0.938 / 143.7 (180) | joist 13.9; stud 6.8 (unchanged) | identical |
| Ex10 | COMPLETE → COMPLETE | 0.862 → 0.862 | 0.844 (stud-S5-C100X50X15X1.0-G350, 6.5 web crippling at track (end reaction)) | 74.1 (0.370, stud-S1-C100X50X15X1.0-G350) | 0.857 / 133.1 (180) | joist 11.6; stud 4.4 (unchanged) | CFS identical; frame numbers vary run to run (note 3) |
| Ex11 | COMPLETE → COMPLETE | 0.940 → 0.940 | 0.940 (joist-C250X70X20X2.5-G350, 6.5 web crippling (end reaction)) | 74.1 (0.370, stud-S1-C100X50X15X1.0-G350) | 0.979 / 146.6 (180) | joist 20.2; stud 4.4 (unchanged) | identical |
| Ex12 | COMPLETE → COMPLETE | 0.862 → 0.862 | 0.836 (joist-C150X60X20X2.0-G350, 6.5 web crippling (end reaction)) | 81.5 (0.407, stud-S1-C100X50X15X1.0-G350) | 0.921 / 194.2 (300) | joist 11.6; stud 4.4 (unchanged) | CFS identical; frame numbers vary run to run (note 3) |
| Ex13 | COMPLETE → COMPLETE | 0.959 → 0.959 | 0.925 (joist-C200X65X20X2.5-G350, 6.1/6.2/6.3 bending) | 81.5 (0.407, stud-S1-C100X50X15X1.0-G350) | 0.890 / 135.9 (180) | joist 17.2; stud 4.4 (unchanged) | identical |
| Ex14 | COMPLETE → COMPLETE | 0.912 → 0.912 | 0.912 (joist-C250X70X20X2.5-G350, 6.5 web crippling (end reaction)) | 74.8 (0.374, stud-S3-C100X50X15X1.6-G350) | 0.922 / 131.0 (180) | joist 20.2; stud 6.8 (unchanged) | identical |
| Ex15 | COMPLETE → COMPLETE | 0.945 → 0.945 | 0.945 (joist-C250X70X20X2.5-G350, 6.5 web crippling (end reaction)) | 74.8 (0.374, stud-S1-C100X50X15X1.6-G350) | 0.931 / 132.2 (180) | joist 20.2; purlin 16.3; stud 6.8 (unchanged) | identical |

1. **Every cold-formed member, connection and status is identical on all 15 jobs** (sections, every check ratio, kg/m²,
   status COMPLETE with 0 open items). The headline differs from the old single member D/C only where a deflection
   ratio was the larger: Ex5 0.968 → 0.776, Ex6 0.857 → 0.822, Ex10 0.862 → 0.844, Ex12 0.862 → 0.836,
   Ex13 0.959 → 0.925 (the deflection ratio is printed beside it).
2. Combination labels on ties and the numbering of the frame's brace elements are not compared: where two combinations
   give the same ratio the frame report prints whichever it visited first, and the Section 12 checks of the braces land
   on permuted element tags (same multiset of ratios).
3. **Run-to-run variation of the hot-rolled frame (Ex7, Ex10, Ex12), not from this branch.** Two runs of the same code
   give two states: Ex7 diaphragm unit shears ±0.3 %, two frame connections 0.1458 / 0.1457, drift ±0.1 % (the second
   run of the same code returned to the snapshot values); Ex10 one non-governing brace strength ratio 0.206 / 0.264
   (its KL/r 0.739 governs); Ex12 Y drifts up to +2 % (≤ 0.00022 against 0.004) and 1053 / 1057 Section 12 rows. No
   governing ratio, cold-formed result or status moves. Probable cause (for the engine owner):
   `hr_vendor_runner._callables` iterates Python sets of braced bays and moment lines (`braces()` returns the set order,
   `col_strong()` takes the first match), and string hashing changes the set order from one process to the next.
   The first wave saw the same on Ex7 (REGRESSION_2026-10.md).
4. Ex3: the plate comparison (400 × 500 × 32 at 1.16, plate bending on the uplift side) uses the same reactions; the
   frame, members and the adopted plate's 0.675 are unchanged.

Gold `cfg.py` changes (report-only text / inputs, md5 before in `baseline_2026-10-23_cfs/cfg_md5.txt`): Ex3
(`compare_plates`, `portal.base_reason`), Ex2 (the purlin deflection label). Harness: `run_job.py` (CFS branch) adds
`headline`, `worst_strength`, `worst_slenderness`, `frame_headline` to run_summary.json (the previous file is
`baseline_2026-10-23_cfs/run_job.py.before_cfs_second_wave`).

Tests: `python -m pytest tests -q -p no:cacheprovider` -- 370 passed (origin/main: 353 passed; the 17 new tests make
the difference).

Publish folder: `/home/claude/cfs_publish2/cfs/` (the 15 reports, viewers and linked frame reports, every local link
resolving; `index.json` with the titles of the first wave, the report h1 as `report_title`, a meta line led by the
strength headline with KL/r beside it, and `headline` / `frame_headline` records for the site build).
