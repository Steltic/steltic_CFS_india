# India CFS — worked-method index (what to mirror for each check)

No `cfs_design_examples` collection is ingested for India: the US design-example recipes
(`rag_v2/usa_reference/cfs_models.jsonl`) carry AISI / ASCE methods and are NOT loaded. The worked method for every
check is the framework's own IS 801 / IS 800 path, exercised by the two reference buildings in CFS_REFERENCE.md and
asserted by `tests/test_wp3_ex1_ex5.py` and `tests/test_wp3_is801_is811.py`. Pair each RAG clause query with the row
below, not with a foreign example.

| Check | IS clause (query it exactly) | Engine function | Reference building |
|---|---|---|---|
| Effective width, stiffened elements | IS 801 5.2.1.1 (5.2.1.2 for w/t > 60) | `is801_members.eff_width_5211 / 5212` | Ex1 studs, Ex5 columns |
| Edge stiffener (lip) adequacy | IS 801 5.2.2.1 | `lip_adequacy_5221` | Ex5 rafters (Fy 294) |
| Basic stress F = 0.60 Fy; +33⅓ % W / EL | IS 801 6.1, Table 2, 6.1.2 | `india_cfs_basis.cfs_combinations` | both |
| Unstiffened compression elements | IS 801 6.2 | `Fc_unstiffened_62` | Q factor |
| Laterally unbraced beams (Cb) | IS 801 6.3 | `cb_63`, `fb_ltb_kgf`, `bending_allowable` | Ex5 rafters / girts |
| Web shear, web bending, combined | IS 801 6.4.1, 6.4.2, 6.4.3 | `web_shear_64`, `web_bending_shear_643` | Ex5 rafters |
| Web crippling (end / interior, single / back-to-back) | IS 801 6.5 | `web_crippling_65` | Ex1 joists (governs), studs at track |
| Axial compression, Q = Qs Qa | IS 801 6.6.1.1 | `q_factor`, `fa1_kgf`, `compression_allowable` | Ex5 posts, knee braces |
| Torsional-flexural buckling (singly-symmetric) | IS 801 6.6.1.2 / 6.6.1.3 | `sigma_tfo_kgf`, `fa2_kgf` | single channels not braced against twist |
| Secondary / bracing members L/r > 120; KL/r ≤ 200 | IS 801 6.6.2, 6.6.3 | `compression_allowable(secondary=True)` | Ex5 longitudinal bracing |
| Combined axial + bending, Cm, F'e | IS 801 6.7.1, 6.7.2 (a) | `cm_67`, `fe_prime_kgf`, `combined_67` | Ex5 columns / rafters |
| Sheathed wall studs (amax, Kw,min, Pmin) | IS 801 8.1 | `wall_stud_81` | Ex1 studs (governs) |
| Fillet / plug welds | IS 801 7.2.1 | `weld_allowable_721`, `fillet_weld_721` | — |
| Two channels back to back, connector spacing | IS 801 7.3 | `interconnection_73`, `is811_sections.built_up` | Ex5 columns (governs 0.65) |
| Bolted connections (spacing, net section, bearing, bolt shear) | IS 801 7.5.1–7.5.4 | `bolted_connection_75`, `india_cfs_portal.bolt_group_75` | Ex5 knee / apex |
| Section properties (Ri = 1.5 t flats) | IS 811 Tables 1–10, 7.2.3 | `is811_sections.props / next_size` | all |
| Storey wind (Vb k1 k2 k3 k4, Kd, Ka, Cpe, Cpi) | IS 875-3 6.2–6.3, 7.2, Tables 2 / 4 / 5 / 6, 7.3 | `india_cfs_lateral.wind_story_forces`, `india_cfs_portal.wind_patterns` | both |
| Imposed loads, roof imposed, storage | IS 875-2 Table 1, Table 2 | cfg `loads` | Ex5 mezzanine 7.5 kN/m² |
| Working-stress combinations | IS 875-5 8.1, Notes 1 / 4 / 5 | `india_cfs_basis.cfs_combinations` | both |
| Zone, Z, I, R, Sa/g, Ah, W, VB, Ta, RSA | IS 1893 Annex E, Tables 3 / 7 / 8 / 9 / 10, 6.4.2, 7.3, 7.6.2, 7.7 | vendored `india_seismic` (HR), `india_cfs_portal.seismic_elastic` | both |
| Storey drift 0.004 h | IS 1893 7.11.1 | HR engine / portal `drift_table` | both |
| Sway / deflection limits (read-only) | IS 800 Table 6 (`purpose = serviceability_limits_table6`) | portal `drift_table`, joist deflection row | Ex5 h/150, Ex1 L/240 |
| Hot-rolled braced frame, connections, bases | IS 800 Section 12, 7, 8, 10, 11; IS 18168 (`purpose = lateral_frame_is800`) | vendored HR engine via `india_cfs_lateral.run_lateral` | Ex1 |
| All-CFS portal bases (working stress) | IS 800 11.6.2, 11.4.1 (c) | `india_cfs_portal.base_check` (`IS800_WSM`) | Ex5 |
| Lateral system by zone (D3 / L7 gate) | IS 1893 Table 9 + Note 1; IS 18168 1.3 | `india_cfs_lateral.resolve_system` | — |

Hand-value anchors (from `tests/test_wp3_is801_is811.py`): CLR100X50X15X2 at Fy 240: Q = 0.952, Fa1 = 103 MPa
(KL/r 77.5: `is801_fa1(250, 1, 77.5)` = 106.0 MPa), sheathed Pa = 44.0 kN; single channel not braced against twist:
Fa2 = 339.5 kgf/cm², σTFO = 650.3 kgf/cm², P = 14.18 kN (18.9 kN with +33⅓ %); CLR250X80X25X5 at Fy 345, L = 6 m:
Fb = 44.3 MPa (6.3 LTB).
