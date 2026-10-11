# steltic-CFS-india — 2026-10: briefs renumbered, most common building types first

Branch `fix/2026-10-peb-briefs`. No engine logic changes.

- **The 15 CFS briefs are renumbered** so the most common building types come first: portal sheds with IS 801
  purlins and girts, then braced-frame buildings by storey count. Old → new: Ex1 → 7, Ex2 → 1, Ex3 → 10, Ex4 → 12,
  Ex5 → 3, Ex6 → 11, Ex7 → 13, Ex8 → 8, Ex9 → 14, Ex10 → 4, Ex11 → 5, Ex12 → 15, Ex13 → 9, Ex14 → 6, Ex15 → 2.
  Brief texts are unchanged except their ids. Map and policy: `steltic_india/test_buildings/RENUMBERING_2026-10.md`.
- Mechanical rename (`steltic_india/scripts/renumber_2026-10.py`): the `IN_CFS_ExN` and `IN_ExN` ids in file and
  folder names (briefs, `usa_reference/` fixtures and original briefs, `tests/fixtures/IN_CFS_Ex7/`,
  `tests/fixtures/IN_CFS_Ex3/`) and in every text file; the reviewed short forms that meant a CFS brief ("Ex5" for
  the all-CFS portal, "Ex10" for the high-bay, "Ex1" for the reference building) in the agent prompt, the contract,
  the preflight messages and `contract/DESIGN_EG_INDEX.md`. `CHANGES_2026-09-review.md` keeps the old numbers and
  now carries a note at the top.
- **Vendored HR engine (`steel_engine/hr_vendor/`) re-synced** with steltic_india `fix/2026-10-peb-briefs`: brief ids
  in comments, docstrings and one message string only. `check_vendored`: 45 identical. `VENDORED_FROM.md` notes the
  re-sync; record the merged steltic_india commit there after that PR merges.
- `steltic/main.py`: `in1` … `in15` serve IN_CFS_Ex1 … IN_CFS_Ex15 in the new order.
- `test_buildings/README_INDIA.md` lists the briefs in the new order.
- Tests: the brief lint id sets follow the new numbers (cyclone belt Ex1 / Ex13 / Ex5; re-entrant Ex4, Ex5, Ex8, Ex11,
  Ex13, Ex14, Ex15; Ex1 SCBF braces; Ex2 food storage); `test_fix_C02.py` and `test_wp3_ex1_ex5.py` load the
  fixtures IN_CFS_Ex7 and IN_CFS_Ex3. Full suite with `STELTIC_HR_ROOT` on the HR branch: **313 passed**.
