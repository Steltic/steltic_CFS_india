# India CFS worked reference — two engine-reproducible buildings (asserted by pytest)

Both buildings are run end-to-end by `tests/test_wp3_ex1_ex5.py` from the fixtures
`tests/fixtures/IN_CFS_Ex1/build_and_run.py` and `tests/fixtures/IN_CFS_Ex5/build_and_run.py`; the numbers below are
the ones the tests assert (tolerances in the test file). They are the worked METHOD to mirror — never copy a number
into another building.

## A. IN_CFS_Ex1 — 4-storey residential, New Delhi: hot-rolled SCBF + IS 801 studs / joists

**Problem.** 12 m × 8 m plan, 4 × 3.0 m storeys, residential (48 persons). New Delhi: IS 1893 Annex E Zone IV,
Z = 0.24, soil Type II; IS 875-3 Annex A Vb = 47 m/s, terrain category 3, inland (Kd 0.9, k4 1.0). Loads: floor
D 1.5 + partitions 1.0 (also 1.0 in W: max(0.5, 1.0) under ruling R1, IS 1893 7.3.6 "the higher values shall be
used"), IL 2.0 (IS 875-2 Table 1), roof D 1.0, Lr 0.75, cladding 0.5 kN/m².

**Method (the sequence to mirror).**
1. Zone IV → SCBF, R = 4.5 (IS 1893 Table 9 SBF concentric; L7), IS 18168:2023 applies (Zone IV residential).
   `lateral_frame`: 2 × 2 bays (6 m × 4 m), X-bracing in every perimeter bay, fixed bases, E250 B0. The SFRS sections are
   sized by IS 18168:2023 5.3 / Table 2 (limit = coefficient × ε/√Ry = 0.845 × coefficient for E250, Ry 1.4):
   lateral columns WPB200X200X61.3 (b/tf 6.67 ≤ 7.61; WPB200X200X50.92 at 8.42 fails), braces WPB200X200X50.92
   (brace row 8.42 ≤ 9.55; plastic section, 12.8.2.5), X beams NPB300X150X49.32 (b/tf 5.98 ≤ 7.61, d/tw 34.8 ≤ 37.6;
   NPB300X165X39.88 at 8.51 / 50.1 fails), Y beams NPB200X130X31.56 (6.70 / 29.7; NPB200X130X27.37 at 7.82 fails);
   WPB200X200X42.26 gravity columns (not SFRS). CJP-welded gussets at brace ends; fin plates 3 × M20 HSFG (220 mm,
   X beams) / 2 × M20 HSFG (150 mm, Y beams — fits the 190 mm clear web); 650 × 650 × 65 base plates (E250, t > 40:
   fy 230) with 6 × M30 anchors, embedment 1500 mm (bond π d L τbd = 169.6 kN per anchor; EOR input, IS 456 not in
   corpus, VERIFY).
2. Seismic: I = 1.0 (Table 8 (iii)); Ta = 0.09 h/√d = 0.312 s (X) / 0.382 s (Y); Sa/g = 2.5 (soil II);
   Ah = (0.24/2)(1.0/4.5)(2.5) = 0.0667; W ≈ 1488 kN (D + 25 % IL, Table 10; partitions 1.0); VB = Ah W ≈ 99.2 kN;
   Zone IV → RSA (7.7.1) scaled to VB (scale 1.15 X / 1.21 Y); drift max 4.7 × 10⁻⁵ ≪ 0.004 (7.11.1).
3. Hot-rolled frame D/C (IS 800, vendored engine): floor X beam NPB300X150X49.32 0.74, roof X beam 0.58, Y beams
   0.63, brace 0.74, gravity column 0.64, lateral column 0.33; connections ≤ 0.98 (brace-end gusset Whitmore yield
   0.98; SFRS column base 0.91, governed by the anchorage embedment under the 12.12 / IS 18168 9.3 base demand of
   155 kN per anchor). IS 18168 Table 2 (brace / column / beam rows), 7.2, 10.2, 12.8 and 12.12 checks all pass
   (1009 capacity-design checks, 0 fail). The lateral sub-run sees the parent job's stored `rag/` hits (each
   retrieval row's `file` → `hit_file`), so the HR evidence gate passes; status `complete`, 0 reasons.
4. CFS studs CLR100X50X15X2 at 400 mm, 3.0 m, Fy 240 MPa (IS 1079 / IS 801 Table 2 → F = 1450 kgf/cm²), sheathed both
   faces (Kw 40 N/mm per side, a = 300 mm, screw lateral capacity 600 N — EOR / test inputs, VERIFY), non-load-bearing,
   designed at EVERY storey (records stud-S1 … stud-S4). Member-level wind (`member_pd`): Ka = 1.0 for the 1.2 m² stud
   element (Table 4), Table 5 governing over all four walls and both angles (+0.7 / −0.6, h/w = l/w = 1.5), local −1.1
   in the edge strips with Kd 1.0 (7.2.1 Note 2), Cpi ±0.2 → 1.50 kN/m² at the top storey, 0.75 f effective widths and
   +33⅓ %: governing IS 801 8.1 (b) a ≤ amax, D/C 0.43; 8.1 (c) Kw ≥ Kw,min 0.33; 6.7 interaction 0.27 (fb from
   M/Sx_eff, C01); 6.5 web crippling at the track 0.24 (DL + 1.0 W).
5. CFS joists CLR180X50X20X3.15 at 400 mm spanning 4.0 m, compression flange restrained by the deck: governing
   6.1 / 6.2 / 6.3 bending D/C 0.545 (DL + IL, increase 1.0; Ma = Fb Sx_eff, WP6 / E6); deflection span/300 (IS 800
   Table 6, other buildings, floor, elements not susceptible to cracking — read-only) 0.24.
6. Diaphragm: unit shear F/(n B) per frame line (n = 2 perimeter lines per direction; one line → F/B with a cantilever
   chord) ≤ 6.0 kN/m (cited product test value, EOR input); max 2.70 kN/m at storey 3 (Y) → ok; chord force (F/L) s²/(8 B)
   reported.
7. Package: `design_basis = "IS801_WSM"`, `lateral_frame_basis = "IS800_LSD"`; every stud W-row carries
   `allowable_increase = 1.3333`, every DL / DL+IL row 1.0; `capacity_basis ∈ {IS801_allowable, test, EOR_input}`;
   consistency empty; report has no US strings and prints IS 801:1975, IS 811:1987, IS 875 (Part 3):2015,
   IS 1893 (Part 1):2016, IS 800:2007, IS 18168:2023 and "Ah =".

## B. IN_CFS_Ex5 — two-span ALL-CFS portal warehouse + mezzanine, Hyderabad: elastic (R = 1.0)

**Problem.** 2 × 12 m spans, eave 7.0 m, apex 8.4 m (13.1°), frames at 5.0 m, 7 frames (30 m), plan 24 × 30 m;
general storage (I = 1.0). Hyderabad: Zone II, Z = 0.10, soil II; Vb 44 m/s, terrain 2, inland (Kd 0.9); no design
snow (IS 875-4 scope, found:false). Roof D 0.35, Lr 0.75 − 0.02 × 3.1 = 0.69 (IS 875-2 Table 2 (ii)), cladding 0.20.
Mezzanine 12 × 8 m at 3.5 m on independent posts, storage IL 7.5 kN/m² (Table 1 viii(a) minimum), D 1.5, braced to the
ground by its own X-bracing.

**Method.**
1. `all_cfs_portal = True`, `portal.seismic_basis = "elastic_R1"`: the report opens with the SEISMIC BASIS statement —
   R = 1.0, Ah = (Z/2)(I/1.0)(Sa/g) = 0.125, IS 800 Section 12 not applicable, IS 801 working stress with +33⅓ % on
   EL / WL, wind governs (Zone II).
2. Frame: columns and rafters 2 × CLR250X80X25X5 back to back (IS 801 7.3 connectors), Fy 294 MPa (30 kgf/mm² →
   F = 1800 kgf/cm²), FIXED bases (IS 800 Annex D sway K; pinned bases gave K > 2.8 and KL/r > 200), knee braces
   2 × CLR200X80X25X4 at 2.5 m below the eave / 4.5 m along the rafter, fly braces to the inner flange at every girt on
   the columns (1.5 m) and every second purlin on the rafters (3.0 m). (C01 re-size, ruling R12: with the IS 801 6.7
   stress corrected the previous frame — knee brace at 3.0 m, column fly braces at 3.0 m — gave column 6.7 = 1.13;
   2 × CLR250X80X25X5 is already the heaviest IS 811 lipped channel, so the column is relieved by bracing and the knee.)
3. Wind: IS 875-3 member patterns (Table 5 walls θ = 0 / 90, Table 6 roof, Cpi ± 0.2 at 5 % openings), Ka frame tributary,
   H_base wind 46.5 kN vs EQ 8.0 kN → wind governs; eave sway 28.6 mm at 1.0 W < h/150 = 46.7 mm (IS 800 Table 6, industrial,
   elastic cladding); EQ storey drift 0.0011 < 0.004 (7.11.1) at VB with γ 1.0. Secondary members take member-level
   pressures, not the frame patterns: purlins (7.5 m² element, Ka 1.0) Table 6 at 13.1° −0.95 overall / −1.4 local
   (eave strip, Kd 1.0) with Cpi +0.2 → uplift 1.86 kN/m²; girts Table 5 −0.5 / +0.7 overall, −0.8 local → 1.16 kN/m².
   Gable wind on the longitudinal bracing: Table 5 θ 90 of this building, C +0.7 / D −0.2 (net 0.9).
4. Seismic W: frame roof 63.7 kN (VB frame 8.0 kN); whole portal 446 kN (VB 55.7 kN); mezzanine 504 kN (VB 63 kN on its own
   bracing). Ta = 0.09 h/√d = 0.154 s, Sa/g 2.5, Ah ≥ Table 7 minimum 0.007.
5. IS 801 checks per role (D/C): column 0.85 (6.7.1 interaction at DL+IL+1.0WM0+R: M 55.3 kN·m, fb = M/Sx_eff 187.9 MPa
   vs Fb 235.2 MPa with the 6.1.2 increase, fa 7.8 MPa), rafter 0.74 (7.3 (a) interconnection spacing), knee brace 0.41
   (6.6 compression, DL+IL+1.0W), mezzanine post 2 × CLR150X50X25X4 0.81 (6.6 axial + bracing overturning, DL+IL+1.0EL),
   mezzanine beam 2 × CLR250X80X25X4 spanning 3.0 m, 3.0 m tributary 0.83 (6.1 / 6.2 / 6.3 bending, DL+IL), joists
   CLR200X80X25X4 0.39 (6.5), purlins CLR200X80X20X3.15 0.62 (uplift bending, bottom flange, 0.9DL+1.0W) and girts
   CLR180X80X20X3.15 0.54 at 1.5 m spanning 5.0 m, both `zone = "all"` (the old CLR150X50X20X3.15 gave 2.03 / 1.52 under
   the member-level wind).
6. Connections: knee and apex bolt groups M16 4.6 (IS 801 7.5 elastic vector method) 0.80; column base 500 × 600 × 40 with
   6 × M24 4.6 (IS 800 11.6.2 / 11.4.1 (c) working stress, `capacity_basis = "IS800_WSM"`, pedestal bearing 6.0 MPa EOR
   input) 0.85, governed by the anchorage embedment (M24, 500 mm in M25: 45.2 kN per anchor, EOR input, VERIFY); longitudinal
   X-bracing CLR150X50X20X3.15, 3 bays, tension-only 0.25; mezzanine bracing CLR100X50X15X2 0.56.
7. Status `complete`, 0 reasons; EOR inputs listed (pedestal bearing, anchorage embedment). Fail-closed: removing `site.k2_table` or
   `load_plan.cfs_combinations` raises `PortalError` — no default pressures, no default combinations.

## Discipline to carry into every design
* The lateral system is the D3 system for the zone; CFS members are gravity / wind members with IS 801 allowables.
* Each check row: `{combo, check, value, limit, dc, ok, clause, cite, source, capacity_basis, allowable_increase}`; the gate
  recomputes dc = value / limit and refuses a stored dc that disagrees.
* Wind / EL rows: 0.75 f effective widths and allowable × 4/3 (IS 801 5.2.1.1, 6.1.2); the section is never less than that
  required for DL + IL alone.
* EOR / test inputs are declared, cited, marked VERIFY and listed in `EOR_inputs.json`; they never silently become code values.
