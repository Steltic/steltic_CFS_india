# India CFS worked reference — two engine-reproducible buildings (asserted by pytest)

Both buildings are run end-to-end by `tests/test_wp3_ex1_ex5.py` from the fixtures
`tests/fixtures/IN_CFS_Ex1/build_and_run.py` and `tests/fixtures/IN_CFS_Ex5/build_and_run.py`; the numbers below are
the ones the tests assert (tolerances in the test file). They are the worked METHOD to mirror — never copy a number
into another building.

## A. IN_CFS_Ex1 — 4-storey residential, New Delhi: hot-rolled SCBF + IS 801 studs / joists

**Problem.** 12 m × 8 m plan, 4 × 3.0 m storeys, residential (48 persons). New Delhi: IS 1893 Annex E Zone IV,
Z = 0.24, soil Type II; IS 875-3 Annex A Vb = 47 m/s, terrain category 3, inland (Kd 0.9, k4 1.0). Loads: floor
D 1.5 + partitions 1.0 (0.5 in W), IL 2.0 (IS 875-2 Table 1), roof D 1.0, Lr 0.75, cladding 0.5 kN/m².

**Method (the sequence to mirror).**
1. Zone IV → SCBF, R = 4.5 (IS 1893 Table 9 SBF concentric; L7), IS 18168:2023 applies (Zone IV residential).
   `lateral_frame`: 2 × 2 bays (6 m × 4 m), X-bracing in every perimeter bay, fixed bases; IS 808 WPB200X200X50.92
   lateral columns and braces (plastic section, 12.8.2.5), WPB200X200X42.26 gravity columns, NPB300X165X39.88 (X) /
   NPB200X130X27.37 (Y) beams, E250 B0; CJP-welded gussets at brace ends, 3 × M20 HSFG fin plates, 650 × 650 × 60
   base plates with 6 × M30 anchors (embedment = EOR input, IS 456 not in corpus).
2. Seismic: I = 1.0 (Table 8 (iii)); Ta = 0.09 h/√d = 0.312 s (X) / 0.382 s (Y); Sa/g = 2.5 (soil II);
   Ah = (0.24/2)(1.0/4.5)(2.5) = 0.0667; W ≈ 1318 kN (D + 25 % IL, Table 10; partitions 0.5); VB = Ah W ≈ 87.9 kN;
   Zone IV → RSA (7.7.1) scaled to VB (scale 1.16 X / 1.22 Y); drift max 4.6 × 10⁻⁵ ≪ 0.004 (7.11.1).
3. Hot-rolled frame D/C (IS 800, vendored engine): floor NPB300 0.87, roof 0.35, brace 0.13, gravity column 0.64,
   lateral column 0.24; connections ≤ 0.98. Open item: the vendored 12.8.2.4 `brace_tension_share` check fails
   (gravity compression dominates the brace force in a light building) → status `partial` with exactly those reasons.
4. CFS studs CLR100X50X15X2 at 400 mm, 3.0 m, Fy 240 MPa (IS 1079 / IS 801 Table 2 → F = 1450 kgf/cm²), sheathed both
   faces (Kw 40 N/mm per side, a = 300 mm, screw lateral capacity 600 N — EOR / test inputs, VERIFY), non-load-bearing,
   wind (Cpe ± Cpi) pd at 0.75 f effective widths and +33⅓ %: governing IS 801 8.1 (b) a ≤ amax, D/C 0.43; 8.1 (c)
   Kw ≥ Kw,min 0.33; 6.5 web crippling at the track 0.18 (DL + 1.0 W).
5. CFS joists CLR180X50X20X3.15 at 400 mm spanning 4.0 m, compression flange restrained by the deck: governing 6.5 end
   crippling D/C 0.38 (DL + IL, increase 1.0); deflection L/240 (IS 800 Table 6, read-only) 0.19.
6. Diaphragm: unit shear F/(2B) per storey ≤ 6.0 kN/m (cited product test value, EOR input); max 2.31 kN/m at storey 3
   → ok; chord force F L/(8 B) reported.
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
   2 × CLR150X50X25X4 at 2.5 m below the eave / 3.0 m along the rafter, fly braces at 3.0 m.
3. Wind: IS 875-3 member patterns (Table 5 walls θ = 0 / 90, Table 6 roof, Cpi ± 0.2 at 5 % openings), Ka frame tributary,
   H_base wind 46.5 kN vs EQ 8.0 kN → wind governs; eave sway 42.7 mm at 1.0 W < h/150 = 46.7 mm (IS 800 Table 6, industrial,
   elastic cladding); EQ storey drift 0.0016 < 0.004 (7.11.1) at VB with γ 1.0.
4. Seismic W: frame roof 63.7 kN (VB frame 8.0 kN); whole portal 446 kN (VB 55.7 kN); mezzanine 504 kN (VB 63 kN on its own
   bracing). Ta = 0.09 h/√d = 0.154 s, Sa/g 2.5, Ah ≥ Table 7 minimum 0.007.
5. IS 801 checks per role (D/C): column 0.65 (7.3 (a) interconnection spacing governs; stress interaction 0.18), rafter 0.74,
   knee brace 0.71 (6.6 compression, DL+IL+1.0W), mezzanine post 2 × CLR150X50X25X4 0.75 (6.6 axial, DL+IL), joists
   CLR200X80X25X4 0.39 (6.5), purlins / girts CLR150X50X20X3.15 at 1.5 m spanning 5.0 m 0.69 / 0.24 (deflection, information).
6. Connections: knee and apex bolt groups M16 4.6 (IS 801 7.5 elastic vector method) 0.80; column base 500 × 600 × 40 with
   6 × M24 4.6 (IS 800 11.6.2 / 11.4.1 (c) working stress, `capacity_basis = "IS800_WSM"`, pedestal bearing 6.0 MPa EOR
   input) 0.78; longitudinal X-bracing CLR150X50X20X3.15, 3 bays, tension-only 0.34; mezzanine bracing CLR100X50X15X2 0.56.
7. Status `complete`, 0 reasons; EOR inputs listed (pedestal bearing). Fail-closed: removing `site.k2_table` or
   `load_plan.cfs_combinations` raises `PortalError` — no default pressures, no default combinations.

## Discipline to carry into every design
* The lateral system is the D3 system for the zone; CFS members are gravity / wind members with IS 801 allowables.
* Each check row: `{combo, check, value, limit, dc, ok, clause, cite, source, capacity_basis, allowable_increase}`; the gate
  recomputes dc = value / limit and refuses a stored dc that disagrees.
* Wind / EL rows: 0.75 f effective widths and allowable × 4/3 (IS 801 5.2.1.1, 6.1.2); the section is never less than that
  required for DL + IL alone.
* EOR / test inputs are declared, cited, marked VERIFY and listed in `EOR_inputs.json`; they never silently become code values.
