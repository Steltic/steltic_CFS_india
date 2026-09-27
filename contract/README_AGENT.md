# India CFS Building Design Agent — guide & workflow

## 1. Mission
Deliver a grounded, reproducible design package for one building in India whose floors / walls / roof
secondaries are cold-formed light-gauge steel (IS 801:1975 working stress, IS 811:1987 sections) and whose
lateral system is a hot-rolled IS 800:2007 Section 12 frame (D3 / L7) — or, for the single all-CFS portal
brief, an elastically designed (R = 1.0) cold-formed portal. Every number in the package is either computed
by the framework from a cited clause or declared as an EOR input with its source. Nothing is filled from memory.

## 2. Your knowledge base (RAG collections — see IS_COLLECTIONS.md)
| Use | Documents | Rule |
|---|---|---|
| CFS members | `IS_801_1975`, `IS_811_1987` (+ `IS_811_1987_Amd1_2011`) | primary design authority; Amd 1 may index 0 sections → `found:false` |
| Loads (every job) | `IS_875_Part_1_2026` … `IS_875_Part_5_1987`, `IS_1893_Part_1_2016` | mandatory into `cfg['load_plan']` |
| Hot-rolled lateral frame | `IS_800_2007`, `IS_18168_2023` | only with `purpose = "lateral_frame_is800"`; Table 6 with `purpose = "serviceability_limits_table6"` |
| Worked examples | none ingested for India | the two reference buildings in CFS_REFERENCE.md (asserted by pytest) are the worked method |

The US design-example recipes (`rag_v2/usa_reference/cfs_models.jsonl`) are NOT ingested and never queried.

## 3. The design workflow (the pipeline does the mechanics AND the IS 801 / IS 800 checks)
1. **Intake** — city → IS 1893 Annex E zone, IS 875-3 Annex A Vb, terrain category, cyclone belt (6.3.4);
   occupancy → I (Table 8); plan, storeys, mezzanine, loads.
2. **Retrieve** — one document per call, exact ids when known (`exact_table` 9, `exact_section` 6.1.2 …), fts only
   to navigate; file each hit into `load_plan.retrieval` with `stem / query / found / cite / file / quote / purpose`
   (`file` = the stored `rag/<slug>.json`, `quote` verbatim from it; a found:false row whose value is used carries
   `{value, source, cite, verify: True}`). Corpus server: `RAG_API_URL`; corpus folder: `INDIA_CORPUS_ROOT`
   (AGENT_START, "Corpus and search tool").
3. **Compose `cfg.py`** — the schema in AGENT_START.md. Choose the D3 system for the zone, a rational braced-bay
   layout (perimeter X-bracing is the default), IS 808 columns / beams / braces, IS 811 studs / joists / purlins /
   girts, the sheathing and diaphragm test values (EOR inputs, VERIFY), the connections.
4. **Run** — `import pipeline; res = pipeline.design_and_report(name, cfg)`. The pipeline:
   * preflight (schema, units, banned keys, IS 811 labels, drift limit);
   * IS 875-3 storey wind (Vb k1 k2 k3 k4, Kd, Ka, Cpe Table 5) and IS 1893 seismic (Z, I, R, Sa/g for the soil, Ta = 0.09 h/√d,
     Ah = (Z/2)(I/R)(Sa/g) ≥ Table 7 minimum, W with Table 10 imposed share, RSA scaled to VB where 7.7.1 requires it);
   * the vendored hot-rolled India engine (subprocess, `steel_engine/hr_vendor_runner.py`) → frame members, braces,
     connections, bases, drift, IS 800 status. The runner translates the CFS cfg into the HR cfg: N-mm geometry
     (`SX` / `SY` from `bay_x_m` / `bay_y_m`, `xcoords` / `ycoords` from the gold grid), `seis` {Z, I, R, zone, soil,
     R_x, R_y}, `custom_build` from `custom_build_module`, `roof_planes` / `roof_regions` from the gold block, the
     X01 keys `diaphragm_stiffness` / `flexible_diaphragm_analysis` / `flexible_diaphragm_eor`, and `hr_cfg_extra`
     verbatim; the job's `rag/` is copied into `lateral/<name>/rag/` (`run_lateral(rag_dir=)`) so the HR evidence
     gate sees the same hits;
   * IS 801 checks on every CFS role (6.6.1.1 / 6.6.1.2 compression with Q, 6.3 bending, 6.4 shear, 6.5 crippling, 6.7 combined
     with Cm and 1/(1 − fa/F'e), 8.1 sheathed studs, 7.3 interconnection, 7.5 bolts) at IS 875-5 8.1 combinations, +33⅓ % on W / EL only;
   * diaphragm unit shear and chord forces per storey against the cited diaphragm allowable;
   * `design/calc_package_cfs.json`, `report.html` (kN / m / mm), `viewer_3d.html`, `EOR_inputs.json`, `STATUS.md`,
     `consistency` and `india_cfs_gates.design_status`.
5. **Iterate** — read `STATUS.md`; every open reason names a member, connection, base, diaphragm or EOR input. Resize
   (`is811_sections.next_size`), add plies (max 2), shorten spans, stiffen the frame, or declare the input; re-run.
6. **Finish** — status `complete`, or `partial` with each reason written up as an engineering item in your reply.

## 4. What "validated" means
* `preflight.check(cfg)` → no ERROR;
* hot-rolled frame status `complete` (IS 800 members / connections / drift / IS 18168 checks pass);
* every CFS member row `ok = True`, D/C recomputed from `value / limit` ≤ 1.0, `capacity_basis` one of
  `IS801_allowable`, `test`, `EOR_input` (portal bases: `IS800_WSM`), `allowable_increase` 4/3 only on W / EL combos;
* diaphragm rows ok; connections ok; drift ≤ 0.004 h (IS 1893 7.11.1) and ≤ h/150 at 1.0 W (IS 800 Table 6) for portals;
* `consistency.check` empty: no basis mixing, no `.bak`, no US strings, no MISSING in the report;
* `design_status` = `complete`.

## 5. Caveats — state these in any output
* CFS members are gravity / wind members; the lateral system is the hot-rolled frame (or, Ex5, an elastic R = 1.0 portal).
* Kw, sheathing attachment capacity, diaphragm allowable shear, anchor embedment, pedestal bearing are EOR / test inputs (VERIFY).
* IS 811 Amendment 1 may be unindexed (found:false); catalogue rows failing the thin-wall validator are quarantined
  (`steel_engine/is811_quarantine.csv`) and cannot be used.
* IS 801 6.7.2(b) (eccentric load on the side away from the shear centre) is reported `ok = None` (TODO verify) — keep loads
  in the plane of symmetry or on the shear-centre side.
* Re-entrant plans: one 3-D model; the Table 5(ii) flexible-diaphragm run uses the declared deck stiffness (an isotropic
  membrane from `lateral_frame.diaphragm_stiffness`, EOR input) — state its source; the CFS diaphragm-demand rows keep
  the rigid-diaphragm formula.
* `cfs_connections` = declared CFS connection rows `[{id, value, limit, dc, ok, clause, cite, source, note}]` are copied
  into the package and gated like every other row (`waived` is refused). `allow_sfia_twin` is not honoured: SFIA
  designators are refused.

## 6. Deliverables (the pipeline writes all of them)
`cfg.py`, `design/calc_package_cfs.json`, `load_plan.json`, `lateral/lateral_result.json` (and the HR sub-job
`lateral/<name>/` with its own `STATUS.engine.md` and `rag/` copy), `report.html`, `viewer_3d.html`, `EOR_inputs.json`,
`STATUS.md`, `rag/*`.

## 7. Definition of DONE
Design status `complete` (or `partial` with every reason explained), report grounded in IS 801 / IS 811 / IS 875 / IS 1893 /
IS 800 / IS 18168 with clause cites and Z / I / R / Sa/g / Ah / VB / T printed, EOR inputs listed, no US strings.

## 8. The design LOOP
cfg → pipeline → STATUS.md → fix the named item → pipeline → … → complete. Never edit the package by hand; never
re-render the report from a hand-edited package.
