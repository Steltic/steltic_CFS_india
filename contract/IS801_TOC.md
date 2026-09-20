# IS 801:1975 / IS 811:1987 — clause map for exact-id RAG queries (India CFS)

Authoritative text lives in the India RAG corpus (`IS_801_1975`, `IS_811_1987`, `IS_811_1987_Amd1_2011`). Query the
id ALONE with `type = exact_section` / `exact_table`; never paraphrase a clause number from memory. Printed page
numbers are those of the IS 801 PDF (read at 300 dpi when the engine was written) — use them to check a hit.

## IS 801:1975 — Code of practice for use of cold-formed light gauge steel structural members in general building construction

| Clause | Subject | Page | What the engine takes from it |
|---|---|---|---|
| 5.1 | Deflection — no numerical limit in IS 801 (limits come from IS 800 Table 6, read-only) | — | joist / purlin deflection rows are informational |
| 5.2.1.1 | Effective design width of stiffened compression elements: (w/t)lim = 1435/√f; b/t = (2120/√f)[1 − 465/((w/t)√f)]; tubes 1540 / 420; 0.75 f for W / EQ with the 6.1.2 increase; deflection 1850 / 2710 / 600 | 6 | `eff_width_5211` |
| 5.2.1.2 | be/t = b/t − 0.10 (w/t − 60) for w/t > 60 | 7 | `eff_width_5212` |
| 5.2.2.1 | Edge stiffener: Imin = 1.83 t⁴ √((w/t)² − 281 200/Fy) ≥ 9.2 t⁴; dmin = 2.8 t ⁶√((w/t)² − 281 200/Fy) ≥ 4.8 t; no simple lip when w/t > 60 | 8 | `lip_adequacy_5221` |
| 6.1, Table 2 | Basic design stress F = 0.60 Fy (Fy 21 / 24 / 30 / 36 kgf/mm² → F 1250 / 1450 / 1800 / 2160 kgf/cm²) | 11 | `cfs_members.Fy_MPa` → F |
| 6.1.2 | 33⅓ % increase for wind or earthquake, alone or combined; section not less than for DL + LL | 13 | `allowable_increase` 4/3 on W / EL rows only |
| 6.2 | Unstiffened compression elements Fc by w/t (0.60 Fy; 0.767 − 3.15 × 10⁻⁴ (w/t)√Fy; 562 000/(w/t)²; 25–60 rule; Fy < 2320 footnote) | 13–14 | `Fc_unstiffened_62`, `q_factor` |
| 6.3 | Laterally unbraced beams: Fb between 0.36 and 1.8 π²E Cb/Fy; 0.6 π²E Cb d Iyc/(L² Sxc) beyond; zeds; Cb = 1.75 + 1.05 (M1/M2) + 0.3 (M1/M2)² ≤ 2.3 | 14–15 | `cb_63`, `fb_ltb_kgf` |
| 6.4.1 | Web shear Fv = 1275 √Fy/(h/t) ≤ 0.40 Fy; 5 850 000/(h/t)² beyond | 15 | `web_shear_64` |
| 6.4.2 / 6.4.3 | Web bending Fbw = 36 560 000/(h/t)²; combined √((fbw/Fbw)² + (fv/Fv)²) ≤ 1 | 16 | `web_bending_shear_643` |
| 6.5 | Web crippling: single web end / interior formulae (R ≤ 4 t), back-to-back t² Fy (4.44 + 0.558 √(N/t)) / (6.66 + 1.146 √(N/t)); N ≤ h; h/t ≤ 150 | 16–17 | `web_crippling_65` |
| 6.6.1.1 | Axial compression Fa1 = 0.522 Q Fy − (Q Fy KL/r / 12 500)²; 10 680 000/(KL/r)² beyond Cc/√Q; Q = Qs Qa; E = 2 074 000 kgf/cm² | 17–18 | `fa1_kgf`, `compression_allowable` |
| 6.6.1.2 | Torsional-flexural buckling: σTFO, σex, σt, β, r0; Fa2 = 0.522 Fy − Fy²/(7.67 σTFO) or 0.522 σTFO; G = 795 000 | 19–20 | `sigma_tfo_kgf`, `fa2_kgf` |
| 6.6.1.3 | Q < 1: Q Fy replaces Fy in 6.6.1.2 | 20 | `compression_allowable` |
| 6.6.2 | Bracing / secondary members L/r > 120: Fas = Fa/(1.3 − L/(400 r)) | 20–21 | `compression_allowable(secondary=True)` |
| 6.6.3 | KL/r ≤ 200 | 21 | slenderness row |
| 6.7.1 | Doubly-symmetric combined stress: fa/Fa1 + Cmx fbx/((1 − fa/F'ex) Fbx) + … ≤ 1; fa/Fa0 + fbx/Fb1x + … ≤ 1; fa/Fa1 < 0.15 simplification | 21 | `combined_67` |
| 6.7.2 | Singly-symmetric: (a) bending in the plane of symmetry with Cm / F'e; (b) load away from the shear centre (σTF) — engine reports ok = None | 21–22 | `combined_67` |
| 6.7 (definitions) | Cm = 0.85 sway; 0.6 − 0.4 M1/M2 ≥ 0.4 braced; 0.85 / 1.0 with transverse load; F'e = 12 π²E/(23 (K Lb/rb)²) (+⅓ per 6.1.2); Fa0 = 6.6.1.1 at L = 0 | 23–24 | `cm_67`, `fe_prime_kgf` |
| 7.2.1 | Fillet / plug weld throat shear 955 / 1100 / 1250 kgf/cm² by Fy | 26 | `weld_allowable_721`, `fillet_weld_721` |
| 7.3 | Two channels back to back: Smax = L rcy/(2 r1) (compression), L/6 (flexure); connector strength | 27 | `interconnection_73`, `built_up(n_ply=2)` |
| 7.5.1 | Bolt spacing / edge distance ≥ 1.5 d and ≥ P/(0.6 Fy t) | 29 | `bolted_connection_75` |
| 7.5.2 | Net section (1.0 − 0.9 r + 3 r d/s) 0.6 Fy ≤ 0.6 Fy | 29–30 | `bolted_connection_75` |
| 7.5.3 | Bearing 2.1 Fy | 30 | `bolted_connection_75` |
| 7.5.4 | Bolt shear 970 (precision) / 820 (black) / 1060 (4.6) kgf/cm² | 30 | `bolted_connection_75`, `bolt_group_75` |
| 8.1 | Wall studs sheathed both faces: amax = 8 E I2 Kw/(A² Fy²) and ≤ L r2/(2 r1); Kw,min = Fy² a A²/(8 E I2); Pmin = Kw Ps (L/240)/(2 √(E I2 Kw/a) − Ps); attachment capacity (d) | 30–31 | `wall_stud_81` |
| 8.2 | Channel and Z-sections used as beams — bracing against twist when neither flange is connected to deck / sheathing: 8.2.1 brace spacing ≤ L/4, 8.2.2 brace force P1 (K' = m/d channels, Ixy/Ix zeds), 8.2.3 stress per 6.3 with L = a | 32 | purlins / girts without a restrained flange: `L_unbraced_mm` = the 8.2.1 brace interval (fly braces) |
| 9.1.4 | "The provisions of 9 do not apply to light gauge steel diaphragms" | 33 | diaphragm capacity = cited product / test value |

## IS 811:1987 — Cold-formed light gauge structural steel sections

| Item | Subject | Engine |
|---|---|---|
| Tables 1–11 | Dimensions / properties: EA / UA angles, CWS / CWR channels without lips, CLS / CLR channels with lips, HS / HRH / HRB hat sections, LZ lipped zeds | `is811_sections.props(label)` from the corpus `structured/sections.csv`, thin-wall validated |
| 7.2.3 | "The sectional properties, as given in Tables 1 to 11, have been calculated assuming Ri as 1.5 t" | `props()['flats']`, `Ri` |
| Amendment 1 (2011) | Editorial; may index 0 sections | record `found:false` honestly (`is811_GAPS.md`) |
| Yield strength | NOT in IS 811 — `Fy = None` in the catalogue | `cfs_members.Fy_MPa` with IS 1079 / IS 801 Table 2 cite |

Quarantined rows (validator failures, `steel_engine/is811_quarantine.csv`) return `found:false` and cannot be designed with.

## Loads (mandatory every job, separate documents)
IS 875 (Part 1):2026 unit weights; (Part 2):1987 Tables 1 / 2 imposed; (Part 3):2015 6.2 / 6.3 / 7.2 / 7.3, Tables 2 / 4 / 5 / 6, Annex A;
(Part 4):2021 snow; (Part 5):1987 8.1 combinations; IS 1893 (Part 1):2016 Annex E, Tables 3 / 7 / 8 / 9 / 10, 6.4.2, 7.3, 7.6.2, 7.7, 7.11.1.

## IS 800:2007 / IS 18168:2023 — gated
Only for the hot-rolled lateral frame (`purpose = "lateral_frame_is800"`: Table 4 combinations, Section 12, 7 / 8 / 10 / 11) and
the Table 6 deflection limits (`purpose = "serviceability_limits_table6"`, read-only). Never for a cold-formed member capacity.
