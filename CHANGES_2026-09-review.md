# steltic-cfs-india 1.1.0 — 2026-09 review fixes

Branch `fix/2026-09-review`, based on the delivered 1.0.2 tree. Scope rows C01–C16, the CFS side of H22, H30 and R01–R04, the CFS part of X01, X02 and X06, D01, D04 and D05, and the re-run fixes (RR-BUG-3, RR-BUG-4, RR-BUG-6, DOCS-OPEN-1).

`steel_engine/hr_vendor/` is re-vendored from steltic_india `fix/2026-09-review`; `VENDORED_FROM.md` records the exact commit. After steltic_india is merged, re-run `scripts/check_vendored.py` against the merged HR checkout.

## Results that change for existing jobs

- **C01 (P0).** IS 801 bending stress is now converted from N-mm to kgf-cm as ×N_TO_KGF/10. The old factor under-reported fb about 10×.
  - The Ex5 reference portal was re-sized. The column was already the heaviest IS 811 channel, so fly braces at every girt (Lu 1500) and knee braces 2×CLR200X80X25X4 were added. Column 6.7 D/C is 0.853.
  - Purlins CLR200X80X20X3.15, girts CLR180X80X20X3.15.
  - Fy stays 294 MPa, per R12. `contract/CFS_REFERENCE.md` is re-baselined.
- **All HR engine changes reach the CFS lateral sub-run** through the vendor. See steltic_india `CHANGES_2026-09-review.md`, in particular W, IS 18168 Table 2 and the stricter evidence gate.
- **CFS Ex1 fixture:** the SCBF frame is re-sized to IS 18168 Table 2, with partitions 1.0 kN/m² in W.
- **Member-level IS 875-3 wind** for studs, purlins and girts. Ka is per direction and area-checked against Table 4.
- **Diaphragm demands:** single braced line, per-storey lines and capacities, re-entrant collectors.
- **LZ (lipped-zed) bending** is refused with found:false until principal-axis bending is implemented.
- **Reports and viewer:** a None D/C shows as "not evaluated". Lateral reasons are ranked by the HR reason class.

## New capabilities

- Mixed lateral systems (C10).
- Per-line bases and sections, multi-level columns and free nodes in the frame builder (C11, C06). `india_cfs_frame_build` is now a thin wrapper over the shared HR `frame_build.py` (X06).
- Pitched roofs (X02).
- Flexible-diaphragm analysis for L, T, U, Z and cruciform plans (X01).
- The site map reading and the R5 site-proxy record are forwarded to the HR run (DOCS-OPEN-1).

## Tests

- `STELTIC_HR_ROOT=<steltic_india checkout> python3 -m pytest tests -q -p no:cacheprovider` gives 308 passed.
- `python3 scripts/check_vendored.py` reports 45 files identical.

## Additions from the gold-standard round (2026-09-26/27)

- **HR engine re-vendored** with owner rulings O1/O2, GOLD-1..7, AUD-1..4, GOLD-764 and GOLD-COLL. See the steltic_india release notes.
- **O3:** the framed-area check falls back to `geometry.floor_area_m2`, taken as the per-level plan area.
- **GOLD-1:** CFS consistency uses limit/value only for minimum-type (`sense >=`) rows.
- **AUD-1..4, CFS side:** plate fy by band in the portal base, 7.6.4 label reconciliation, `lateral_frame.diaphragm_type`, portal `embedment_cite` and the bond form, and `delegated_design` passed to the HR run.
- **GOLD-COLL:** `lateral_frame.diaphragm_by_level`.
- **H3 (audit HIGH):** the diaphragm deck shear per line is now the analysed line reaction (rigid + flexible envelope) ÷ the deck length actually present along that line. The old equal share F/(n B) is kept only for information.
  - New optional key: `geometry.diaphragm_line_length_m`.
  - If no reactions are available, the check fails closed.
- **H3-T:** IS 1893 7.8.2 accidental torsion (0.05 b) is added to the rigid line reactions.

## IS corpus (not distributed)

The BIS standards corpus is not published with this repo, because the standards are copyright BIS. Build your own from your licensed PDFs in the Steltic hub (first pass, Docling). Then have a frontier LLM fix it using `CORPUS_FIX_LLM_INSTRUCTIONS.md`, and import the result back into the hub. See README, "IS corpus (standards grounding)". Without a corpus the engine still runs: retrievals return found:false, and COMPLETE needs EOR records.

## Commits (oldest first; subjects only — hashes change when the branch is replayed onto GitHub)
- C01: IS 801 bending stress N-mm -> kgf-cm is x N_TO_KGF/10 (6.7 fbx/fby, 6.4.2 fbw); re-size Ex5 portal (CFS-A-01, CFS-A-11, E6)
- C15: refuse lipped-zed (LZ) bending with found:false until principal-axis bending is implemented
- C04: snow combinations read loads.snow as well as top-level snow / snow_summary.applicable (CFS-D-07)
- C10: mixed lateral systems (SMF+SCBF, EBF+SMF) with R = min or per-direction R_x/R_y; keep braced bays (CFS-A-14, CFS-D-06)
- H22 (CFS side, ruling R1): partitions in W default to max(0.5, design allowance); preflight WARN when declared lower
- C05 (+ C02 Ka part): keep declared storey wind W_X/W_Y with a cite; per-level exposed face; Ka per direction (CFS-C-06, CFS-B-06, CFS-D-10)
- C03: diaphragm demands -- single braced line, per-storey lines / capacities, re-entrant collectors (CFS-A-03, CFS-D-12, CFS-B-13, CFS-C-17)
- R01 R02 R03 R04 L-08(part): CFS standards search tool -- errors, exact hits, evidence files
- R01: stop the ladder once the corpus says the document is not in it
- C11 + C06: frame builder honours base per line, ranged / per-line sections, multi-level columns, consecutive beams, free nodes; framed-area ERROR
- C12: traceable summaries, literal-D/C rule by tolerance for underived rows only, blocking reasons first with a count, rag evidence checks (CFS-A-02, B-03, C-04, B-02, L-13)
- C13: check_vendored.py resolves STELTIC_HR_ROOT or a sibling steltic_india(-main) checkout, else SKIP (exit 0); no /home/claude/rv paths (L-08)
- C02 + C14: member-level IS 875-3 wind for studs / purlins / girts; member groups, eave struts, headers, point loads
- C07: all-CFS portal -- gable Cpe from Table 5 per building, mezzanine post overturning axial under EL, mezzanine beam role, anchorage EOR slot (CFS-A-12)
- D04 (+ C01 reference numbers): CFS contract 'Advanced cfg keys'; floor deflection span/300 / span/360; CFS_REFERENCE re-baselined
- R02: recognise an exact table reply by the table's own caption title
- C16: re-vendor the HR engine from steltic_india fix/2026-09-review (H01–H52)
- FIX1 (H30 CFS side): lateral HR sub-run sees the parent job's stored rag/ hits
- FIX1 (H05 / R1): re-size the CFS Ex1 SCBF frame to IS 18168 Table 2; partitions 1.0 in W
- X06: india_cfs_frame_build becomes a thin wrapper over the shared HR steel_engine/frame_build.py (E11, HR-B-20)
- X02: pitched-roof (apex / rafter) support in india_cfs_frame_build and the hr_vendor_runner spec (CFS-A-15, HR-E-05)
- X01: CFS lateral frame runs the HR Table 5(ii) flexible-diaphragm analysis (L / T / U / Z / cruciform plans)
- C16: re-vendor the HR engine after phase 2 (X01 flexible diaphragm, X02 roof planes, X03 bases, X04/X06 frame_build + multi-unit, X05/X07)
- D01: CFS brief corrections B15-B24 + brief lint (L-14; rulings R2, R5, R6, R7)
- D04 (phase-2 extension): CFS contract documents the keys that reach the HR run, the shared frame builder, the corpus env and rag_dir
- D05: CFS contract lint -- every cfg key the CFS-only modules read is named in contract/*.md or README*.md
- RR-BUG-6: CFS wind storey forces resolve Ka per direction (area-checked declared Ka)
- DOCS-OPEN-1: forward the site map reading / R5 site-proxy record to the HR lateral sub-run
- RR-BUG-4: CFS lateral reasons ranked by the HR reason class; the cap keeps every class
- RR-BUG-3: never format a None D/C in the CFS report / portal viewer; clear C07 mezzanine-beam reason
- C16: re-vendor HR engine at 726d180 (RR-BUG-1,2,4,5,6)
- O3: C06 framed-area check falls back to geometry.floor_area_m2 (owner ruling O3, 2026-09-26)
- C16: re-vendor HR engine (owner rulings O1, O2)
- GOLD-1: CFS consistency recomputes minimum-type rows as limit / value (IN_CFS_Ex13, IN_CFS_Ex7, blocking)
- GOLD-2 (X01): document per-level lateral_frame.diaphragm_stiffness (IN_CFS_Ex9)
- C16: re-vendor HR engine (gold-run fixes GOLD-1..7)
- AUD-2 (CFS): all-CFS portal base plate fy from IS 2062:2025 Table 3 by thickness
- AUD-1 (CFS): regression test -- CFS evidence rule needs the row's own stored hit
- AUD-3 (CFS): board diaphragm declared rigid without a basis is a preflight WARN; lateral 7.6.4 warnings reach the CFS status
- AUD-4 (CFS): portal anchorage derived / asserted with source + cite, breakout record, anchorage WARNs
- C16: re-vendor HR engine (audit fixes AUD-1..4)
- GOLD-764 (CFS): diaphragm rows carry the HR flexible run's 7.6.4 record on the code-literal ratio (IN_CFS_Ex9)
- GOLD-COLL (CFS): lateral_frame.diaphragm_by_level reaches the HR run (IN_CFS_Ex9)
- C16: re-vendor HR engine (GOLD-764 literal 7.6.4, GOLD-COLL collector accumulation)
- H3: CFS diaphragm shear from the analysed line reactions / deck length along each line (audit round 5)
- H3-T: IS 1893 7.8.2 accidental torsion in the rigid line reactions of the CFS diaphragm check
- C16 + Windows: re-vendor HR consistency (AUD-1 path fix); report link uses '/' separators
- X06 test (Windows): T1 parity rel 1e-3 -- near-mechanism frames (T1 5.9-6.9 s) differ ~1e-4 between LAPACK builds
- Corpus: drop references to the private corpus repo; users build their own IS corpus in the Steltic hub
- CORPUS_FIX_LLM_INSTRUCTIONS.md: the owner's instructions for the corpus fix pass (replaces the placeholder)
- CORPUS_FIX_LLM_INSTRUCTIONS.md: final version (matches the hub's bundled corpus module: validate probes, optional scripts/*.json, Import fixed corpus tab)
