# steltic-CFS-india — 2026-10 third wave (repeatable frame models, cold-formed leftovers)

Branch `fix/2026-10-third-cfs`, from origin/main dcda6c2. Two items of the third wave:
- handoff P3: repeatable runs;
- handoff P9: the cold-formed leftovers.

The vendored HR engine is unchanged (no re-vendor). HR main will gain a column in-span moment check (lead branch
`fix/2026-10-column-span-moment`). After it merges, the lead re-vendors and the CFS lateral frames may move.

## P3 — repeatable frame models

- **Cause (confirmed).**
  - `hr_vendor_runner._callables` read the braced bays and moment lines from Python sets of `("X", i, j)` tuples.
  - String hashing changes the set order from one process to the next. So the brace elements were numbered
    differently from run to run, and a column shared by an X-braced and a Y-braced bay took whichever bay came first.
  - Only the three golds that use the regular-grid builder (no job frame builder) took this path: Ex7, Ex10 and Ex12.
    They are exactly the three that varied.
  - A probe of the old function under hash seeds 0–3 gave four different brace orders, and the Ex7 corner columns
    faced Y / X / X / Y.
- **Fix.**
  - Braces are numbered in sorted order (X before Y, then i, j), as the shared HR frame builder already does.
  - Moment lines are visited X before Y. Every other set is used for membership only.
- **Stated rule for a column in frames of both directions** (`COL_STRONG_RULE`, printed in chapter 4 with the columns
  it decides):
  - The strong axis lies in the plane of the moment-frame line the column stands on; a column on X and Y moment lines
    faces X.
  - Otherwise it lies in the plane of the first braced bay that contains it, in schedule order with the lowest storey
    first. A corner of two braced walls therefore faces the bay listed first. This is the rule the shared HR frame
    builder (`frame_build.col_strong`) already applies to every job-builder gold.
  - Any other column takes the declared default, X. This was `None` before, which the engine read as X.
  - The beam-to-column joints of the braced bays are simple. A shared column carries the axial forces of both bays and
    is checked for buckling about both axes whichever way it faces.
  - On the job-builder path only the X-and-Y moment-line case is fixed. That case does not occur in any gold.
- **Fixed hash seed.**
  - The frame sub-run is started with `PYTHONHASHSEED` (the parent's value, else 0). Whatever the vendored HR engine
    still reads from a set therefore repeats.
  - The gold harness copy re-executes itself with `PYTHONHASHSEED=0`.
- **Proof.**
  - The 15 golds were run twice at the P3 commit df71fc8, each run under heavy, rc 0 every time.
  - Every output file of every job is byte-identical between the two runs: 9–81 files per job (calc packages, frame
    packages, reports, viewers, STATUS, schedules). Only `run_summary.json` differs, by its elapsed time.

## P9 — cold-formed leftovers

New design code is in `steel_engine/india_cfs_secondary.py`, report text in `steel_engine/report_cfs_third_wave.py`,
and the new cfg keys are documented in `contract/AGENT_START.md`.

- **Stud deflection criterion.**
  - IS 801 5.1 sets no limit and IS 800:2007 Table 6 has no stud row. A stud group that declares no criterion now gets
    a stated one: the Table 6 row "other buildings, lateral deflection under wind" read for the stud span between
    floors.
  - It is height/300 for elastic cladding (the default) and height/500 for a declared brittle lining.
  - This is the basis the six golds that declare a criterion already use. IS 800 5.6.1 lets the design engineer take
    a stricter value.
  - The deflection row is a real check now, no longer "information". The auto-selected studs of the golds that
    declared none are re-selected (table below).
- **CFS Ex1, internal pressure on the cyclone coast** (owner decision, 2026-11-01).
  - Ex1 keeps its published design. It declares its openings protected (`opening_protection`).
  - The report prints a design requirement for the design engineer and owner: impact-rated doors, roller shutters and
    glazing, so that no dominant opening forms in a cyclone.
  - It also states the basis of the internal pressure used: IS 875 (Part 3):2015 7.3.2.1, normal permeability,
    Cpi +0.2 / −0.2.
  - It says that an opening left open or failed would bring 7.3.2.2 / Fig. 2 (Cpi up to +0.8), for which the design
    would not apply.
  - For reference (not adopted), the dominant-opening case on Ex1 overstressed the published rafter: 1.296 under
    0.9DL+1.5WM0+. Carrying it needed a heavier rafter and column, panel-zone plates and longer anchors.
- **Dominant-opening code path, kept for jobs that declare one.**
  - `wind_internal_pressure` = {case, Cpi_pos, Cpi_neg, opening, basis, cite} is enveloped with the opening-ratio Cpi
    (never reduced) in the member pressures of every purlin, girt and stud.
  - It is applied to the frame's member-wind patterns: (Cpe − Cpi) pd → (Cpe − Cpi′) pd, with pd recovered from the
    pattern's roof record.
  - It is printed in chapter 2. It contradicts `opening_protection`, and the engine refuses the pair.
- **CFS Ex2, snow drift, the vestibule and the condenser platform** (IS 875 (Part 4):2021, the 2021 text in the
  corpus).
  - The 5.2.4 drift is computed in the engine:
    - μ1 = 0.80;
    - μw = (l1 + l2)/2h, capped at k h/s0 with k = 2 kN/m², and kept within 0.80–4.0;
    - μs = 0 for an upper roof of 15° or less;
    - l3 = 2h, kept within 5–15 m;
    - Note 2 interpolation when l2 < l3.
  - The 5.2.6 drift is computed as μ2 = k h/s0, kept within 0.8–2.0, over l = 2h (5–15 m).
  - The vestibule lean-to is designed for the drift profile:
    - cold-formed roof joists (trapezoidal load);
    - the door header (a framed opening) carrying the joists;
    - the door jambs (axial and wind);
    - the back-wall studs.
  - The condenser platform has beams and posts. Its dead load goes to the frame at the two knees as nodal loads with
    the moment of the post offsets, and is included in the seismic weight. The drift around it is checked.
- **Purlin cleats** (Ex1, Ex2).
  - Bolts in the purlin web to IS 801 7.5: 7.5.1 edge distance, 7.5.3 bearing, 7.5.4 bolt shear. Lapped purlins have
    two webs.
  - The plate cleat welded to the rafter flange is checked to IS 800:2007 Section 11 working stress:
    - 11.5.2 (a) form for compression with minor-axis bending (K at its 1 + 0.8 n bound, Cm 1.0, fac = 0.6 fcd by
      11.3.1 / 7.1.2.1 class c);
    - 11.5.3 for tension with bending;
    - 11.6.3.1 fillet welds;
    - 11.1.4 increases.
  - Simple-span purlins put two purlin ends on one cleat.
  - The downslope component goes to the declared sag rods (both jobs declare them). The default is the cleat.
- **Eave struts** (CFS Ex3, all-cold-formed portal).
  - The axial force is derived from the longitudinal bracing: the governing longitudinal force / 2 side walls, taken
    whole through the strut at the braced bay.
  - It is designed with its own-weight bending to IS 801 6.6 / 6.7 (the existing `design_eave_strut`), auto-selected.
  - Ex1 and Ex2 keep their hot-rolled eave members, designed in the frame run.
- **Screwed connections.** IS 801:1975 has weld (7.2) and bolt (7.5) provisions only. Chapter 7 now states that
  screwed connections are designed from the screw maker's tested values or a test programme.
- **Diaphragm capacities: flag kept.**
  - IS 801 9.1.4 says its clause 9 does not apply to light-gauge diaphragms.
  - The board and sheet diaphragms of Ex1 and Ex4–Ex15 rest on fastener capacities, which IS 801 does not give.
  - There is no code-based derivation in the corpus, so they stay "assumed allowable: confirm with the manufacturer's
    test report", flagged at a ratio of 0.90 or more.
  - Ex2 is the exception and stays "calculated": its capacity is the IS 800 11.2.1 tension of the hot-rolled roof
    bracing.
- **Load-bearing LGSF example: not added.**
  - IS 1893 (Part 1):2016 Table 9 lists no light-gauge steel system (sheathed or strap-braced stud walls), so a
    load-bearing LGSF building has no R.
  - Table 9 Note 1 also requires ductile systems in Zones III–V.
  - IS 801:1975 has no shear-wall, strap-bracing or diaphragm provisions. Programme ruling D3 keeps the hot-rolled
    frame as the lateral system.
  - An LGSF example would need a code basis the corpus does not hold.

## Tests

- `tests/test_third_wave_2026_10.py` (new, 15 tests).
  - P3:
    - hash-seed independence of the frame callables, tested in subprocesses with seeds 0–11;
    - the shared-corner rule, which follows the declared order;
    - a column on moment lines in both directions;
    - the default axis;
    - the builder-path pin;
    - the sub-run's hash seed;
    - the report text.
  - P9:
    - the stud criterion;
    - the dominant-opening envelope on the members and on the frame patterns, never reduced, and refused with
      protected openings;
    - the opening-protection text;
    - the simple-beam closed forms;
    - the IS 875 (Part 4) drift (Ex2 hand calculation, every bound, Note 2, the steep upper roof);
    - the purlin cleats (rows, two ends per cleat, downslope to the sag rods, lapped webs, detailing class);
    - the platform knee loads (node, sign at either eave) and the eave-strut force;
    - the lean-to (members, drift-loaded reaction against a hand calculation).
- `tests/test_wp3_ex1_ex5.py`: the Ex1 fixture's wind-increase assertion now reads the strength rows only. The stud's
  service deflection row became a real check.
- Whole suite: **400 passed** (origin/main 385).

## Gold re-runs (15 CFS golds, sandbox copy `/home/claude/wt/CFS/gold/jobs_cfs`)

- **Snapshot.** "Before" is the lead's gold outputs as they stood (the 2026-10-24 run of 56c743b = main), copied
  before any change.
- **Runs.** Every run used the sandbox gold harness (`PYTHONHASHSEED=0`) with each job under `/home/claude/bin/heavy`.
  Every run returned rc 0 and status COMPLETE with 0 open items.
  - P3 at df71fc8: two passes, byte-identical to each other.
  - Final engine 7817df4: two passes.
- **Comparison.** `compare3.py` compares every cold-formed member check row, every connection, the diaphragm rows, the
  frame summary and the frame's own package. Numbers are compared to 6 decimals and at most 9 significant figures; a
  1e-12 relative round-off seen in the lapped-purlin rows is not a design difference.

| Job | Change (cause) | Headline: worst cold-formed strength ratio, before → after | kg/m² (role) | Frame |
|---|---|---|---|---|
| Ex1 | Openings protected (requirement printed); purlin cleats added, 0.440 (welds) | 0.976 → 0.976 (girt Z200X65X20X2.0) | unchanged (girt 4.4, purlin 5.4) | unchanged |
| Ex2 | Vestibule: joists C250X70X20X3.15 0.929, header 2xC250X70X20X2.5 0.842, jambs 2xC150X60X20X1.6 0.980, back-wall studs 2xC100X50X15X1.0 0.637. Condenser platform: beams 2xC250X70X20X2.0 0.706, posts C100X50X15X1.0 0.577. Purlin cleats 0.741 (12 mm plate; 10 mm gave 1.04). About 830 kg added | 0.796 → 0.980 (vestibule door jamb) | purlin / girt unchanged; vestibule 700 kg on 24 m², platform 128 kg | W 4102.5 → 4125.3 kN, V_B 553.8 → 556.9 kN; frame headline 0.928 → 0.935 (column WPB800X300X262.34); EBF link continuity 0.980 and base 0.948 unchanged |
| Ex3 | Eave struts 2xC250X70X20X2.0, P = 74.2 kN (148.4 kN gable wind / 2), 0.902; 12 struts, 782 kg (1.1 kg/m²) | 0.910 → 0.910 (purlin Z150X60X20X2.0) | unchanged + eave struts | all-CFS portal unchanged |
| Ex4, Ex5, Ex6, Ex9, Ex14, Ex15 | none | unchanged | unchanged | identical |
| Ex7 | P3 (corner columns face X; brace numbering) + stated stud criterion: studs C100X50X15X1.0 → 1.2 (deflection 10.5 mm > H/300) | 0.789 → 0.684 (joist; the old stud crippling ratio falls with the thicker web) | stud 4.4 → 5.2 | headline 0.739 unchanged; connection 0.1458 → 0.1453; drift and diaphragm within ±0.1 % |
| Ex8 | stud criterion added (passes) | 0.974 → 0.974 | unchanged | identical |
| Ex10 | P3 + studs 1.0 → 1.2 (11.7 mm > H/300) | 0.844 → 0.836 | stud 4.4 → 5.2 | non-governing brace 0.206 → 0.264; headline 0.857 unchanged |
| Ex11 | stud criterion added (passes) | 0.940 → 0.940 | unchanged | identical |
| Ex12 | P3 + stud criterion (passes) | 0.836 → 0.836 | unchanged | Y drift +2 % (≤ 0.000224 / 0.004); Section 12 rows 1050 → 1054; headline 0.921 unchanged |
| Ex13 | studs 1.0 → 1.6 (14.4 mm > H/300) | 0.925 → 0.925 | stud 4.4 → 6.8 | identical |

Notes:
- **Repeatability.** The two passes at the final engine 7817df4 are byte-identical on all 15 jobs: 9–81 output files
  per job, `run_summary.json` excepted. So are the two P3 passes at df71fc8.
- **Public text.** A scan of the 15 reports for leaks (paths, module names, JSON keys, EOR, owner ruling,
  "(Part 1):1987", "(was None)") is clean.
- **Gold cfg changes (sandbox copy, for the lead to adopt):**
  - Ex1: an appended "2026-10 third wave" block (opening protection, cleat spec, the opening-ratio register entry).
  - Ex2: an appended block (lean_to, roof_platforms, cleat spec, two eor_inputs).
  - Ex3: an appended block (eave_struts).
  - Ex4: the job path from `__file__` (no design change).
  - Ex1–Ex3 are otherwise the published cfgs.


## Re-vendor from the final HR main (2026-11-07)

- `steel_engine/hr_vendor/` is re-vendored from steltic_india main **f0a83dd** (PRs #29–#36: the MSME shed, the engine-check fixes, the Indian section families and the PEB golds), with `scripts/revendor_hr.py`. `check_vendored.py` reports 58 identical files.
- All 15 CFS golds were re-run on it, each under heavy with `PYTHONHASHSEED=0`. `tools/compare3.py` against the previous final pass gives **all designs identical** at 6 decimals: the cold-formed members and connections, the diaphragms, the hot-rolled frames, the statuses and kg/m².
- The pin test follows the new commit. Full suite: **400 passed**.
